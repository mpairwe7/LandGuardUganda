# Model Card — LandGuard Fraud Scorer

**Model name:** `isoforest-rules-v2-20260530`
**Card version:** 1.1 — drafted 2026-05-28, updated 2026-05-30 (v2 scorer)
**Maintainer:** LandGuard Uganda (`MAINTAINERS.md`)
**Status:** Pre-pilot baseline. Quantitative metrics in §6–§7 will be
re-measured against the Mityana pilot after first 90 days of real data.

> **v2 change (2026-05-30, no retrain):** the `district_norm_z` feature was
> being hardcoded to `0.0` at inference while `train.py` generated a real
> distribution for it — a train/serve skew defect. v2 computes the feature at
> inference from district transfer history
> (`features.py::_district_norm_z`). The IsolationForest artefact
> (`isoforest-v1.joblib`) is unchanged — it was always trained on the correct
> 9-feature layout. Version bumped per §7 (feature-pipeline change). Go-live
> note: [`isoforest-rules-v2-20260530.md`](./isoforest-rules-v2-20260530.md).

This card follows the structure of *Mitchell et al., Model Cards for Model
Reporting (FAT* 2019)* — adapted to a hybrid rules + anomaly-detection
system used at low-volume, low-stakes flagging (never custodial).

---

## 1. Model details

- **Architecture:** Hybrid scorer combining a deterministic rule engine
  (`backend/app/fraud/rules.py`) with an unsupervised IsolationForest
  anomaly detector (`backend/app/fraud/training/train.py`).
- **Combiner:** `risk_score = round( 60·ml_score + Σ (weightᵢ · ruleᵢ) )`,
  clamped to `[0, 100]` — see `backend/app/fraud/scorer.py::score_subject`.
- **IsolationForest hyperparameters:** `n_estimators=200`,
  `contamination=0.05`, `random_state=20260620` (deterministic seed).
- **Features (9, in fixed order):**
  `hours_since_last_transfer`, `log1p(consideration_UGX)`,
  `log1p(area_hectares)`, `owner_age_days`, `prior_parcels_for_owner`,
  `prior_disputes_for_owner`, `district_norm_z` (consideration-per-hectare
  z-score vs district), `hour_of_day`, `weekday`. Defined in
  `backend/app/fraud/features.py`.
- **Rules (7):** geometry overlap (w=30), rapid re-transfer (w=20),
  NIN re-use across multiple parcels (w=15), size anomaly vs district
  median (w=10), watchlist-name fuzzy match (w=20), consideration anomaly
  (w=15), NIRA KYC failure (w=25). Each rule returns a score in `[0,1]`
  and a plain-English explanation surfaced to the reviewing officer.
- **Output thresholds (one place, no env override):**
  - `risk_score < 40` → `NONE` — audit row only, no operator action
  - `40 ≤ risk_score < 75` → `FLAG` — review queue (P3, advisory)
  - `risk_score ≥ 75` → `BLOCK` — review queue (P1, urgent)
- **Versioning:** `SCORER_VERSION = "isoforest-rules-v2-20260530"`.
  Persisted on every score; reproducibility audits join on this field.
- **License:** MIT (model artefact ships with the source under the same
  licence as the rest of the repository).

## 2. Intended use

- **Primary:** Surface candidate transfers, titles, and parcel mutations
  that warrant a human reviewer's attention in a Ugandan District Land
  Office (initially Mityana). The output is **always advisory**; no
  custodial change happens without an officer's affirmation.
- **Primary users:** Land Officers (review queue), Auditors (post-hoc
  parity reports), the LandGuard maintainer team (drift monitoring).
- **Out of scope:**
  1. Any decision about ownership, status, or value of a parcel.
  2. Any decision about the credibility of a citizen as a person.
  3. Any automated FREEZE, hold, suspension, or denial of service.
  4. Use outside the Mityana pilot district without re-validation
     (district-specific training data, district-tuned thresholds).
  5. Real-time blocking at the public verifier — the verifier is read-only
     and never consults this scorer.

