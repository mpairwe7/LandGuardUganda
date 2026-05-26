"""Anchor service — periodic on-chain Merkle root commitment.

Loop trigger (per district):
1. Volume: ≥ ``ANCHOR_FLUSH_BATCH_SIZE`` unanchored events
2. Time:   ≥ ``ANCHOR_FLUSH_INTERVAL_SECONDS`` since last anchor

Wrapped in the shared :class:`CircuitBreaker` — testnet outages queue
batches but never block off-chain writes (the architectural payoff).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from app.audit import audit_emit, get_ledger
from app.audit.merkle import (
    compute_merkle_root,
    compute_merkle_root_evm,
    merkle_proof_evm,
)
from app.blockchain.client import get_blockchain_client
from app.blockchain.models import MerkleProof
from app.config import get_settings
from app.database import get_connection
from app.resilience import CircuitBreaker, CircuitOpenError
from app.util.metrics import (
    anchor_batches_total,
    anchor_breaker_open,
    anchor_failures_total,
    anchor_queue_depth,
)

logger = logging.getLogger(__name__)

# Shared breaker — exposed for the demo control panel + health endpoint.
ANCHOR_BREAKER = CircuitBreaker(
    name="blockchain_anchor",
    failure_threshold=3,
    reset_timeout=10.0,
    max_timeout=300.0,
)


def get_anchor_breaker() -> CircuitBreaker:
    return ANCHOR_BREAKER


def _last_anchor_ts(district_id: int) -> float:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT anchored_at FROM anchors WHERE district_id = ? "
            "ORDER BY anchored_at DESC LIMIT 1",
            (district_id,),
        ).fetchone()
    return float(row[0]) if row else 0.0


def _list_districts() -> list[int]:
    with get_connection() as conn:
        rows = conn.execute("SELECT id FROM districts").fetchall()
    return [int(r[0]) for r in rows]


def _insert_anchor(record: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO anchors "
            "(batch_id, district_id, root_hash, first_seq, last_seq, leaf_count, "
            " tx_hash, block_number, anchored_at, confirmed_at, status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                record["batch_id"],
                record["district_id"],
                record["root_hash"],
                record["first_seq"],
                record["last_seq"],
                record["leaf_count"],
                record.get("tx_hash"),
                record.get("block_number"),
                record["anchored_at"],
                record.get("confirmed_at"),
                record["status"],
            ),
        )
        conn.commit()


def _update_anchor_status(batch_id: str, **fields: Any) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [batch_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE anchors SET {sets} WHERE batch_id = ?", values)
        conn.commit()


async def flush_district(district_id: int, *, force: bool = False) -> dict[str, Any]:
    """Anchor unanchored events for one district. Returns receipt summary."""
    settings = get_settings()
    ledger = get_ledger()
    tenant = str(district_id)
    events = ledger.unanchored(tenant_id=tenant, limit=settings.anchor_flush_batch_size * 4)
    anchor_queue_depth.labels(district_id=tenant).set(len(events))
    if not events:
        return {"district_id": district_id, "status": "EMPTY", "leaf_count": 0}
    # Time-based threshold per district. Skip flush if neither the
    # batch-size nor the elapsed-time bound is met, unless the caller
    # explicitly forces it (demo control panel, manual operator flush).
    if (
        not force
        and len(events) < settings.anchor_flush_batch_size
        and time.time() - _last_anchor_ts(district_id)
        < settings.anchor_flush_interval_seconds
    ):
        return {
            "district_id": district_id,
            "status": "DEFERRED",
            "leaf_count": len(events),
        }

    first_seq = events[0]["seq"]
    last_seq = events[-1]["seq"]
    leaves = [e["payload_hash"] for e in events]
    # Off-chain integrity root (SHA-256, index-ordered) — kept for the chain
    # verifier and the public audit kit so any third party can recompute it
    # without an EVM client.
    sha256_root = compute_merkle_root(leaves)
    # On-chain anchored root (sorted-pair keccak over keccak(sha256_hex) leaves)
    # — what the LandRegistryAnchor.verifyProof actually attests.
    onchain_root = compute_merkle_root_evm(leaves)
    batch_id = str(uuid.uuid4())
    record = {
        "batch_id": batch_id,
        "district_id": district_id,
        "root_hash": onchain_root,
        "first_seq": first_seq,
        "last_seq": last_seq,
        "leaf_count": len(leaves),
        "anchored_at": time.time(),
        "status": "PENDING",
    }
    _insert_anchor(record)

    client = get_blockchain_client()
    try:
        receipt = await ANCHOR_BREAKER.call(
            client.commit_batch,
            batch_id=batch_id,
            district_id=district_id,
            merkle_root_hex=onchain_root,
        )
    except CircuitOpenError:
        anchor_breaker_open.set(1)
        anchor_failures_total.labels(reason="breaker_open").inc()
        _update_anchor_status(batch_id, status="PENDING")
        logger.warning(
            "anchor_breaker_open_batch_queued",
            extra={"district_id": district_id, "batch_id": batch_id},
        )
        return {**record, "status": "PENDING_BREAKER_OPEN"}
    except Exception as exc:
        anchor_failures_total.labels(reason="rpc_error").inc()
        _update_anchor_status(batch_id, status="FAILED")
        logger.exception(
            "anchor_submit_failed",
            extra={"district_id": district_id, "batch_id": batch_id, "error": str(exc)},
        )
        return {**record, "status": "FAILED", "error": str(exc)}

    anchor_breaker_open.set(0)
    anchor_batches_total.labels(district_id=tenant, result=receipt.status).inc()
    _update_anchor_status(
        batch_id,
        tx_hash=receipt.tx_hash,
        block_number=receipt.block_number,
        confirmed_at=receipt.confirmed_at,
        status=receipt.status,
    )
    ledger.mark_anchored(tenant_id=tenant, first_seq=first_seq, last_seq=last_seq, batch_id=batch_id)
    audit_emit(
        event_type="ANCHOR_COMMITTED",
        payload={
            "batch_id": batch_id,
            "onchain_root": onchain_root,
            "sha256_root": sha256_root,
            "tx_hash": receipt.tx_hash,
            "block_number": receipt.block_number,
            "first_seq": first_seq,
            "last_seq": last_seq,
            "leaf_count": len(leaves),
            "chain_id": receipt.chain_id,
        },
        district_id=district_id,
        actor_user_id="system:anchor_service",
    )
    return receipt.to_dict()


def build_proof_for_event(*, district_id: int, leaf_seq: int) -> MerkleProof | None:
    """Materialise the on-chain-compatible Merkle inclusion proof.

    Returns the (leaf, siblings, root) triple in sorted-pair keccak form —
    directly consumable by ``LandRegistryAnchor.verifyProof``. Any auditor
    can independently cross-check by recomputing
    ``verify_merkle_proof_evm(leaf, siblings, root)`` in pure Python.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT a.batch_id, a.root_hash, a.first_seq, a.last_seq "
            "FROM audit_events e JOIN anchors a ON a.batch_id = e.anchored_in "
            "WHERE e.tenant_id = ? AND e.seq = ?",
            (str(district_id), leaf_seq),
        ).fetchone()
        if not row:
            return None
        batch_id, root, first_seq, last_seq = row
        leaves_rows = conn.execute(
            "SELECT seq, payload_hash FROM audit_events "
            "WHERE tenant_id = ? AND seq BETWEEN ? AND ? ORDER BY seq",
            (str(district_id), first_seq, last_seq),
        ).fetchall()
    leaves = [str(r[1]) for r in leaves_rows]
    target_index = next(i for i, r in enumerate(leaves_rows) if int(r[0]) == leaf_seq)
    proof = merkle_proof_evm(leaves, target_index)
    return MerkleProof(
        batch_id=str(batch_id),
        leaf=proof["leaf"],
        siblings=proof["siblings"],
        root=str(root),
    )


async def anchor_loop_forever() -> None:
    """Background loop launched by FastAPI lifespan."""
    settings = get_settings()
    interval = max(15, settings.anchor_flush_interval_seconds // 10)
    logger.info("anchor_loop_started", extra={"poll_interval": interval})
    while True:
        try:
            for district_id in _list_districts():
                try:
                    await flush_district(district_id)
                except Exception:
                    logger.exception("flush_district_failed", extra={"district_id": district_id})
        except Exception:
            logger.exception("anchor_loop_iteration_failed")
        await asyncio.sleep(interval)
