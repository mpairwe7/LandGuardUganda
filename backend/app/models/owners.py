"""Owner (citizen) HTTP models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.models.common import StrictModel
from app.util.ids import validate_nin

KycStatus = Literal["PENDING", "VERIFIED", "REJECTED", "EXPIRED"]


class OwnerCreateRequest(StrictModel):
    nin: str = Field(min_length=14, max_length=14)
    full_name: str = Field(min_length=2, max_length=128)
    dob: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    phone: str | None = Field(default=None, min_length=9, max_length=16)

    @field_validator("nin")
    @classmethod
    def _check_nin(cls, v: str) -> str:
        if not validate_nin(v):
            raise ValueError("nin must match Uganda NIRA shape CM[A-Z0-9]{12}")
        return v


class OwnerRecord(StrictModel):
    id: str
    nin_redacted: str  # Last 4 only.
    full_name: str
    dob: str | None
    phone: str | None
    kyc_status: KycStatus
    kyc_verified_at: float | None
    created_at: float
    updated_at: float


class KycVerifyRequest(StrictModel):
    nin: str = Field(min_length=14, max_length=14)
    biometric_template: str | None = Field(
        default=None,
        description="Optional base64-encoded biometric template for match.",
    )

    @field_validator("nin")
    @classmethod
    def _check_nin(cls, v: str) -> str:
        if not validate_nin(v):
            raise ValueError("invalid NIN shape")
        return v
