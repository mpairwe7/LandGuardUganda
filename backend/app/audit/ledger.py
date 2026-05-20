"""Hash-chained, append-only audit ledger.

Per-district chain — every district anchors independently. A row's
``row_hash = sha256(prev_hash + payload_hash)`` makes any tampering
detectable by rewalking the chain (see :mod:`app.audit.verifier`).

Schema is created on first use. Uses the shared :mod:`app.database`
dispatch so SQLite (dev) and Postgres (prod) both work without
caller changes.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .merkle import compute_merkle_root, sha256_hex

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_events (
    event_id      TEXT PRIMARY KEY,
    event_type    TEXT NOT NULL,
    tenant_id     TEXT NOT NULL,
    user_id       TEXT NOT NULL,
    payload_json  TEXT NOT NULL,
    ts            REAL NOT NULL,
    seq           INTEGER NOT NULL,
    prev_hash     TEXT NOT NULL,
    payload_hash  TEXT NOT NULL,
    row_hash      TEXT NOT NULL,
    anchored_in   TEXT REFERENCES anchors(batch_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_seq ON audit_events(tenant_id, seq);
CREATE INDEX IF NOT EXISTS idx_audit_type       ON audit_events(event_type, ts);
CREATE INDEX IF NOT EXISTS idx_audit_unanchored ON audit_events(tenant_id, anchored_in)
    WHERE anchored_in IS NULL;
"""

# SQLite doesn't accept partial indexes with WHERE on older versions; we apply
# a non-partial fallback for SQLite where needed (init handles it).
_SQLITE_FALLBACK = """
CREATE INDEX IF NOT EXISTS idx_audit_unanchored ON audit_events(tenant_id, anchored_in);
"""


@dataclass
class AuditEvent:
    """One row in the audit ledger.

    The ``payload`` is structured content (e.g. {"parcel_id": ...,
    "owner_id": ...}). It's serialised deterministically (sorted keys)
    before hashing so the same logical event always produces the same
    ``payload_hash``.
    """

    event_id: str
    event_type: str
    tenant_id: str
    user_id: str
    payload: dict[str, Any]
    ts: float = field(default_factory=time.time)
    seq: int = 0
    prev_hash: str = ""
    payload_hash: str = ""
    row_hash: str = ""

    def to_row(self) -> tuple[Any, ...]:
        return (
            self.event_id,
            self.event_type,
            self.tenant_id,
            self.user_id,
            json.dumps(self.payload, sort_keys=True, default=str),
            self.ts,
            self.seq,
            self.prev_hash,
            self.payload_hash,
            self.row_hash,
        )


