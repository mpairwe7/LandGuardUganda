"""PUBLIC Merkle-proof verifier — no auth. The showcase wow endpoint.

A QR-encoded title carries (title_no | content_hash). Anyone — a
foreign investor, a journalist, a citizen — can call this endpoint
and confirm the title is anchored to the on-chain root. Rate-limited
strictly to keep abuse bounded.

NOTE: This module deliberately does NOT use ``from __future__ import
annotations``. slowapi's ``@limiter.limit`` wraps the function; the
wrapper's globals belong to slowapi's module, so stringified annotations
become unresolvable forward refs at FastAPI route-registration time.
Keeping concrete type annotations here sidesteps that.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request

from app.blockchain import get_blockchain_client
from app.blockchain.anchor_service import build_proof_for_event
from app.database import get_connection
from app.middleware.limits import limit_public_verify
from app.models.verify import VerifyTitleRequest, VerifyTitleResponse

router = APIRouter(prefix="/api/v1/verify", tags=["public-verify"])
logger = logging.getLogger(__name__)


def _read_title(title_no: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT title_no, parcel_id, district_id, content_hash, merkle_proof, "
            "       issued_at, registrar_id "
            "FROM titles WHERE title_no = ?",
            (title_no,),
        ).fetchone()
    if not row:
        return None
    return {
        "title_no": row[0],
        "parcel_id": row[1],
        "district_id": int(row[2]),
        "content_hash": row[3],
        "merkle_proof": json.loads(row[4]) if row[4] else None,
        "issued_at": float(row[5]),
        "registrar_id": row[6],
    }


def _read_anchor_for_title(title_no: str, parcel_id: str | None = None) -> dict | None:
    """Find the anchor that includes the audit event for this title issuance.

    Primary path: match by ``"title_no"`` in the audit-event payload.
    Fallback: when ``parcel_id`` is provided AND the primary path misses,
    match by ``"parcel_id"`` in the payload of a ``TITLE_ISSUED`` event.
    This rescues legacy seeded data whose TITLE_ISSUED payload omitted
    ``title_no`` — without that fallback, every pre-fix seeded title
    would silently fail verification.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT a.batch_id, a.root_hash, a.tx_hash, a.block_number, a.anchored_at, "
            "       a.confirmed_at, a.status "
            "FROM anchors a "
            "WHERE a.batch_id = ("
            "  SELECT anchored_in FROM audit_events "
            "  WHERE event_type = 'TITLE_ISSUED' "
            "  AND payload_json LIKE ?"
            "  ORDER BY seq DESC LIMIT 1"
            ")",
            (f'%"title_no": "{title_no}"%',),
        ).fetchone()
        if (not row or not row[0]) and parcel_id:
            row = conn.execute(
                "SELECT a.batch_id, a.root_hash, a.tx_hash, a.block_number, a.anchored_at, "
                "       a.confirmed_at, a.status "
                "FROM anchors a "
                "WHERE a.batch_id = ("
                "  SELECT anchored_in FROM audit_events "
                "  WHERE event_type = 'TITLE_ISSUED' "
                "  AND payload_json LIKE ?"
                "  ORDER BY seq DESC LIMIT 1"
                ")",
                (f'%"parcel_id": "{parcel_id}"%',),
            ).fetchone()
    if not row or not row[0]:
        return None
    return {
        "batch_id": row[0],
        "root_hash": row[1],
        "tx_hash": row[2],
        "block_number": int(row[3]) if row[3] is not None else None,
        "anchored_at": float(row[4]),
        "confirmed_at": float(row[5]) if row[5] is not None else None,
        "status": row[6],
    }


