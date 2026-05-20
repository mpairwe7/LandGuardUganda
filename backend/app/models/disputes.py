"""Dispute HTTP models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.models.common import StrictModel

DisputeType = Literal["OVERLAP", "OWNERSHIP", "BOUNDARY", "FRAUD", "ENCROACHMENT"]
DisputeState = Literal[
    "FILED", "UNDER_REVIEW", "MEDIATION", "RESOLVED", "DISMISSED", "ESCALATED_COURT"
]


class DisputeFileRequest(StrictModel):
    parcel_id: str = Field(min_length=11, max_length=32)
    respondent_id: str | None = None
    dispute_type: DisputeType
    evidence: dict[str, Any] | None = None


class DisputeResolveRequest(StrictModel):
    resolution: str = Field(min_length=8, max_length=2048)
    state: Literal["RESOLVED", "DISMISSED", "ESCALATED_COURT"] = "RESOLVED"


class DisputeRecord(StrictModel):
    id: str
    parcel_id: str
    claimant_id: str
    respondent_id: str | None
    dispute_type: DisputeType
    state: DisputeState
    evidence: dict[str, Any] | None
    resolution: str | None
    district_id: int
    filed_at: float
    resolved_at: float | None
