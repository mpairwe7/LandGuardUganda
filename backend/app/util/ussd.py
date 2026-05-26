"""USSD session state machine + response formatting.

LandGuard exposes a feature-phone pathway so the ~60% of rural Ugandans
without smartphones can verify land titles. The session state is kept in
Redis (with a short TTL) keyed on the caller's MSISDN. Responses follow
the Africa's Talking USSD protocol — ``CON ...`` to keep the session open,
``END ...`` to terminate.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.util.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

# All responses must fit in a single USSD frame (~182 chars worst case
# across operators). Verification result text targets 160 to be safe.
MAX_USSD_LEN = 182


@dataclass(frozen=True)
class UssdRequest:
    """Subset of the Africa's Talking USSD POST body we care about."""

    session_id: str
    service_code: str
    phone_number: str
    text: str  # accumulated input across the session, '*' delimited

    @classmethod
    def from_form(cls, form: dict[str, str]) -> UssdRequest:
        return cls(
            session_id=form.get("sessionId", ""),
            service_code=form.get("serviceCode", ""),
            phone_number=form.get("phoneNumber", ""),
            text=form.get("text", ""),
        )

    @property
    def steps(self) -> list[str]:
        """Africa's Talking concatenates user input with '*' between turns."""
        return [s for s in (self.text or "").split("*") if s]


def truncate(message: str) -> str:
    if len(message) <= MAX_USSD_LEN:
        return message
    return message[: MAX_USSD_LEN - 1] + "…"


def con(message: str) -> str:
    return "CON " + truncate(message)


def end(message: str) -> str:
    return "END " + truncate(message)


def short_proof_label(batch_id: str | None) -> str:
    if not batch_id:
        return "no batch"
    return batch_id[:8]


def format_verify_result(result: dict[str, Any]) -> str:
    """Render a verifier response in <=160 chars for USSD/SMS."""
    title = result.get("title_no") or "(unknown)"
    if result.get("valid"):
        block = result.get("block_number") or "—"
        tx = (result.get("tx_hash") or "")[2:10]
        return f"✓ Title {title} VERIFIED on block {block} (tx {tx}). Tamper-evident."
    reason = (result.get("reason") or "unverified").replace("_", " ")
    return f"✗ Title {title}: {reason}. Visit a District Land Office or call 0414-XXXXXX."


# ---------------------------------------------------------------------------
# Session storage (Redis with in-memory fallback) — short-lived (5 min TTL).
# ---------------------------------------------------------------------------


def _session_key(session_id: str) -> str:
    return f"ussd:session:{session_id}"


async def session_load(session_id: str) -> dict[str, Any]:
    raw = await cache_get(_session_key(session_id))
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


async def session_save(session_id: str, data: dict[str, Any]) -> None:
    await cache_set(_session_key(session_id), json.dumps(data), ttl_seconds=300)
