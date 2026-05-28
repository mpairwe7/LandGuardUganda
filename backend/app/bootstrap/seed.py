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


# ─── seed_demo_extras — richer narrative data ──────────────────────────────


def _sha256_short(s: str) -> str:
    return sha256_hex(s)[:64]


def seed_demo_extras() -> dict[str, int]:
    """Issue a handful of titles, a completed transfer, and pending fraud
    reviews so the public anchor timeline and the officer review queue
    have visible state on a fresh deploy.

    Idempotent: every insert is guarded by an existence check (titles by
    title_no, transfers by signed_payload digest, reviews by subject_id).
    """
    now = time.time()
    issued_titles = 0
    issued_transfers = 0
    queued_reviews = 0

    with get_connection() as conn:
        # Resolve seed owners by hash (already inserted by seed_demo_state)
        def _owner_id(nin: str) -> str | None:
            row = conn.execute(
                "SELECT id FROM owners WHERE nin_hash = ?", (sha256_hex(nin),)
            ).fetchone()
            return str(row[0]) if row else None

        nakato_id = _owner_id(NAKATO_NIN)
        okello_id = _owner_id(OKELLO_NIN)
        namatovu_id = _owner_id(NAMATOVU_NIN)
        auma_id = _owner_id(AUMA_NIN)
        bwambale_id = _owner_id(BWAMBALE_NIN)

        # Pick a few existing Mityana background parcels (district 3) and
        # tie them to demo owners so the title-issue flow has variety.
        background = conn.execute(
            "SELECT parcel_id FROM parcels WHERE district_id = 3 "
            "AND parcel_id != ? ORDER BY parcel_id LIMIT 6",
            (HERO_PARCEL,),
        ).fetchall()
        background_ids = [r[0] for r in background]

        # Title for the hero parcel + a few others.
        title_plan: list[tuple[str, str | None, str]] = [
            (HERO_PARCEL, nakato_id, "demo-registrar"),
        ]
        if len(background_ids) >= 3 and okello_id and namatovu_id and auma_id:
            title_plan += [
                (background_ids[0], okello_id, "demo-registrar"),
                (background_ids[1], namatovu_id, "demo-registrar"),
                (background_ids[2], auma_id, "demo-registrar"),
            ]

        for idx, (parcel_id, owner_id, registrar_id) in enumerate(title_plan):
            if owner_id is None:
                continue
            title_no = f"MITYANA/V1/{20260000 + idx + 1}"
            exists = conn.execute(
                "SELECT 1 FROM titles WHERE title_no = ?", (title_no,)
            ).fetchone()
            if exists:
                continue
            # Stamp owner on the parcel and write the title.
            conn.execute(
                "UPDATE parcels SET current_owner_id = ?, status = 'ACTIVE', updated_at = ? "
                "WHERE parcel_id = ?",
                (owner_id, now, parcel_id),
            )
            content_hash = sha256_hex(
                json.dumps(
                    {
                        "title_no": title_no,
                        "parcel_id": parcel_id,
                        "owner_id": owner_id,
                        "issued_at": now,
                    },
                    sort_keys=True,
                )
            )
            conn.execute(
                "INSERT INTO titles (title_no, parcel_id, issued_at, registrar_id, "
                " district_id, content_hash) VALUES (?,?,?,?,?,?)",
                (title_no, parcel_id, now, registrar_id, 3, content_hash),
            )
            issued_titles += 1

        # One completed sale: Okello → Namatovu of background_ids[0].
        if (
            okello_id
            and namatovu_id
            and background_ids
            and conn.execute(
                "SELECT 1 FROM transfers WHERE parcel_id = ? AND status = 'COMPLETED'",
                (background_ids[0],),
            ).fetchone()
            is None
        ):
            transfer_id = str(uuid.uuid4())
            signed = json.dumps(
                {
                    "parcel_id": background_ids[0],
                    "from": okello_id,
                    "to": namatovu_id,
                    "consideration_ugx": 14_500_000,
                    "transfer_type": "SALE",
                },
                sort_keys=True,
            )
            conn.execute(
                "INSERT INTO transfers (id, parcel_id, from_owner_id, to_owner_id, "
                " transfer_type, consideration, status, signed_payload, initiated_at, "
                " completed_at, district_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    transfer_id,
                    background_ids[0],
                    okello_id,
                    namatovu_id,
                    "SALE",
                    14_500_000.0,
                    "COMPLETED",
                    signed,
                    now - 86400,
                    now,
                    3,
                ),
            )
            conn.execute(
                "UPDATE parcels SET current_owner_id = ?, updated_at = ? WHERE parcel_id = ?",
                (namatovu_id, now, background_ids[0]),
            )
            issued_transfers += 1

        # Pending fraud reviews — three plausible signals an Officer
        # would adjudicate. Subject IDs are stable so re-runs are no-ops.
        #
        # Signal shape MUST match app.models.fraud.FraudSignalResponse
        # ({name, weight, score, explanation}) — the runtime API serialises
        # the queue via that model, so any drift here turns
        # ``GET /api/v1/fraud/reviews`` into a 500 (pydantic validation
        # error) which silently breaks the Officer console review queue.
        review_plan = [
            {
                "id": "review-watchlist-bwambale",
                "subject_type": "owner",
                "subject_id": bwambale_id or "bwambale-pending",
                "risk_score": 92,
                "recommended_action": "BLOCK",
                "signals": [
                    {"name": "watchlist_name", "weight": 20, "score": 1.0,
                     "explanation": "Owner name matches watchlist entry 'Patrick Bwambale' at 97% similarity"},
                    {"name": "nira_kyc", "weight": 25, "score": 0.88,
                     "explanation": "NIRA returned no match for the supplied NIN"},
                ],
            },
            {
                "id": "review-rapid-resale",
                "subject_type": "transfer",
                "subject_id": "transfer-rapid-resale-demo",
                "risk_score": 71,
                "recommended_action": "FLAG",
                "signals": [
                    {"name": "rapid_retransfer", "weight": 20, "score": 0.9,
                     "explanation": "Resale 9 days after acquisition"},
                    {"name": "consideration_anomaly", "weight": 15, "score": 0.58,
                     "explanation": "0.42x median Mityana Town Council parcel price"},
                ],
            },
            {
                "id": "review-duplicate-nin",
                "subject_type": "owner",
                "subject_id": "owner-duplicate-nin-demo",
                "risk_score": 64,
                "recommended_action": "FLAG",
                "signals": [
                    {"name": "nin_reuse", "weight": 15, "score": 1.0,
                     "explanation": "Two parcels filed under the same NIN within 24 h"},
                    {"name": "geometry_overlap", "weight": 30, "score": 0.4,
                     "explanation": "Filings from Mityana + Gulu within a 24-hour window"},
                ],
            },
        ]
        for r in review_plan:
            exists = conn.execute(
                "SELECT 1 FROM fraud_review_queue WHERE id = ?", (r["id"],)
            ).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO fraud_review_queue (id, subject_type, subject_id, district_id, "
                " risk_score, recommended_action, signals, scorer_version, state, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    r["id"],
                    r["subject_type"],
                    r["subject_id"],
                    3,
                    r["risk_score"],
                    r["recommended_action"],
                    json.dumps(r["signals"]),
                    "isolation-forest-v1+rules-v1",
                    "PENDING_REVIEW",
                    now,
                ),
            )
            queued_reviews += 1

        conn.commit()

    # Audit events for everything we created — these will be picked up
    # by the anchor loop and produce multiple anchor batches so the
    # public timeline isn't a single row.
    #
    # Payload MUST include title_no — the public verifier (verify.py) and
    # the title-proof endpoint (anchors.py) match anchored audit events by
    # ``payload_json LIKE '%"title_no": "<no>"%'``. Without it, every
    # seeded title shows verified=false / reason=title_pending_anchor even
    # after its batch is anchored.
    for idx, (parcel_id, owner_id, registrar_id) in enumerate(title_plan):
        if owner_id is None:
            continue
        title_no = f"MITYANA/V1/{20260000 + idx + 1}"
        audit_emit(
            event_type="TITLE_ISSUED",
            payload={
                "title_no": title_no,
                "parcel_id": parcel_id,
                "owner_id": owner_id,
                "registrar_id": registrar_id,
            },
            district_id=3,
            actor_user_id="seed:demo",
        )
    if issued_transfers and okello_id and namatovu_id and background_ids:
        audit_emit(
            event_type="TRANSFER_COMPLETED",
            payload={
                "parcel_id": background_ids[0],
                "from_owner_id": okello_id,
                "to_owner_id": namatovu_id,
                "transfer_type": "SALE",
            },
            district_id=3,
            actor_user_id="seed:demo",
        )

    return {
        "titles": issued_titles,
        "transfers": issued_transfers,
        "fraud_reviews": queued_reviews,
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
    x = seed_demo_extras()
    logger.info(
        "seed_on_startup_done districts=%d parcels=%d hero=%s titles=%d transfers=%d reviews=%d",
        d["districts"],
        d["parcels_inserted"],
        s["hero_parcel"],
        x["titles"],
        x["transfers"],
        x["fraud_reviews"],
    )
    return True
