#!/usr/bin/env python
"""Seed the showcase narrative: Mrs. Nakato, the fraudster, fraud watchlist.

Idempotent: re-running just refreshes the demo state without duplicating rows.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.audit import audit_emit  # noqa: E402
from app.audit.merkle import sha256_hex  # noqa: E402
from app.crypto import encrypt  # noqa: E402
from app.database import apply_migrations, get_connection  # noqa: E402
from app.util.ids import make_upi  # noqa: E402

# --- Identities ---
NAKATO_NIN = "CM82010110A4P0"
BWAMBALE_NIN = "CM82010110A4P9"  # the fraudster's forgery (NIRA returns no match)
OKELLO_NIN = "CM85030212B7Q1"
NAMATOVU_NIN = "CM91070514C9R2"
AUMA_NIN = "CM88110316D2S3"

# --- Mrs. Nakato's hero parcel ---
HERO_PARCEL = make_upi(district_id=3, parcel_number=24718, year=2026)

HERO_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [32.0419, 0.4017],
        [32.0432, 0.4017],
        [32.0432, 0.4028],
        [32.0419, 0.4028],
        [32.0419, 0.4017],
    ]],
}

WATCHLIST = [
    ("Patrick Bwambale", "Repeat broker — flagged in two prior land-fraud cases (2024)."),
    ("Henry Mwesigwa", "Identity-theft conviction 2023."),
    ("Mukasa Ssekitooleko", "Forged signature on three transfers, currently in court."),
]


def upsert_owner(conn, *, nin: str, full_name: str, dob: str, kyc: str) -> str:
    nin_hash = sha256_hex(nin)
    row = conn.execute(
        "SELECT id FROM owners WHERE nin_hash = ?", (nin_hash,)
    ).fetchone()
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


def main() -> None:
    apply_migrations()
    now = time.time()
    with get_connection() as conn:
        nakato_id = upsert_owner(
            conn,
            nin=NAKATO_NIN,
            full_name="Sarah Nakato",
            dob="1982-01-01",
            kyc="VERIFIED",
        )
        okello_id = upsert_owner(
            conn,
            nin=OKELLO_NIN,
            full_name="Joseph Okello",
            dob="1985-03-02",
            kyc="VERIFIED",
        )
        namatovu_id = upsert_owner(
            conn,
            nin=NAMATOVU_NIN,
            full_name="Aisha Namatovu",
            dob="1991-07-05",
            kyc="VERIFIED",
        )
        auma_id = upsert_owner(
            conn,
            nin=AUMA_NIN,
            full_name="Esther Auma",
            dob="1988-11-03",
            kyc="VERIFIED",
        )
        bwambale_id = upsert_owner(
            conn,
            nin=BWAMBALE_NIN,
            full_name="Patrick Bwambale",
            dob="1979-09-12",
            kyc="PENDING",
        )

        # Hero parcel — Mrs. Nakato's Mityana plot.
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
                    json.dumps(HERO_POLYGON),
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

        # Fraud watchlist seeding.
        for name, reason in WATCHLIST:
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

        # Staff users — for the demo role-switcher.
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

    # Emit a couple of seed audit events so the chain is non-empty on first run.
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

    print(
        f"seeded demo state: hero parcel {HERO_PARCEL} owned by Sarah Nakato; "
        "fraudster Patrick Bwambale (KYC PENDING); 3 watchlist names; 6 staff users."
    )


if __name__ == "__main__":
    main()
