#!/usr/bin/env python
"""Issue HS256 dev tokens for each demo role — for use in the showcase."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.auth.jwt_auth import make_dev_token  # noqa: E402

ROLES = [
    ("demo-citizen", "CITIZEN", None, "Sarah Nakato"),
    ("demo-surveyor", "SURVEYOR", 3, "Surveyor Otim"),
    ("demo-officer", "LAND_OFFICER", 3, "Officer Apio"),
    ("demo-registrar", "REGISTRAR", 3, "Registrar Kasozi"),
    ("demo-auditor", "AUDITOR", None, "Auditor Mubiru"),
    ("demo-admin", "ADMIN", None, "Admin Owor"),
]


def main() -> None:
    for user_id, role, district_id, name in ROLES:
        token = make_dev_token(
            user_id=user_id,
            role=role,
            district_id=district_id,
            full_name=name,
            email=f"{user_id}@landguard.ug",
            ttl_seconds=86_400 * 14,  # 2 weeks
        )
        print(f"# {role} — {name}")
        print(token)
        print()


if __name__ == "__main__":
    main()
