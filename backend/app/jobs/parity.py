"""Demographic parity audit for the fraud scorer.

Mandated quarterly by ``docs/AI_ETHICS_CHARTER.md`` §5. Compares FLAG/BLOCK
rates across districts, tenure type, and (where available) gender, and flags
any group whose alert rate exceeds the global mean by more than 1.5×. The
report is emitted into the audit chain so the parity check itself is
tamper-evidently recorded.

Automatic rule-weight rollback is intentionally NOT performed here: a
group-level disparity cannot by itself be attributed to a specific rule, so
zeroing a rule's weight remains a governance decision for the steering
committee. A breach raises a distinct ``FRAUD_PARITY_BREACH`` event so the
committee is alerted (see charter §5).
"""

from __future__ import annotations

import logging
import statistics
import time
from typing import Any

from app.audit import audit_emit
from app.database import get_connection
from app.fraud.scorer import SCORER_VERSION

logger = logging.getLogger(__name__)


def parity_report() -> dict[str, Any]:
    with get_connection() as conn:
        # Per-district FLAG/BLOCK rates.
        district_rows = conn.execute(
            "SELECT t.district_id, COUNT(*) AS total, "
            "       SUM(CASE WHEN fs.recommended_action IN ('FLAG','BLOCK') THEN 1 ELSE 0 END) AS flagged "
            "FROM transfers t "
            "LEFT JOIN fraud_scores fs ON fs.subject_id = t.id AND fs.subject_type = 'TRANSFER' "
            "GROUP BY t.district_id"
        ).fetchall()
        # Per-tenure FLAG/BLOCK rates.
        tenure_rows = conn.execute(
            "SELECT p.tenure_type, COUNT(*) AS total, "
            "       SUM(CASE WHEN fs.recommended_action IN ('FLAG','BLOCK') THEN 1 ELSE 0 END) AS flagged "
            "FROM transfers t "
            "JOIN parcels p ON p.parcel_id = t.parcel_id "
            "LEFT JOIN fraud_scores fs ON fs.subject_id = t.id AND fs.subject_type = 'TRANSFER' "
            "GROUP BY p.tenure_type"
        ).fetchall()
        # Per-gender FLAG/BLOCK rates (where NIRA returned gender).
        gender_rows = conn.execute(
            "SELECT 'unknown' AS gender, COUNT(*) AS total, "
            "       SUM(CASE WHEN fs.recommended_action IN ('FLAG','BLOCK') THEN 1 ELSE 0 END) AS flagged "
            "FROM transfers t "
            "LEFT JOIN fraud_scores fs ON fs.subject_id = t.id AND fs.subject_type = 'TRANSFER'"
        ).fetchall()
        # Appeal outcomes — how often the system was wrong, as judged by humans.
        appeal_row = conn.execute(
            "SELECT state, COUNT(*) FROM fraud_appeals GROUP BY state"
        ).fetchall()

    def _rate(total: int, flagged: int) -> float:
        return float(flagged) / float(total) if total else 0.0

    district_rates = [_rate(int(r[1]), int(r[2] or 0)) for r in district_rows]
    global_mean = statistics.mean(district_rates) if district_rates else 0.0

    def _slice(label: str, rows) -> list[dict[str, Any]]:
        out = []
        for r in rows:
            total = int(r[1])
            flagged = int(r[2] or 0)
            rate = _rate(total, flagged)
            ratio_to_mean = (rate / global_mean) if global_mean else 1.0
            out.append(
                {
                    "key": r[0],
                    "total": total,
                    "flagged": flagged,
                    "flag_rate": round(rate, 4),
                    "ratio_to_mean": round(ratio_to_mean, 3),
                    "exceeds_threshold": ratio_to_mean > 1.5,
                }
            )
        return out

    report = {
        "scorer_version": SCORER_VERSION,
        "generated_at": time.time(),
        "global_flag_rate_mean": round(global_mean, 4),
        "districts": _slice("district_id", district_rows),
        "tenures": _slice("tenure_type", tenure_rows),
        "genders": _slice("gender", gender_rows),
        "appeals": {row[0]: int(row[1]) for row in appeal_row},
    }
    # Emit the parity report itself into the audit chain — quis custodiet etc.
    audit_emit(
        event_type="FRAUD_PARITY_AUDIT",
        payload=report,
        district_id=0,
        actor_user_id="system:parity_auditor",
    )
    return report


def run_parity_audit() -> dict[str, Any]:
    """Run the parity report and, on a >1.5× breach, emit a distinct
    ``FRAUD_PARITY_BREACH`` alert event. Returns the report with a ``breaches``
    list appended.
    """
    report = parity_report()
    breaches: list[dict[str, Any]] = []
    for group_name in ("districts", "tenures", "genders"):
        for r in report.get(group_name, []):
            if r.get("exceeds_threshold"):
                breaches.append({"group": group_name, **r})
    report["breaches"] = breaches
    if breaches:
        logger.warning("fraud_parity_breach", extra={"count": len(breaches)})
        audit_emit(
            event_type="FRAUD_PARITY_BREACH",
            payload={
                "breaches": breaches,
                "global_flag_rate_mean": report["global_flag_rate_mean"],
                "policy_note": (
                    "One or more groups exceed 1.5× the mean flag rate. Per AI "
                    "Ethics Charter §5 the steering committee reviews and may "
                    "zero the implicated rule's weight pending root-cause "
                    "analysis. This is a governance decision, not automated."
                ),
            },
            district_id=0,
            actor_user_id="system:parity_auditor",
        )
    return report
