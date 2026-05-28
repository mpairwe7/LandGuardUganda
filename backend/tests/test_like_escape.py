"""Pack F2 — escape_like_value helper, defensive against LIKE-injection.

UPI_REGEX prevents ``%``, ``_``, ``\\`` from entering legitimate
parcel_id values, but the verifier's audit-event LIKE fallback would
broaden the match if an attacker bypassed the validator. The helper +
``ESCAPE '\\'`` clause shut that down.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.util.sql import escape_like_value


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("UG-MIT-024718/2026", "UG-MIT-024718/2026"),  # canonical UPI — untouched
        ("MITYANA/V1/20260001", "MITYANA/V1/20260001"),  # title-no — untouched
        ("UG-MIT-%/2026", "UG-MIT-\\%/2026"),  # % escaped
        ("UG-MIT-_/2026", "UG-MIT-\\_/2026"),  # _ escaped
        ("backslash\\here", "backslash\\\\here"),  # \ self-escaped
        ("all_three%\\here", "all\\_three\\%\\\\here"),  # combined
        ("", ""),
    ],
)
def test_escape_like_value(raw: str, expected: str) -> None:
    assert escape_like_value(raw) == expected


def test_escape_blocks_broadening_match() -> None:
    """An attacker-controlled ``%`` must NOT match unrelated rows.

    Without ``ESCAPE '\\'`` the ``%`` would be a wildcard. Asserts that
    the helper + clause together collapse the wildcard to a literal.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (payload TEXT)")
    conn.executemany(
        "INSERT INTO t VALUES (?)",
        [
            ('{"parcel_id": "UG-MIT-000100/2026"}',),
            ('{"parcel_id": "UG-MIT-000200/2026"}',),
            # The attacker row — claims their parcel is "UG-MIT-%/2026"
            # which without escaping would match the two rows above.
            ('{"parcel_id": "UG-MIT-%/2026"}',),
        ],
    )
    attacker_input = "UG-MIT-%/2026"
    pattern = f'%"parcel_id": "{escape_like_value(attacker_input)}"%'
    rows = conn.execute(
        "SELECT payload FROM t WHERE payload LIKE ? ESCAPE '\\'",
        (pattern,),
    ).fetchall()
    # Exactly one match — the literal attacker row, not the legitimate
    # ones it would have wildcarded into.
    assert len(rows) == 1
    assert "UG-MIT-%/2026" in rows[0][0]
    conn.close()


def test_escape_preserves_real_uvalues() -> None:
    """Real UPI values (which never contain LIKE-specials) round-trip."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (payload TEXT)")
    conn.execute("INSERT INTO t VALUES ('{\"parcel_id\": \"UG-MIT-024718/2026\"}')")
    pattern = f'%"parcel_id": "{escape_like_value("UG-MIT-024718/2026")}"%'
    rows = conn.execute(
        "SELECT payload FROM t WHERE payload LIKE ? ESCAPE '\\'",
        (pattern,),
    ).fetchall()
    assert len(rows) == 1
    conn.close()
