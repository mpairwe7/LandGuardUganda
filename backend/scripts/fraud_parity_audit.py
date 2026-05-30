#!/usr/bin/env python
"""CLI wrapper: demographic parity audit for the fraud scorer.

The canonical implementation lives in :mod:`app.jobs.parity`. Mandated
quarterly by ``docs/AI_ETHICS_CHARTER.md`` §5; also run automatically by the
in-process scheduler (:mod:`app.jobs.scheduler`). Prints the JSON report and a
non-zero-highlighted warning when any group exceeds 1.5× the mean flag rate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.jobs.parity import run_parity_audit  # noqa: E402

if __name__ == "__main__":
    report = run_parity_audit()
    print(json.dumps(report, indent=2))
    breaches = report.get("breaches", [])
    if breaches:
        print(
            f"\n⚠ PARITY ALERT: {len(breaches)} group(s) exceed 1.5× the mean flag rate.",
            file=sys.stderr,
        )
        for g in breaches:
            print(
                f"   group={g['group']}  key={g['key']}  "
                f"rate={g['flag_rate']}  ratio={g['ratio_to_mean']}",
                file=sys.stderr,
            )
    sys.exit(0)
