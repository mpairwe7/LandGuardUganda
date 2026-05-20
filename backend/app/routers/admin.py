"""Administrative endpoints: districts, staff, audit-chain verification."""

from __future__ import annotations

import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app.audit.verifier import verify_chain
from app.auth import AuthContext, Role, require_role
from app.database import get_connection
from app.models.common import StrictModel

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class CreateDistrictRequest(StrictModel):
    id: int = Field(ge=1, le=10_000)
    name: str = Field(min_length=2, max_length=128)
    region: str = Field(min_length=2, max_length=64)


class CreateStaffRequest(StrictModel):
    external_id: str = Field(min_length=2, max_length=128)
    district_id: int | None = None
    role: str = Field(min_length=2)
    email: str | None = None
    full_name: str | None = None


@router.post("/districts", dependencies=[Depends(require_role(Role.ADMIN))])
async def create_district(payload: CreateDistrictRequest) -> dict[str, object]:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM districts WHERE id = ?", (payload.id,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="district already exists")
        conn.execute(
            "INSERT INTO districts (id, name, region, created_at) VALUES (?,?,?,?)",
            (payload.id, payload.name, payload.region, time.time()),
        )
        conn.commit()
    return {"id": payload.id, "name": payload.name, "region": payload.region}


@router.post("/staff", dependencies=[Depends(require_role(Role.ADMIN))])
async def create_staff(payload: CreateStaffRequest) -> dict[str, object]:
    role = Role.parse(payload.role)
    if role is None:
        raise HTTPException(status_code=422, detail=f"unknown role: {payload.role}")
    staff_id = str(uuid.uuid4())
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO staff_users (id, external_id, district_id, role, email, full_name, "
            " created_at, last_seen_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                staff_id,
                payload.external_id,
                payload.district_id,
                role.value,
                payload.email,
                payload.full_name,
                now,
                now,
            ),
        )
        conn.commit()
    return {"id": staff_id, "external_id": payload.external_id, "role": role.value}


@router.get("/audit/verify/{district_id}")
async def audit_verify(
    district_id: int,
    ctx: Annotated[AuthContext, Depends(require_role(Role.AUDITOR, Role.ADMIN))],
) -> dict[str, object]:
    report = verify_chain(str(district_id))
    return report.to_dict()
