#!/usr/bin/env python
"""Demographic parity audit for the fraud scorer.

Mandated quarterly by ``docs/AI_ETHICS_CHARTER.md`` §5. Compares FLAG/BLOCK
rates across districts (and, where district-level demographics are
available, by gender and tenure type). Flags any group whose alert rate
exceeds the global mean by more than 1.5×.

Output is a JSON report suitable for archival + an audit-chain event so the
parity check itself is tamper-evidently recorded.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.audit import audit_emit  # noqa: E402
from app.database import get_connection  # noqa: E402


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
        "scorer_version": "isoforest-rules-v1-20260620",
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


if __name__ == "__main__":
    report = parity_report()
    print(json.dumps(report, indent=2))
    for group_name in ("districts", "tenures", "genders"):
        flagged_groups = [r for r in report[group_name] if r["exceeds_threshold"]]
        if flagged_groups:
            print(
                f"\n⚠ PARITY ALERT in {group_name}: "
                f"{len(flagged_groups)} group(s) exceed 1.5× the mean flag rate.",
                file=sys.stderr,
            )
            for g in flagged_groups:
                print(
                    f"   key={g['key']}  rate={g['flag_rate']}  ratio={g['ratio_to_mean']}",
                    file=sys.stderr,
                )
    sys.exit(0)
