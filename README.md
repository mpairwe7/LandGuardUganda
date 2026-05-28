# LandGuard Uganda

**Blockchain-Enhanced Land Administration & Titling Support System**
A prototype submission to the **Uganda MoICT&NG National Innovator Registry** — showcase date **25 June 2026**.

> Land records that no one can fake. Verified by anyone, anywhere — from a smartphone, a feature phone, or a printed certificate.

## Why this exists

Roughly **60% of Uganda's land is unclear or contested in ownership** (UN-Habitat, 2024).
Double-titling, ghost owners, and forged signatures drive disputes that can take
decades to resolve in court. The existing National Land Information System (NLIS)
is a database — if someone alters a record, only that database knows. Citizens
have no way to prove their title's authenticity to a buyer, a bank, or a journalist
without paying a registrar.

LandGuard fixes this by making land records **cryptographically tamper-evident**
and **publicly verifiable** — without putting personal data on a public chain,
without smartphone-only access, and without single-key custody.

## The five claims (and the receipts)

| Claim | Where to look |
|---|---|
| **1. Tamper-evident at national scale** | `backend/app/audit/ledger.py` — per-district hash-chained ledger. Every state change writes one row; `row_hash = sha256(prev_hash + payload_hash)`. Walk-verifier in `audit/verifier.py`. |
| **2. Anchored on a public blockchain at pennies per batch** | `contracts/src/LandRegistryAnchor.sol` — every 5 min or 100 events per district. Sorted-pair keccak Merkle, matched byte-for-byte by `compute_merkle_root_evm` in Python and `verifyMerkleProofEvm` in TypeScript. See ADR-0001. |
| **3. No single key can anchor** | `contracts/src/MultiSigRegistrar.sol` — 3-of-5 named signers (MoLHUD, NITA-U, District Land Board, LandGuard, Independent Observer). See `docs/CUSTODY.md`. |
| **4. AI flags, humans decide** | `backend/app/fraud/worker.py` writes to `fraud_review_queue`; the parcel is frozen **only** when a Land Officer affirms via `POST /api/v1/fraud/review/{id}/affirm`. Citizens can appeal. See `docs/AI_ETHICS_CHARTER.md`. |
| **5. Verifiable from a feature phone** | `backend/app/routers/ussd.py` — Africa's Talking-compatible USSD shortcode `*247*256#` and SMS pathway. ~UGX 60/verification. See `docs/USSD_DEPLOYMENT.md`. |

## Architecture at a glance

```
                          ┌─────────────────────────┐
                          │  Citizens (smartphone)  │
                          │  Citizens (USSD/SMS)    │
                          │  Public verifier (any)  │
                          └────────────┬────────────┘
                                       │
                  ┌────────────────────┼────────────────────┐
                  ▼                                          ▼
   ┌────────────────────────────┐         ┌────────────────────────────┐
   │  Next.js 16 PWA + Officer  │         │  USSD/SMS gateway          │
   │  Console (Bun, Tailwind 4) │         │  (Africa's Talking)        │
   └─────────────┬──────────────┘         └─────────────┬──────────────┘
                 └──────────────┬───────────────────────┘
                                ▼
   ┌────────────────────────────────────────────────────────────────────┐
   │  FastAPI 0.111 backend (Python 3.12, uv)                           │
   │  ├─ Zero-trust JWT auth (RS256/HS256)                              │
   │  ├─ Hash-chained audit ledger (per-district)                       │
   │  ├─ AI fraud scorer + human-in-the-loop review queue               │
   │  ├─ NIRA client (mock | live)                                      │
   │  └─ Anchor service (CircuitBreaker-protected)                      │
   └────────────────────────────┬───────────────────────────────────────┘
                                ▼
   ┌────────────────────────────────────────────────────────────────────┐
   │  MultiSigRegistrar.sol  →  LandRegistryAnchor.sol                  │
   │  (3-of-5 named signers)    (immutable on-chain anchor)             │
   │  Anvil locally · Sepolia · any EVM chain                           │
   └────────────────────────────────────────────────────────────────────┘
```

## What's inside

| Path | Contents | Setup guide |
| --- | --- | --- |
| **`backend/`** | FastAPI service: routes, audit ledger, fraud scorer with human-in-the-loop, NIRA client, blockchain client (mock/anvil/sepolia/multisig), USSD + SMS verifier | [`backend/README.md`](./backend/README.md) |
| **`frontend/`** | Next.js 16 (Bun) UI: public verifier, citizen portal, surveyor map drawer, officer review queue, registrar console, auditor console, demo control panel, printable title certificate | [`frontend/README.md`](./frontend/README.md) |
| **`contracts/`** | `LandRegistryAnchor.sol` + `MultiSigRegistrar.sol` with Foundry tests, OpenZeppelin AccessControl + Pausable | [`contracts/README.md`](./contracts/README.md) |
| **`docs/`** | Architecture, requirements + evaluation mapping, design system, custody, AI ethics, MOU template, audit package, threat model, USSD deployment, ADRs | — |
| **`scripts/`** | Cross-cutting dev/demo orchestration | — |
| **`monitoring/`** | Prometheus + Grafana + OTel collector configs | — |

