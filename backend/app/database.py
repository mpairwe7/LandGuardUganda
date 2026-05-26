"""Synchronous DB dispatcher for ledger + repositories.

Async DB work (FastAPI routes) uses :mod:`app.db.pool` instead — the
sync layer here exists because the audit ledger's append-under-lock
discipline is most cleanly expressed in synchronous code and only ever
runs within thread executor pools called from async handlers.

SQLite (dev) uses WAL for read concurrency. Postgres (prod) uses
psycopg-3 sync via short-lived connections; pooling is delegated to
PgBouncer or the deployment's connection pool.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_LOCAL = threading.local()


def _sqlite_connect(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def _postgres_connect() -> Any:
    """Lazy psycopg import — only loaded when DB_BACKEND=postgres."""
    import psycopg

    settings = get_settings()
    dsn = settings.postgres_dsn.replace("+asyncpg", "")
    return psycopg.connect(dsn, autocommit=False)


@contextmanager
def get_connection() -> Iterator[Any]:
    """Yield a thread-local connection appropriate for the backend.

    For SQLite, returns a sqlite3.Connection. For Postgres, returns a
    psycopg.Connection. The shape is similar enough for our SQL — the
    audit ledger and migrations are written to be backend-agnostic.
    """
    settings = get_settings()
    if settings.db_backend == "sqlite":
        if not hasattr(_LOCAL, "sqlite_conn"):
            _LOCAL.sqlite_conn = _sqlite_connect(settings.sqlite_path)
        conn = _LOCAL.sqlite_conn
        yield conn
        return

    # Postgres: short-lived per-call connection (caller commits).
    conn = _postgres_connect()
    try:
        yield conn
    finally:
        conn.close()


def close_connections() -> None:
    """Close thread-local connections — call on shutdown."""
    conn = getattr(_LOCAL, "sqlite_conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            logger.exception("error_closing_sqlite_connection")
        finally:
            del _LOCAL.sqlite_conn


def apply_migrations() -> None:
    """Apply ``app/db/migrations/*.sql`` in lexicographic order.

    Idempotent: every migration uses ``IF NOT EXISTS`` discipline.
    """
    migrations_dir = os.path.join(os.path.dirname(__file__), "db", "migrations")
    if not os.path.isdir(migrations_dir):
        logger.warning("migrations_dir_missing", extra={"dir": migrations_dir})
        return
    files = sorted(f for f in os.listdir(migrations_dir) if f.endswith(".sql"))
    with get_connection() as conn:
        cur = conn.cursor()
        for fn in files:
            path = os.path.join(migrations_dir, fn)
            with open(path, encoding="utf-8") as fh:
                script = fh.read()
            logger.info("applying_migration", extra={"file": fn})
            for stmt in _split_statements(script):
                if not stmt.strip():
                    continue
                try:
                    cur.execute(stmt)
                except Exception as exc:
                    msg = str(exc).lower()
                    if "already exists" in msg or "duplicate" in msg:
                        continue
                    logger.exception("migration_stmt_failed", extra={"file": fn})
                    raise
        conn.commit()


def _split_statements(script: str) -> list[str]:
    """Naive SQL splitter that respects $$ blocks for plpgsql functions."""
    out: list[str] = []
    buf: list[str] = []
    in_dollar = False
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        if "$$" in line:
            in_dollar = not in_dollar
        buf.append(line)
        if not in_dollar and stripped.endswith(";"):
            out.append("\n".join(buf))
            buf = []
    if buf:
        out.append("\n".join(buf))
    return out
