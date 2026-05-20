"""Transfer HTTP models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.models.common import StrictModel

TransferType = Literal["SALE", "GIFT", "INHERITANCE", "COURT_ORDER", "SUBDIVISION"]
TransferStatus = Literal["PENDING", "APPROVED", "REJECTED", "COMPLETED", "REVERSED"]


class TransferCreateRequest(StrictModel):
    parcel_id: str = Field(min_length=11, max_length=32)
    from_owner_id: str | None = None
    to_owner_id: str = Field(min_length=8, max_length=64)
    transfer_type: TransferType
    consideration: float | None = Field(default=None, ge=0)


class TransferRecord(StrictModel):
    id: str
    parcel_id: str
    from_owner_id: str | None
    to_owner_id: str
    transfer_type: TransferType
    consideration: float | None
    status: TransferStatus
    initiated_at: float
    completed_at: float | None
    district_id: int
