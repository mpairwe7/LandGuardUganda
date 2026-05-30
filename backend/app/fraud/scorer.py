"""IsolationForest + rule combiner — produces final fraud scores.

The model file is built once by ``scripts/train_fraud_model.py`` and
lazy-loaded on first use. If the file is missing, we fall back to a
rules-only score so the demo still works even on a clean checkout.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.database import get_connection
from app.fraud.features import assemble_features
from app.fraud.rules import RuleSignal, run_all_rules
from app.util.metrics import fraud_blocks_total, fraud_scores_total

logger = logging.getLogger(__name__)

# v2 (2026-05-30): no model retrain — the `district_norm_z` feature was being
# hardcoded to 0.0 at inference (a serving-time defect) while training used a
# real distribution for it. v2 populates the feature, removing train/serve
# skew. Version bumped per AI Ethics Charter §7 (feature-pipeline change).
SCORER_VERSION = "isoforest-rules-v2-20260530"
_MODEL_PATH = Path(__file__).resolve().parent / "training" / "isoforest-v1.joblib"

_MODEL: Any | None = None


def _maybe_load_model() -> Any | None:
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    if not _MODEL_PATH.exists():
        return None
    try:
        import joblib

        _MODEL = joblib.load(_MODEL_PATH)
        logger.info("fraud_model_loaded", extra={"path": str(_MODEL_PATH)})
        return _MODEL
    except Exception:
        logger.exception("fraud_model_load_failed")
        return None


@dataclass(frozen=True)
class FraudScore:
    risk_score: int  # 0–100
    recommended_action: str  # "NONE" | "FLAG" | "BLOCK"
    signals: list[RuleSignal]
    ml_score: float | None  # IsolationForest anomaly score, normalised
    scorer_version: str = SCORER_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "recommended_action": self.recommended_action,
            "signals": [s.to_dict() for s in self.signals],
            "ml_score": self.ml_score,
            "scorer_version": self.scorer_version,
        }


def score_subject(context: dict[str, Any]) -> FraudScore:
    """Compute a fraud score for one subject.

    ``context`` must include enough identifiers for the rules to look
    things up: ``parcel_id``, ``to_owner_id`` (or ``owner_id``),
    ``consideration``, ``area_hectares``, ``owner_full_name``.
    """
    signals = run_all_rules(context)
    rules_score = sum(s.weight * s.score for s in signals)

    model = _maybe_load_model()
    ml_score: float | None = None
    if model is not None:
        try:
            features = assemble_features(context)
            vec = np.array([features])
            # IsolationForest: lower score == more anomalous. Convert to [0,1].
            raw = model.score_samples(vec)[0]
            # Normalise — empirical: typical normal samples ~ -0.4, outliers < -0.55.
            ml_score = max(0.0, min(1.0, (-raw - 0.4) / 0.3))
        except Exception:
            logger.exception("isoforest_score_failed")
            ml_score = None

    ml_component = 60.0 * (ml_score or 0.0)
    risk_score = int(round(min(100.0, ml_component + rules_score)))

    if risk_score >= 75:
        action = "BLOCK"
    elif risk_score >= 40:
        action = "FLAG"
    else:
        action = "NONE"

    score = FraudScore(
        risk_score=risk_score,
        recommended_action=action,
        signals=[s for s in signals if s.fired()],
        ml_score=ml_score,
    )
    fraud_scores_total.labels(action=action).inc()
    if action == "BLOCK":
        fraud_blocks_total.inc()
    return score


def persist_score(
    *,
    subject_type: str,
    subject_id: str,
    score: FraudScore,
) -> None:
    """Idempotent on (subject_type, subject_id, scorer_version)."""
    payload = json.dumps([s.to_dict() for s in score.signals], default=str)
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO fraud_scores "
            "(id, subject_type, subject_id, risk_score, signals, "
            " recommended_action, scored_at, scorer_version) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                subject_type,
                subject_id,
                score.risk_score,
                payload,
                score.recommended_action,
                time.time(),
                score.scorer_version,
            ),
        )
        conn.commit()


def latest_score(subject_type: str, subject_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT risk_score, signals, recommended_action, scored_at, scorer_version "
            "FROM fraud_scores WHERE subject_type = ? AND subject_id = ? "
            "ORDER BY scored_at DESC LIMIT 1",
            (subject_type, subject_id),
        ).fetchone()
    if not row:
        return None
    return {
        "risk_score": int(row[0]),
        "signals": json.loads(row[1]),
        "recommended_action": str(row[2]),
        "scored_at": float(row[3]),
        "scorer_version": str(row[4]),
    }
