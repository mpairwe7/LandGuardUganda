"""Walks the per-district audit chain and verifies hash integrity.

Run as a scheduled job (or on-demand via the auditor console) to
prove that no rows have been tampered with since they were written.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from .ledger import GENESIS_HASH, get_ledger
from .merkle import sha256_hex

logger = logging.getLogger(__name__)


@dataclass
class VerificationReport:
    tenant_id: str
    total_events: int
    verified: bool
    first_corrupt_seq: int | None
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "total_events": self.total_events,
            "verified": self.verified,
            "first_corrupt_seq": self.first_corrupt_seq,
            "reason": self.reason,
        }


def verify_chain(tenant_id: str, *, batch: int = 500) -> VerificationReport:
    """Walk the chain for ``tenant_id`` and verify every row.

    Returns success only when every row's ``payload_hash`` equals the
    canonical SHA-256 of its payload AND every row's ``row_hash`` equals
    ``sha256(prev_hash + payload_hash)``.
    """
    ledger = get_ledger()
    total = ledger.count(tenant_id)
    prev_hash = GENESIS_HASH
    cursor = 0
    seen = 0
    while True:
        rows = ledger.read(tenant_id, since_seq=cursor, limit=batch)
        if not rows:
            break
        for row in rows:
            canonical = json.dumps(row["payload"], sort_keys=True, default=str)
            recomputed_payload = sha256_hex(canonical)
            if recomputed_payload != row["payload_hash"]:
                return VerificationReport(
                    tenant_id=tenant_id,
                    total_events=total,
                    verified=False,
                    first_corrupt_seq=row["seq"],
                    reason="payload_hash_mismatch",
                )
            expected_row = sha256_hex(prev_hash + row["payload_hash"])
            if expected_row != row["row_hash"]:
                return VerificationReport(
                    tenant_id=tenant_id,
                    total_events=total,
                    verified=False,
                    first_corrupt_seq=row["seq"],
                    reason="row_hash_chain_break",
                )
            prev_hash = row["row_hash"]
            seen += 1
            cursor = row["seq"]
    return VerificationReport(
        tenant_id=tenant_id,
        total_events=seen,
        verified=True,
        first_corrupt_seq=None,
        reason=None,
    )
