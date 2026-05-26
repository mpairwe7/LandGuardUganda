"""Smoke test of the public Merkle-proof verifier endpoint."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.audit import get_ledger, reset_ledger
from app.blockchain.anchor_service import flush_district
from app.blockchain.client import reset_blockchain_client
from app.database import get_connection
from app.main import create_app


@pytest.fixture
def client():
    reset_ledger()
    reset_blockchain_client()
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO districts (id, name, region, created_at) "
            "VALUES (3,'Mityana','Central',?)",
            (now,),
        )
        conn.execute(
            "INSERT OR IGNORE INTO parcels (parcel_id, tenure_type, district_id, "
            " sub_county, geometry_geojson, area_hectares, status, created_at, updated_at) "
            "VALUES ('UG-MIT-024718/2026','MAILO',3,'Mityana TC','{}',1.0,'ACTIVE',?,?)",
            (now, now),
        )
        conn.commit()
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_verify_unknown_title(client):
    resp = client.post("/api/v1/verify/title", json={"title_no": "UG-XXX-000000/2026"})
    assert resp.status_code == 200
    assert not resp.json()["valid"]
    assert resp.json()["reason"] == "title_not_found"


@pytest.mark.asyncio
async def test_verify_after_anchor():
    # Issue + anchor a title manually (bypassing auth), then verify.
    title_no = "UG-MIT-T00001/2026"
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO districts (id, name, region, created_at) "
            "VALUES (3,'Mityana','Central',?)",
            (now,),
        )
        conn.execute(
            "INSERT OR IGNORE INTO parcels (parcel_id, tenure_type, district_id, "
            " sub_county, geometry_geojson, area_hectares, status, created_at, updated_at) "
            "VALUES ('UG-MIT-024718/2026','MAILO',3,'Mityana TC','{}',1.0,'ACTIVE',?,?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO titles (title_no, parcel_id, issued_at, registrar_id, "
            " district_id, content_hash) VALUES (?,?,?,?,?,?)",
            (title_no, "UG-MIT-024718/2026", now, "registrar-test", 3, "hash" * 16),
        )
        conn.commit()
    ledger = get_ledger()
    ledger.append(
        event_type="TITLE_ISSUED",
        payload={"title_no": title_no, "parcel_id": "UG-MIT-024718/2026"},
        tenant_id="3",
        user_id="registrar-test",
    )
    receipt = await flush_district(district_id=3, force=True)
    assert receipt["status"] == "CONFIRMED"
    from app.main import create_app

    with TestClient(create_app()) as c:
        resp = c.post("/api/v1/verify/title", json={"title_no": title_no})
        body = resp.json()
        assert resp.status_code == 200, body
        assert body["valid"]
        assert body["batch_id"] == receipt["batch_id"]