## 3. Factors

- **Relevant population:** adult land owners in Mityana District (~370 k
  residents per UBOS 2024). The pilot covers freehold, mailo, customary,
  and leasehold tenure types.
- **Subgroups monitored for parity:** district (initially trivially one),
  tenure type, and gender where NIRA returns it. Re-evaluated quarterly
  via `backend/scripts/fraud_parity_audit.py`.
- **Instrumentation factors not modelled:** literacy, language of the
  registry interaction (English vs Luganda), distance to district office,
  feature-phone vs smartphone access. These are deliberately **not** model
  inputs to avoid encoding socio-economic proxies for fraud risk.

## 4. Metrics

The model is unsupervised; classical precision/recall against a labelled
ground-truth set is not yet meaningful (no labelled corpus of confirmed
Ugandan land fraud exists publicly). We instead track operational metrics
that a human reviewer can act on:

| Metric | Target | Why |
|---|---|---|
| Review-queue throughput (median time-to-decision) | ≤ 4 working hours | Officer SLA per `docs/SLA_TARGETS.md` |
| Officer dismissal rate of `BLOCK` items | ≤ 30% | Sustained higher rate → false-positive drift; trigger threshold re-tune |
| Officer affirmation rate of `BLOCK` items | ≥ 50% | Sustained lower rate → ditto |
| Demographic parity ratio (any group / global mean) | ≤ 1.5× | Hard threshold from `docs/AI_ETHICS_CHARTER.md` §5 |
| Appeals upheld (citizen wins on review) | reported, not capped | Transparency metric; trend-watched |
| Score reproducibility on rescore | 100% same risk_score for same context | Determinism property; failure indicates drift in feature pipeline |

All metrics are computed off the audit ledger + `fraud_scores` table and
surface on the operator Grafana dashboard
(`monitoring/grafana/dashboards/landguard-sla.json` after Pack E1).

## 5. Evaluation data

**Pre-pilot status:** none. There is no labelled corpus of real Ugandan
land-fraud transactions and synthesising one would require ethics review
plus stakeholder consent. We have therefore made the conservative choice
to deploy with **rules-dominant scoring** (the ML contribution is capped
at 60 of the 100 risk-score points) and an explicit no-auto-FREEZE
invariant — see §8.

**Pilot-phase plan (Mityana, first 90 days):**

- Daily export of `fraud_scores` joined to `fraud_review_queue` outcomes,
  written to `evidence/fraud-audit/<date>/scores.csv` (committed to a
  read-restricted audit branch, not to `main`, until anonymisation review
  completes per DPPA-2019).
- 90-day re-fit using only confirmed-fraud labels from officer
  affirmations; threshold re-tune subject to a four-eyes review by the
  Independent Observer signer (see `docs/CUSTODY.md`).

## 6. Training data

- **Synthetic-but-realistic:** 2 000 samples generated by
  `backend/app/fraud/training/train.py::_synthetic_samples` with a fixed
  random seed (`20260620`). Each sample is one row of the 9-feature
  vector, drawn from a mixture of "honest transfer" distributions plus
  a 5% anomaly fraction with deliberately extreme values (sub-hour gaps,
  near-zero consideration on multi-hectare parcels, owners with double-
  digit prior parcels).
- **No real Ugandan citizen data was used to train this model.** The
  pre-pilot artefact (`isoforest-v1.joblib`) is a baseline shape, not a
  generalisation of any real population. This is a deliberate ethical
  choice: training a custodial-adjacent model on unconsented citizen
  data before the pilot has stakeholder sign-off would violate the AI
  Ethics Charter and DPPA-2019.
- **Bias surface:** the synthetic distribution is uniform across the
  conceptual subgroups in §3 (no encoded socio-economic priors), but
  cannot guarantee parity in deployment — that is what §7 monitors.

