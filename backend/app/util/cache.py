"""Redis client + small helpers (idempotency, NIRA cache, fraud locks).

Falls back to an in-memory dict when Redis is unreachable, so the
service degrades gracefully (sibling project's pattern). The in-memory
fallback is single-worker only — production Redis outage is logged
loudly so operators know to investigate.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import redis.asyncio as redis_async

from app.config import get_settings

logger = logging.getLogger(__name__)

_REDIS: redis_async.Redis | None = None
_FALLBACK: dict[str, tuple[float, str]] = {}
_FALLBACK_LOCK = asyncio.Lock()


async def get_redis() -> redis_async.Redis | None:
    global _REDIS
    settings = get_settings()
    if _REDIS is not None:
        return _REDIS
    try:
        client = redis_async.from_url(settings.redis_url, decode_responses=True)
        await asyncio.wait_for(client.ping(), timeout=1.5)
        _REDIS = client
        return _REDIS
    except Exception as exc:
        logger.warning("redis_unavailable_using_fallback", extra={"error": str(exc)})
        return None


async def cache_set(key: str, value: str, ttl_seconds: int) -> None:
    client = await get_redis()
    if client is not None:
        await client.set(key, value, ex=ttl_seconds)
        return
    async with _FALLBACK_LOCK:
        _FALLBACK[key] = (time.time() + ttl_seconds, value)


async def cache_get(key: str) -> str | None:
    client = await get_redis()
    if client is not None:
        v = await client.get(key)
        return v if v is None else str(v)
    async with _FALLBACK_LOCK:
        entry = _FALLBACK.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            del _FALLBACK[key]
            return None
        return value


async def cache_setnx(key: str, value: str, ttl_seconds: int) -> bool:
    """SET if NX with TTL — returns True if key was set (not previously present)."""
    client = await get_redis()
    if client is not None:
        result = await client.set(key, value, ex=ttl_seconds, nx=True)
        return bool(result)
    async with _FALLBACK_LOCK:
        entry = _FALLBACK.get(key)
        if entry is not None and time.time() <= entry[0]:
            return False
        _FALLBACK[key] = (time.time() + ttl_seconds, value)
        return True


async def cache_delete(key: str) -> None:
    client = await get_redis()
    if client is not None:
        await client.delete(key)
        return
    async with _FALLBACK_LOCK:
        _FALLBACK.pop(key, None)


async def stream_publish(stream: str, fields: dict[str, Any]) -> str | None:
    client = await get_redis()
    if client is None:
        logger.warning("redis_unavailable_stream_publish_skipped", extra={"stream": stream})
        return None
    return await client.xadd(stream, {k: str(v) for k, v in fields.items()})
