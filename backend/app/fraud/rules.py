"""Hand-coded rule signals.

Each rule:
- inspects a candidate subject (transfer/title/parcel/owner) + context
- returns a :class:`RuleSignal` with ``score`` in [0,1] and a
  plain-English ``explanation``
- has a fixed ``weight`` used by the combiner in :mod:`scorer`

Rules are written to fail safe: any internal error returns score 0,
not None — fraud scoring must never crash the calling workflow.
"""

from __future__ import annotations

import json
import logging
import statistics
from dataclasses import dataclass
from typing import Any, Callable

from rapidfuzz.fuzz import token_set_ratio

from app.database import get_connection
from app.util.geo import overlap_fraction, parse_geojson

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuleSignal:
    name: str
    weight: int
    score: float  # 0.0–1.0
    explanation: str

    def fired(self) -> bool:
        return self.score > 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weight": self.weight,
            "score": self.score,
            "explanation": self.explanation,
        }


def _zero(name: str, weight: int, reason: str) -> RuleSignal:
    return RuleSignal(name=name, weight=weight, score=0.0, explanation=reason)


def rule_geometry_overlap(context: dict[str, Any]) -> RuleSignal:
    """Fires when the candidate parcel geometry overlaps any other ACTIVE parcel."""
    weight = 30
    parcel_id = context.get("parcel_id")
    if not parcel_id:
        return _zero("geometry_overlap", weight, "no parcel_id")
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT geometry_geojson, district_id FROM parcels WHERE parcel_id = ?",
                (parcel_id,),
            ).fetchone()
            if not row:
                return _zero("geometry_overlap", weight, "parcel not found")
            geom_json, district_id = row
            others = conn.execute(
                "SELECT parcel_id, geometry_geojson FROM parcels "
                "WHERE district_id = ? AND parcel_id != ? AND status = 'ACTIVE'",
                (district_id, parcel_id),
            ).fetchall()
        candidate = parse_geojson(geom_json)
        worst = 0.0
        worst_id = None
        for pid, other_geom in others:
            other = parse_geojson(other_geom)
            frac = overlap_fraction(candidate, other)
            if frac > worst:
                worst = frac
                worst_id = pid
        if worst <= 0.05:
            return _zero("geometry_overlap", weight, "no significant overlap")
        score = min(1.0, worst / 0.5)
        return RuleSignal(
            name="geometry_overlap",
            weight=weight,
            score=score,
            explanation=(
                f"Parcel polygon overlaps {worst*100:.1f}% with active parcel {worst_id}."
            ),
        )
    except Exception:
        logger.exception("rule_geometry_overlap_error")
        return _zero("geometry_overlap", weight, "internal error")


def rule_rapid_retransfer(context: dict[str, Any]) -> RuleSignal:
    """Fires when a parcel has been transferred more than 2× in the trailing 90 days."""
    weight = 20
    parcel_id = context.get("parcel_id")
    if not parcel_id:
        return _zero("rapid_retransfer", weight, "no parcel_id")
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM transfers "
                "WHERE parcel_id = ? AND completed_at IS NOT NULL "
                "AND completed_at > strftime('%s','now') - 90*86400",
                (parcel_id,),
            ).fetchone()
        count = int(row[0] or 0)
        if count <= 2:
            return _zero("rapid_retransfer", weight, f"{count} completed transfers in 90d")
        score = min(1.0, (count - 2) / 4.0)
        return RuleSignal(
            name="rapid_retransfer",
            weight=weight,
            score=score,
            explanation=f"{count} completed transfers in 90 days (threshold: 2).",
        )
    except Exception:
        logger.exception("rule_rapid_retransfer_error")
        return _zero("rapid_retransfer", weight, "internal error")


def rule_nin_reuse(context: dict[str, Any]) -> RuleSignal:
    """Fires when the same NIN owner appears on many parcels recently."""
    weight = 15
    owner_id = context.get("to_owner_id") or context.get("owner_id")
    if not owner_id:
        return _zero("nin_reuse", weight, "no owner")
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT parcel_id) FROM transfers "
                "WHERE to_owner_id = ? AND initiated_at > strftime('%s','now') - 30*86400",
                (owner_id,),
            ).fetchone()
        count = int(row[0] or 0)
        if count <= 3:
            return _zero("nin_reuse", weight, f"{count} parcels claimed in 30d")
        score = min(1.0, (count - 3) / 6.0)
        return RuleSignal(
            name="nin_reuse",
            weight=weight,
            score=score,
            explanation=f"NIN appears on {count} distinct parcels in trailing 30 days.",
        )
    except Exception:
        logger.exception("rule_nin_reuse_error")
        return _zero("nin_reuse", weight, "internal error")


