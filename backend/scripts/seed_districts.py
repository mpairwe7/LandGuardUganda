#!/usr/bin/env python
"""Seed the four pilot districts + background parcel population.

Idempotent. Run manually for ad-hoc re-seeding outside the
lifespan-driven on-startup seed:

    uv run python scripts/seed_districts.py

The logic lives in `app.bootstrap.seed.seed_districts_and_parcels` so the
same function can be reused by `app.main.lifespan`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.bootstrap.seed import seed_districts_and_parcels  # noqa: E402
from app.database import apply_migrations  # noqa: E402


def main() -> None:
    apply_migrations()
    result = seed_districts_and_parcels()
    print(
        f"seeded {result['districts']} districts; "
        f"{result['parcels_inserted']} new parcels inserted"
    )


if __name__ == "__main__":
    main()
