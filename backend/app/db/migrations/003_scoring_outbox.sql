-- Migration 003: durable fraud-scoring outbox.
--
-- The Redis stream is the fast path for fraud scoring, but it is best-effort:
-- if Redis is unavailable when a transfer is created, the enqueue silently
-- no-ops and the transfer would never be scored. That made the approval gate
-- fail OPEN. This table is a transactional outbox: a row is written in the
-- SAME transaction as the transfer insert, and the worker sweeps it as a
-- fallback so every subject is eventually scored regardless of Redis health.
-- IF NOT EXISTS discipline keeps the migration idempotent.

CREATE TABLE IF NOT EXISTS fraud_scoring_jobs (
    id              TEXT PRIMARY KEY,
    subject_type    TEXT NOT NULL,
    subject_id      TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (state IN ('PENDING','DONE','FAILED')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    created_at      REAL NOT NULL,
    next_attempt_at REAL,
    last_error      TEXT
);
CREATE INDEX IF NOT EXISTS idx_scoring_jobs_pending
    ON fraud_scoring_jobs(state, next_attempt_at);
