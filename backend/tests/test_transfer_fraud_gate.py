"""Fail-closed fraud gate (G1).

A transfer must carry a current fraud score before it can be approved:
- an existing BLOCK score stops approval;
- an unscored transfer is scored *synchronously* at approve time (so it is
  never approved blind), and a synchronously-computed BLOCK still stops it.
"""

from __future__ import annotations

import json
import time
import uuid

from fastapi.testclient import TestClient

from app.database import get_connection
from app.fraud.scorer import FraudScore, latest_score, persist_score
from app.main import create_app

_OFFICER = {"X-Demo-Role": "LAND_OFFICER", "X-Demo-District": "3"}
_UNIT_SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]}


def _seed_parcel(*, kyc: str = "VERIFIED", geometry: dict | None = None) -> dict:
    now = time.time()
    parcel_id = f"UG-MIT-{uuid.uuid4().hex[:6]}/2026"
    owner_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO districts (id, name, region, created_at) "
            "VALUES (3,'Mityana','Central',?)",
            (now,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO owners (id, nin_hash, full_name, kyc_status, "
            " created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (owner_id, uuid.uuid4().hex * 2, "Test Person", kyc, now, now),
        )
        conn.execute(
            "INSERT OR REPLACE INTO parcels (parcel_id, tenure_type, district_id, "
            " sub_county, geometry_geojson, area_hectares, current_owner_id, status, "
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                parcel_id,
                "MAILO",
                3,
                "Mityana TC",
                json.dumps(geometry or _UNIT_SQUARE),
                1.0,
                owner_id,
                "ACTIVE",
                now,
                now,
            ),
        )
        conn.commit()
    return {"parcel_id": parcel_id, "owner_id": owner_id}


def _seed_transfer(parcel_id: str, to_owner_id: str, *, status: str = "PENDING") -> str:
    tid = str(uuid.uuid4())
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO transfers (id, parcel_id, from_owner_id, to_owner_id, "
            " transfer_type, consideration, status, signed_payload, initiated_at, "
            " completed_at, district_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                tid,
                parcel_id,
                None,
                to_owner_id,
                "SALE",
                1_000_000.0,
                status,
                json.dumps({"x": 1}),
                now,
                now if status == "COMPLETED" else None,
                3,
            ),
        )
        conn.commit()
    return tid


def test_existing_block_score_blocks_approval():
    seed = _seed_parcel()
    tid = _seed_transfer(seed["parcel_id"], seed["owner_id"])
    persist_score(
        subject_type="TRANSFER",
        subject_id=tid,
        score=FraudScore(risk_score=90, recommended_action="BLOCK", signals=[], ml_score=0.8),
    )
    resp = TestClient(create_app()).post(
        f"/api/v1/transfers/{tid}/approve", headers=_OFFICER
    )
    assert resp.status_code == 409, resp.text
    with get_connection() as conn:
        status = conn.execute(
            "SELECT status FROM parcels WHERE parcel_id=?", (seed["parcel_id"],)
        ).fetchone()[0]
    assert status == "ACTIVE"


def test_unscored_clean_transfer_is_scored_then_approved():
    seed = _seed_parcel(kyc="VERIFIED")
    tid = _seed_transfer(seed["parcel_id"], seed["owner_id"])
    assert latest_score("TRANSFER", tid) is None  # not scored yet
    resp = TestClient(create_app()).post(
        f"/api/v1/transfers/{tid}/approve", headers=_OFFICER
    )
    assert resp.status_code == 200, resp.text
    # Fail-CLOSED: approval must have triggered synchronous scoring.
    assert latest_score("TRANSFER", tid) is not None


def test_unscored_fraudulent_transfer_is_blocked_synchronously():
    # Receiving owner KYC REJECTED (nira_kyc=25) + full geometry overlap (30)
    # + 6 completed transfers in 90d (rapid_retransfer=20) => rules>=75 => BLOCK,
    # with NO pre-existing score. The gate must score synchronously and 409.
    seed = _seed_parcel(kyc="REJECTED", geometry=_UNIT_SQUARE)
    _seed_parcel(geometry=_UNIT_SQUARE)  # overlapping ACTIVE parcel, same district
    for _ in range(6):
        _seed_transfer(seed["parcel_id"], seed["owner_id"], status="COMPLETED")
    tid = _seed_transfer(seed["parcel_id"], seed["owner_id"])
    assert latest_score("TRANSFER", tid) is None
    resp = TestClient(create_app()).post(
        f"/api/v1/transfers/{tid}/approve", headers=_OFFICER
    )
    assert resp.status_code == 409, resp.text
    score = latest_score("TRANSFER", tid)
    assert score is not None and score["recommended_action"] == "BLOCK"
