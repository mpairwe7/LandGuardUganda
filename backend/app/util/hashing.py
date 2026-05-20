"""Canonical JSON + hex hashing helpers (re-exports from audit.merkle)."""

from __future__ import annotations

import json
from typing import Any

from app.audit.merkle import pair_hash, sha256_hex

__all__ = ["canonical_json", "pair_hash", "sha256_hex", "content_hash"]


def canonical_json(payload: dict[str, Any]) -> str:
    """Deterministic JSON encoding: sort keys, ascii-safe, defaults stringified."""
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def content_hash(payload: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON; the universal content fingerprint."""
    return sha256_hex(canonical_json(payload))
