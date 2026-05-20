"""Fraud-score HTTP models."""

from __future__ import annotations

from typing import Literal

from app.models.common import StrictModel


class FraudSignalResponse(StrictModel):
    name: str
    weight: int
    score: float
    explanation: str


class FraudScoreResponse(StrictModel):
    subject_type: Literal["TRANSFER", "TITLE", "OWNER", "PARCEL"]
    subject_id: str
    risk_score: int
    recommended_action: Literal["NONE", "FLAG", "BLOCK"]
    signals: list[FraudSignalResponse]
    scored_at: float
    scorer_version: str
