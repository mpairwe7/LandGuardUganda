#!/usr/bin/env python
"""Seed the showcase narrative — hero parcel, fraudster, watchlist, staff.

Idempotent. Run manually for ad-hoc re-seeding outside the
lifespan-driven on-startup seed:

    uv run python scripts/seed_demo.py

The logic lives in `app.bootstrap.seed.seed_demo_state` so the same
function can be reused by `app.main.lifespan`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.bootstrap.seed import seed_demo_state  # noqa: E402
from app.database import apply_migrations  # noqa: E402


def main() -> None:
    apply_migrations()
    result = seed_demo_state()
    print(
        f"seeded demo state: hero parcel {result['hero_parcel']} owned by Sarah Nakato; "
        f"{result['watchlist']} watchlist entries; {result['staff']} staff users."
    )


if __name__ == "__main__":
    main()
