-- Migration 002: human-in-the-loop fraud review queue + appeal records.
--
-- The fraud scorer no longer auto-FREEZES on BLOCK. Instead it writes a
-- review-queue entry; a Land Officer must affirm or dismiss within 24h.
-- After 24h with no action a scheduled job applies the recommended action,
-- but emits a separate audit event citing "automated escalation" so the
-- timeline shows clearly what happened.

CREATE TABLE IF NOT EXISTS fraud_review_queue (
    id              TEXT PRIMARY KEY,
    subject_type    TEXT NOT NULL,
    subject_id      TEXT NOT NULL,
    district_id     INTEGER NOT NULL,
    risk_score      INTEGER NOT NULL,
    recommended_action TEXT NOT NULL CHECK (recommended_action IN ('FLAG','BLOCK')),
    signals         TEXT NOT NULL,
    scorer_version  TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'PENDING_REVIEW'
        CHECK (state IN ('PENDING_REVIEW','HUMAN_AFFIRMED','HUMAN_DISMISSED','AUTO_ESCALATED','EXPIRED')),
    created_at      REAL NOT NULL,
    reviewed_at     REAL,
    reviewed_by     TEXT,
    review_notes    TEXT
);
CREATE INDEX IF NOT EXISTS idx_review_state ON fraud_review_queue(district_id, state, created_at);
CREATE INDEX IF NOT EXISTS idx_review_subject ON fraud_review_queue(subject_type, subject_id);

-- Citizen-initiated appeals against a fraud flag.
CREATE TABLE IF NOT EXISTS fraud_appeals (
    id              TEXT PRIMARY KEY,
    review_id       TEXT REFERENCES fraud_review_queue(id),
    subject_type    TEXT NOT NULL,
    subject_id      TEXT NOT NULL,
    appellant_id    TEXT NOT NULL,
    statement       TEXT NOT NULL,
    evidence        TEXT,
    state           TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (state IN ('OPEN','UNDER_REVIEW','UPHELD','DENIED','WITHDRAWN')),
    filed_at        REAL NOT NULL,
    resolved_at     REAL,
    resolution_note TEXT
);
CREATE INDEX IF NOT EXISTS idx_appeals_subject ON fraud_appeals(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_appeals_state ON fraud_appeals(state, filed_at);
