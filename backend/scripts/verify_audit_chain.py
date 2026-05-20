#!/usr/bin/env python
"""Walk a district's ledger and verify chain integrity.

Usage: uv run python scripts/verify_audit_chain.py 3
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.audit.verifier import verify_chain  # noqa: E402


def main(district_id: str) -> int:
    report = verify_chain(district_id)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.verified else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "3"))
