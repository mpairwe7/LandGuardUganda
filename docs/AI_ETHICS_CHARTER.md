# LandGuard AI Ethics Charter

**Effective date:** 25 June 2026 (pilot launch)
**Owner:** LandGuard Steering Committee (MoICT, MoLHUD, NITA-U, independent observer)
**Review cadence:** Quarterly; published amendments versioned in this repository.

LandGuard's fraud scorer (``app/fraud/``) is **decision support**, not a
decision-maker. This charter binds the team, the system, and the operating
districts to the principles below.

---

## 1. Human-in-the-loop is mandatory

The IsolationForest + rule combiner produces three recommendations:
``NONE``, ``FLAG``, ``BLOCK``. **None of them auto-freezes a parcel.**

- ``FLAG`` and ``BLOCK`` write a row to ``fraud_review_queue`` (state
  ``PENDING_REVIEW``) and emit a ``FRAUD_REVIEW_QUEUED`` audit event.
- Only a ``LAND_OFFICER`` or ``REGISTRAR`` calling ``POST
  /api/v1/fraud/review/{id}/affirm`` causes a parcel to be frozen. The
  audit chain records the reviewer's user_id and free-text notes.
- If no human reviews within 24 hours, ``scripts/escalate_pending_reviews.py``
  applies the recommended action under a clearly labelled
  ``FRAUD_AUTO_ESCALATED`` event so timelines distinguish "human decided"
  from "human did nothing".

A reviewer may NEVER affirm a flag they themselves filed; the resolver of a
citizen appeal must be a different role (``AUDITOR`` or a ``REGISTRAR``
other than the affirming officer).

## 2. Explainability is non-negotiable

Every alert surfaces, in plain English, the signals that fired and their
contribution to the risk score:

> "Risk score 82 (BLOCK)
>  • KYC unverified at NIRA (weight 25)
>  • Name matches fraud watchlist at 97% (weight 20)
>  • Parcel was transferred 4 times in 90 days (weight 20)"

No signal is "the model said so". The IsolationForest contribution is
disclosed as ``ml_anomaly_score`` separately and may not exceed 60 points
of the combined 100-point scale.

## 3. Right to appeal

Any citizen whose transfer is flagged or whose parcel is frozen because of
a fraud signal can file ``POST /api/v1/fraud/appeals`` with a written
statement. Appeals are resolved by an auditor or registrar — never by the
officer who affirmed the flag. Upholding an appeal automatically unfreezes
the parcel and emits a ``FRAUD_APPEAL_RESOLVED`` audit event.

We publish quarterly statistics on appeal volume, outcome split, and median
time-to-resolution.

## 4. Data minimisation

- The model is trained only on **transaction features** (timing, area,
  consideration), never on protected attributes (name, gender, ethnicity,
  district of birth).
- The watchlist rule (``rule_watchlist_name``) is a transparency tool: the
  watchlist is governed by a separate ``data/fraud-watchlist-governance.md``
  procedure and entries must cite a court order or named investigator. A
  watchlist match is necessary but not sufficient for a ``BLOCK``.
- Phone numbers used in USSD/SMS verification are SHA-256-hashed before any
  storage (``app/routers/ussd.py``).

## 5. Demographic parity audits

``scripts/fraud_parity_audit.py`` runs quarterly. It compares FLAG/BLOCK
rates across:

- District
- Tenure type (Mailo / Freehold / Leasehold / Customary)
- Gender (where NIRA provides it, with consent)

Any group whose flag rate exceeds 1.5× the global mean triggers a published
review. The audit itself emits a ``FRAUD_PARITY_AUDIT`` event so the
audit-of-the-audit is also tamper-evident.

If a parity breach is found, the affected rule's weight is set to zero
pending root-cause analysis; the scorer continues operating with the
remaining rules. This rollback is by design — the system fails *quiet*,
not silent.

## 6. Disclosure on the artefact

Every printed title certificate includes a footer:

> "LandGuard uses AI-assisted fraud screening on transfers involving this
>  parcel. AI screening is a decision-support tool, never the sole basis
>  for a custodial decision. Citizens may appeal any fraud-related action
>  at any District Land Office or via USSD *247*256*9#."

## 7. Model lineage

- The active model card is
  [`docs/model-cards/fraud-scorer.md`](./model-cards/fraud-scorer.md) —
  follows Mitchell et al. (FAT* 2019) structure, must be updated when
  ``SCORER_VERSION``, the feature list, the rule list, or the action
  thresholds change.
- ``scorer_version`` is recorded on every score row. Re-scoring with the
  same version is a no-op; re-scoring with a new version creates a new row
  and a ``FRAUD_RESCORED`` audit event.
- Training data, hyperparameters, and contamination rate are versioned
  alongside the model file (``app/fraud/training/isoforest-v1.joblib``).
- New scorer versions require a written go-live note signed by the
  LandGuard project lead AND an independent reviewer; the note is committed
  to ``docs/model-cards/``.

## 8. What this system will NEVER do

- Make a custodial decision (freeze, reject, escalate) without a recorded
  human review.
- Use immigration status, religious affiliation, political affiliation, or
  ethnic identity as a feature.
- Sell or share fraud-score data with a third party outside MoLHUD,
  NITA-U, or a Ugandan court of competent jurisdiction.
- Block a verification request from a citizen attempting to confirm their
  own parcel — even if that citizen is the subject of an open fraud review.

## 9. Sign-offs

| Role | Name | Date |
|---|---|---|
| LandGuard Project Lead | _to be signed_ | _2026-06-_ |
| MoLHUD Designate | _pending pilot MOU_ | _2026-06-_ |
| NITA-U Designate | _pending pilot MOU_ | _2026-06-_ |
| Independent Observer (Makerere CSL) | _pending letter_ | _2026-06-_ |
