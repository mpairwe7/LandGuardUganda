"""district_norm_z is computed at inference (G5), not a constant 0.0.

Previously the 7th feature was hardcoded to 0.0 at serving time while training
drew it from a real distribution — train/serve skew. These tests assert the
feature now responds to the input.
"""

from __future__ import annotations

import json
import time
import uuid

from app.database import get_connection
from app.fraud.features import FEATURE_NAMES, assemble_features

_NORM_Z_IDX = FEATURE_NAMES.index("district_norm_z")
_SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]}


def _seed_district_with_varied_prices(district_id: int = 7, n: int = 8) -> None:
    """Seed n transfers whose consideration-per-hectare varies, so the district
    has a non-degenerate (stdev > 0) price distribution."""
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO districts (id,name,region,created_at) VALUES (?,?,?,?)",
            (district_id, "D", "R", now),
        )
        owner_id = str(uuid.uuid4())
        conn.execute(
            "INSERT OR REPLACE INTO owners (id,nin_hash,full_name,kyc_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (owner_id, uuid.uuid4().hex * 2, "O", "VERIFIED", now, now),
        )
        for i in range(n):
            pid = f"UG-D{district_id}-{uuid.uuid4().hex[:6]}/2026"
            conn.execute(
                "INSERT OR REPLACE INTO parcels (parcel_id,tenure_type,district_id,sub_county,"
                " geometry_geojson,area_hectares,current_owner_id,status,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (pid, "MAILO", district_id, "TC", json.dumps(_SQUARE), 1.0, owner_id, "ACTIVE", now, now),
            )
            # area = 1.0, so consideration == consideration-per-hectare; vary it.
            consideration = 1_000_000.0 * (1.0 + i * 0.2)
            conn.execute(
                "INSERT INTO transfers (id,parcel_id,from_owner_id,to_owner_id,transfer_type,"
                " consideration,status,signed_payload,initiated_at,district_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), pid, None, owner_id, "SALE", consideration, "PENDING",
                 json.dumps({}), now, district_id),
            )
        conn.commit()


def test_district_norm_z_responds_to_price():
    _seed_district_with_varied_prices()  # mean cph ≈ 1.7e6
    near_mean = assemble_features(
        {"district_id": 7, "consideration": 1_700_000.0, "area_hectares": 1.0}
    )
    extreme = assemble_features(
        {"district_id": 7, "consideration": 1_000_000_000.0, "area_hectares": 1.0}
    )
    assert abs(extreme[_NORM_Z_IDX]) > 1.0, "extreme price must move district_norm_z off zero"
    assert abs(near_mean[_NORM_Z_IDX]) < abs(extreme[_NORM_Z_IDX])


def test_district_norm_z_zero_without_enough_data():
    # Unknown district with no transfers => insufficient norm => baseline 0.0.
    vec = assemble_features(
        {"district_id": 9999, "consideration": 5_000_000.0, "area_hectares": 1.0}
    )
    assert vec[_NORM_Z_IDX] == 0.0