def _read_event_seq_for_title(title_no: str, district_id: int, parcel_id: str | None = None) -> int | None:
    """Sequence number of the TITLE_ISSUED audit event for this title.

    Same primary + parcel_id fallback as ``_read_anchor_for_title`` —
    needed for proof reconstruction against legacy seeded data.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT seq FROM audit_events "
            "WHERE tenant_id = ? AND event_type = 'TITLE_ISSUED' "
            "AND payload_json LIKE ?",
            (str(district_id), f'%"title_no": "{title_no}"%'),
        ).fetchone()
        if not row and parcel_id:
            row = conn.execute(
                "SELECT seq FROM audit_events "
                "WHERE tenant_id = ? AND event_type = 'TITLE_ISSUED' "
                "AND payload_json LIKE ?",
                (str(district_id), f'%"parcel_id": "{parcel_id}"%'),
            ).fetchone()
    return int(row[0]) if row else None


@router.post("/title", response_model=VerifyTitleResponse)
@limit_public_verify
async def verify_title(request: Request, payload: VerifyTitleRequest) -> VerifyTitleResponse:
    """Verify a title against its anchor.

    Two modes:
    - Online: pass ``title_no`` only; we look up its anchor + proof and
      verify against the chain. Suitable for the demo.
    - Offline-bridged: pass a full {title_no, batch_id, leaf, siblings}
      bundle (as encoded in the printed QR). Lets verification work
      against a chain even if the LandGuard database is unreachable —
      the on-chain root is sufficient.
    """
    client = get_blockchain_client()

    if payload.title_no and not (payload.batch_id and payload.leaf and payload.siblings is not None):
        title = _read_title(payload.title_no)
        if not title:
            return VerifyTitleResponse(
                valid=False,
                title_no=payload.title_no,
                anchor_status="UNKNOWN",
                anchored_at=None,
                batch_id=None,
                tx_hash=None,
                block_number=None,
                chain_id=None,
                reason="title_not_found",
            )
        anchor = _read_anchor_for_title(payload.title_no, parcel_id=title["parcel_id"])
        if not anchor:
            return VerifyTitleResponse(
                valid=False,
                title_no=payload.title_no,
                anchor_status="PENDING_ANCHOR",
                anchored_at=None,
                batch_id=None,
                tx_hash=None,
                block_number=None,
                chain_id=None,
                reason="title_pending_anchor",
            )
        seq = _read_event_seq_for_title(payload.title_no, title["district_id"], parcel_id=title["parcel_id"])
        if seq is None:
            return VerifyTitleResponse(
                valid=False,
                title_no=payload.title_no,
                anchor_status=anchor["status"],
                anchored_at=anchor["anchored_at"],
                batch_id=anchor["batch_id"],
                tx_hash=anchor["tx_hash"],
                block_number=anchor["block_number"],
                chain_id=None,
                reason="audit_event_missing",
            )
        proof = build_proof_for_event(district_id=title["district_id"], leaf_seq=seq)
        if proof is None:
            return VerifyTitleResponse(
                valid=False,
                title_no=payload.title_no,
                anchor_status=anchor["status"],
                anchored_at=anchor["anchored_at"],
                batch_id=anchor["batch_id"],
                tx_hash=anchor["tx_hash"],
                block_number=anchor["block_number"],
                chain_id=None,
                reason="proof_unavailable",
            )
        valid = await client.verify_proof(
            batch_id=proof.batch_id,
            leaf_hex=proof.leaf,
            proof_hex=proof.siblings,
        )
        return VerifyTitleResponse(
            valid=valid,
            title_no=payload.title_no,
            anchor_status=anchor["status"],
            anchored_at=anchor["anchored_at"],
            batch_id=anchor["batch_id"],
            tx_hash=anchor["tx_hash"],
            block_number=anchor["block_number"],
            chain_id=client.chain_id,
            reason=None if valid else "merkle_verification_failed",
        )

    # Offline-bridged: trust nothing in our DB; only the supplied bundle + the chain.
    if not (payload.batch_id and payload.leaf and payload.siblings is not None):
        raise HTTPException(
            status_code=422,
            detail="Provide title_no, or (batch_id + leaf + siblings)",
        )
    valid = await client.verify_proof(
        batch_id=payload.batch_id,
        leaf_hex=payload.leaf,
        proof_hex=payload.siblings,
    )
    return VerifyTitleResponse(
        valid=valid,
        title_no=payload.title_no,
        anchor_status="ANCHORED" if valid else "UNKNOWN",
        anchored_at=None,
        batch_id=payload.batch_id,
        tx_hash=None,
        block_number=None,
        chain_id=client.chain_id,
        reason=None if valid else "merkle_verification_failed",
    )


@router.get("/sample-qr-payload", include_in_schema=False)
async def sample_qr_payload() -> dict[str, str]:
    """Tiny helper used by the demo Control Panel + QR generator to produce
    a verifiable payload for the showcase audience.
    """
    return {
        "title_no": "UG-MIT-T00007/2026",
        "hint": "POST to /api/v1/verify/title with this title_no",
    }
