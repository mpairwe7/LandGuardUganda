"""Pytest fixtures for LandGuard backend tests.

Sets up an isolated environment per test session:
- Sandbox-safe temp dirs (avoid NAS-mounted defaults).
- In-memory Redis surrogate (no live Redis dependency in unit tests).
- SQLite DB created fresh once per session; cleared between tests.
- Mock blockchain + mock NIRA providers.

Env vars are set at MODULE import time so they precede any
``from app.* import ...`` in test modules.
"""

from __future__ import annotations

import os
import tempfile

# Sandbox-safe temp root for the SQLite DB. We use ``tempfile.mkdtemp``
# directly so it runs before any test module imports — pytest's
# ``tmp_path_factory`` would otherwise be too late.
_TEST_TMP = tempfile.mkdtemp(prefix="landguard-tests-", dir="/tmp")
_TEST_DB = os.path.join(_TEST_TMP, "test.db")

os.environ.setdefault("APP_ENV", "development")
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_PATH"] = _TEST_DB
os.environ["BLOCKCHAIN_PROVIDER"] = "mock"
os.environ["NIRA_PROVIDER"] = "mock"
os.environ["DEMO_MODE"] = "true"
os.environ["AUTH_REQUIRED"] = "false"
os.environ["JWT_HS256_SECRET"] = "this-is-a-test-secret-thirty-two-bytes!"
os.environ["PII_ENCRYPTION_KEY"] = "dGVzdGtleS0zMi1ieXRlcy0wMTIzNDU2Nzg5MDEyMzQ1Ng=="
# slowapi's limits library accepts "memory://" — no Redis required.
os.environ["REDIS_URL"] = "memory://"
os.environ["OTEL_ENABLED"] = "false"

# Invalidate any cached settings then apply migrations.
from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

import pytest  # noqa: E402

from app.database import apply_migrations  # noqa: E402

apply_migrations()


# Tables wiped between tests so order-dependence and FK leakage are
# eliminated. Order matters — children before parents.
_WIPE_TABLES = [
    "fraud_appeals",
    "fraud_review_queue",
    "fraud_scores",
    "fraud_watchlist",
    "disputes",
    "transfers",
    "titles",
    "nira_verifications",
    "anchors",
    "audit_events",
    "parcels",
    "owners",
    "staff_users",
    "districts",
]


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate all business tables before each test + reset singletons."""
    from app.database import get_connection

    with get_connection() as conn:
        for table in _WIPE_TABLES:
            try:
                conn.execute(f"DELETE FROM {table}")
            except Exception:
                pass
        conn.commit()
    from app.audit import reset_ledger
    from app.blockchain.client import reset_blockchain_client
    from app.nira.client import reset_nira_client

    reset_ledger()
    reset_blockchain_client()
    reset_nira_client()
    yield