## 7. Quantitative analyses

**Pre-pilot:** Held-out synthetic-data anomaly recovery (sklearn
`IsolationForest.score_samples` on a fresh `_synthetic_samples()` draw)
recovers planted anomalies at ~78% rate at the `risk_score ≥ 75` cutoff.
This is *not* a generalisation claim — only evidence that the model
distinguishes the synthetic anomaly shape it was trained against.

**Pilot-phase reporting:** quarterly via the parity-audit script:

```
docker compose exec backend python scripts/fraud_parity_audit.py
```

Produces `evidence/fraud-parity/<timestamp>/report.md` — flag rate by
district, tenure type, and gender, plus the global mean. Any group whose
flag rate exceeds 1.5× the global mean triggers a **rule re-weight to
zero** for the offending signal until investigated. This is enforced
by code review, not by an automatic mutation — to avoid a feedback loop
where the model edits itself to dodge the audit.

## 8. Ethical considerations — *the load-bearing section*

> **No auto-FREEZE.**
> `app/fraud/worker.py` only writes to `fraud_review_queue`. A parcel
> may become `FROZEN` only via `FRAUD_HUMAN_AFFIRMED` (officer
> affirmation) or `FRAUD_AUTO_ESCALATED` (24-h timeout, clearly labelled
> in the audit chain). Anything else violates the AI Ethics Charter.

This invariant is enforced in three places that must all agree:

1. `backend/app/fraud/worker.py:_act_on_score` — the only writer to the
   review queue; it never mutates parcel status.
2. `backend/scripts/escalate_pending_reviews.py` — the timeout path;
   emits `FRAUD_AUTO_ESCALATED` as a distinct event type so the audit
   ledger's reader can tell a machine-applied freeze from a human one.
3. `contracts/test/MerkleParity.t.sol` + `backend/tests/test_fraud_review_workflow.py`
   — cross-checks: any new code path that flips parcel status must
   travel through one of those two event types or the test suite fails.

Additional safeguards:

- **Plain-language explanation per alert:** every `RuleSignal.explanation`
  field is human-readable English (and queued for Luganda translation
  before the pilot) — no opaque scores reach the citizen.
- **Right of appeal:** `POST /api/v1/fraud/appeals` opens a parallel
  review that bypasses the originating officer and is logged separately.
- **Audit-grade traceability:** every score is hashed and committed to
  the per-district audit chain; the chain is anchored on a public chain
  every 5 min or 100 events. A retroactive change to a score is therefore
  publicly detectable.
- **Quarterly parity audit:** see §4 and `scripts/fraud_parity_audit.py`.
- **Human override is one-click:** the officer console exposes a
  dismiss action that requires a short typed justification, also audited.

## 9. Caveats and recommendations

- The model is **unsupervised + rule-dominant**. Treat its outputs as
  *attention pointers*, never as evidence of wrongdoing.
- ML scores can shift after a model refit. The `scorer_version` field
  pinned on every persisted score lets reviewers compare like-with-like.
- Rule weights and thresholds are calibrated to the pre-pilot synthetic
  distribution. Expect a re-tune after 90 days of pilot data. The
  re-tune procedure is a four-eyes review (LandGuard maintainer +
  Independent Observer signer).
- This card MUST be updated when any of the following changes:
  `SCORER_VERSION`, feature list, rule list, action thresholds,
  audit-event taxonomy, or the parity-audit cadence.
- If the synthetic training data is replaced with real data, this card
  reverts to draft and the model name receives a new version suffix.

---

**See also:** `docs/AI_ETHICS_CHARTER.md`, `docs/GOVERNANCE.md`,
`docs/STANDARDS_ALIGNMENT.md` (NIST AI RMF + ISO 42001 mapping),
`backend/scripts/fraud_parity_audit.py`,
`backend/scripts/escalate_pending_reviews.py`.
