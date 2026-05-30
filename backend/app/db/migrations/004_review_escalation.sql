-- Migration 004: non-custodial escalation marker on the review queue.
--
-- The 24h escalation job NO LONGER freezes a parcel (see app/jobs/escalation.py
-- and docs/AI_ETHICS_CHARTER.md §1/§8). Instead it stamps escalated_at and
-- raises the entry's priority to a supervising officer, leaving the row in
-- PENDING_REVIEW so a human must still affirm before any FREEZE. The re-add of
-- this column on a warm DB raises "duplicate column", which apply_migrations()
-- swallows — so this stays idempotent.

ALTER TABLE fraud_review_queue ADD COLUMN escalated_at REAL;
