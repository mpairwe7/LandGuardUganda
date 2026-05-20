"""Append-only, hash-chained audit ledger for LandGuard Uganda.

Every meaningful state change in the system (title issuance, transfer,
KYC verification, dispute filing, anchor commit) writes one
:class:`AuditEvent` via :func:`audit_emit`.

The ledger is per-district (tenant = district_id) so each district's
chain anchors independently — one district's outage or bad actor
cannot corrupt another's verifiability.

Patterns reused from the FinalYearProject sibling at
``App/backend/app/audit/`` with minimal edits — the cryptographic
discipline is identical.
"""

from __future__ import annotations

import logging
from typing import Any

from .ledger import AuditEvent, AuditLedger, GENESIS_HASH, get_ledger, reset_ledger
from .merkle import (
    compute_merkle_root,
    compute_merkle_root_evm,
    keccak_hex,
    keccak_pair_sorted,
    merkle_proof_evm,
    pair_hash,
    sha256_hex,
    verify_merkle_proof_evm,
)

logger = logging.getLogger(__name__)

__all__ = [
    "AuditEvent",
    "AuditLedger",
    "GENESIS_HASH",
    "audit_emit",
    "compute_merkle_root",
    "compute_merkle_root_evm",
    "get_ledger",
    "keccak_hex",
    "keccak_pair_sorted",
    "merkle_proof_evm",
    "pair_hash",
    "reset_ledger",
    "sha256_hex",
    "verify_merkle_proof_evm",
]


def audit_emit(
    event_type: str,
    payload: dict[str, Any],
    *,
    district_id: int | str,
    actor_user_id: str,
) -> AuditEvent | None:
    """Best-effort audit write.

    Audit failures NEVER crash the calling request. A failure here is
    a serious incident — increment Prometheus ``audit_failure_total``
    and surface a structured log — but the user-facing operation must
    still succeed because the off-chain data is still in Postgres.

    Args:
        event_type: One of TITLE_ISSUED, TRANSFER_INITIATED,
            TRANSFER_COMPLETED, DISPUTE_FILED, OWNERSHIP_FROZEN,
            KYC_VERIFIED, ANCHOR_COMMITTED, FRAUD_BLOCK, etc.
        payload: Structured event content. Serialised deterministically
            (sorted keys) before hashing.
        district_id: Tenant boundary; coerced to str.
        actor_user_id: Staff user or citizen UUID emitting the event.
    """
    try:
        ledger = get_ledger()
        return ledger.append(
            event_type=event_type,
            payload=payload,
            tenant_id=str(district_id),
            user_id=str(actor_user_id),
        )
    except Exception:
        logger.exception(
            "audit_emit_failed",
            extra={
                "event_type": event_type,
                "district_id": district_id,
                "actor_user_id": actor_user_id,
            },
        )
        # Optional Prometheus counter increment hook — wired in app.main lifespan.
        from app.util.metrics import audit_failure_total

        audit_failure_total.inc()
        return None
