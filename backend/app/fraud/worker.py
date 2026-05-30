"""Async fraud-scoring worker (Redis stream consumer).

Human-in-the-loop policy (see ``docs/AI_ETHICS_CHARTER.md``):

- ``NONE``  → no further action; score is persisted for audit only.
- ``FLAG``  → write to ``fraud_review_queue`` (state PENDING_REVIEW). A Land
              Officer affirms or dismisses; no automatic parcel state change.
- ``BLOCK`` → write to ``fraud_review_queue`` (state PENDING_REVIEW). The
              parcel is NOT auto-frozen. If 24h pass with no human review, the
              escalation job (``app.jobs.escalation``) raises the entry's
              priority to a supervising officer and emits a
              ``FRAUD_REVIEW_ESCALATED`` audit event — it NEVER freezes: a
              human must still affirm before any parcel state change
              (AI Ethics Charter §1/§8).

The IsolationForest is NEVER the sole basis for a custodial decision. A
plain-language explanation accompanies every alert and citizens can file an
appeal at ``POST /api/v1/fraud/appeals``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import socket
import time
import uuid
from typing import Any

from app.audit import audit_emit
from app.database import get_connection
from app.fraud.scorer import SCORER_VERSION, latest_score, persist_score, score_subject
from app.util.cache import cache_setnx, get_redis, stream_publish

logger = logging.getLogger(__name__)

STREAM_NAME = "stream:fraud:scoring"
CONSUMER_GROUP = "landguard-scorers"
# Per-process consumer name. Multiple API replicas must NOT share one name in
# the Redis consumer group — that corrupts pending-entry ownership and acks.
# hostname+pid makes each replica/process own its own in-flight entries.
CONSUMER_NAME = f"scorer-{socket.gethostname()}-{os.getpid()}"

_RUNNING = False
_last_sweep = 0.0
_SWEEP_INTERVAL_SECONDS = 15.0
_OUTBOX_MAX_ATTEMPTS = 5


async def enqueue_score(*, subject_type: str, subject_id: str) -> str | None:
    """Add one scoring task to the Redis stream."""
    return await stream_publish(
        STREAM_NAME,
        {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "enqueued_at": time.time(),
        },
    )


def _build_transfer_context(transfer_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT t.id, t.parcel_id, t.from_owner_id, t.to_owner_id, "
            "       t.consideration, t.transfer_type, t.district_id, "
            "       p.area_hectares, o.full_name, t.signed_payload "
            "FROM transfers t "
            "JOIN parcels p ON p.parcel_id = t.parcel_id "
            "LEFT JOIN owners o ON o.id = t.to_owner_id "
            "WHERE t.id = ?",
            (transfer_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "transfer_id": row[0],
        "parcel_id": row[1],
        "from_owner_id": row[2],
        "to_owner_id": row[3],
        "consideration": row[4],
        "transfer_type": row[5],
        "district_id": row[6],
        "area_hectares": row[7],
        "owner_full_name": row[8],
        "signed_payload": row[9],
    }


def _enqueue_for_review(
    *,
    subject_type: str,
    subject_id: str,
    district_id: int,
    score: dict[str, Any],
) -> str:
    """Add an entry to ``fraud_review_queue``. No parcel state change yet."""
    review_id = str(uuid.uuid4())
    with get_connection() as conn:
        # Idempotency: if a PENDING_REVIEW already exists for this subject at
        # the same scorer_version, skip the insert.
        existing = conn.execute(
            "SELECT id FROM fraud_review_queue WHERE subject_type = ? AND subject_id = ? "
            "AND scorer_version = ? AND state = 'PENDING_REVIEW'",
            (subject_type, subject_id, score["scorer_version"]),
        ).fetchone()
        if existing:
            return str(existing[0])
        conn.execute(
            "INSERT INTO fraud_review_queue "
            "(id, subject_type, subject_id, district_id, risk_score, recommended_action, "
            " signals, scorer_version, state, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                review_id,
                subject_type,
                subject_id,
                district_id,
                int(score["risk_score"]),
                score["recommended_action"],
                json.dumps(score["signals"]),
                score["scorer_version"],
                "PENDING_REVIEW",
                time.time(),
            ),
        )
        conn.commit()
    return review_id


def _act_on_score(subject_type: str, subject_id: str, score: dict[str, Any]) -> None:
    """Apply policy-compliant side effects per the recommended action.

    NEVER auto-freezes. Only writes to the review queue + audit ledger.
    """
    action = score["recommended_action"]
    if action == "NONE":
        return
    if subject_type != "TRANSFER":
        return
    with get_connection() as conn:
        row = conn.execute(
            "SELECT parcel_id, district_id, to_owner_id FROM transfers WHERE id = ?",
            (subject_id,),
        ).fetchone()
    if not row:
        return
    parcel_id, district_id, _to_owner_id = row
    review_id = _enqueue_for_review(
        subject_type=subject_type,
        subject_id=subject_id,
        district_id=int(district_id),
        score=score,
    )
    audit_emit(
        event_type="FRAUD_REVIEW_QUEUED",
        payload={
            "review_id": review_id,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "parcel_id": parcel_id,
            "risk_score": score["risk_score"],
            "recommended_action": action,
            "scorer_version": score["scorer_version"],
            "signals": score["signals"],
            "policy_note": (
                "ML decision queued for human review. No parcel state change "
                "without affirmative action by a LAND_OFFICER or REGISTRAR. "
                "Escalation deadline: 24 hours."
            ),
        },
        district_id=int(district_id),
        actor_user_id="system:fraud_scorer",
    )


async def _score_once(message: dict[str, Any]) -> None:
    subject_type = message.get("subject_type", "TRANSFER")
    subject_id = message.get("subject_id")
    if not subject_id:
        return

    lock_key = f"fraud:scoring:lock:{subject_type}:{subject_id}"
    locked = await cache_setnx(lock_key, "1", ttl_seconds=300)
    if not locked:
        return

    prior = latest_score(subject_type, subject_id)
    if prior and prior.get("scorer_version") == SCORER_VERSION:
        return

    context = (
        _build_transfer_context(subject_id) if subject_type == "TRANSFER" else None
    )
    if context is None:
        logger.info(
            "fraud_score_skipped_missing_context",
            extra={"subject_type": subject_type, "subject_id": subject_id},
        )
        return

    score = score_subject(context)
    persist_score(subject_type=subject_type, subject_id=subject_id, score=score)
    _act_on_score(subject_type, subject_id, score.to_dict())


def score_now(subject_type: str, subject_id: str) -> dict[str, Any] | None:
    """Score a subject synchronously and return the persisted score dict.

    Used by the durable-outbox sweep and by the fail-closed approval gate
    (``transfers.approve_transfer``). Idempotent: if a score already exists at
    the current ``SCORER_VERSION`` it is returned unchanged. Returns ``None``
    only when no score exists and none can be computed (e.g. missing context).
    """
    prior = latest_score(subject_type, subject_id)
    if prior and prior.get("scorer_version") == SCORER_VERSION:
        return prior
    context = (
        _build_transfer_context(subject_id) if subject_type == "TRANSFER" else None
    )
    if context is None:
        return prior
    score = score_subject(context)
    persist_score(subject_type=subject_type, subject_id=subject_id, score=score)
    _act_on_score(subject_type, subject_id, score.to_dict())
    return latest_score(subject_type, subject_id)


def _finish_job(
    job_id: str,
    *,
    state: str,
    attempts: int,
    error: str | None = None,
    next_attempt_at: float | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE fraud_scoring_jobs SET state = ?, attempts = ?, last_error = ?, "
            "next_attempt_at = ? WHERE id = ?",
            (state, attempts, error, next_attempt_at, job_id),
        )
        conn.commit()


def sweep_scoring_outbox(limit: int = 20) -> int:
    """Drain due rows from the durable ``fraud_scoring_jobs`` outbox.

    This is the fallback that guarantees eventual scoring even if Redis was
    unavailable when the transfer was created (the stream fast-path no-ops
    then). :func:`score_now` is idempotent, so a row also picked up by the
    stream consumer is harmless. Returns the number of jobs processed.
    """
    now = time.time()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, subject_type, subject_id, attempts FROM fraud_scoring_jobs "
            "WHERE state = 'PENDING' AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
            "ORDER BY created_at LIMIT ?",
            (now, limit),
        ).fetchall()
    processed = 0
    for row in rows:
        job_id, subject_type, subject_id, attempts = row[0], row[1], row[2], int(row[3] or 0)
        try:
            score_now(subject_type, subject_id)
            _finish_job(job_id, state="DONE", attempts=attempts)
            processed += 1
        except Exception as exc:  # noqa: BLE001 — record + retry, never crash the loop
            attempts += 1
            if attempts >= _OUTBOX_MAX_ATTEMPTS:
                _finish_job(job_id, state="FAILED", attempts=attempts, error=str(exc)[:500])
                logger.error("fraud_scoring_job_failed", extra={"job_id": job_id})
            else:
                backoff = min(300.0, 2.0**attempts)
                _finish_job(
                    job_id,
                    state="PENDING",
                    attempts=attempts,
                    error=str(exc)[:500],
                    next_attempt_at=time.time() + backoff,
                )
    return processed


async def _maybe_sweep_outbox() -> None:
    """Throttled wrapper so the consumer loop sweeps the outbox at most once
    per ``_SWEEP_INTERVAL_SECONDS`` rather than on every 1s idle tick."""
    global _last_sweep
    now = time.time()
    if now - _last_sweep < _SWEEP_INTERVAL_SECONDS:
        return
    _last_sweep = now
    try:
        sweep_scoring_outbox()
    except Exception:
        logger.exception("fraud_outbox_sweep_error")


async def consumer_loop_forever() -> None:
    """Consume the Redis stream until cancelled.

    The stream is the fast path. Durability does NOT depend on it: every
    transfer also writes a row to the ``fraud_scoring_jobs`` outbox in its own
    transaction, and this loop sweeps that outbox (:func:`sweep_scoring_outbox`)
    so subjects are eventually scored even if Redis was down at enqueue time.
    """
    global _RUNNING
    if _RUNNING:
        return
    _RUNNING = True
    while _RUNNING:
        try:
            redis = await get_redis()
            if redis is None:
                # Redis down: the durable outbox is the only path to scoring.
                await _maybe_sweep_outbox()
                await asyncio.sleep(2)
                continue
            # Group already exists on warm restart → just continue.
            with contextlib.suppress(Exception):
                await redis.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
            entries = await redis.xreadgroup(
                CONSUMER_GROUP, CONSUMER_NAME, {STREAM_NAME: ">"}, count=10, block=1000
            )
            await _maybe_sweep_outbox()
            if not entries:
                continue
            for _stream, items in entries:
                for entry_id, fields in items:
                    try:
                        message = dict(fields)
                        await _score_once(message)
                    except Exception:
                        logger.exception(
                            "fraud_score_consumer_error",
                            extra={"entry_id": entry_id},
                        )
                    finally:
                        # Ack errors are non-fatal — the consumer-group
                        # XPENDING cleanup will retry stuck entries.
                        with contextlib.suppress(Exception):
                            await redis.xack(STREAM_NAME, CONSUMER_GROUP, entry_id)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("fraud_consumer_loop_iteration_error")
            await asyncio.sleep(1)


def stop_consumer() -> None:
    global _RUNNING
    _RUNNING = False
