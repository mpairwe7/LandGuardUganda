"""Feature vector assembly for the IsolationForest model."""

from __future__ import annotations

import math
import statistics
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


def _district_norm_z(district_id: Any, consideration: float, area_ha: float) -> float:
    """Z-score of this subject's consideration-per-hectare vs. the district's
    historical transfers.

    Returns ``0.0`` when there isn't enough district data — which is exactly the
    no-signal baseline the IsolationForest was trained to treat as "normal".
    Previously this whole feature was hardcoded to ``0.0`` at inference while
    the training set generated a real distribution for it, causing train/serve
    skew; this restores the intended signal.
    """
    if district_id is None or consideration <= 0 or area_ha <= 0:
        return 0.0
    with get_connection() as conn:
        others = [
            float(r[0]) / max(float(r[1]), 1e-6)
            for r in conn.execute(
                "SELECT t.consideration, p.area_hectares "
                "FROM transfers t JOIN parcels p ON p.parcel_id = t.parcel_id "
                "WHERE p.district_id = ? AND t.consideration IS NOT NULL "
                "AND t.consideration > 0 AND p.area_hectares > 0",
                (district_id,),
            ).fetchall()
        ]
    if len(others) < 5:
        return 0.0
    mean = statistics.mean(others)
    stdev = statistics.pstdev(others)
    if stdev <= 0:
        return 0.0
    cph = consideration / area_ha
    z = (cph - mean) / stdev
    # Clamp so a single wild outlier can't dominate the feature vector.
    return max(-10.0, min(10.0, z))


def assemble_features(context: dict[str, Any]) -> list[float]:
    """Build the 9-element feature vector for one transfer subject."""
    parcel_id = context.get("parcel_id")
    owner_id = context.get("to_owner_id") or context.get("owner_id")
    consideration = _safe_float(context.get("consideration"))
    area_ha = _safe_float(context.get("area_hectares"))

    hours_since_last = 9999.0
    prior_parcels = 0
    prior_disputes = 0
    norm_z = _district_norm_z(context.get("district_id"), consideration, area_ha)
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