## Documentation index

**Panel evaluators start here:**

0. **[`docs/SHOWCASE_EVALUATION_MAPPING.md`](./docs/SHOWCASE_EVALUATION_MAPPING.md)** — one-page map of the seven evaluation criteria to specific files, features, and reproducible evidence. Read this first if you have 5 minutes.

For an auditor, evaluator, or maintainer, in depth:

1. **[`docs/REQUIREMENTS.md`](./docs/REQUIREMENTS.md)** — system requirements, capacity targets, compliance posture.
2. **[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)** — full architecture, data flow, tenancy, fraud, resilience, observability, testing, migration paths.
3. **[`docs/DESIGN_SYSTEM.md`](./docs/DESIGN_SYSTEM.md)** — UI/UX contract.
4. **[`docs/IMPACT_EVIDENCE.md`](./docs/IMPACT_EVIDENCE.md)** — reproducible Lighthouse/axe/load-test evidence, user research plan, TCO model.
5. **[`docs/SLA_TARGETS.md`](./docs/SLA_TARGETS.md)** — SLOs, observability, incident response, DPPA §19 breach runbook.
6. **[`docs/STANDARDS_ALIGNMENT.md`](./docs/STANDARDS_ALIGNMENT.md)** — DPPA, NITA-U, ISO 42001, NIST AI RMF, OWASP ASVS, WCAG 2.2, World Bank LGAF, OpenHIE-Land.
7. **[`docs/audit/AUDIT_PACKAGE.md`](./docs/audit/AUDIT_PACKAGE.md)** — one-page index of artefacts + reproduction recipe.
8. **[`docs/audit/CODEBASE_MAP.md`](./docs/audit/CODEBASE_MAP.md)** — file-by-file inventory of the current repo state.
9. **[`docs/audit/THREAT_MODEL.md`](./docs/audit/THREAT_MODEL.md)** — STRIDE-style threat model.
10. **[`docs/TEAM.md`](./docs/TEAM.md)** — team, governance, capacity-building commitments.
11. **[`MAINTAINERS.md`](./MAINTAINERS.md)** — review thresholds and security-contact path.
12. **[`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md)** — Contributor Covenant 2.1.
13. **[`CHANGELOG.md`](./CHANGELOG.md)** — dated CVE/dep/architecture timeline.
14. **[`docs/AI_ETHICS_CHARTER.md`](./docs/AI_ETHICS_CHARTER.md)** — human-in-the-loop policy.
14b. **[`docs/model-cards/fraud-scorer.md`](./docs/model-cards/fraud-scorer.md)** — Mitchell-et-al. model card for the fraud scorer (NIST AI RMF / ISO 42001 evidence).
15. **[`docs/CUSTODY.md`](./docs/CUSTODY.md)** — 3-of-5 multi-sig signer plan.
16. **[`docs/GOVERNANCE.md`](./docs/GOVERNANCE.md)** — DPPA-2019 compliance posture.
17. **[`docs/USSD_DEPLOYMENT.md`](./docs/USSD_DEPLOYMENT.md)** — USSD pathway deployment guide.
17b. **[`docs/CRANE_CLOUD_DEPLOYMENT.md`](./docs/CRANE_CLOUD_DEPLOYMENT.md)** — Crane Cloud operator guide (clusters, API, secrets, troubleshooting). Adapted from `mpairwe7/MLOPS_V1`'s deployment doc.
18. **[`docs/moa-templates/MoLHUD-Mityana-Pilot-MOU.md`](./docs/moa-templates/MoLHUD-Mityana-Pilot-MOU.md)** — drop-in pilot MOU template.
19. **[`docs/adr/`](./docs/adr/)** — architecture decision records: 0001 dual-Merkle, 0002 zero-trust posture, 0003 regional-chain migration.
20. **[`DEMO_RUNBOOK.md`](./DEMO_RUNBOOK.md)** — 25 June 2026 showcase script + recovery procedures.
21. **[`QUICKSTART.md`](./QUICKSTART.md)** — five-minute local bring-up.

**Reproducible evidence scripts** (project-root `scripts/`):

| Script | Produces | Bound to |
|---|---|---|
| `bash scripts/generate_sbom.sh` | `evidence/sbom/*.json` (CycloneDX SBOMs + SHA-256) | `docs/IMPACT_EVIDENCE.md` §3.1 |
| `bash scripts/lighthouse_ci.sh` | `evidence/lighthouse/<ts>/*.json|.html` | `docs/IMPACT_EVIDENCE.md` §1.1 |
| `bash scripts/load_test.sh` | `evidence/load/<ts>/summary.json` | `docs/SLA_TARGETS.md` §2 |

**Deployment scripts** (run from your interactive shell):

| Script | What it does | Reference |
|---|---|---|
| `bash scripts/bootstrap_cranecloud.sh` | Logs into Crane Cloud, creates LandGuard project on RENU, deploys backend + frontend apps. Writes UUIDs + URLs to `/tmp/landguard-cranecloud-bootstrap.env` for the next script. Idempotent. | [`docs/CRANE_CLOUD_DEPLOYMENT.md`](./docs/CRANE_CLOUD_DEPLOYMENT.md) §"Three-command bootstrap" |
| `bash scripts/setup_github_secrets.sh` | Walks through setting the 8 GitHub secrets via `gh secret set --body -` (interactive, no echo). Auto-fills UUIDs from the bootstrap summary and known mpairwe7 defaults. | [`docs/CRANE_CLOUD_DEPLOYMENT.md`](./docs/CRANE_CLOUD_DEPLOYMENT.md) §5 |

## Five-minute setup

```bash
# 1. Bring up Postgres, Redis, local Anvil, deploy contract, start services.
docker compose --profile default up -d --build

# 2. Seed showcase state + train the fraud model.
docker compose exec backend python scripts/seed_districts.py
docker compose exec backend python scripts/seed_demo.py
docker compose exec backend python scripts/train_fraud_model.py

# 3. Mint dev tokens for each demo role.
docker compose exec backend python scripts/issue_dev_tokens.py
```

For the **production-posture demo** (3-of-5 multi-sig with auto co-signer):

```bash
MULTISIG_ENABLED=true docker compose --profile default --profile multisig up -d --build
```

Open <http://localhost:3000> · demo control panel at <http://localhost:3000/demo?demo=1>.

For Sepolia instead of Anvil:

```bash
export SEPOLIA_RPC_URL=...
export SEPOLIA_REGISTRAR_PRIVATE_KEY=0x...
docker compose -f docker-compose.yml -f docker-compose.sepolia.yml up -d --build
```

## Hosting & CI/CD (sovereign by default)

LandGuard hosts on **Crane Cloud** (Makerere AI Lab's Uganda-resident
Platform-as-a-Service) for sovereignty reasons documented in
[`docs/STANDARDS_ALIGNMENT.md`](./docs/STANDARDS_ALIGNMENT.md) §1.2.

| Concern | File |
|---|---|
CI/CD is split between **GitHub Actions** (canonical, fully automated)
and an **operator-led local path** via `infra/cranecloud/` (first-time
app creation, ad-hoc deploys, debugging).

| Concern | File |
|---|---|
| Operator-led deploy guide | [`infra/cranecloud/README.md`](./infra/cranecloud/README.md) |
| Operator-led deploy wrappers | [`infra/cranecloud/Makefile`](./infra/cranecloud/Makefile) |
| What gets deployed (image, port, env names) | [`infra/cranecloud/manifest.yaml`](./infra/cranecloud/manifest.yaml) |
| Per-environment templates | [`infra/cranecloud/environments/`](./infra/cranecloud/environments/) |
| **One-shot GitHub-secrets bootstrap** | [`scripts/setup_github_secrets.sh`](./scripts/setup_github_secrets.sh) |

GitHub Actions:

| Workflow | Trigger | Purpose |
|---|---|---|
| [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) | every PR + push to main | backend tests, forge tests, frontend build, OSV-Scanner, docker-build verify, SBOM artefact upload, axe-core accessibility |
| [`.github/workflows/build-push.yml`](./.github/workflows/build-push.yml) | push to main; `v*` tags; manual | builds + pushes images to `docker.io/${DOCKERHUB_USERNAME}/landguard-uganda-{backend,frontend}`; auto-dispatches deploy on `v*` tag |
| [`.github/workflows/deploy-cranecloud.yml`](./.github/workflows/deploy-cranecloud.yml) | dispatched by build-push.yml; or manual | direct curl to `api.cranecloud.io` (POST /users/login → PATCH /apps/{id}) — no CLI dep |
| [`.github/dependabot.yml`](./.github/dependabot.yml) | weekly Monday 06:00 Africa/Kampala | uv + npm + actions + docker dependency updates |

**Required GitHub secrets** (set once via `bash scripts/setup_github_secrets.sh`):

| Scope | Name | Source |
|---|---|---|
| Repository | `DOCKERHUB_USERNAME` | your Docker Hub username |
| Repository | `DOCKERHUB_TOKEN` | hub.docker.com → Account Settings → PATs (Read/Write/Delete) |
| `production` env | `CRANE_CLOUD_EMAIL` | Crane Cloud account email |
| `production` env | `CRANE_CLOUD_PASSWORD` | Crane Cloud account password |
| `production` env | `CRANE_CLOUD_BACKEND_APP_ID` | `cranecloud apps list` UUID for the backend |
| `production` env | `CRANE_CLOUD_FRONTEND_APP_ID` | `cranecloud apps list` UUID for the frontend |
| `production` env | `CRANE_CLOUD_BACKEND_URL` | optional — for `/healthz` polling |
| `production` env | `CRANE_CLOUD_FRONTEND_URL` | optional — for `/api/health` polling |

Same naming as `mpairwe7/OptiscanAI` so the same setup applies across
repos. The setup script reads each value via `read -s` (no echo) and
pipes to `gh secret set NAME --body -` (no argv exposure).

## Government readiness

- **MOU template** (`docs/moa-templates/MoLHUD-Mityana-Pilot-MOU.md`) — drop-in
  starting point for a 6-month Mityana pilot with MoLHUD + NITA-U + Independent
  Observer.
- **Custody plan** (`docs/CUSTODY.md`) — five named signers, three required;
  HSM-protected in production.
- **AI ethics charter** (`docs/AI_ETHICS_CHARTER.md`) — human-in-the-loop is
  mandatory, demographic parity audits quarterly, citizen appeals supported.
- **Auditor's package** (`docs/audit/AUDIT_PACKAGE.md`) — one-page index of
  what to look at and how to reproduce verification from scratch.
- **Threat model** (`docs/audit/THREAT_MODEL.md`) — assets, adversaries,
  mitigations.
- **DPPA-2019 compliance** (`docs/GOVERNANCE.md`) — DPO designation,
  right-to-erasure tombstones, NIN AES-GCM encryption at rest.

## Demo

The 25 June 2026 showcase has a tight 8–12 minute script with six acts:
hook → problem → anchor (with multi-sig) → human-in-the-loop fraud review →
audience verifies (smartphone + feature phone) → resilience. See
[`DEMO_RUNBOOK.md`](./DEMO_RUNBOOK.md).

## Verify a title offline

Anyone can verify a LandGuard title proof without our backend, our frontend,
or even chain access — just one Python file and `eth-utils`.

```bash
pip install eth-utils
python scripts/verify_offline.py --bundle title-proof.json --root 0xabc...
# PASS  leaf=0x...  root=0xabc...
```

The script ([`scripts/verify_offline.py`](./scripts/verify_offline.py)) inlines
the same sorted-pair keccak rule used by
[`LandRegistryAnchor.verifyProof`](./contracts/src/LandRegistryAnchor.sol),
[`app/audit/merkle.py::verify_merkle_proof_evm`](./backend/app/audit/merkle.py),
and [`lib/merkle.ts::verifyMerkleProofEvm`](./frontend/src/lib/merkle.ts).
The four implementations are cross-checked against
[`contracts/test/merkle-parity.json`](./contracts/test/merkle-parity.json) on
every CI run — drift surfaces immediately.

## Security posture (highlights)

- TLS via Caddy with strict CSP, STS, frame-ancestors=none.
- All containers run as non-root with `cap_drop: [ALL]`, no-new-privileges.
- Raw NINs encrypted at rest (AES-GCM); only `sha256(nin)` is queryable.
- Phone numbers (USSD/SMS) never logged in plaintext — only `sha256(msisdn)`.
- Rate-limited everywhere; public verifier capped at 20/min/IP.
- Idempotency keys on every mutating verb.
- JWT auth with RS256 OIDC in prod (`AUTH_MODE=oidc`).
- 3-of-5 multi-sig custody of on-chain registrar role.
- Smart-contract kill switch (`LandRegistryAnchor.pause()`) under
  `DEFAULT_ADMIN_ROLE`.

## Roadmap (post-showcase)

- Sign Mityana pilot MOU; engage one Ugandan academic partner as the
  fifth signer (Makerere CSL recommended).
- Replace mock NIRA with real NIRA API once MoICT&NG publishes the 2026 spec.
- Migrate from SQLite WAL to Postgres + PostGIS for >1M parcels.
- Move worker tier onto a dedicated process when daily transfers exceed
  10k/day.
- Independent third-party smart-contract audit (8 hours engagement, budget
  ~UGX 5M).
- UCC USSD shortcode assignment for the production verifier.
- Pilot launch in Mityana, Q4 2026.

## Contact

**LandGuard Uganda Team** · `mpairwelauben75@gmail.com`
