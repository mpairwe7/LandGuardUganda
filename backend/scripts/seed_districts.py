#!/usr/bin/env python
"""Seed the four Ugandan districts used by the demo + 200 random parcels.

Run with: uv run python scripts/seed_districts.py
"""

from __future__ import annotations

import json
import random
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import apply_migrations, get_connection  # noqa: E402
from app.util.ids import make_upi  # noqa: E402

DISTRICTS = [
    (1, "Kampala Central", "Central"),
    (2, "Wakiso", "Central"),
    (3, "Mityana", "Central"),
    (4, "Gulu", "Northern"),
]

DISTRICT_CENTRES = {
    1: (32.5825, 0.3476),   # Kampala
    2: (32.4660, 0.4044),   # Wakiso
    3: (32.0419, 0.4017),   # Mityana
    4: (32.2898, 2.7747),   # Gulu
}

SUB_COUNTIES = {
    1: ["Central Division", "Kawempe", "Nakawa", "Makindye", "Lubaga"],
    2: ["Kira", "Nansana", "Wakiso TC", "Kakiri", "Entebbe"],
    3: ["Mityana TC", "Bulera", "Maanyi", "Sekanyonyi", "Kakindu"],
    4: ["Bardege", "Layibi", "Pece", "Laroo", "Awach"],
}


def synth_polygon(district_id: int, parcel_num: int) -> dict:
    cx, cy = DISTRICT_CENTRES[district_id]
    rng = random.Random((district_id * 7919) + parcel_num)
    dx = (rng.random() - 0.5) * 0.3
    dy = (rng.random() - 0.5) * 0.3
    centre_x = cx + dx
    centre_y = cy + dy
    # ~30 m × 30 m parcel
    delta = 0.00027 + rng.random() * 0.0006
    coords = [
        [centre_x - delta, centre_y - delta],
        [centre_x + delta, centre_y - delta],
        [centre_x + delta, centre_y + delta],
        [centre_x - delta, centre_y + delta],
        [centre_x - delta, centre_y - delta],
    ]
    return {"type": "Polygon", "coordinates": [coords]}


def main() -> None:
    apply_migrations()
    now = time.time()
    rng = random.Random(20260620)
    with get_connection() as conn:
        for did, name, region in DISTRICTS:
            conn.execute(
                "INSERT OR IGNORE INTO districts (id, name, region, created_at) "
                "VALUES (?,?,?,?)",
                (did, name, region, now),
            )
        # Insert a background population of parcels for fraud-detection norms.
        for did, _, _ in DISTRICTS:
            for n in range(50):
                parcel_num = 100 + n
                upi = make_upi(did, parcel_num)
                exists = conn.execute(
                    "SELECT 1 FROM parcels WHERE parcel_id = ?", (upi,)
                ).fetchone()
                if exists:
                    continue
                area_ha = round(rng.uniform(0.05, 4.0), 4)
                tenure = rng.choice(["MAILO", "FREEHOLD", "LEASEHOLD", "CUSTOMARY"])
                sub = rng.choice(SUB_COUNTIES[did])
                conn.execute(
                    "INSERT INTO parcels (parcel_id, tenure_type, district_id, "
                    " sub_county, geometry_geojson, area_hectares, current_owner_id, status, "
                    " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        upi,
                        tenure,
                        did,
                        sub,
                        json.dumps(synth_polygon(did, parcel_num)),
                        area_ha,
                        None,
                        "ACTIVE",
                        now,
                        now,
                    ),
                )
        conn.commit()
    print(
        f"seeded {len(DISTRICTS)} districts and {len(DISTRICTS)*50} background parcels"
    )


if __name__ == "__main__":
    main()
