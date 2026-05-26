"""Feature vector assembly for the IsolationForest model."""

from __future__ import annotations

import math
import time
from datetime import UTC, datetime
from typing import Any

from app.database import get_connection

FEATURE_NAMES = [
    "hours_since_last_transfer",
    "log1p_consideration",
    "log1p_area_ha",
    "owner_age_days",
    "prior_parcel_count",
    "prior_dispute_count",
    "district_norm_z",
    "hour_of_day",
    "weekday",
]


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def assemble_features(context: dict[str, Any]) -> list[float]:
    """Build the 9-element feature vector for one transfer subject."""
    parcel_id = context.get("parcel_id")
    owner_id = context.get("to_owner_id") or context.get("owner_id")
    consideration = _safe_float(context.get("consideration"))
    area_ha = _safe_float(context.get("area_hectares"))

    hours_since_last = 9999.0
    prior_parcels = 0
    prior_disputes = 0
    norm_z = 0.0
    if parcel_id:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT max(initiated_at) FROM transfers WHERE parcel_id = ?",
                (parcel_id,),
            ).fetchone()
            if row and row[0]:
                hours_since_last = max(0.0, (time.time() - float(row[0])) / 3600.0)
            d_row = conn.execute(
                "SELECT count(*) FROM disputes WHERE parcel_id = ?",
                (parcel_id,),
            ).fetchone()
            if d_row:
                prior_disputes = int(d_row[0] or 0)
    if owner_id:
        with get_connection() as conn:
            p_row = conn.execute(
                "SELECT count(*) FROM transfers WHERE to_owner_id = ?",
                (owner_id,),
            ).fetchone()
            if p_row:
                prior_parcels = int(p_row[0] or 0)
    # KYC age in days
    owner_age_days = 0.0
    if owner_id:
        with get_connection() as conn:
            o_row = conn.execute(
                "SELECT created_at FROM owners WHERE id = ?",
                (owner_id,),
            ).fetchone()
            if o_row and o_row[0]:
                owner_age_days = max(0.0, (time.time() - float(o_row[0])) / 86400.0)

    now = datetime.now(tz=UTC)
    return [
        hours_since_last,
        math.log1p(consideration),
        math.log1p(area_ha),
        owner_age_days,
        float(prior_parcels),
        float(prior_disputes),
        norm_z,
        float(now.hour),
        float(now.weekday()),
    ]
