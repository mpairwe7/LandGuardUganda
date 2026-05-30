"""Worker consumer name is per-process (G3).

Multiple API replicas must not share a single Redis consumer name (that
corrupts pending-entry ownership). The name is derived from hostname+pid.
"""

from __future__ import annotations

import os

from app.fraud import worker


def test_consumer_name_is_per_process():
    assert worker.CONSUMER_NAME != "scorer-1"
    assert worker.CONSUMER_NAME.startswith("scorer-")
    assert str(os.getpid()) in worker.CONSUMER_NAME
