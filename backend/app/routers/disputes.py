"""Land dispute workflow."""

from __future__ import annotations

import json
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.audit import audit_emit
from app.auth import AuthContext, Role, require_role, require_user
from app.database import get_connection
from app.models.disputes import (
    DisputeFileRequest,
    DisputeRecord,
    DisputeResolveRequest,
)

router = APIRouter(prefix="/api/v1/disputes", tags=["disputes"])


def _row_to_dispute(row) -> DisputeRecord:
    return DisputeRecord(
        id=row[0],
        parcel_id=row[1],
        claimant_id=row[2],
        respondent_id=row[3],
        dispute_type=row[4],
        state=row[5],
        evidence=json.loads(row[6]) if row[6] else None,
        resolution=row[7],
        district_id=int(row[8]),
        filed_at=float(row[9]),
        resolved_at=float(row[10]) if row[10] is not None else None,
    )


@router.post("", response_model=DisputeRecord, status_code=201)
async def file_dispute(
    payload: DisputeFileRequest,
    ctx: Annotated[AuthContext, Depends(require_user)],
) -> DisputeRecord:
    with get_connection() as conn:
        parcel = conn.execute(
            "SELECT parcel_id, district_id FROM parcels WHERE parcel_id = ?",
            (payload.parcel_id,),
        ).fetchone()
        if not parcel:
            raise HTTPException(status_code=404, detail="parcel not found")
        district_id = int(parcel[1])
        dispute_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO disputes (id, parcel_id, claimant_id, respondent_id, "
            " dispute_type, state, evidence, district_id, filed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                dispute_id,
                payload.parcel_id,
                ctx.user_id,
                payload.respondent_id,
                payload.dispute_type,
                "FILED",
                json.dumps(payload.evidence) if payload.evidence else None,
                district_id,
                time.time(),
            ),
        )
        # Freeze the parcel for fraud/overlap/ownership disputes immediately.
        if payload.dispute_type in ("FRAUD", "OVERLAP", "OWNERSHIP"):
            conn.execute(
                "UPDATE parcels SET status = 'DISPUTED', updated_at = ? WHERE parcel_id = ?",
                (time.time(), payload.parcel_id),
            )
        conn.commit()
        row = conn.execute(
            "SELECT id, parcel_id, claimant_id, respondent_id, dispute_type, state, "
            " evidence, resolution, district_id, filed_at, resolved_at "
            "FROM disputes WHERE id = ?",
            (dispute_id,),
        ).fetchone()
    audit_emit(
        event_type="DISPUTE_FILED",
        payload={
            "dispute_id": dispute_id,
            "parcel_id": payload.parcel_id,
            "dispute_type": payload.dispute_type,
            "claimant_id": ctx.user_id,
        },
        district_id=district_id,
        actor_user_id=ctx.user_id,
    )
    return _row_to_dispute(row)


@router.get("", response_model=list[DisputeRecord])
async def list_disputes(
    ctx: Annotated[AuthContext, Depends(require_user)],
    district_id: int | None = Query(default=None),
    state: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[DisputeRecord]:
    where: list[str] = []
    params: list[object] = []
    if district_id is not None:
        where.append("district_id = ?")
        params.append(district_id)
    if state:
        where.append("state = ?")
        params.append(state)
    # Citizens see only their own disputes; staff see all.
    if ctx.role is Role.CITIZEN:
        where.append("claimant_id = ?")
        params.append(ctx.user_id)
    sql = (
        "SELECT id, parcel_id, claimant_id, respondent_id, dispute_type, state, "
        " evidence, resolution, district_id, filed_at, resolved_at FROM disputes"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY filed_at DESC LIMIT ?"
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dispute(r) for r in rows]


@router.post("/{dispute_id}/review", response_model=DisputeRecord)
async def review_dispute(
    dispute_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(Role.LAND_OFFICER, Role.REGISTRAR))],
) -> DisputeRecord:
    with get_connection() as conn:
        conn.execute(
            "UPDATE disputes SET state = 'UNDER_REVIEW' WHERE id = ?",
            (dispute_id,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, parcel_id, claimant_id, respondent_id, dispute_type, state, "
            " evidence, resolution, district_id, filed_at, resolved_at "
            "FROM disputes WHERE id = ?",
            (dispute_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="dispute not found")
    audit_emit(
        event_type="DISPUTE_REVIEWED",
        payload={"dispute_id": dispute_id},
        district_id=int(row[8]),
        actor_user_id=ctx.user_id,
    )
    return _row_to_dispute(row)


@router.post("/{dispute_id}/resolve", response_model=DisputeRecord)
async def resolve_dispute(
    dispute_id: str,
    payload: DisputeResolveRequest,
    ctx: Annotated[AuthContext, Depends(require_role(Role.REGISTRAR))],
) -> DisputeRecord:
    now = time.time()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT parcel_id, district_id FROM disputes WHERE id = ?",
            (dispute_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="dispute not found")
        parcel_id = row[0]
        district_id = int(row[1])
        conn.execute(
            "UPDATE disputes SET state = ?, resolution = ?, resolved_at = ? WHERE id = ?",
            (payload.state, payload.resolution, now, dispute_id),
        )
        # If resolved/dismissed, unfreeze the parcel (best-effort; no-op if not FROZEN/DISPUTED).
        if payload.state in ("RESOLVED", "DISMISSED"):
            conn.execute(
                "UPDATE parcels SET status = 'ACTIVE', updated_at = ? "
                "WHERE parcel_id = ? AND status IN ('DISPUTED','FROZEN')",
                (now, parcel_id),
            )
        conn.commit()
        full_row = conn.execute(
            "SELECT id, parcel_id, claimant_id, respondent_id, dispute_type, state, "
            " evidence, resolution, district_id, filed_at, resolved_at "
            "FROM disputes WHERE id = ?",
            (dispute_id,),
        ).fetchone()
    audit_emit(
        event_type="DISPUTE_RESOLVED",
        payload={
            "dispute_id": dispute_id,
            "state": payload.state,
            "resolution": payload.resolution,
        },
        district_id=district_id,
        actor_user_id=ctx.user_id,
    )
    return _row_to_dispute(full_row)
