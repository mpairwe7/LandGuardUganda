"""DB seeding routines for non-production deploys.

`maybe_seed_on_startup(settings)` is called from `app.main.lifespan`. It is
a no-op when:
  - `APP_ENV == "production"`, or
  - the districts table already has rows (signal of an existing DB).

Each individual seed function is independently idempotent (INSERT OR IGNORE
on districts/parcels, owner-row existence checks, watchlist-row name
checks) so re-running them on a non-empty DB would be safe; the empty-DB
gate just avoids redundant work and the audit-event side-effects on every
pod restart.

The functions are also re-exported as CLI entry points in
`backend/scripts/seed_*.py` for manual operator-driven re-seeding.
"""

from __future__ import annotations

import json
import logging
import random
import time
import uuid
from typing import Any

from app.audit import audit_emit
from app.audit.merkle import sha256_hex
from app.config import Settings
from app.crypto import encrypt
from app.database import get_connection
from app.util.ids import make_upi

logger = logging.getLogger(__name__)


# ─── seed_districts ────────────────────────────────────────────────────────

DISTRICTS: list[tuple[int, str, str]] = [
    (1, "Kampala Central", "Central"),
    (2, "Wakiso", "Central"),
    (3, "Mityana", "Central"),
    (4, "Gulu", "Northern"),
]

_DISTRICT_CENTRES: dict[int, tuple[float, float]] = {
    1: (32.5825, 0.3476),
    2: (32.4660, 0.4044),
    3: (32.0419, 0.4017),
    4: (32.2898, 2.7747),
}

_SUB_COUNTIES: dict[int, list[str]] = {
    1: ["Central Division", "Kawempe", "Nakawa", "Makindye", "Lubaga"],
    2: ["Kira", "Nansana", "Wakiso TC", "Kakiri", "Entebbe"],
    3: ["Mityana TC", "Bulera", "Maanyi", "Sekanyonyi", "Kakindu"],
    4: ["Bardege", "Layibi", "Pece", "Laroo", "Awach"],
}

_PARCELS_PER_DISTRICT = 50


def _synth_polygon(district_id: int, parcel_num: int) -> dict[str, Any]:
    cx, cy = _DISTRICT_CENTRES[district_id]
    rng = random.Random((district_id * 7919) + parcel_num)
    dx = (rng.random() - 0.5) * 0.3
    dy = (rng.random() - 0.5) * 0.3
    centre_x = cx + dx
    centre_y = cy + dy
    delta = 0.00027 + rng.random() * 0.0006
    coords = [
        [centre_x - delta, centre_y - delta],
        [centre_x + delta, centre_y - delta],
        [centre_x + delta, centre_y + delta],
        [centre_x - delta, centre_y + delta],
        [centre_x - delta, centre_y - delta],
    ]
    return {"type": "Polygon", "coordinates": [coords]}


def seed_districts_and_parcels() -> dict[str, int]:
    """Seed the four pilot districts + a background population of parcels."""
    now = time.time()
    rng = random.Random(20260620)
    inserted_parcels = 0
    with get_connection() as conn:
        for did, name, region in DISTRICTS:
            conn.execute(
                "INSERT OR IGNORE INTO districts (id, name, region, created_at) "
                "VALUES (?,?,?,?)",
                (did, name, region, now),
            )
        for did, _, _ in DISTRICTS:
            for n in range(_PARCELS_PER_DISTRICT):
                parcel_num = 100 + n
                upi = make_upi(did, parcel_num)
                exists = conn.execute(
                    "SELECT 1 FROM parcels WHERE parcel_id = ?", (upi,)
                ).fetchone()
                if exists:
                    continue
                area_ha = round(rng.uniform(0.05, 4.0), 4)
                tenure = rng.choice(["MAILO", "FREEHOLD", "LEASEHOLD", "CUSTOMARY"])
                sub = rng.choice(_SUB_COUNTIES[did])
                conn.execute(
                    "INSERT INTO parcels (parcel_id, tenure_type, district_id, "
                    " sub_county, geometry_geojson, area_hectares, current_owner_id, status, "
                    " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        upi,
                        tenure,
                        did,
                        sub,
                        json.dumps(_synth_polygon(did, parcel_num)),
                        area_ha,
                        None,
                        "ACTIVE",
                        now,
                        now,
                    ),
                )
                inserted_parcels += 1
        conn.commit()
    return {
        "districts": len(DISTRICTS),
        "parcels_inserted": inserted_parcels,
    }


# ─── seed_demo ─────────────────────────────────────────────────────────────

NAKATO_NIN = "CM82010110A4P0"
BWAMBALE_NIN = "CM82010110A4P9"  # the fraudster's forged variant
OKELLO_NIN = "CM85030212B7Q1"
NAMATOVU_NIN = "CM91070514C9R2"
AUMA_NIN = "CM88110316D2S3"

HERO_PARCEL = make_upi(district_id=3, parcel_number=24718, year=2026)

_HERO_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [32.0419, 0.4017],
            [32.0432, 0.4017],
            [32.0432, 0.4028],
            [32.0419, 0.4028],
            [32.0419, 0.4017],
        ]
    ],
}

_WATCHLIST = [
    ("Patrick Bwambale", "Repeat broker — flagged in two prior land-fraud cases (2024)."),
    ("Henry Mwesigwa", "Identity-theft conviction 2023."),
    ("Mukasa Ssekitooleko", "Forged signature on three transfers, currently in court."),
]


