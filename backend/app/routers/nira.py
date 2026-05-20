"""NIRA verification endpoint (audited, rate-limited)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import Field, field_validator

from app.audit import audit_emit
from app.audit.merkle import sha256_hex
from app.auth import AuthContext, Role, require_role
from app.models.common import StrictModel
from app.nira.cache import verify_nin_cached
from app.util.ids import validate_nin

router = APIRouter(prefix="/api/v1/nira", tags=["nira"])


class NIRAVerifyBody(StrictModel):
    nin: str = Field(min_length=14, max_length=14)

    @field_validator("nin")
    @classmethod
    def _shape(cls, v: str) -> str:
        if not validate_nin(v):
            raise ValueError("invalid NIN shape")
        return v


@router.post("/verify")
async def verify_nin_endpoint(
    payload: NIRAVerifyBody,
    ctx: Annotated[AuthContext, Depends(require_role(Role.LAND_OFFICER, Role.REGISTRAR))],
) -> dict[str, object]:
    result = await verify_nin_cached(payload.nin)
    audit_emit(
        event_type="NIRA_VERIFY",
        payload={
            "nin_hash": sha256_hex(payload.nin),
            "matched": bool(result.get("matched")),
            "stale": bool(result.get("stale")),
        },
        district_id=ctx.user.district_id or 0,
        actor_user_id=ctx.user_id,
    )
    return result
