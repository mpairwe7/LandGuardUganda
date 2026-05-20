"""Title HTTP models."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.models.common import StrictModel


class TitleIssueRequest(StrictModel):
    parcel_id: str = Field(min_length=11, max_length=32)
    owner_id: str = Field(min_length=8, max_length=64)


class TitleRecord(StrictModel):
    title_no: str
    parcel_id: str
    issued_at: float
    registrar_id: str
    district_id: int
    content_hash: str
    merkle_proof: dict[str, Any] | None
    revoked_at: float | None
    revoke_reason: str | None
    anchor_status: str  # "PENDING" | "ANCHORED"
    tx_hash: str | None
    block_number: int | None
