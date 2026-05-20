"""Public verifier endpoint models (no auth, rate-limited)."""

from __future__ import annotations

from pydantic import Field

from app.models.common import StrictModel


class VerifyTitleRequest(StrictModel):
    """Either provide title_no alone (the system materialises the proof
    from its records), or provide a fully-formed proof to verify against
    the on-chain anchor without any database lookup.
    """

    title_no: str | None = Field(default=None, min_length=4, max_length=64)
    batch_id: str | None = None
    leaf: str | None = Field(default=None, pattern=r"^(0x)?[0-9a-fA-F]{64}$")
    siblings: list[str] | None = None


class VerifyTitleResponse(StrictModel):
    valid: bool
    title_no: str | None
    anchor_status: str
    anchored_at: float | None
    batch_id: str | None
    tx_hash: str | None
    block_number: int | None
    chain_id: int | None
    reason: str | None
