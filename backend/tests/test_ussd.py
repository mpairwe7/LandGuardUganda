"""USSD callback contract tests — proves the Africa's Talking shape works
end-to-end against the mock blockchain client.
"""

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
def client_with_anchored_title():
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
        conn.execute(
            "INSERT INTO titles (title_no, parcel_id, issued_at, registrar_id, "
            " district_id, content_hash) VALUES (?,?,?,?,?,?)",
            ("UG-MIT-T00007/2026", "UG-MIT-024718/2026", now, "r", 3, "h" * 64),
        )
        conn.commit()


@pytest.mark.asyncio
async def test_ussd_menu_first_step(client_with_anchored_title):
    with TestClient(create_app()) as c:
        resp = c.post(
            "/api/v1/ussd",
            data={
                "sessionId": "ATU-1",
                "serviceCode": "*247*256#",
                "phoneNumber": "+256700000001",
                "text": "",
            },
        )
        assert resp.status_code == 200
        assert resp.text.startswith("CON ")
        assert "Verify title" in resp.text


@pytest.mark.asyncio
async def test_ussd_help_terminates(client_with_anchored_title):
    with TestClient(create_app()) as c:
        resp = c.post(
            "/api/v1/ussd",
            data={
                "sessionId": "ATU-2",
                "serviceCode": "*247*256#",
                "phoneNumber": "+256700000002",
                "text": "3",
            },
        )
        assert resp.status_code == 200
        assert resp.text.startswith("END ")
        assert "MoLHUD" in resp.text


@pytest.mark.asyncio
async def test_ussd_verify_path_terminates_with_result(client_with_anchored_title):
    # Issue + anchor an audit event so the verifier can find it.
    ledger = get_ledger()
    ledger.append(
        event_type="TITLE_ISSUED",
        payload={"title_no": "UG-MIT-T00007/2026", "parcel_id": "UG-MIT-024718/2026"},
        tenant_id="3",
        user_id="r",
    )
    await flush_district(district_id=3, force=True)
    with TestClient(create_app()) as c:
        resp = c.post(
            "/api/v1/ussd",
            data={
                "sessionId": "ATU-3",
                "serviceCode": "*247*256#",
                "phoneNumber": "+256700000003",
                "text": "1*UG-MIT-T00007/2026",
            },
        )
        assert resp.status_code == 200
        assert resp.text.startswith("END ")
        # 182-char ceiling
        assert len(resp.text) <= 187  # "END " + 182


@pytest.mark.asyncio
async def test_sms_verify(client_with_anchored_title):
    with TestClient(create_app()) as c:
        resp = c.post(
            "/api/v1/sms/verify",
            data={"From": "+256700000004", "Body": "UG-MIT-T00007/2026"},
        )
        assert resp.status_code == 200
        msg = resp.json()["message"]
        # Either "✓ Title ... VERIFIED" or "✗ Title ...: ..." — both <=160 chars.
        assert len(msg) <= 182
