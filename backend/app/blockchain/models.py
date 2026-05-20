"""Plain dataclasses returned by blockchain clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AnchorReceipt:
    """Receipt from committing a batch to the chain."""

    batch_id: str
    district_id: int
    merkle_root: str
    tx_hash: str
    block_number: int | None
    chain_id: int
    submitted_at: float
    confirmed_at: float | None
    status: str  # "PENDING" | "SUBMITTED" | "CONFIRMED" | "FAILED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "district_id": self.district_id,
            "merkle_root": self.merkle_root,
            "tx_hash": self.tx_hash,
            "block_number": self.block_number,
            "chain_id": self.chain_id,
            "submitted_at": self.submitted_at,
            "confirmed_at": self.confirmed_at,
            "status": self.status,
        }


@dataclass(frozen=True)
class MerkleProof:
    """A Merkle inclusion proof targeting an on-chain anchor."""

    batch_id: str
    leaf: str  # hex, 0x-prefixed bytes32 form expected by Solidity verifier
    siblings: list[str] = field(default_factory=list)
    root: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "leaf": self.leaf,
            "siblings": list(self.siblings),
            "root": self.root,
        }
