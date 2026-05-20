"""Idempotency-Key middleware (24h Redis dedupe).

Reads ``Idempotency-Key`` header on mutating verbs. If we've seen the
key before for this user + route, we return the cached response instead
of re-running the handler. Falls back gracefully when Redis is down
(behaviour: skip dedupe + log; the underlying handler must still be safe
to re-run).
"""

from __future__ import annotations

import json
import logging
import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.util.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

HEADER = "Idempotency-Key"
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
UUID_RE = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def _idem_key(request: Request, supplied: str) -> str:
    user_id = "anon"
    auth = getattr(request.state, "auth", None)
    if auth is not None:
        user_id = auth.user_id
    return f"idem:{user_id}:{request.url.path}:{supplied}"


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in MUTATING:
            return await call_next(request)
        if request.url.path.startswith(("/healthz", "/readyz", "/metrics", "/api/v1/verify")):
            return await call_next(request)
        supplied = request.headers.get(HEADER)
        if not supplied:
            # We DO NOT enforce presence on every mutating endpoint —
            # individual routers can mark themselves as requiring it.
            return await call_next(request)
        if not UUID_RE.match(supplied):
            return JSONResponse(
                status_code=422,
                content={"detail": "Idempotency-Key must match UUID-like shape"},
            )
        cache_key = _idem_key(request, supplied)
        cached = await cache_get(cache_key)
        if cached:
            try:
                envelope = json.loads(cached)
                return JSONResponse(
                    status_code=int(envelope["status"]),
                    content=envelope["body"],
                    headers={"X-Idempotent-Replay": "true"},
                )
            except Exception:
                logger.exception("idempotency_cache_decode_failed", extra={"key": cache_key})
        response = await call_next(request)
        if response.status_code < 500 and response.media_type == "application/json":
            try:
                # Read the body without breaking downstream iteration.
                body_bytes = b""
                async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                    body_bytes += chunk
                envelope = {
                    "status": response.status_code,
                    "body": json.loads(body_bytes.decode("utf-8")) if body_bytes else None,
                }
                await cache_set(cache_key, json.dumps(envelope), ttl_seconds=86400)
                return JSONResponse(
                    status_code=response.status_code,
                    content=envelope["body"],
                    headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"},
                )
            except Exception:
                logger.exception("idempotency_cache_write_failed", extra={"key": cache_key})
        return response
