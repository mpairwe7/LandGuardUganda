"""Train the IsolationForest model used by the fraud scorer.

The training set is synthetic-but-realistic: we generate a population
of "honest" transfers around the central district norm, then sprinkle
in a small fraction of obvious outliers (over-large parcels with very
low consideration, or rapid-fire repeat transfers).

Run once at project setup. The artifact is written to
``isoforest-v1.joblib`` and the scorer lazy-loads it from there.
"""

from __future__ import annotations

import logging
import math
import random
from collections.abc import Iterable
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

ARTIFACT_PATH = Path(__file__).resolve().parent / "isoforest-v1.joblib"


def _synthetic_samples(n: int = 2000, *, anomaly_rate: float = 0.05) -> Iterable[list[float]]:
    rng = random.Random(20260620)
    for _ in range(n):
        is_anomaly = rng.random() < anomaly_rate
        if is_anomaly:
            hours_since_last = rng.choice([0.5, 2.0, 6.0])
            consideration = rng.choice([1.0, 50.0, 1e9])
            area_ha = rng.choice([0.001, 9000.0])
            owner_age = rng.choice([0.0, 0.5])
            prior_parcels = rng.randint(15, 40)
            prior_disputes = rng.randint(3, 12)
            norm_z = rng.uniform(3.0, 6.0) * rng.choice([-1, 1])
        else:
            hours_since_last = rng.uniform(48.0, 5000.0)
            consideration = rng.lognormvariate(15.0, 1.2)  # UGX scale
            area_ha = abs(rng.gauss(2.0, 1.5)) + 0.05
            owner_age = abs(rng.gauss(600.0, 300.0))
            prior_parcels = rng.randint(0, 3)
            prior_disputes = rng.randint(0, 1)
            norm_z = rng.gauss(0.0, 0.8)
        hour = rng.randint(0, 23)
        weekday = rng.randint(0, 6)
        yield [
            hours_since_last,
            math.log1p(consideration),
            math.log1p(area_ha),
            owner_age,
            float(prior_parcels),
            float(prior_disputes),
            norm_z,
            float(hour),
            float(weekday),
        ]


def train_and_save() -> Path:
    # `X` follows the sklearn convention (uppercase for feature
    # matrices, lowercase y for labels). N806 is a false positive here.
    X = np.array(list(_synthetic_samples()))  # noqa: N806
    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=20260620,
    )
    model.fit(X)
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, ARTIFACT_PATH)
    logger.info("fraud_model_trained", extra={"path": str(ARTIFACT_PATH), "samples": len(X)})
    return ARTIFACT_PATH


if __name__ == "__main__":
    path = train_and_save()
    print(f"wrote {path}")
