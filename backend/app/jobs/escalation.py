"""Escalate fraud reviews left untouched past the SLA — WITHOUT freezing.

Per ``docs/AI_ETHICS_CHARTER.md`` §1/§8 the system never makes a custodial
decision (freeze, reject) without a *recorded human review*. The previous
escalation job auto-FROZE the parcel after 24h, which contradicted that
invariant (and, worse, was never actually scheduled). This implementation:

- does **NOT** freeze the parcel and does **NOT** auto-file a dispute;
- raises the review's priority to a supervising officer (``escalated_at`` is
  stamped) and emits a ``FRAUD_REVIEW_ESCALATED`` audit event;
- leaves the entry in ``PENDING_REVIEW`` so the normal affirm/dismiss human
  path still applies — a human is still the only thing that can FREEZE.
"""

from __future__ import annotations

import logging
import time

from app.audit import audit_emit
from app.database import get_connection

logger = logging.getLogger(__name__)

ESCALATION_THRESHOLD_SECONDS = 24 * 3600


def escalate_pending(now: float | None = None) -> int:
    """Escalate overdue, not-yet-escalated ``PENDING_REVIEW`` entries.

    ``now`` is injectable for testing. Idempotent: each entry is escalated at
    most once (guarded by ``escalated_at IS NULL``), so repeated runs are safe.
    Returns the number of entries escalated.
    """
    now = time.time() if now is None else now
    cutoff = now - ESCALATION_THRESHOLD_SECONDS
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, subject_type, subject_id, district_id, risk_score, "
            " recommended_action, scorer_version, created_at "
            "FROM fraud_review_queue "
            "WHERE state = 'PENDING_REVIEW' AND created_at < ? AND escalated_at IS NULL",
            (cutoff,),
        ).fetchall()
    if not rows:
        logger.info("fraud_escalation_no_overdue_reviews")
        return 0
    escalated = 0
    for row in rows:
        (
            review_id,
            subject_type,
            subject_id,
            district_id,
            risk_score,
            action,
            scorer_version,
            created_at,
        ) = row
        with get_connection() as conn:
            conn.execute(
                "UPDATE fraud_review_queue SET escalated_at = ? WHERE id = ?",
                (now, review_id),
            )
            conn.commit()
        audit_emit(
            event_type="FRAUD_REVIEW_ESCALATED",
            payload={
                "review_id": review_id,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "risk_score": int(risk_score),
                "recommended_action": action,
                "scorer_version": scorer_version,
                "age_hours": int((now - float(created_at)) / 3600),
                "escalated_to": "supervising_officer",
                "policy_note": (
                    "No human review within 24 hours. Priority raised to a "
                    "supervising officer. NO parcel state change was made — a "
                    "human must still affirm before any FREEZE (AI Ethics "
                    "Charter §1/§8: no custodial action without a recorded "
                    "human review)."
                ),
            },
            district_id=int(district_id),
            actor_user_id="system:escalation_job",
        )
        escalated += 1
    logger.info("fraud_escalation_done", extra={"escalated": escalated})
    return escalated
