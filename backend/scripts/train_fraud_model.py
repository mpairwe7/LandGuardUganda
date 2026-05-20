#!/usr/bin/env python
"""Train + persist the IsolationForest model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.fraud.training.train import train_and_save  # noqa: E402


if __name__ == "__main__":
    path = train_and_save()
    print(f"wrote model: {path}")