def rule_size_anomaly(context: dict[str, Any]) -> RuleSignal:
    """Fires when the parcel area is a strong outlier vs. district norm."""
    weight = 10
    parcel_id = context.get("parcel_id")
    if not parcel_id:
        return _zero("size_anomaly", weight, "no parcel_id")
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT area_hectares, district_id FROM parcels WHERE parcel_id = ?",
                (parcel_id,),
            ).fetchone()
            if not row:
                return _zero("size_anomaly", weight, "parcel not found")
            area, district_id = float(row[0]), int(row[1])
            others = [
                float(r[0])
                for r in conn.execute(
                    "SELECT area_hectares FROM parcels WHERE district_id = ? AND parcel_id != ?",
                    (district_id, parcel_id),
                ).fetchall()
            ]
        if len(others) < 5:
            return _zero("size_anomaly", weight, "insufficient district norm")
        mean = statistics.mean(others)
        stdev = statistics.pstdev(others) or 1e-6
        z = abs(area - mean) / stdev
        if z < 3.0:
            return _zero("size_anomaly", weight, f"z={z:.2f}")
        score = min(1.0, (z - 3.0) / 5.0)
        return RuleSignal(
            name="size_anomaly",
            weight=weight,
            score=score,
            explanation=(
                f"Parcel size {area:.2f}ha is z={z:.1f} from district mean {mean:.2f}ha."
            ),
        )
    except Exception:
        logger.exception("rule_size_anomaly_error")
        return _zero("size_anomaly", weight, "internal error")


def rule_watchlist_name(context: dict[str, Any]) -> RuleSignal:
    """Fires on fuzzy name match against the fraud watchlist."""
    weight = 20
    name = (context.get("owner_full_name") or "").strip()
    if not name:
        return _zero("watchlist_name", weight, "no owner name")
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT full_name, reason FROM fraud_watchlist"
            ).fetchall()
        worst = 0
        worst_reason = None
        for full_name, reason in rows:
            ratio = token_set_ratio(name, full_name)
            if ratio > worst:
                worst = ratio
                worst_reason = reason
        if worst <= 85:
            return _zero("watchlist_name", weight, f"max ratio {worst}")
        score = min(1.0, (worst - 85) / 15)
        return RuleSignal(
            name="watchlist_name",
            weight=weight,
            score=score,
            explanation=f"Name matches watchlist at {worst}% (reason: {worst_reason}).",
        )
    except Exception:
        logger.exception("rule_watchlist_name_error")
        return _zero("watchlist_name", weight, "internal error")


def rule_consideration_anomaly(context: dict[str, Any]) -> RuleSignal:
    """Fires when consideration / hectare is extreme vs. district median."""
    weight = 15
    consideration = context.get("consideration")
    parcel_id = context.get("parcel_id")
    if consideration is None or not parcel_id:
        return _zero("consideration_anomaly", weight, "missing inputs")
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT area_hectares, district_id FROM parcels WHERE parcel_id = ?",
                (parcel_id,),
            ).fetchone()
            if not row:
                return _zero("consideration_anomaly", weight, "parcel not found")
            area, district_id = float(row[0]), int(row[1])
            others = [
                float(r[0]) / max(float(r[1]), 1e-6)
                for r in conn.execute(
                    "SELECT t.consideration, p.area_hectares "
                    "FROM transfers t JOIN parcels p ON p.parcel_id = t.parcel_id "
                    "WHERE p.district_id = ? AND t.consideration IS NOT NULL "
                    "AND t.consideration > 0",
                    (district_id,),
                ).fetchall()
            ]
        if len(others) < 5 or area <= 0:
            return _zero("consideration_anomaly", weight, "insufficient district norm")
        median = statistics.median(others)
        ratio = float(consideration) / area
        if median <= 0:
            return _zero("consideration_anomaly", weight, "zero median")
        deviation = abs(ratio - median) / median
        if deviation < 2.0:
            return _zero("consideration_anomaly", weight, f"deviation={deviation:.2f}")
        score = min(1.0, (deviation - 2.0) / 5.0)
        return RuleSignal(
            name="consideration_anomaly",
            weight=weight,
            score=score,
            explanation=(
                f"UGX/ha {ratio:,.0f} deviates {deviation*100:.0f}% from district median "
                f"{median:,.0f} UGX/ha."
            ),
        )
    except Exception:
        logger.exception("rule_consideration_anomaly_error")
        return _zero("consideration_anomaly", weight, "internal error")


def rule_nira_kyc(context: dict[str, Any]) -> RuleSignal:
    """Fires when the receiving owner has no verified KYC."""
    weight = 25
    owner_id = context.get("to_owner_id") or context.get("owner_id")
    if not owner_id:
        return _zero("nira_kyc", weight, "no owner")
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT kyc_status FROM owners WHERE id = ?",
                (owner_id,),
            ).fetchone()
        if not row:
            return _zero("nira_kyc", weight, "owner not found")
        status = str(row[0])
        if status == "VERIFIED":
            return _zero("nira_kyc", weight, "KYC verified")
        score_map = {"PENDING": 0.6, "EXPIRED": 0.8, "REJECTED": 1.0}
        return RuleSignal(
            name="nira_kyc",
            weight=weight,
            score=score_map.get(status, 0.5),
            explanation=f"Receiving owner KYC status is {status}.",
        )
    except Exception:
        logger.exception("rule_nira_kyc_error")
        return _zero("nira_kyc", weight, "internal error")


RuleFn = Callable[[dict[str, Any]], RuleSignal]

RULES: list[RuleFn] = [
    rule_geometry_overlap,
    rule_rapid_retransfer,
    rule_nin_reuse,
    rule_size_anomaly,
    rule_watchlist_name,
    rule_consideration_anomaly,
    rule_nira_kyc,
]


def run_all_rules(context: dict[str, Any]) -> list[RuleSignal]:
    return [rule(context) for rule in RULES]
