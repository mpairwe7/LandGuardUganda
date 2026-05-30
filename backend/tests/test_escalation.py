"""Escalation never freezes (G2).

An overdue PENDING_REVIEW BLOCK is escalated to a supervising officer
(``escalated_at`` stamped) but the parcel stays ACTIVE and the entry stays
human-reviewable — a human is still the only thing that can FREEZE.
"""

from __future__ import annotations

import json
import time
import uuid

from app.database import get_connection
from app.jobs.escalation import ESCALATION_THRESHOLD_SECONDS, escalate_pending

_UNIT_SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]}


def _seed_overdue_block_review() -> dict:
    now = time.time()
    parcel_id = f"UG-MIT-{uuid.uuid4().hex[:6]}/2026"
    owner_id = str(uuid.uuid4())
    review_id = str(uuid.uuid4())
    subject_id = str(uuid.uuid4())
    created = now - ESCALATION_THRESHOLD_SECONDS - 3600  # 25h+ old
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO districts (id,name,region,created_at) "
            "VALUES (3,'Mityana','Central',?)",
            (now,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO owners (id, nin_hash, full_name, kyc_status, "
            " created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (owner_id, uuid.uuid4().hex * 2, "Test", "VERIFIED", now, now),
        )
        conn.execute(
            "INSERT OR REPLACE INTO parcels (parcel_id, tenure_type, district_id, "
            " sub_county, geometry_geojson, area_hectares, current_owner_id, status, "
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (parcel_id, "MAILO", 3, "TC", json.dumps(_UNIT_SQUARE), 1.0, owner_id, "ACTIVE", now, now),
        )
        conn.execute(
            "INSERT INTO transfers (id, parcel_id, from_owner_id, to_owner_id, "
            " transfer_type, status, signed_payload, initiated_at, district_id) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (subject_id, parcel_id, None, owner_id, "SALE", "PENDING", json.dumps({"x": 1}), now, 3),
        )
        conn.execute(
            "INSERT INTO fraud_review_queue (id, subject_type, subject_id, district_id, "
            " risk_score, recommended_action, signals, scorer_version, state, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (review_id, "TRANSFER", subject_id, 3, 90, "BLOCK", "[]", "test", "PENDING_REVIEW", created),
        )
        conn.commit()
    return {"parcel_id": parcel_id, "review_id": review_id}


def test_escalation_does_not_freeze():
    seed = _seed_overdue_block_review()
    assert escalate_pending() == 1
    with get_connection() as conn:
        parcel_status = conn.execute(
            "SELECT status FROM parcels WHERE parcel_id=?", (seed["parcel_id"],)
        ).fetchone()[0]
        review = conn.execute(
            "SELECT state, escalated_at FROM fraud_review_queue WHERE id=?", (seed["review_id"],)
        ).fetchone()
        dispute_count = conn.execute(
            "SELECT COUNT(*) FROM disputes WHERE parcel_id=?", (seed["parcel_id"],)
        ).fetchone()[0]
    assert parcel_status == "ACTIVE", "escalation must NEVER freeze"
    assert review[0] == "PENDING_REVIEW", "entry stays human-reviewable"
    assert review[1] is not None, "escalated_at must be stamped"
    assert dispute_count == 0, "no auto-filed FRAUD dispute on escalation"


def test_escalation_is_idempotent():
    _seed_overdue_block_review()
    assert escalate_pending() == 1
    assert escalate_pending() == 0  # already escalated → not re-escalated
