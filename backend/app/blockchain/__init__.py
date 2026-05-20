"""Blockchain anchoring layer — the LandGuard innovation centerpiece.

A dual-layer trust model:
1. Off-chain: hash-chained audit ledger (see :mod:`app.audit`)
2. On-chain: periodic Merkle-root anchoring of batches via web3.py

This package isolates everything that talks to a chain so the rest of
the codebase remains chain-agnostic. Provider is selected at startup
via ``BLOCKCHAIN_PROVIDER`` (mock | anvil | sepolia).
"""

from __future__ import annotations

from .client import BlockchainClient, get_blockchain_client
from .models import AnchorReceipt, MerkleProof

__all__ = [
    "AnchorReceipt",
    "BlockchainClient",
    "MerkleProof",
    "get_blockchain_client",
]
