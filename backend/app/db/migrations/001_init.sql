-- LandGuard Uganda — initial schema (backend-agnostic).
-- Postgres-flavoured but compatible with SQLite via the dispatcher.
-- IF NOT EXISTS discipline so this migration is idempotent.

CREATE TABLE IF NOT EXISTS districts (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    region      TEXT NOT NULL,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS owners (
    id                TEXT PRIMARY KEY,
    nin_hash          TEXT NOT NULL UNIQUE,
    nin_encrypted     BLOB,
    full_name         TEXT NOT NULL,
    dob               TEXT,
    phone             TEXT,
    kyc_status        TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (kyc_status IN ('PENDING','VERIFIED','REJECTED','EXPIRED')),
    kyc_verified_at   REAL,
    biometric_hash    TEXT,
    created_at        REAL NOT NULL,
    updated_at        REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_owners_nin_hash ON owners(nin_hash);
CREATE INDEX IF NOT EXISTS idx_owners_kyc      ON owners(kyc_status, kyc_verified_at);

CREATE TABLE IF NOT EXISTS parcels (
    parcel_id          TEXT PRIMARY KEY,
    tenure_type        TEXT NOT NULL
        CHECK (tenure_type IN ('MAILO','FREEHOLD','LEASEHOLD','CUSTOMARY')),
    district_id        INTEGER NOT NULL REFERENCES districts(id),
    sub_county         TEXT NOT NULL,
    geometry_geojson   TEXT NOT NULL,
    area_hectares      REAL NOT NULL,
    current_owner_id   TEXT REFERENCES owners(id),
    status             TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE','DISPUTED','FROZEN','TRANSFERRED')),
    created_at         REAL NOT NULL,
    updated_at         REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_parcels_district ON parcels(district_id, status);
CREATE INDEX IF NOT EXISTS idx_parcels_owner    ON parcels(current_owner_id);

CREATE TABLE IF NOT EXISTS titles (
    title_no         TEXT PRIMARY KEY,
    parcel_id        TEXT NOT NULL REFERENCES parcels(parcel_id),
    issued_at        REAL NOT NULL,
    registrar_id     TEXT NOT NULL,
    district_id      INTEGER NOT NULL,
    content_hash     TEXT NOT NULL,
    merkle_proof     TEXT,
    revoked_at       REAL,
    revoke_reason    TEXT
);
CREATE INDEX IF NOT EXISTS idx_titles_parcel   ON titles(parcel_id);
CREATE INDEX IF NOT EXISTS idx_titles_district ON titles(district_id, issued_at);

CREATE TABLE IF NOT EXISTS transfers (
    id              TEXT PRIMARY KEY,
    parcel_id       TEXT NOT NULL REFERENCES parcels(parcel_id),
    from_owner_id   TEXT REFERENCES owners(id),
    to_owner_id     TEXT NOT NULL REFERENCES owners(id),
    transfer_type   TEXT NOT NULL
        CHECK (transfer_type IN ('SALE','GIFT','INHERITANCE','COURT_ORDER','SUBDIVISION')),
    consideration   REAL,
    status          TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING','APPROVED','REJECTED','COMPLETED','REVERSED')),
    signed_payload  TEXT NOT NULL,
    initiated_at    REAL NOT NULL,
    completed_at    REAL,
    district_id     INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transfers_parcel ON transfers(parcel_id, completed_at);
CREATE INDEX IF NOT EXISTS idx_transfers_owner  ON transfers(to_owner_id);
CREATE INDEX IF NOT EXISTS idx_transfers_status ON transfers(district_id, status);

CREATE TABLE IF NOT EXISTS disputes (
    id              TEXT PRIMARY KEY,
    parcel_id       TEXT NOT NULL REFERENCES parcels(parcel_id),
    claimant_id     TEXT NOT NULL REFERENCES owners(id),
    respondent_id   TEXT REFERENCES owners(id),
    dispute_type    TEXT NOT NULL
        CHECK (dispute_type IN ('OVERLAP','OWNERSHIP','BOUNDARY','FRAUD','ENCROACHMENT')),
    state           TEXT NOT NULL DEFAULT 'FILED'
        CHECK (state IN ('FILED','UNDER_REVIEW','MEDIATION','RESOLVED','DISMISSED','ESCALATED_COURT')),
    evidence        TEXT,
    resolution      TEXT,
    district_id     INTEGER NOT NULL,
    filed_at        REAL NOT NULL,
    resolved_at     REAL
);
CREATE INDEX IF NOT EXISTS idx_disputes_parcel ON disputes(parcel_id);
CREATE INDEX IF NOT EXISTS idx_disputes_state  ON disputes(district_id, state);

CREATE TABLE IF NOT EXISTS anchors (
    batch_id         TEXT PRIMARY KEY,
    district_id      INTEGER NOT NULL REFERENCES districts(id),
    root_hash        TEXT NOT NULL,
    first_seq        INTEGER NOT NULL,
    last_seq         INTEGER NOT NULL,
    leaf_count       INTEGER NOT NULL,
    tx_hash          TEXT,
    block_number     INTEGER,
    anchored_at      REAL NOT NULL,
    confirmed_at     REAL,
    status           TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING','SUBMITTED','CONFIRMED','FAILED','REVERTED'))
);
CREATE INDEX IF NOT EXISTS idx_anchors_district ON anchors(district_id, anchored_at);
CREATE INDEX IF NOT EXISTS idx_anchors_status   ON anchors(status, anchored_at);

CREATE TABLE IF NOT EXISTS nira_verifications (
    nin_hash    TEXT PRIMARY KEY,
    verified_at REAL NOT NULL,
    expires_at  REAL NOT NULL,
    result      TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'MOCK'
);
CREATE INDEX IF NOT EXISTS idx_nira_expiry ON nira_verifications(expires_at);

CREATE TABLE IF NOT EXISTS staff_users (
    id            TEXT PRIMARY KEY,
    external_id   TEXT NOT NULL,
    district_id   INTEGER REFERENCES districts(id),
    role          TEXT NOT NULL
        CHECK (role IN ('CITIZEN','SURVEYOR','LAND_OFFICER','REGISTRAR','AUDITOR','PUBLIC_VERIFIER','ADMIN')),
    email         TEXT,
    full_name     TEXT,
    created_at    REAL NOT NULL,
    last_seen_at  REAL NOT NULL,
    UNIQUE (district_id, external_id)
);

CREATE TABLE IF NOT EXISTS fraud_scores (
    id                 TEXT PRIMARY KEY,
    subject_type       TEXT NOT NULL
        CHECK (subject_type IN ('TRANSFER','TITLE','OWNER','PARCEL')),
    subject_id         TEXT NOT NULL,
    risk_score         INTEGER NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    signals            TEXT NOT NULL,
    recommended_action TEXT NOT NULL CHECK (recommended_action IN ('NONE','FLAG','BLOCK')),
    scored_at          REAL NOT NULL,
    scorer_version     TEXT NOT NULL,
    UNIQUE (subject_type, subject_id, scorer_version)
);
CREATE INDEX IF NOT EXISTS idx_fraud_subject ON fraud_scores(subject_type, subject_id, scored_at);

CREATE TABLE IF NOT EXISTS fraud_watchlist (
    id          TEXT PRIMARY KEY,
    full_name   TEXT NOT NULL,
    reason      TEXT NOT NULL,
    added_by    TEXT NOT NULL,
    added_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_watchlist_name ON fraud_watchlist(full_name);
