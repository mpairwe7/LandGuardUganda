#!/usr/bin/env python
"""Escalate fraud reviews that have sat untouched for >24h.

This is the explicit fallback path documented in ``docs/AI_ETHICS_CHARTER.md``:
ML alerts never silently auto-FREEZE — but if no human reviews within 24h,
the system applies the recommended action and emits a distinct
``FRAUD_AUTO_ESCALATED`` audit event so the timeline distinguishes
"human decision" from "operator inaction default".

Wire into cron / a scheduled task; not part of the FastAPI lifespan.
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
from app.database import get_connection  # noqa: E402

ESCALATION_THRESHOLD_SECONDS = 24 * 3600


def escalate_pending() -> int:
    now = time.time()
    cutoff = now - ESCALATION_THRESHOLD_SECONDS
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, subject_type, subject_id, district_id, risk_score, "
            " recommended_action, signals, scorer_version, created_at "
            "FROM fraud_review_queue WHERE state = 'PENDING_REVIEW' AND created_at < ?",
            (cutoff,),
        ).fetchall()
    if not rows:
        print("no overdue reviews")
        return 0
    escalated = 0
    for row in rows:
        review_id, subject_type, subject_id, district_id, risk_score, action, signals_json, scorer_version, created_at = row
        with get_connection() as conn:
            conn.execute(
                "UPDATE fraud_review_queue SET state = 'AUTO_ESCALATED', reviewed_at = ?, "
                "reviewed_by = 'system:escalation_job' WHERE id = ?",
                (now, review_id),
            )
            applied = None
            if action == "BLOCK" and subject_type == "TRANSFER":
                tx_row = conn.execute(
                    "SELECT parcel_id, to_owner_id FROM transfers WHERE id = ?",
                    (subject_id,),
                ).fetchone()
                if tx_row:
                    parcel_id, to_owner_id = tx_row
                    conn.execute(
                        "UPDATE parcels SET status = 'FROZEN', updated_at = ? WHERE parcel_id = ?",
                        (now, parcel_id),
                    )
                    existing = conn.execute(
                        "SELECT id FROM disputes WHERE parcel_id = ? AND dispute_type = 'FRAUD' "
                        "AND state NOT IN ('RESOLVED','DISMISSED')",
                        (parcel_id,),
                    ).fetchone()
                    if not existing:
                        conn.execute(
                            "INSERT INTO disputes "
                            "(id, parcel_id, claimant_id, dispute_type, state, evidence, "
                            " district_id, filed_at) VALUES (?,?,?,?,?,?,?,?)",
                            (
                                str(uuid.uuid4()),
                                parcel_id,
                                to_owner_id,
                                "FRAUD",
                                "UNDER_REVIEW",
                                json.dumps(
                                    {
                                        "source": "automated_escalation",
                                        "review_id": review_id,
                                        "review_age_hours": int(
                                            (now - float(created_at)) / 3600
                                        ),
                                    }
                                ),
                                int(district_id),
                                now,
                            ),
                        )
                    applied = {"parcel_frozen": parcel_id}
            conn.commit()
        audit_emit(
            event_type="FRAUD_AUTO_ESCALATED",
            payload={
                "review_id": review_id,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "risk_score": int(risk_score),
                "recommended_action": action,
                "scorer_version": scorer_version,
                "age_hours": int((now - float(created_at)) / 3600),
                "applied": applied,
                "policy_note": (
                    "No human review within 24 hours. Applying the recommended "
                    "action under the explicit escalation policy. This is "
                    "system inaction, not a human decision."
                ),
            },
            district_id=int(district_id),
            actor_user_id="system:escalation_job",
        )
        escalated += 1
    print(f"escalated {escalated} overdue review(s)")
    return escalated


if __name__ == "__main__":
    escalate_pending()
