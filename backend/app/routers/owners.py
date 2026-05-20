"""Owner (citizen) registration + KYC + lookup."""

from __future__ import annotations

import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.audit import audit_emit
from app.audit.merkle import sha256_hex
from app.auth import AuthContext, Role, require_role
from app.crypto import encrypt
from app.database import get_connection
from app.models.owners import KycVerifyRequest, OwnerCreateRequest, OwnerRecord
from app.nira.cache import verify_nin_cached

router = APIRouter(prefix="/api/v1/owners", tags=["owners"])


def _redact(nin: str) -> str:
    return f"{'•' * 10}{nin[-4:]}"


def _row_to_owner(row) -> OwnerRecord:
    return OwnerRecord(
        id=row[0],
        nin_redacted=row[1],
        full_name=row[2],
        dob=row[3],
        phone=row[4],
        kyc_status=row[5],
        kyc_verified_at=float(row[6]) if row[6] is not None else None,
        created_at=float(row[7]),
        updated_at=float(row[8]),
    )


def _fetch(owner_id: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, nin_hash, full_name, dob, phone, kyc_status, kyc_verified_at, "
            "       created_at, updated_at FROM owners WHERE id = ?",
            (owner_id,),
        ).fetchone()


@router.post("", response_model=OwnerRecord, status_code=201)
async def create_owner(
    payload: OwnerCreateRequest,
    ctx: Annotated[AuthContext, Depends(require_role(Role.LAND_OFFICER, Role.REGISTRAR))],
) -> OwnerRecord:
    nin_hash = sha256_hex(payload.nin)
    nin_encrypted = encrypt(payload.nin)
    owner_id = str(uuid.uuid4())
    now = time.time()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM owners WHERE nin_hash = ?", (nin_hash,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="owner with this NIN already exists")
        conn.execute(
            "INSERT INTO owners (id, nin_hash, nin_encrypted, full_name, dob, phone, "
            " kyc_status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                owner_id,
                nin_hash,
                nin_encrypted,
                payload.full_name,
                payload.dob,
                payload.phone,
                "PENDING",
                now,
                now,
            ),
        )
        conn.commit()
    audit_emit(
        event_type="OWNER_REGISTERED",
        payload={
            "owner_id": owner_id,
            "nin_hash": nin_hash,
            "full_name": payload.full_name,
        },
        district_id=ctx.user.district_id or 0,
        actor_user_id=ctx.user_id,
    )
    return OwnerRecord(
        id=owner_id,
        nin_redacted=_redact(payload.nin),
        full_name=payload.full_name,
        dob=payload.dob,
        phone=payload.phone,
        kyc_status="PENDING",
        kyc_verified_at=None,
        created_at=now,
        updated_at=now,
    )


@router.post("/{owner_id}/kyc")
async def kyc_verify(
    owner_id: str,
    payload: KycVerifyRequest,
    ctx: Annotated[AuthContext, Depends(require_role(Role.LAND_OFFICER, Role.REGISTRAR))],
) -> dict[str, object]:
    row = _fetch(owner_id)
    if not row:
        raise HTTPException(status_code=404, detail="owner not found")
    result = await verify_nin_cached(payload.nin)
    new_status = "VERIFIED" if result.get("matched") else "REJECTED"
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "UPDATE owners SET kyc_status = ?, kyc_verified_at = ?, updated_at = ? "
            "WHERE id = ?",
            (new_status, now if new_status == "VERIFIED" else None, now, owner_id),
        )
        conn.commit()
    audit_emit(
        event_type=f"KYC_{new_status}",
        payload={
            "owner_id": owner_id,
            "matched": bool(result.get("matched")),
            "source": result.get("source", "MOCK"),
            "stale": bool(result.get("stale")),
            "reason": result.get("reason"),
        },
        district_id=ctx.user.district_id or 0,
        actor_user_id=ctx.user_id,
    )
    return {"owner_id": owner_id, "kyc_status": new_status, "verification": result}


@router.get("/{owner_id}", response_model=OwnerRecord)
async def get_owner(
    owner_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(*Role))],
) -> OwnerRecord:
    row = _fetch(owner_id)
    if not row:
        raise HTTPException(status_code=404, detail="owner not found")
    return OwnerRecord(
        id=row[0],
        nin_redacted=f"•••• ••••  {row[1][-4:]}",
        full_name=row[2],
        dob=row[3],
        phone=row[4],
        kyc_status=row[5],
        kyc_verified_at=float(row[6]) if row[6] is not None else None,
        created_at=float(row[7]),
        updated_at=float(row[8]),
    )


@router.get("/by-nin-hash/{nin_hash}", response_model=OwnerRecord)
async def get_owner_by_hash(
    nin_hash: str,
    ctx: Annotated[AuthContext, Depends(require_role(Role.LAND_OFFICER, Role.REGISTRAR))],
) -> OwnerRecord:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, nin_hash, full_name, dob, phone, kyc_status, kyc_verified_at, "
            "       created_at, updated_at FROM owners WHERE nin_hash = ?",
            (nin_hash,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="owner not found")
    return OwnerRecord(
        id=row[0],
        nin_redacted=f"•••• ••••  {row[1][-4:]}",
        full_name=row[2],
        dob=row[3],
        phone=row[4],
        kyc_status=row[5],
        kyc_verified_at=float(row[6]) if row[6] is not None else None,
        created_at=float(row[7]),
        updated_at=float(row[8]),
    )
