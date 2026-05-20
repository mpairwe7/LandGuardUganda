"""NIRA result caching: Redis hot + DB warm + circuit-breaker wrapping."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.audit.merkle import sha256_hex
from app.config import get_settings
from app.database import get_connection
from app.nira.client import NIRAVerifyResult, get_nira_client
from app.resilience import CircuitBreaker, CircuitOpenError
from app.util.cache import cache_get, cache_set
from app.util.metrics import nira_breaker_open, nira_calls_total

logger = logging.getLogger(__name__)

NIRA_BREAKER = CircuitBreaker(
    name="nira",
    failure_threshold=3,
    reset_timeout=20.0,
    max_timeout=600.0,
)


def get_nira_breaker() -> CircuitBreaker:
    return NIRA_BREAKER


def _redis_key(nin_hash: str) -> str:
    return f"nira:nin:{nin_hash}"


def _read_warm(nin_hash: str) -> tuple[dict[str, Any] | None, bool]:
    """Return (cached_result, is_stale) from the DB cache."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT verified_at, expires_at, result, source "
            "FROM nira_verifications WHERE nin_hash = ?",
            (nin_hash,),
        ).fetchone()
    if row is None:
        return None, False
    verified_at, expires_at, result, source = row
    payload = json.loads(result)
    payload["_source_cache"] = source
    payload["_verified_at"] = verified_at
    return payload, time.time() > float(expires_at)


def _write_warm(nin_hash: str, result: NIRAVerifyResult, *, ttl: int) -> None:
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO nira_verifications "
            "(nin_hash, verified_at, expires_at, result, source) VALUES (?,?,?,?,?)",
            (
                nin_hash,
                now,
                now + ttl,
                json.dumps(result.to_dict(), default=str),
                result.source,
            ),
        )
        conn.commit()


async def verify_nin_cached(nin: str) -> dict[str, Any]:
    """Verify a NIN with hot+warm cache and breaker protection.

    Returns a dict with ``stale: bool`` set when we returned cached
    data because the live call could not be made.
    """
    settings = get_settings()
    nin_hash = sha256_hex(nin)

    # 1) Redis hot cache
    hit = await cache_get(_redis_key(nin_hash))
    if hit:
        return {**json.loads(hit), "stale": False, "cache": "hot"}

    # 2) Try live (breaker-wrapped) before falling back to warm cache.
    client = get_nira_client()
    try:
        result = await NIRA_BREAKER.call(client.verify_nin, nin)
    except CircuitOpenError:
        nira_breaker_open.set(1)
        warm, _stale = _read_warm(nin_hash)
        nira_calls_total.labels(result="breaker_open").inc()
        if warm is not None:
            return {**warm, "stale": True, "cache": "warm-breaker-open"}
        return {
            "nin_valid": False,
            "matched": False,
            "demographics": None,
            "reason": "nira_unavailable",
            "stale": True,
            "cache": "miss-breaker-open",
        }
    except Exception as exc:
        nira_calls_total.labels(result="error").inc()
        logger.exception("nira_verify_failed", extra={"nin_hash": nin_hash})
        warm, _stale = _read_warm(nin_hash)
        if warm is not None:
            return {**warm, "stale": True, "cache": "warm-error", "error": str(exc)}
        raise

    nira_breaker_open.set(0)
    nira_calls_total.labels(result="match" if result.matched else "no_match").inc()
    _write_warm(nin_hash, result, ttl=settings.nira_cache_ttl_seconds)
    payload = result.to_dict()
    await cache_set(_redis_key(nin_hash), json.dumps(payload), settings.nira_cache_ttl_seconds)
    return {**payload, "stale": False, "cache": "miss"}