class AuditLedger:
    """Thread-safe, append-only hash-chained ledger."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._initialised = False

    def _ensure_schema(self) -> None:
        if self._initialised:
            return
        from app.database import get_connection

        with get_connection() as conn:
            cur = conn.cursor()
            for stmt in _SCHEMA_SQL.strip().split(";"):
                stmt = stmt.strip()
                if not stmt:
                    continue
                try:
                    cur.execute(stmt)
                except Exception as exc:
                    if "partial index" in str(exc).lower() or "WHERE" in stmt.upper():
                        cur.execute(_SQLITE_FALLBACK)
                    else:
                        raise
            conn.commit()
        self._initialised = True

    def _last_seq_and_hash(self, tenant_id: str) -> tuple[int, str]:
        from app.database import get_connection

        with get_connection() as conn:
            row = conn.execute(
                "SELECT seq, row_hash FROM audit_events "
                "WHERE tenant_id = ? ORDER BY seq DESC LIMIT 1",
                (tenant_id,),
            ).fetchone()
        if row is None:
            return (0, GENESIS_HASH)
        return (int(row[0]), str(row[1]))

    def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        tenant_id: str,
        user_id: str,
    ) -> AuditEvent:
        """Append one event; return the materialised row."""
        self._ensure_schema()
        with self._lock:
            prev_seq, prev_hash = self._last_seq_and_hash(tenant_id)
            canonical = json.dumps(payload, sort_keys=True, default=str)
            payload_hash = sha256_hex(canonical)
            row_hash = sha256_hex(prev_hash + payload_hash)
            event = AuditEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                tenant_id=tenant_id,
                user_id=user_id,
                payload=payload,
                seq=prev_seq + 1,
                prev_hash=prev_hash,
                payload_hash=payload_hash,
                row_hash=row_hash,
            )
            from app.database import get_connection

            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO audit_events "
                    "(event_id, event_type, tenant_id, user_id, payload_json, "
                    " ts, seq, prev_hash, payload_hash, row_hash) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    event.to_row(),
                )
                conn.commit()
        logger.debug(
            "audit_event_appended",
            extra={
                "event_id": event.event_id,
                "event_type": event_type,
                "tenant_id": tenant_id,
                "seq": event.seq,
            },
        )
        return event

    def read(
        self,
        tenant_id: str,
        *,
        since_seq: int = 0,
        limit: int = 100,
        event_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        from app.database import get_connection

        sql = (
            "SELECT event_id, event_type, tenant_id, user_id, payload_json, "
            "       ts, seq, prev_hash, payload_hash, row_hash, anchored_in "
            "FROM audit_events WHERE tenant_id = ? AND seq > ?"
        )
        params: list[Any] = [tenant_id, since_seq]
        if event_types:
            placeholders = ",".join("?" for _ in event_types)
            sql += f" AND event_type IN ({placeholders})"
            params.extend(event_types)
        sql += " ORDER BY seq ASC LIMIT ?"
        params.append(limit)
        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "event_id": r[0],
                "event_type": r[1],
                "tenant_id": r[2],
                "user_id": r[3],
                "payload": json.loads(r[4]),
                "ts": r[5],
                "seq": r[6],
                "prev_hash": r[7],
                "payload_hash": r[8],
                "row_hash": r[9],
                "anchored_in": r[10],
            }
            for r in rows
        ]

    def count(self, tenant_id: str) -> int:
        from app.database import get_connection

        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM audit_events WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    def unanchored(self, tenant_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        from app.database import get_connection

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT seq, payload_hash FROM audit_events "
                "WHERE tenant_id = ? AND anchored_in IS NULL "
                "ORDER BY seq ASC LIMIT ?",
                (tenant_id, limit),
            ).fetchall()
        return [{"seq": int(r[0]), "payload_hash": r[1]} for r in rows]

    def mark_anchored(self, tenant_id: str, first_seq: int, last_seq: int, batch_id: str) -> int:
        from app.database import get_connection

        with get_connection() as conn:
            cur = conn.execute(
                "UPDATE audit_events SET anchored_in = ? "
                "WHERE tenant_id = ? AND seq BETWEEN ? AND ? "
                "AND anchored_in IS NULL",
                (batch_id, tenant_id, first_seq, last_seq),
            )
            conn.commit()
            return cur.rowcount

    def anchor_range(
        self, first_seq: int, last_seq: int, tenant_id: str
    ) -> dict[str, Any]:
        """Compute the Merkle root for [first_seq, last_seq] in this tenant."""
        from app.database import get_connection

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT payload_hash FROM audit_events "
                "WHERE tenant_id = ? AND seq BETWEEN ? AND ? "
                "ORDER BY seq ASC",
                (tenant_id, first_seq, last_seq),
            ).fetchall()
        leaves = [str(r[0]) for r in rows]
        return {
            "tenant_id": tenant_id,
            "first_seq": first_seq,
            "last_seq": last_seq,
            "leaf_count": len(leaves),
            "merkle_root": compute_merkle_root(leaves),
        }

    def erasure_tombstone(
        self, *, user_id: str, reason: str, tenant_id: str
    ) -> AuditEvent:
        """Right-to-erasure: writes a tombstone referencing the erased user's hash.

        The original chain remains intact so verifiability is preserved;
        downstream readers MUST honour the tombstone when surfacing data.
        """
        return self.append(
            event_type="erasure_tombstone",
            payload={
                "erased_user_hash": sha256_hex(user_id),
                "reason": reason,
                "ts": time.time(),
            },
            tenant_id=tenant_id,
            user_id="system",
        )


_LEDGER: AuditLedger | None = None


def get_ledger() -> AuditLedger:
    global _LEDGER
    if _LEDGER is None:
        _LEDGER = AuditLedger()
    return _LEDGER


def reset_ledger() -> None:
    """Test-only: drop the in-memory singleton."""
    global _LEDGER
    _LEDGER = None
