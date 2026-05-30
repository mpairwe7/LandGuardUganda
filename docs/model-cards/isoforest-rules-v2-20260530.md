# Scorer go-live note — `isoforest-rules-v2-20260530`

**Date:** 2026-05-30
**Supersedes:** `isoforest-rules-v1-20260620`
**Model card:** [`fraud-scorer.md`](./fraud-scorer.md)
**Charter reference:** AI Ethics Charter §7 (model lineage; new versions
require a written go-live note signed by the project lead **and** an
independent reviewer).

## What changed

- **Bug fixed — train/serve skew on `district_norm_z`.** At inference,
  `features.py` hardcoded the 7th feature (`district_norm_z`, the
  consideration-per-hectare z-score vs. the parcel's district) to `0.0`,
  while the training generator (`train.py`) drew it from a real distribution
  (≈`N(0, 0.8)` for honest samples, `±[3,6]` for planted anomalies). The model
  therefore learned to use a signal it never actually received in production.
- **Fix:** `features.py::_district_norm_z` now computes the feature from
  district transfer history at inference (≥5 comparable transfers required;
  clamped to `[-10, 10]`). Falls back to `0.0` only when the district lacks
  enough data — the same baseline the model treats as "normal".

## What did NOT change

- **No retrain.** The IsolationForest artefact `isoforest-v1.joblib` is
  byte-for-byte unchanged; it was always trained on the correct 9-feature
  layout (`random_state=20260620`, `contamination=0.05`, `n_estimators=200`).
- Rule set, weights, combiner formula, and the `NONE/FLAG/BLOCK` thresholds
  (`<40 / 40–74 / ≥75`) are unchanged.
- The no-auto-FREEZE invariant and the human-in-the-loop workflow are
  unchanged (and the 24h escalation no longer freezes — see charter §1/§8).

## Impact

- Subjects scored under v1 retain their v1 rows; new scores carry the v2
  version. The approval gate re-scores any transfer whose latest score is not
  at the current version, so re-scoring happens lazily and is audit-logged
  (`FRAUD_RESCORED`).
- Expected effect: modest increase in sensitivity to price-per-hectare
  outliers that v1 silently ignored. To be re-measured against pilot data.

## Sign-offs

| Role | Name | Date |
|---|---|---|
| LandGuard Project Lead | _to be signed_ | _2026-06-_ |
| Independent Reviewer (Makerere CSL) | _pending letter_ | _2026-06-_ |
