"""X-Request-ID propagation + structured-log binding.

Echoes (or assigns) a per-request UUID and stashes it on
``request.state`` for downstream handlers, audit emission, and OTel.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HEADER_NAME = "X-Request-Id"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get(HEADER_NAME) or uuid.uuid4().hex
        request.state.request_id = rid
        response = await call_next(request)
        response.headers[HEADER_NAME] = rid
        return response
