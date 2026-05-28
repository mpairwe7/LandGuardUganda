"""Fraud score, alert, review, and appeal endpoints.

The ML scorer is a decision-support tool, not a decision-maker. These
endpoints surface the **human-in-the-loop** workflow defined in
``docs/AI_ETHICS_CHARTER.md``:

  POST /fraud/review/{review_id}/affirm   — Land Officer affirms the alert
  POST /fraud/review/{review_id}/dismiss  — Land Officer dismisses the alert
  POST /fraud/appeals                     — Citizen files an appeal
  POST /fraud/appeals/{id}/resolve        — Auditor/Registrar resolves an appeal

Affirmation by a human is the only path to FROZEN. Dismissal closes the
queue entry and clears the flag from the officer's screen.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field

from app.audit import audit_emit
from app.auth import AuthContext, Role, require_role, require_user
from app.database import get_connection
from app.fraud.scorer import latest_score
from app.fraud.worker import enqueue_score
from app.models.common import StrictModel
from app.models.fraud import FraudScoreResponse, FraudSignalResponse

router = APIRouter(prefix="/api/v1/fraud", tags=["fraud"])


# ---------------------------------------------------------------------------
# Scores read-only + alerts
# ---------------------------------------------------------------------------


@router.get("/score/{subject_type}/{subject_id}", response_model=FraudScoreResponse)
async def get_score(
    subject_type: str,
    subject_id: str,
    ctx: Annotated[
        AuthContext, Depends(require_role(Role.LAND_OFFICER, Role.REGISTRAR, Role.AUDITOR))
    ],
) -> FraudScoreResponse:
    score = latest_score(subject_type, subject_id)
    if not score:
        raise HTTPException(status_code=404, detail="no fraud score yet")
    return FraudScoreResponse(
        subject_type=subject_type,  # type: ignore[arg-type]
        subject_id=subject_id,
        risk_score=score["risk_score"],
        recommended_action=score["recommended_action"],
        signals=[_coerce_signal(s) for s in score["signals"]],
        scored_at=score["scored_at"],
        scorer_version=score["scorer_version"],
    )


@router.post("/rescore")
async def rescore(
    subject_type: str,
    subject_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(Role.REGISTRAR, Role.LAND_OFFICER))],
) -> dict[str, object]:
    await enqueue_score(subject_type=subject_type, subject_id=subject_id)
    return {"enqueued": True, "subject_type": subject_type, "subject_id": subject_id}


@router.get("/alerts", response_model=list[FraudScoreResponse])
async def list_alerts(
    ctx: Annotated[AuthContext, Depends(require_role(Role.LAND_OFFICER, Role.REGISTRAR))],
    district_id: int | None = Query(default=None),
    action: str | None = Query(default="FLAG", description="FLAG or BLOCK"),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[FraudScoreResponse]:
    where = ["fs.recommended_action != 'NONE'"]
    params: list[object] = []
    if action and action != "ALL":
        where.append("fs.recommended_action = ?")
        params.append(action)
    sql = (
        "SELECT fs.id, fs.subject_type, fs.subject_id, fs.risk_score, fs.signals, "
        "       fs.recommended_action, fs.scored_at, fs.scorer_version "
        "FROM fraud_scores fs"
    )
    if district_id is not None:
        sql += (
            " LEFT JOIN transfers t ON t.id = fs.subject_id AND fs.subject_type = 'TRANSFER' "
            " LEFT JOIN titles ti ON ti.title_no = fs.subject_id AND fs.subject_type = 'TITLE' "
        )
        where.append("(t.district_id = ? OR ti.district_id = ?)")
        params.extend([district_id, district_id])
    sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY fs.scored_at DESC LIMIT ?"
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    out: list[FraudScoreResponse] = []
    for r in rows:
        signals = json.loads(r[4]) if r[4] else []
        out.append(
            FraudScoreResponse(
                subject_type=r[1],
                subject_id=r[2],
                risk_score=int(r[3]),
                recommended_action=r[5],
                signals=[_coerce_signal(s) for s in signals],
                scored_at=float(r[6]),
                scorer_version=r[7],
            )
        )
    return out


# ---------------------------------------------------------------------------
# Human review queue
# ---------------------------------------------------------------------------


class ReviewItem(StrictModel):
    id: str
    subject_type: str
    subject_id: str
    district_id: int
    risk_score: int
    recommended_action: Literal["FLAG", "BLOCK"]
    signals: list[FraudSignalResponse]
    scorer_version: str
    state: str
    created_at: float
    reviewed_at: float | None
    reviewed_by: str | None
    review_notes: str | None


class ReviewDecision(StrictModel):
    notes: str = Field(min_length=4, max_length=2048)


def _coerce_signal(s: dict) -> FraudSignalResponse:
    """Tolerant coercion from any persisted signal shape to the API model.

    Older seeded rows used ``{rule, score, evidence}`` (score on a 0–100
    scale) before the FraudSignalResponse schema settled on
    ``{name, weight, score, explanation}`` (score 0.0–1.0). To keep the
    Officer console review queue functional against legacy data without a
    DB migration, map the old keys to the new ones and re-scale the
    score. Anything that still can't be parsed yields a minimal
    placeholder so one bad row never 500s the whole list.
    """
    name = s.get("name") or s.get("rule") or "unknown"
    explanation = s.get("explanation") or s.get("evidence") or ""
    weight = int(s["weight"]) if "weight" in s else 10
    raw_score = s.get("score", 0.0)
    try:
        score_f = float(raw_score)
    except (TypeError, ValueError):
        score_f = 0.0
    if score_f > 1.0:  # legacy 0–100 scale
        score_f = score_f / 100.0
    try:
        return FraudSignalResponse(
            name=str(name), weight=weight, score=score_f, explanation=str(explanation)
        )
    except Exception:
        return FraudSignalResponse(name="unknown", weight=0, score=0.0, explanation="")


def _row_to_review(row) -> ReviewItem:
    return ReviewItem(
        id=row[0],
        subject_type=row[1],
        subject_id=row[2],
        district_id=int(row[3]),
        risk_score=int(row[4]),
        recommended_action=row[5],
        signals=[_coerce_signal(s) for s in json.loads(row[6] or "[]")],
        scorer_version=row[7],
        state=row[8],
        created_at=float(row[9]),
        reviewed_at=float(row[10]) if row[10] is not None else None,
        reviewed_by=row[11],
        review_notes=row[12],
    )


def _load_review(review_id: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, subject_type, subject_id, district_id, risk_score, "
            " recommended_action, signals, scorer_version, state, created_at, "
            " reviewed_at, reviewed_by, review_notes "
            "FROM fraud_review_queue WHERE id = ?",
            (review_id,),
        ).fetchone()


@router.get("/reviews", response_model=list[ReviewItem])
async def list_reviews(
    ctx: Annotated[AuthContext, Depends(require_role(Role.LAND_OFFICER, Role.REGISTRAR, Role.AUDITOR))],
    district_id: int | None = Query(default=None),
    state: str = Query(default="PENDING_REVIEW"),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[ReviewItem]:
    sql = (
        "SELECT id, subject_type, subject_id, district_id, risk_score, "
        " recommended_action, signals, scorer_version, state, created_at, "
        " reviewed_at, reviewed_by, review_notes FROM fraud_review_queue WHERE state = ?"
    )
    params: list[object] = [state]
    if district_id is not None:
        sql += " AND district_id = ?"
        params.append(district_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_review(r) for r in rows]


@router.post("/review/{review_id}/affirm", response_model=ReviewItem)
async def affirm_review(
    review_id: str,
    decision: ReviewDecision,
    ctx: Annotated[AuthContext, Depends(require_role(Role.LAND_OFFICER, Role.REGISTRAR))],
) -> ReviewItem:
    """Land Officer affirms the ML alert. THIS is what causes a FREEZE — not the ML."""
    row = _load_review(review_id)
    if not row:
        raise HTTPException(status_code=404, detail="review not found")
    if row[8] != "PENDING_REVIEW":
        raise HTTPException(status_code=409, detail=f"review already in state {row[8]}")
    subject_type = row[1]
    subject_id = row[2]
    district_id = int(row[3])
    action = row[5]
    now = time.time()
    parcel_id_for_freeze: str | None = None
    with get_connection() as conn:
        conn.execute(
            "UPDATE fraud_review_queue SET state = 'HUMAN_AFFIRMED', "
            "reviewed_at = ?, reviewed_by = ?, review_notes = ? WHERE id = ?",
            (now, ctx.user_id, decision.notes, review_id),
        )
        # Only on BLOCK do we apply the parcel-level state change — and even
        # then only because a human just affirmed it.
        if action == "BLOCK" and subject_type == "TRANSFER":
            tx_row = conn.execute(
                "SELECT parcel_id FROM transfers WHERE id = ?", (subject_id,)
            ).fetchone()
            if tx_row:
                parcel_id_for_freeze = str(tx_row[0])
                conn.execute(
                    "UPDATE parcels SET status = 'FROZEN', updated_at = ? WHERE parcel_id = ?",
                    (now, parcel_id_for_freeze),
                )
                # Also auto-file the FRAUD dispute (was previously the worker's job).
                existing = conn.execute(
                    "SELECT id FROM disputes WHERE parcel_id = ? AND dispute_type = 'FRAUD' "
                    "AND state NOT IN ('RESOLVED','DISMISSED')",
                    (parcel_id_for_freeze,),
                ).fetchone()
                if not existing:
                    conn.execute(
                        "INSERT INTO disputes "
                        "(id, parcel_id, claimant_id, dispute_type, state, evidence, "
                        " district_id, filed_at) VALUES (?,?,?,?,?,?,?,?)",
                        (
                            str(uuid.uuid4()),
                            parcel_id_for_freeze,
                            ctx.user_id,
                            "FRAUD",
                            "UNDER_REVIEW",
                            json.dumps(
                                {
                                    "source": "fraud_review_affirmed",
                                    "review_id": review_id,
                                    "reviewer": ctx.user_id,
                                    "notes": decision.notes,
                                }
                            ),
                            district_id,
                            now,
                        ),
                    )
        conn.commit()
        updated = _load_review(review_id)
    audit_emit(
        event_type="FRAUD_HUMAN_AFFIRMED",
        payload={
            "review_id": review_id,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "reviewer": ctx.user_id,
            "notes": decision.notes,
            "applied_action": action,
            "parcel_frozen": parcel_id_for_freeze,
        },
        district_id=district_id,
        actor_user_id=ctx.user_id,
    )
    return _row_to_review(updated)


@router.post("/review/{review_id}/dismiss", response_model=ReviewItem)
async def dismiss_review(
    review_id: str,
    decision: ReviewDecision,
    ctx: Annotated[AuthContext, Depends(require_role(Role.LAND_OFFICER, Role.REGISTRAR))],
) -> ReviewItem:
    """Land Officer dismisses the ML alert as a false positive."""
    row = _load_review(review_id)
    if not row:
        raise HTTPException(status_code=404, detail="review not found")
    if row[8] != "PENDING_REVIEW":
        raise HTTPException(status_code=409, detail=f"review already in state {row[8]}")
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "UPDATE fraud_review_queue SET state = 'HUMAN_DISMISSED', "
            "reviewed_at = ?, reviewed_by = ?, review_notes = ? WHERE id = ?",
            (now, ctx.user_id, decision.notes, review_id),
        )
        conn.commit()
        updated = _load_review(review_id)
    audit_emit(
        event_type="FRAUD_HUMAN_DISMISSED",
        payload={
            "review_id": review_id,
            "subject_type": row[1],
            "subject_id": row[2],
            "reviewer": ctx.user_id,
            "notes": decision.notes,
        },
        district_id=int(row[3]),
        actor_user_id=ctx.user_id,
    )
    return _row_to_review(updated)


# ---------------------------------------------------------------------------
# Citizen appeals — the right-to-be-heard pathway
# ---------------------------------------------------------------------------


class AppealCreateRequest(StrictModel):
    subject_type: Literal["TRANSFER", "TITLE", "OWNER", "PARCEL"]
    subject_id: str
    review_id: str | None = None
    statement: str = Field(min_length=20, max_length=4096)
    evidence: dict | None = None


class AppealRecord(StrictModel):
    id: str
    review_id: str | None
    subject_type: str
    subject_id: str
    appellant_id: str
    statement: str
    evidence: dict | None
    state: str
    filed_at: float
    resolved_at: float | None
    resolution_note: str | None


class AppealResolveRequest(StrictModel):
    outcome: Literal["UPHELD", "DENIED"]
    note: str = Field(min_length=20, max_length=4096)


def _row_to_appeal(row) -> AppealRecord:
    return AppealRecord(
        id=row[0],
        review_id=row[1],
        subject_type=row[2],
        subject_id=row[3],
        appellant_id=row[4],
        statement=row[5],
        evidence=json.loads(row[6]) if row[6] else None,
        state=row[7],
        filed_at=float(row[8]),
        resolved_at=float(row[9]) if row[9] is not None else None,
        resolution_note=row[10],
    )


@router.post("/appeals", response_model=AppealRecord, status_code=201)
async def file_appeal(
    payload: AppealCreateRequest,
    ctx: Annotated[AuthContext, Depends(require_user)],
) -> AppealRecord:
    """Any authenticated citizen can appeal a fraud flag affecting them."""
    appeal_id = str(uuid.uuid4())
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO fraud_appeals "
            "(id, review_id, subject_type, subject_id, appellant_id, statement, "
            " evidence, state, filed_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                appeal_id,
                payload.review_id,
                payload.subject_type,
                payload.subject_id,
                ctx.user_id,
                payload.statement,
                json.dumps(payload.evidence) if payload.evidence else None,
                "OPEN",
                now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, review_id, subject_type, subject_id, appellant_id, "
            " statement, evidence, state, filed_at, resolved_at, resolution_note "
            "FROM fraud_appeals WHERE id = ?",
            (appeal_id,),
        ).fetchone()
    audit_emit(
        event_type="FRAUD_APPEAL_FILED",
        payload={
            "appeal_id": appeal_id,
            "subject_type": payload.subject_type,
            "subject_id": payload.subject_id,
            "review_id": payload.review_id,
        },
        district_id=ctx.user.district_id or 0,
        actor_user_id=ctx.user_id,
    )
    return _row_to_appeal(row)


@router.get("/appeals", response_model=list[AppealRecord])
async def list_appeals(
    ctx: Annotated[AuthContext, Depends(require_user)],
    state: str = Query(default="OPEN"),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[AppealRecord]:
    sql = (
        "SELECT id, review_id, subject_type, subject_id, appellant_id, statement, "
        " evidence, state, filed_at, resolved_at, resolution_note "
        "FROM fraud_appeals WHERE state = ?"
    )
    params: list[object] = [state]
    # Citizens see their own; staff see all.
    if ctx.role is Role.CITIZEN:
        sql += " AND appellant_id = ?"
        params.append(ctx.user_id)
    sql += " ORDER BY filed_at DESC LIMIT ?"
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_appeal(r) for r in rows]


@router.post("/appeals/{appeal_id}/resolve", response_model=AppealRecord)
async def resolve_appeal(
    appeal_id: str,
    payload: AppealResolveRequest,
    ctx: Annotated[AuthContext, Depends(require_role(Role.AUDITOR, Role.REGISTRAR))],
) -> AppealRecord:
    """An auditor or registrar (not the original officer) decides the appeal."""
    now = time.time()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT subject_type, subject_id, state FROM fraud_appeals WHERE id = ?",
            (appeal_id,),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="appeal not found")
        if existing[2] != "OPEN":
            raise HTTPException(status_code=409, detail=f"appeal already {existing[2]}")
        new_state = "UPHELD" if payload.outcome == "UPHELD" else "DENIED"
        conn.execute(
            "UPDATE fraud_appeals SET state = ?, resolved_at = ?, resolution_note = ? WHERE id = ?",
            (new_state, now, payload.note, appeal_id),
        )
        # If the appeal is upheld, unfreeze any parcel that was frozen because
        # of this subject.
        if (
            payload.outcome == "UPHELD"
            and existing[0] == "TRANSFER"
        ):
            tx_row = conn.execute(
                "SELECT parcel_id FROM transfers WHERE id = ?", (existing[1],)
            ).fetchone()
            if tx_row:
                conn.execute(
                    "UPDATE parcels SET status = 'ACTIVE', updated_at = ? "
                    "WHERE parcel_id = ? AND status IN ('FROZEN','DISPUTED')",
                    (now, tx_row[0]),
                )
        conn.commit()
        row = conn.execute(
            "SELECT id, review_id, subject_type, subject_id, appellant_id, statement, "
            " evidence, state, filed_at, resolved_at, resolution_note "
            "FROM fraud_appeals WHERE id = ?",
            (appeal_id,),
        ).fetchone()
    audit_emit(
        event_type="FRAUD_APPEAL_RESOLVED",
        payload={
            "appeal_id": appeal_id,
            "outcome": payload.outcome,
            "resolver": ctx.user_id,
            "note": payload.note,
        },
        district_id=ctx.user.district_id or 0,
        actor_user_id=ctx.user_id,
    )
    return _row_to_appeal(row)
