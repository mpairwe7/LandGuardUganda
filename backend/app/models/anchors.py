"""Anchor (blockchain batch) HTTP models."""

from __future__ import annotations

from typing import Literal

from app.models.common import StrictModel

AnchorStatus = Literal["PENDING", "SUBMITTED", "CONFIRMED", "FAILED", "REVERTED"]


class AnchorRecord(StrictModel):
    batch_id: str
    district_id: int
    root_hash: str
    first_seq: int
    last_seq: int
    leaf_count: int
    tx_hash: str | None
    block_number: int | None
    anchored_at: float
    confirmed_at: float | None
    status: AnchorStatus


class AnchorListResponse(StrictModel):
    items: list[AnchorRecord]
    total: int
