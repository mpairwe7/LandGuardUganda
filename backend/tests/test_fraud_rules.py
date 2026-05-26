"""Fraud rule signal tests."""

from __future__ import annotations

import json
import time
import uuid

from app.database import get_connection
from app.fraud.rules import (
    rule_geometry_overlap,
    rule_nira_kyc,
    rule_size_anomaly,
    rule_watchlist_name,
)


def _seed_parcel(parcel_id: str, district_id: int, geom: dict, area: float) -> None:
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO districts (id, name, region, created_at) "
            "VALUES (?,?,?,?)",
            (district_id, "TestDistrict", "Central", now),
        )
        conn.execute(
            "INSERT OR REPLACE INTO parcels (parcel_id, tenure_type, district_id, "
            " sub_county, geometry_geojson, area_hectares, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (parcel_id, "MAILO", district_id, "Test", json.dumps(geom), area, "ACTIVE", now, now),
        )
        conn.commit()


def test_geometry_overlap_fires():
    poly_a = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [0, 0.001], [0.001, 0.001], [0.001, 0], [0, 0]]],
    }
    poly_b = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [0, 0.001], [0.001, 0.001], [0.001, 0], [0, 0]]],
    }
    _seed_parcel("UG-MIT-100001/2026", 3, poly_a, 0.01)
    _seed_parcel("UG-MIT-100002/2026", 3, poly_b, 0.01)
    signal = rule_geometry_overlap({"parcel_id": "UG-MIT-100001/2026"})
    assert signal.fired()
    assert "overlaps" in signal.explanation


def test_watchlist_name_fires_on_fuzzy_match():
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO fraud_watchlist (id, full_name, reason, added_by, added_at) "
            "VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), "Patrick Bwambale", "Test", "seed", now),
        )
        conn.commit()
    signal = rule_watchlist_name({"owner_full_name": "Bwambale Patrick"})
    assert signal.fired()


def test_nira_kyc_fires_on_pending():
    now = time.time()
    owner_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO owners (id, nin_hash, full_name, kyc_status, "
            " created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (owner_id, "h" * 64, "Test Person", "PENDING", now, now),
        )
        conn.commit()
    signal = rule_nira_kyc({"to_owner_id": owner_id})
    assert signal.fired()


def test_size_anomaly_quiet_for_small_district():
    # Insufficient norm population → never fires (safety default).
    signal = rule_size_anomaly({"parcel_id": "does-not-exist"})
    assert not signal.fired()
