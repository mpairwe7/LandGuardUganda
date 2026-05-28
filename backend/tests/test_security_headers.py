"""Pack F1 — SecurityHeadersMiddleware response-header contract.

The Caddyfile sets the same headers at the edge, but on Crane Cloud
backends are exposed directly so the app layer must carry the
hardening on its own. These tests pin the contract.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# Always-on headers — every response carries them, regardless of route.
# ---------------------------------------------------------------------------

ALWAYS_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    # Server header is overwritten to remove "uvicorn" disclosure.
    "Server": "landguard",
}


@pytest.mark.parametrize("path", ["/healthz", "/readyz", "/api/v1/verify/sample-qr-payload"])
def test_always_on_security_headers(client: TestClient, path: str) -> None:
    resp = client.get(path)
    for name, value in ALWAYS_HEADERS.items():
        assert resp.headers.get(name) == value, f"{name} on {path}: got {resp.headers.get(name)!r}"


def test_permissions_policy_present(client: TestClient) -> None:
    resp = client.get("/healthz")
    pp = resp.headers.get("Permissions-Policy", "")
    assert "camera=(self)" in pp
    assert "microphone=()" in pp


def test_csp_on_json_responses(client: TestClient) -> None:
    """JSON responses carry a Content-Security-Policy header."""
    resp = client.get("/healthz")
    assert resp.headers.get("content-type", "").startswith("application/json")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert csp, "JSON response should carry CSP"
    assert "frame-ancestors 'none'" in csp


def test_no_server_uvicorn_disclosure(client: TestClient) -> None:
    """The Server header MUST NOT advertise the underlying stack."""
    resp = client.get("/healthz")
    assert "uvicorn" not in resp.headers.get("Server", "").lower()
    assert "fastapi" not in resp.headers.get("Server", "").lower()


def test_request_id_propagates(client: TestClient) -> None:
    """Existing X-Request-ID middleware still wires up alongside ours."""
    resp = client.get("/healthz", headers={"X-Request-Id": "test-rid-1234"})
    assert resp.headers.get("X-Request-Id") == "test-rid-1234"