def _upsert_owner(conn, *, nin: str, full_name: str, dob: str, kyc: str) -> str:
    nin_hash = sha256_hex(nin)
    row = conn.execute("SELECT id FROM owners WHERE nin_hash = ?", (nin_hash,)).fetchone()
    if row:
        return str(row[0])
    owner_id = str(uuid.uuid4())
    now = time.time()
    conn.execute(
        "INSERT INTO owners (id, nin_hash, nin_encrypted, full_name, dob, kyc_status, "
        " kyc_verified_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            owner_id,
            nin_hash,
            encrypt(nin),
            full_name,
            dob,
            kyc,
            now if kyc == "VERIFIED" else None,
            now,
            now,
        ),
    )
    return owner_id


def seed_demo_state() -> dict[str, Any]:
    """Seed the showcase narrative: Mrs. Nakato, the fraudster, watchlist, staff."""
    now = time.time()
    with get_connection() as conn:
        nakato_id = _upsert_owner(
            conn, nin=NAKATO_NIN, full_name="Sarah Nakato", dob="1982-01-01", kyc="VERIFIED"
        )
        _upsert_owner(
            conn, nin=OKELLO_NIN, full_name="Joseph Okello", dob="1985-03-02", kyc="VERIFIED"
        )
        _upsert_owner(
            conn, nin=NAMATOVU_NIN, full_name="Aisha Namatovu", dob="1991-07-05", kyc="VERIFIED"
        )
        _upsert_owner(
            conn, nin=AUMA_NIN, full_name="Esther Auma", dob="1988-11-03", kyc="VERIFIED"
        )
        _upsert_owner(
            conn, nin=BWAMBALE_NIN, full_name="Patrick Bwambale", dob="1979-09-12", kyc="PENDING"
        )

        exists = conn.execute(
            "SELECT 1 FROM parcels WHERE parcel_id = ?", (HERO_PARCEL,)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO parcels (parcel_id, tenure_type, district_id, "
                " sub_county, geometry_geojson, area_hectares, current_owner_id, status, "
                " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    HERO_PARCEL,
                    "MAILO",
                    3,
                    "Mityana TC",
                    json.dumps(_HERO_POLYGON),
                    1.4500,
                    nakato_id,
                    "ACTIVE",
                    now,
                    now,
                ),
            )
        else:
            conn.execute(
                "UPDATE parcels SET current_owner_id = ?, status = 'ACTIVE', updated_at = ? "
                "WHERE parcel_id = ?",
                (nakato_id, now, HERO_PARCEL),
            )

        for name, reason in _WATCHLIST:
            row = conn.execute(
                "SELECT id FROM fraud_watchlist WHERE full_name = ?", (name,)
            ).fetchone()
            if row:
                continue
            conn.execute(
                "INSERT INTO fraud_watchlist (id, full_name, reason, added_by, added_at) "
                "VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), name, reason, "seed_demo", now),
            )

        staff = [
            ("demo-surveyor", 3, "SURVEYOR", "Surveyor Otim"),
            ("demo-officer", 3, "LAND_OFFICER", "Officer Apio"),
            ("demo-registrar", 3, "REGISTRAR", "Registrar Kasozi"),
            ("demo-auditor", None, "AUDITOR", "Auditor Mubiru"),
            ("demo-admin", None, "ADMIN", "Admin Owor"),
            ("demo-citizen", None, "CITIZEN", "Sarah Nakato"),
        ]
        for ext, did, role, fname in staff:
            row = conn.execute(
                "SELECT id FROM staff_users WHERE external_id = ?", (ext,)
            ).fetchone()
            if row:
                continue
            conn.execute(
                "INSERT INTO staff_users (id, external_id, district_id, role, email, "
                " full_name, created_at, last_seen_at) VALUES (?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), ext, did, role, f"{ext}@landguard.ug", fname, now, now),
            )
        conn.commit()

    # Two opening audit events so the chain is non-empty on first run.
    audit_emit(
        event_type="PARCEL_REGISTERED",
        payload={
            "parcel_id": HERO_PARCEL,
            "tenure_type": "MAILO",
            "owner_id": nakato_id,
            "sub_county": "Mityana TC",
        },
        district_id=3,
        actor_user_id="seed:demo",
    )
    audit_emit(
        event_type="KYC_VERIFIED",
        payload={"owner_id": nakato_id, "matched": True, "source": "MOCK"},
        district_id=3,
        actor_user_id="seed:demo",
    )
    return {
        "hero_parcel": HERO_PARCEL,
        "watchlist": len(_WATCHLIST),
        "staff": 6,
    }


# ─── DB-empty check + lifespan entry point ─────────────────────────────────


def is_db_empty() -> bool:
    """True when the districts table has zero rows.

    Used as the gate for on-startup seeding — districts are the parent
    of nearly every domain row, so this is a reliable proxy for "the DB
    has never been seeded."
    """
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM districts").fetchone()
        return int(row[0]) == 0


def maybe_seed_on_startup(settings: Settings) -> bool:
    """Idempotent demo-seed for non-production deploys.

    Returns True if seeding ran. Skips when APP_ENV is production or
    when the DB already has districts (i.e. a prior pod already seeded).
    """
    if settings.app_env == "production":
        logger.info("seed_on_startup_skipped reason=production_env")
        return False
    if not is_db_empty():
        logger.info("seed_on_startup_skipped reason=db_not_empty")
        return False
    logger.info("seed_on_startup_begin app_env=%s", settings.app_env)
    d = seed_districts_and_parcels()
    s = seed_demo_state()
    logger.info(
        "seed_on_startup_done districts=%d parcels=%d hero=%s",
        d["districts"],
        d["parcels_inserted"],
        s["hero_parcel"],
    )
    return True
