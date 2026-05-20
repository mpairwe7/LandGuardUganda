"""Human-in-the-loop fraud review tests.

Verifies the ethical-AI invariant: a BLOCK score does NOT auto-freeze the
parcel. A human must affirm; a citizen can appeal; an auditor can overturn.
"""

from __future__ import annotations

import json
import time
import uuid

import pytest

from app.database import get_connection
from app.fraud.scorer import FraudScore, persist_score
from app.fraud.worker import _act_on_score


@pytest.fixture(autouse=True)
def _seed_minimal():
    now = time.time()
    transfer_id = str(uuid.uuid4())
    parcel_id = "UG-MIT-099001/2026"
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
            (owner_id, "h" * 64, "Test Person", "VERIFIED", now, now),
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
                json.dumps({"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]}),
                1.0,
                owner_id,
                "ACTIVE",
                now,
                now,
            ),
        )
        conn.execute(
            "INSERT INTO transfers "
            "(id, parcel_id, from_owner_id, to_owner_id, transfer_type, status, "
            " signed_payload, initiated_at, district_id) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                transfer_id,
                parcel_id,
                None,
                owner_id,
                "SALE",
                "PENDING",
                json.dumps({"x": 1}),
                now,
                3,
            ),
        )
        conn.commit()
    yield {"transfer_id": transfer_id, "parcel_id": parcel_id, "owner_id": owner_id}


def test_block_does_not_auto_freeze(_seed_minimal):
    fixture = _seed_minimal
    score = FraudScore(
        risk_score=90,
        recommended_action="BLOCK",
        signals=[],
        ml_score=0.8,
    )
    persist_score(subject_type="TRANSFER", subject_id=fixture["transfer_id"], score=score)
    _act_on_score("TRANSFER", fixture["transfer_id"], score.to_dict())

    # Parcel MUST still be ACTIVE — the ML cannot freeze without a human.
    with get_connection() as conn:
        row = conn.execute(
            "SELECT status FROM parcels WHERE parcel_id = ?",
            (fixture["parcel_id"],),
        ).fetchone()
        review = conn.execute(
            "SELECT state, recommended_action FROM fraud_review_queue "
            "WHERE subject_id = ?",
            (fixture["transfer_id"],),
        ).fetchone()
    assert row[0] == "ACTIVE", "ML scorer must never auto-freeze"
    assert review is not None, "review queue entry must exist"
    assert review[0] == "PENDING_REVIEW"
    assert review[1] == "BLOCK"


def test_flag_only_queues_for_review(_seed_minimal):
    fixture = _seed_minimal
    score = FraudScore(
        risk_score=55,
        recommended_action="FLAG",
        signals=[],
        ml_score=0.5,
    )
    persist_score(subject_type="TRANSFER", subject_id=fixture["transfer_id"], score=score)
    _act_on_score("TRANSFER", fixture["transfer_id"], score.to_dict())
    with get_connection() as conn:
        review = conn.execute(
            "SELECT state, recommended_action FROM fraud_review_queue "
            "WHERE subject_id = ?",
            (fixture["transfer_id"],),
        ).fetchone()
        parcel = conn.execute(
            "SELECT status FROM parcels WHERE parcel_id = ?",
            (fixture["parcel_id"],),
        ).fetchone()
    assert review is not None
    assert review[1] == "FLAG"
    assert parcel[0] == "ACTIVE"


def test_none_action_does_not_create_review(_seed_minimal):
    fixture = _seed_minimal
    score = FraudScore(
        risk_score=10,
        recommended_action="NONE",
        signals=[],
        ml_score=0.05,
    )
    persist_score(subject_type="TRANSFER", subject_id=fixture["transfer_id"], score=score)
    _act_on_score("TRANSFER", fixture["transfer_id"], score.to_dict())
    with get_connection() as conn:
        review = conn.execute(
            "SELECT COUNT(*) FROM fraud_review_queue WHERE subject_id = ?",
            (fixture["transfer_id"],),
        ).fetchone()
    assert review[0] == 0
