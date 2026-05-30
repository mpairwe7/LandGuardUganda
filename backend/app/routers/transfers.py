"""Ownership transfer workflow."""

from __future__ import annotations

import json
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.audit import audit_emit
from app.auth import AuthContext, Role, require_role
from app.database import get_connection
from app.fraud.scorer import SCORER_VERSION, latest_score
from app.fraud.worker import enqueue_score, score_now
from app.models.transfers import TransferCreateRequest, TransferRecord

router = APIRouter(prefix="/api/v1/transfers", tags=["transfers"])


def _row_to_transfer(row) -> TransferRecord:
    return TransferRecord(
        id=row[0],
        parcel_id=row[1],
        from_owner_id=row[2],
        to_owner_id=row[3],
        transfer_type=row[4],
        consideration=float(row[5]) if row[5] is not None else None,
        status=row[6],
        initiated_at=float(row[7]),
        completed_at=float(row[8]) if row[8] is not None else None,
        district_id=int(row[9]),
    )


@router.post("", response_model=TransferRecord, status_code=201)
async def create_transfer(
    payload: TransferCreateRequest,
    ctx: Annotated[AuthContext, Depends(require_role(Role.LAND_OFFICER, Role.CITIZEN))],
) -> TransferRecord:
    transfer_id = str(uuid.uuid4())
    now = time.time()
    with get_connection() as conn:
        parcel = conn.execute(
            "SELECT parcel_id, district_id, status, current_owner_id "
            "FROM parcels WHERE parcel_id = ?",
            (payload.parcel_id,),
        ).fetchone()
        if not parcel:
            raise HTTPException(status_code=404, detail="parcel not found")
        if parcel[2] not in ("ACTIVE", "TRANSFERRED"):
            raise HTTPException(
                status_code=409,
                detail=f"parcel status is {parcel[2]} — cannot transfer",
            )
        district_id = int(parcel[1])
        to_owner = conn.execute(
            "SELECT id, kyc_status FROM owners WHERE id = ?",
            (payload.to_owner_id,),
        ).fetchone()
        if not to_owner:
            raise HTTPException(status_code=404, detail="to_owner not found")
        signed_payload = {
            "parcel_id": payload.parcel_id,
            "from_owner_id": payload.from_owner_id or parcel[3],
            "to_owner_id": payload.to_owner_id,
            "transfer_type": payload.transfer_type,
            "consideration": payload.consideration,
            "initiated_at": now,
            "initiated_by": ctx.user_id,
        }
        conn.execute(
            "INSERT INTO transfers (id, parcel_id, from_owner_id, to_owner_id, "
            " transfer_type, consideration, status, signed_payload, initiated_at, district_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                transfer_id,
                payload.parcel_id,
                payload.from_owner_id or parcel[3],
                payload.to_owner_id,
                payload.transfer_type,
                payload.consideration,
                "PENDING",
                json.dumps(signed_payload, default=str),
                now,
                district_id,
            ),
        )
        # Transactional outbox: written in the SAME transaction as the transfer
        # so scoring is guaranteed to be attempted even if the Redis fast-path
        # enqueue below no-ops (Redis down). The worker sweeps this table.
        conn.execute(
            "INSERT INTO fraud_scoring_jobs "
            "(id, subject_type, subject_id, state, attempts, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), "TRANSFER", transfer_id, "PENDING", 0, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, parcel_id, from_owner_id, to_owner_id, transfer_type, "
            " consideration, status, initiated_at, completed_at, district_id "
            "FROM transfers WHERE id = ?",
            (transfer_id,),
        ).fetchone()
    audit_emit(
        event_type="TRANSFER_INITIATED",
        payload={"transfer_id": transfer_id, "parcel_id": payload.parcel_id, "to_owner_id": payload.to_owner_id},
        district_id=district_id,
        actor_user_id=ctx.user_id,
    )
    await enqueue_score(subject_type="TRANSFER", subject_id=transfer_id)
    return _row_to_transfer(row)


def _read_transfer(transfer_id: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, parcel_id, from_owner_id, to_owner_id, transfer_type, "
            " consideration, status, initiated_at, completed_at, district_id "
            "FROM transfers WHERE id = ?",
            (transfer_id,),
        ).fetchone()


@router.post("/{transfer_id}/approve", response_model=TransferRecord)
async def approve_transfer(
    transfer_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(Role.REGISTRAR, Role.LAND_OFFICER))],
) -> TransferRecord:
    row = _read_transfer(transfer_id)
    if not row:
        raise HTTPException(status_code=404, detail="transfer not found")
    # Fail-CLOSED fraud gate: a transfer must carry a current fraud score before
    # it can complete. If scoring never ran (Redis was down at create time, or
    # the worker lagged), score it synchronously now rather than approving blind.
    score = latest_score("TRANSFER", transfer_id)
    if not score or score.get("scorer_version") != SCORER_VERSION:
        score = score_now("TRANSFER", transfer_id)
    if not score:
        raise HTTPException(
            status_code=503,
            detail="fraud score unavailable; cannot approve transfer yet — retry shortly",
        )
    if score["recommended_action"] == "BLOCK":
        raise HTTPException(
            status_code=409,
            detail=(
                f"transfer fraud-blocked (risk_score={score['risk_score']}); "
                "resolve the FRAUD dispute first"
            ),
        )
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "UPDATE transfers SET status = 'COMPLETED', completed_at = ? WHERE id = ?",
            (now, transfer_id),
        )
        conn.execute(
            "UPDATE parcels SET current_owner_id = ?, status = 'TRANSFERRED', updated_at = ? "
            "WHERE parcel_id = ?",
            (row[3], now, row[1]),
        )
        conn.commit()
        new_row = _read_transfer(transfer_id)
    audit_emit(
        event_type="TRANSFER_COMPLETED",
        payload={"transfer_id": transfer_id, "parcel_id": row[1], "to_owner_id": row[3]},
        district_id=int(row[9]),
        actor_user_id=ctx.user_id,
    )
    return _row_to_transfer(new_row)


@router.post("/{transfer_id}/reject", response_model=TransferRecord)
async def reject_transfer(
    transfer_id: str,
    reason: str,
    ctx: Annotated[AuthContext, Depends(require_role(Role.REGISTRAR, Role.LAND_OFFICER))],
) -> TransferRecord:
    row = _read_transfer(transfer_id)
    if not row:
        raise HTTPException(status_code=404, detail="transfer not found")
    with get_connection() as conn:
        conn.execute(
            "UPDATE transfers SET status = 'REJECTED' WHERE id = ?",
            (transfer_id,),
        )
        conn.commit()
        new_row = _read_transfer(transfer_id)
    audit_emit(
        event_type="TRANSFER_REJECTED",
        payload={"transfer_id": transfer_id, "reason": reason},
        district_id=int(row[9]),
        actor_user_id=ctx.user_id,
    )
    return _row_to_transfer(new_row)


@router.get("/{transfer_id}", response_model=TransferRecord)
async def get_transfer(
    transfer_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(*Role))],
) -> TransferRecord:
    row = _read_transfer(transfer_id)
    if not row:
        raise HTTPException(status_code=404, detail="transfer not found")
    return _row_to_transfer(row)
