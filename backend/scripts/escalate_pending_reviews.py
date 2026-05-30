#!/usr/bin/env python
"""CLI wrapper: escalate fraud reviews left untouched past the 24h SLA.

The canonical implementation lives in :mod:`app.jobs.escalation`. This entry
point exists for manual / cron invocation; the API also runs it automatically
via the in-process scheduler (:mod:`app.jobs.scheduler`).

Per ``docs/AI_ETHICS_CHARTER.md`` §1/§8, escalation raises a review's priority
to a supervising officer and NEVER freezes a parcel — a human must still
affirm before any custodial action.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.jobs.escalation import escalate_pending  # noqa: E402

if __name__ == "__main__":
    n = escalate_pending()
    print(f"escalated {n} overdue review(s) — no parcel was frozen")
