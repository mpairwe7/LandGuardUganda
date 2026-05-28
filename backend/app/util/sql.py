"""SQL-helper utilities.

``escape_like_value`` exists because the audit-event LIKE-pattern
fallback the verifier uses interpolates a *string drawn from the
``titles.parcel_id`` column* into a SQLite LIKE pattern. UPIs are
constrained by ``UPI_REGEX`` (``^UG-[A-Z]{3}-\\d{6}/\\d{4}$``) so the
characters that have LIKE meaning (``%``, ``_``, ``\\``) cannot legally
appear — but defense-in-depth: if the regex is ever loosened or
bypassed via an out-of-band write to the parcels table, an attacker
who controls a parcel_id with ``%`` could broaden the LIKE match and
exfiltrate audit-event payloads for other parcels.

The helper escapes those three characters with a ``\\`` prefix and the
caller pairs the resulting pattern with ``ESCAPE '\\'`` so SQLite
treats them literally.
"""

from __future__ import annotations

# Characters with LIKE-pattern meaning in SQLite. Backslash is included
# so we can escape ourselves (``\\\\`` matches a literal backslash).
_LIKE_SPECIAL = ("\\", "%", "_")


def escape_like_value(value: str) -> str:
    """Escape ``%``, ``_``, ``\\`` in *value* for use inside a LIKE pattern.

    Callers MUST pair the resulting pattern with ``ESCAPE '\\'`` in the
    SQL statement so the escape character is honoured. Example::

        param = f'%"parcel_id": "{escape_like_value(parcel_id)}"%'
        conn.execute("... WHERE col LIKE ? ESCAPE '\\\\'", (param,))
    """
    out = value
    for c in _LIKE_SPECIAL:
        out = out.replace(c, "\\" + c)
    return out
