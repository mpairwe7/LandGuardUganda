# Fraud-scorer parity audit — pre-pilot baseline

**Generated:** 2026-05-28T06:49:46Z
**Repo commit:** `6231225`
**Scorer version:** `isoforest-rules-v1-20260620`
**Script:** `backend/scripts/fraud_parity_audit.py`
**Raw JSON:** [`report.json`](./report.json)

## What this is

The quarterly demographic-parity audit mandated by
[`docs/AI_ETHICS_CHARTER.md` §5](../../../docs/AI_ETHICS_CHARTER.md) and the
[fraud-scorer model card](../../../docs/model-cards/fraud-scorer.md) §4.
Each run compares the FLAG/BLOCK rate of every subgroup (district, tenure
type, gender-where-known) against the global mean. A subgroup whose rate
exceeds **1.5× the mean** triggers an investigation under the AI Ethics
Charter.

> **Pre-pilot caveat.** This run was executed against a synthetic dataset
> (60 transfers, seeded by a deterministic generator) — no real Ugandan
> citizen data was used. The output proves the audit pipeline is wired
> end-to-end; meaningful production parity numbers will be re-measured
> after the first 90 days of the Mityana pilot. See the model card §5
> and §6 for the evidence plan.

## Reproduce

```bash
# From the repo root, with backend deps synced.
cd backend
uv run python scripts/seed_districts.py
uv run python scripts/seed_demo.py
# (this report's synthetic transfer set is the deterministic random.seed=20260620
# fixture in evidence/fraud-parity/_synth_transfers.py — see notes below)
uv run python scripts/fraud_parity_audit.py > /tmp/parity.json
```

The audit also emits a `FRAUD_PARITY_AUDIT` event into the per-district
audit chain so the audit itself is tamper-evidently recorded; the next
anchor batch commits its hash on-chain.

## Headline numbers

- **Total transfers measured:** 60
- **Global flag rate (FLAG ∪ BLOCK):** 18.13 %
- **Districts exceeding 1.5× the mean:** **2** (districts 3 and 4)
- **Tenure types exceeding 1.5× the mean:** 0
- **Gender groups exceeding 1.5× the mean:** 0 (gender unknown for all
  synthetic owners — NIRA will populate this in pilot phase)
- **Appeals filed:** 0 (no real users)

## Per-district breakdown

| District ID | Total transfers | Flagged | Flag rate | Ratio to global mean | Exceeds 1.5× threshold |
|---:|---:|---:|---:|---:|:---:|
| 1 (Kampala CC) | 15 | 0 | 0.000 | 0.000 | — |
| 2 (Wakiso) | 6 | 1 | 0.167 | 0.919 | — |
| 3 (**Mityana — pilot**) | 28 | 8 | 0.286 | 1.576 | ⚠ alert |
| 4 (Mukono) | 11 | 3 | 0.273 | 1.504 | ⚠ alert |

## Per-tenure breakdown

| Tenure | Total | Flagged | Flag rate | Ratio | Exceeds threshold |
|---|---:|---:|---:|---:|:---:|
| CUSTOMARY | 13 | 2 | 0.154 | 0.849 | — |
| FREEHOLD  | 13 | 3 | 0.231 | 1.273 | — |
| LEASEHOLD | 11 | 1 | 0.091 | 0.501 | — |
| MAILO     | 23 | 6 | 0.261 | 1.439 | — |

## What the alerts mean (and what they don't)

The 1.5× ratio in districts 3 and 4 is an artefact of the **deliberately
skewed synthetic distribution** used to populate this baseline — the
synth seed concentrates anomalous transfers in those two districts so the
audit pipeline has something interesting to detect. It is **not** a
finding about real Ugandan land transactions.

Under live pilot conditions, the same alert would trigger:

1. The originating rules' weights are zeroed for the flagged subgroup
   until investigation completes (`docs/AI_ETHICS_CHARTER.md` §5).
2. A four-eyes review by the LandGuard maintainer + Independent
   Observer signer before any threshold or weight change ships
   (`docs/CUSTODY.md`).
3. The investigation report is committed to `evidence/fraud-parity/` and
   anchored on the audit chain.

## Sign-off chain (live phase)

The pilot-phase parity audit will be co-signed by:

| Role | Owner | Status |
|---|---|---|
| LandGuard maintainer | _pending PGP key publication (Pack B3)_ | — |
| Independent Observer (Makerere CSL) | _pending pilot MOU_ | — |
| District Land Board chair (Mityana) | _pending pilot MOU_ | — |

Once the first live audit runs in production, this evidence directory
will contain one report per quarter following the naming convention
`evidence/fraud-parity/<UTC-timestamp>/`.
