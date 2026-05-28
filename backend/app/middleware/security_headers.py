"""Security headers middleware.

Mirrors the Caddyfile's header block at the FastAPI layer so the same
hardening applies whether the backend is fronted by Caddy (local dev) or
exposed directly (Crane Cloud deploys it as a standalone pod with no
proxy in front).

The Caddy layer keeps adding the headers — duplicate header values are
harmless (the browser uses one), and the defense-in-depth means a
mis-configured edge can't accidentally strip the security posture.

In ``app_env=development`` we relax the Content-Security-Policy enough
to let the auto-generated /docs Swagger UI load its bundled JS + CDN
fonts; in production we lock it down to ``default-src 'self'`` only.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings

# Headers that are always set.
_STATIC_HEADERS: dict[str, str] = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=(self)",
    # Block cross-origin window opens to our origin; harmless for an API.
    "Cross-Origin-Opener-Policy": "same-origin",
    # Don't disclose the server stack ("uvicorn") to opportunistic scanners.
    "Server": "landguard",
}

# CSP — strict in production, with a small relaxation for /docs in dev so
# Swagger UI's CDN-loaded JS still works. The API itself returns JSON, not
# HTML, so the CSP value mostly matters for /docs and error pages.
_CSP_PROD = (
    "default-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'self'"
)
_CSP_DEV = (
    "default-src 'self'; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Append baseline security headers to every response."""

    def __init__(self, app) -> None:
        super().__init__(app)
        settings = get_settings()
        self._csp = _CSP_PROD if settings.app_env == "production" else _CSP_DEV

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for k, v in _STATIC_HEADERS.items():
            # Use direct assignment, NOT setdefault — we want to overwrite
            # any uvicorn-supplied "Server: uvicorn" header.
            response.headers[k] = v
        # CSP only on HTML / JSON / docs responses — skip on /metrics
        # (Prometheus scrape) and any binary payload to keep clients happy.
        ct = response.headers.get("content-type", "")
        if "text/html" in ct or "application/json" in ct or request.url.path in ("/docs", "/redoc"):
            response.headers["Content-Security-Policy"] = self._csp
        return response
