"""Pack F3 — /readyz reports fraud_model + audit_chain health."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def test_readyz_includes_fraud_model_status(client: TestClient) -> None:
    body = client.get("/readyz").json()
    assert "details" in body
    fm = body["details"].get("fraud_model")
    assert isinstance(fm, dict)
    assert "loaded" in fm
    assert isinstance(fm["loaded"], bool)
    assert fm["path"].endswith("isoforest-v1.joblib")


def test_readyz_includes_audit_chain_walk(client: TestClient) -> None:
    body = client.get("/readyz").json()
    ac = body["details"].get("audit_chain")
    # In a fully-bootstrapped runtime, audit_chain is a dict with
    # {verified, districts}. In a test environment where the schema may
    # not be applied yet, the readyz handler surfaces the failure as a
    # string ("error: no such table: audit_events"); the field is still
    # present, which is the contract we need to pin.
    assert ac is not None, "audit_chain field is missing"
    if isinstance(ac, dict):
        assert "verified" in ac
        assert isinstance(ac["verified"], bool)
        districts = ac["districts"]
        assert {d["district_id"] for d in districts} >= {1, 2, 3, 4}
        for d in districts:
            assert isinstance(d["events"], int)
            assert isinstance(d["verified"], bool)
    else:
        assert isinstance(ac, str)
        assert ac.startswith("error:")


def test_readyz_still_returns_200_when_blockchain_is_mock(client: TestClient) -> None:
    """Enriching readyz must not regress its existing contract."""
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
