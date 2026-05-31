# Post-submission patches — 2026-05-28

> The PDF / DOCX / HTML renders in this directory are the **frozen
> submission packet** as submitted on 2026-05-26. Between submission
> and the 25 June 2026 showcase, four tagged releases shipped against
> the same Crane Cloud deployment via the documented CI/CD pipeline.
> This file is the audit-grade record of those changes; everything in
> it is verifiable against the public Git history and the live deploy.

## Live deploy at time of writing

- **Backend (Crane Cloud RENU-01):** <https://landguard-backend-d1e66f33.renu-01.cranecloud.io>
- **Frontend (Crane Cloud RENU-01):** edge IP-gated; CI runner is allowlisted, panel laptop will need to be too on 25 June
- **Active tag:** `v0.2.3-server-header` → image `landwind/landguard-uganda-{backend,frontend}:0.2.3-server-header-9678d7c`
- **Public hardening probe:** **23 / 23 PASS** (see `scripts/probe_security_headers.sh`)
- **Backend pytest:** **51 / 51** passing (was 32 / 32 at submission)
- **Frontend vitest:** **84 / 84** passing (suite was empty at submission)

## Releases since 2026-05-26

| Tag | Commit | Headline |
|---|---|---|
| `v0.2.0-routetest` | `7f29a46`, `45d90aa` | Cross-language Merkle parity tests + offline verifier + showcase evidence pack (model card, fraud-parity audit, Lighthouse a11y 100/100, route-test 43/43) |
| `v0.2.1-prodfix` | `4f77fdf` | Public-verifier seeded-title fix + `/fraud/reviews` 500 fix + slash-in-path-param fix (forward + backward compatible — no DB wipe needed) |
| `v0.2.2-hardening` | `fbc4536` | Pack F: `SecurityHeadersMiddleware` (HSTS/X-CTO/X-Frame/Referrer/COOP/Permissions/CSP), LIKE-injection escape, `/readyz` enrichment (fraud_model + audit_chain) |
| `v0.2.3-server-header` | `9678d7c` | Dockerfile `--no-server-header` so the SecurityHeadersMiddleware "Server: landguard" is the only one (uvicorn was overriding) |
| `v0.2.4-pack-g` | PR #25, #26–#29 | Pack G fraud-integrity hardening (fail-closed approval gate, escalation-never-freezes, replica-safe scheduler, revived `district_norm_z` ML feature, prod-safety key check) + full Dependabot backlog cleared (redis 7, uvicorn 0.48, frontend majors, `oven/bun` 1.3) |

Full details + commit-by-commit breakdown: **[`CHANGELOG.md`](../CHANGELOG.md)**
(top-of-file entry covers this whole cascade).

### 2026-05-31 update — `v0.2.4-pack-g`

- **Active tag now `v0.2.4-pack-g`**; backend pytest **62 / 62**, frontend
  vitest **84 / 84**, Merkle parity **48 / 48**.
- **Pack G** closed critical gaps found in a fresh app-flow audit (beyond the
  published roadmap): a fail-closed fraud-approval gate, an
  escalation-never-freezes fix that makes the **no-auto-FREEZE invariant
  absolute**, a replica-safe scheduler that actually runs the 24h escalation
  and the quarterly parity audit, horizontal worker scaling, a revived ML
  feature (train/serve skew), and a prod-safety check for the dev signing key.
- **This release deliberately refreshes the dependency tree** (redis 7,
  uvicorn 0.48, and the frontend majors incl. `oven/bun` 1.3) — it supersedes
  the Pack-F-era "No new dependencies" note below. The five public claims and
  the dual-Merkle equivalence rule are unchanged.

## What changed in the audit-grade artefacts

These are all additive — the submitted documents remain accurate as a
snapshot.

| New evidence | Path | What it shows |
|---|---|---|
| Local route exercise | `evidence/route-tests/20260528T073903Z/` | 43/43 backend + frontend routes pass against the locally-built Docker stack |
| Production regression | `evidence/deployment-tests/20260528T081451Z/` | 26/26 routes pass on Crane Cloud + the three bugs that prompted v0.2.1 |
| Fraud-parity audit | `evidence/fraud-parity/20260528T064946Z/` | Real audit run (60 synthetic transfers) — AI Ethics Charter §5 evidence |
| Lighthouse post-fix | `evidence/lighthouse/20260528T070440Z/` | A11y 100/100 on all four audited pages after the layout.tsx skip-link fix |
| Cross-language Merkle fixture | `contracts/test/merkle-parity.json` | 10-case canonical fixture consumed by Python, TS, Solidity |
| Fraud-scorer model card | `docs/model-cards/fraud-scorer.md` | Mitchell-et-al. structure; NIST AI RMF / ISO 42001 evidence |
| Maintainer PGP ceremony | `docs/security/KEYGEN_CEREMONY.md` | Reproducible keygen + revocation procedure |

The original submission's `docs/audit/AUDIT_PACKAGE.md` and
`docs/audit/CODEBASE_MAP.md` have been extended in-place to list these
artefacts (see their headers for the date of last revision).

## What did NOT change

- **No on-chain redeployment.** The mock-provider posture on Crane Cloud
  is unchanged; Sepolia deployment remains a planned post-showcase
  graduation per Pack C of the closure plan.
- **No data wipe on Crane Cloud.** The v0.2.1 verifier fallback was
  designed so legacy seeded titles verify without re-seeding.
- **No changes to the five public claims, the no-auto-FREEZE invariant,
  or the cross-language proof equivalence rule.** Pack A *added tests
  that pin* the equivalence rule; the rule itself is unchanged.
- **No new dependencies.** Pack F's middleware uses only stdlib +
  existing FastAPI; Pack A's TS tests use the existing Vitest
  devDependency.

## Reproduction

```bash
# Confirm the live hardening posture (4 endpoints × 7 checks + readyz).
BACKEND=https://landguard-backend-d1e66f33.renu-01.cranecloud.io \
  bash scripts/probe_security_headers.sh
# expect: PASS: 23  FAIL: 0

# Confirm cross-language Merkle parity end-to-end (3 language paths).
forge test --match-contract MerkleParity                  # Solidity
cd frontend && bun run test                               # TypeScript (Vitest, 84/84)
cd .. && python scripts/verify_offline.py \
  --parity contracts/test/merkle-parity.json              # Python (48/48 proofs)

# Confirm a seeded title verifies via the parcel_id fallback.
curl -sX POST https://landguard-backend-d1e66f33.renu-01.cranecloud.io/api/v1/verify/title \
  -H 'Content-Type: application/json' \
  -d '{"title_no":"MITYANA/V1/20260001"}'
# expect: { "valid": true, "anchor_status": "CONFIRMED", ... }
```
