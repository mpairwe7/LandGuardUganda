"""Merkle tree helpers — two hashing regimes, by design.

LandGuard runs **two parallel Merkle trees** over the same set of audit
events:

1. **Off-chain integrity tree** — Bitcoin-style index-ordered SHA-256.
   Used by ``audit/verifier.py`` to walk the per-district hash chain and
   produce a tamper-evidence report that any third-party Python/TS auditor
   can recompute with no chain access. Functions: ``sha256_hex``,
   ``compute_merkle_root``, ``merkle_proof``, ``verify_merkle_proof``.

2. **On-chain anchored tree** — sorted-pair Keccak-256 over
   ``keccak(sha256_hex_leaf)`` leaves. Matches LandRegistryAnchor.sol
   ``verifyProof`` byte-for-byte. This is what the ``commitBatch``
   transaction stores and what the public verifier checks. Functions:
   ``keccak_hex``, ``keccak_pair_sorted``, ``compute_merkle_root_evm``,
   ``merkle_proof_evm``, ``verify_merkle_proof_evm``.

Why two? Off-chain auditors should not need a working EVM client; on-chain
verification should not have to import a SHA-256 library when keccak is
free. The bridge — keccak of the SHA-256 hex leaf — is documented at the
top of ``anchor_service.py`` and explicitly tested in ``test_merkle_cross.py``.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable

from eth_utils import keccak as _keccak


# ---------------------------------------------------------------------------
# Regime 1 — Off-chain integrity tree (SHA-256, index-ordered)
# ---------------------------------------------------------------------------


def sha256_hex(data: bytes | str) -> str:
    """Return the lowercase hex SHA-256 of ``data``."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def pair_hash(left: str, right: str) -> str:
    """Combine two hex hashes into a parent hex hash (deterministic, SHA-256)."""
    return sha256_hex(left + right)


def compute_merkle_root(leaf_hashes: Iterable[str]) -> str:
    """SHA-256 Merkle root, Bitcoin-style duplicate-last for odd levels."""
    level = list(leaf_hashes)
    if not level:
        return ""
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [pair_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def merkle_proof(leaf_hashes: list[str], index: int) -> list[str]:
    """SHA-256 inclusion-proof siblings for ``leaf_hashes[index]``."""
    if not (0 <= index < len(leaf_hashes)):
        raise IndexError(f"leaf index {index} out of range {len(leaf_hashes)}")
    proof: list[str] = []
    level = list(leaf_hashes)
    idx = index
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        sibling = level[idx ^ 1]
        proof.append(sibling)
        level = [pair_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)]
        idx //= 2
    return proof


def verify_merkle_proof(leaf: str, proof: list[str], root: str, index: int) -> bool:
    """Verify a SHA-256 proof against the off-chain integrity root."""
    h = leaf
    idx = index
    for sibling in proof:
        h = pair_hash(sibling, h) if idx & 1 else pair_hash(h, sibling)
        idx //= 2
    return h == root


# ---------------------------------------------------------------------------
# Regime 2 — On-chain anchored tree (sorted-pair Keccak-256)
# ---------------------------------------------------------------------------


def _hex_to_bytes32(value: str) -> bytes:
    """Normalise a hex string (optionally 0x-prefixed) to 32 raw bytes."""
    s = value.lower().removeprefix("0x")
    if len(s) < 64:
        s = s.zfill(64)
    elif len(s) > 64:
        s = s[-64:]
    return bytes.fromhex(s)


def keccak_hex(data: bytes | str) -> str:
    """Keccak-256 of ``data`` as 0x-prefixed lowercase hex."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return "0x" + _keccak(data).hex()


def keccak_pair_sorted(left_hex: str, right_hex: str) -> str:
    """Sorted-pair keccak — matches LandRegistryAnchor.verifyProof exactly.

    Each input is expected to be a 32-byte hex string (with or without ``0x``
    prefix). The pair is hashed as ``keccak(min(a,b) || max(a,b))``.
    """
    a = _hex_to_bytes32(left_hex)
    b = _hex_to_bytes32(right_hex)
    lo, hi = (a, b) if a <= b else (b, a)
    return "0x" + _keccak(lo + hi).hex()


def sha256_leaves_to_keccak(sha256_hex_leaves: Iterable[str]) -> list[str]:
    """Bridge: convert SHA-256 hex leaves to ``keccak(sha256_hex)`` leaves.

    The keccak is computed over the **lowercased hex string** (UTF-8 bytes),
    not the raw 32-byte payload. This is the canonical bridge between the
    audit ledger's SHA-256 discipline and the contract's keccak verifier.
    """
    return [keccak_hex(leaf.lower().removeprefix("0x")) for leaf in sha256_hex_leaves]


def compute_merkle_root_evm(sha256_hex_leaves: Iterable[str]) -> str:
    """Compute the on-chain-compatible Merkle root.

    Given SHA-256 hex leaves from the audit ledger, returns the 0x-prefixed
    keccak root that ``LandRegistryAnchor.commitBatch`` should anchor.
    Sorted-pair keccak; duplicate-last for odd levels (matches OZ MerkleProof
    semantics).
    """
    level = sha256_leaves_to_keccak(sha256_hex_leaves)
    if not level:
        return ""
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [
            keccak_pair_sorted(level[i], level[i + 1])
            for i in range(0, len(level), 2)
        ]
    return level[0]


def merkle_proof_evm(sha256_hex_leaves: list[str], index: int) -> dict[str, Any]:
    """Build the on-chain-compatible inclusion proof for one leaf.

    Returns ``{"leaf": "0x...", "siblings": ["0x...", ...], "root": "0x..."}``
    in keccak hex form. Directly consumable by
    ``LandRegistryAnchor.verifyProof(batchId, leaf, siblings)``.
    """
    if not (0 <= index < len(sha256_hex_leaves)):
        raise IndexError(f"leaf index {index} out of range {len(sha256_hex_leaves)}")
    keccak_leaves = sha256_leaves_to_keccak(sha256_hex_leaves)
    target_leaf = keccak_leaves[index]
    proof: list[str] = []
    level = list(keccak_leaves)
    idx = index
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        sibling = level[idx ^ 1]
        proof.append(sibling)
        level = [
            keccak_pair_sorted(level[i], level[i + 1])
            for i in range(0, len(level), 2)
        ]
        idx //= 2
    return {"leaf": target_leaf, "siblings": proof, "root": level[0]}


def verify_merkle_proof_evm(leaf_hex: str, siblings: list[str], root: str) -> bool:
    """Mirror of LandRegistryAnchor.verifyProof for offline cross-checks.

    Pure-Python implementation that lets any auditor confirm a proof without
    an EVM client.
    """
    h = leaf_hex
    for sibling in siblings:
        h = keccak_pair_sorted(h, sibling)
    return h.lower() == root.lower()
