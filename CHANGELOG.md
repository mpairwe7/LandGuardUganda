# Changelog

Security-relevant changes, dependency bumps, and notable architectural
events. Audit-readable timeline. Entries are reverse-chronological.

The project follows the spirit of [Keep a Changelog](https://keepachangelog.com/);
versioning is calendar-style (`YYYY-MM-DD`) until 1.0.

---

## 2026-05-26 — CI/CD rewired to direct Crane Cloud HTTP API (OptiscanAI pattern)

The previous `deploy-cranecloud.yml` depended on the `cranecloud` Python
CLI inside the runner. That CLI requires an OS keyring backend
(D-Bus / SecretService) which GitHub-hosted runners don't provide, and
fighting the keyring with `PYTHON_KEYRING_BACKEND=null` plus token-file
seeding proved brittle across CLI versions.

The replacement, ported from `mpairwe7/OptiscanAI`'s production
`docker-publish.yml`, uses **direct curl calls to api.cranecloud.io**:

  1. `POST /users/login` with email+password in JSON body → JWT in
     `data.access_token`.
  2. `PATCH /apps/{app_id}` with `{"image": "<docker.io path>:<tag>-<sha7>"}`
     → triggers Crane Cloud pod rollover.
  3. `GET <public-url>/healthz` (or `/api/health`) polled for up to 5 min.

Why SHA-suffixed tags? Crane Cloud diffs the `image` field as a
string. PATCHing the same `:latest` or `:v0.1.0-showcase` tag is a
no-op. We push both the floating tag AND a `<tag>-<sha7>` variant on
every build; the deploy step PATCHes the SHA-suffixed form so every
push produces a fresh image string Crane Cloud sees as new.

Secret-name convention mirrors OptiscanAI:

  Repository-level (`gh secret set NAME --repo …`):
    DOCKERHUB_USERNAME, DOCKERHUB_TOKEN

  `production` environment (`gh secret set NAME --env production`):
    CRANE_CLOUD_EMAIL, CRANE_CLOUD_PASSWORD
    CRANE_CLOUD_BACKEND_APP_ID, CRANE_CLOUD_FRONTEND_APP_ID
    CRANE_CLOUD_BACKEND_URL, CRANE_CLOUD_FRONTEND_URL  (optional, for health-check)

`scripts/setup_github_secrets.sh` walks the operator through setting
all eight via `gh secret set NAME --body -` with `read -s` for the
value, so no secret value ever enters argv, history, or stdout. Use
`--rotate` to force-overwrite already-set values.

`.github/workflows/build-push.yml` simplified: no more
`vars.DOCKER_IMAGE_OWNER` override path; images go to
`docker.io/${DOCKERHUB_USERNAME}/landguard-uganda-{backend,frontend}`
directly. Auto-dispatches `deploy-cranecloud.yml` only on `v*` tag
pushes (`main`-branch pushes only build, never deploy — matches the
production-deploy posture in MAINTAINERS.md).

`production` GitHub environment created via
`gh api -X PUT repos/mpairwe7/LandGuardUganda/environments/production`.
Reviewer protection rules can be added in the GitHub UI later
(Settings → Environments → production → Required reviewers).

The previous CLI-based workflow + `infra/cranecloud/` Makefile path
remain available for operator-led local deploys (first-time app
creation, ad-hoc rollouts, debugging) but are no longer the canonical
CI path.

## 2026-05-25 — Pre-submission deliverables (axe spec, pentest scope, breach runbook)

- `frontend/e2e/accessibility.spec.ts` (new) — Playwright +
  `@axe-core/playwright` spec asserting zero critical / zero serious
  WCAG 2.2 AA violations across six citizen-critical routes. Findings
  attach as JSON to the Playwright HTML report. Bound to a new CI
  job in `.github/workflows/ci.yml` (`accessibility`) that builds the
  frontend, runs the production server, installs Playwright Chromium,
  executes the spec, and uploads the report as a 90-day artefact.
- `frontend/playwright.config.ts` (new) — standard Playwright config
  driving the spec; `BASE_URL` envvar drives the target (defaults to
  localhost prod build on :3031).
- Added `@axe-core/playwright` + `axe-core` to frontend devDeps.
- `docs/audit/PENTEST_SCOPE.md` (new) — OWASP ASVS L2 scope of work
  for the pilot-launch pen-test: in-scope surfaces (web/API, crypto
  invariants, smart contracts, deployment surface, UX), explicit
  out-of-scope list, five-phase methodology, deliverables,
  findings-classification SLAs, budget envelope (UGX 17–23M), retest
  cadence, vendor shortlist (Makerere CSL preferred).
- `docs/runbooks/dppa-breach-notification.md` (new) — DPPA-2019 §19
  72-hour breach-notification procedure: trigger criteria, hour-by-
  hour timeline, decision tree, role separation, containment
  procedures (PII / chain / multi-sig key), PDPO + SMS notification
  templates, audit-chain emission schema, quarterly drill cadence.
- `docs/audit/CODEBASE_MAP.md` §8 updated: closes four prior-known
  gaps (frontend/e2e, scripts/ root, SBOM, pentest scope, DPPA
  runbook) and re-states the remaining honest gaps.

## 2026-05-25 — Lighthouse baseline + a11y skip-link fix

- Generated the first measured Lighthouse baseline against a local
  production build (`evidence/lighthouse/20260525T143155Z/`). Per-page
  scores: P 75–81 / A11y 98 / BP 96 / SEO 100. Measurement environment
  documented in `SUMMARY.md` alongside reproduction commands; honest
  delta to targets called out in `docs/IMPACT_EVIDENCE.md` §1.1.
- Fixed the single failing accessibility audit (`skip-link`) by wrapping
  the page tree in `<main id="main">` in `frontend/src/app/layout.tsx`.
  The skip-link in the layout targets `#main`; the next Lighthouse run
  expected to score Accessibility = 100.
- Hardened `scripts/lighthouse_ci.sh` to work on sandboxed runners:
  prefer `npx` over `bunx` (bunx ENOTSUP on certain filesystems);
  auto-discover Chrome from `~/.cache/puppeteer/chrome-headless-shell`;
  pre-launch Chrome on a fixed devtools port with a writable
  `user-data-dir`; `--disable-storage-reset` to work around
  `Storage.getUsageAndQuota` not supported in chrome-headless-shell.

## 2026-05-25 — CI/CD switches to Docker Hub (reuses FYP/HSU secrets)

- `.github/workflows/build-push.yml` rewritten to push to
  `docker.io/<DOCKERHUB_USERNAME>/landguard-uganda-{backend,frontend}`
  instead of GHCR. Authenticates with `DOCKERHUB_USERNAME` +
  `DOCKERHUB_TOKEN` — the same secret names already configured for
  `Mpairwe7/FinalYearProject` and `Mpairwe7/HealthSyncUganda`, so no
  new secrets need to be created.
- `.github/workflows/deploy-cranecloud.yml` updated to pull from
  `docker.io/<owner>/...` rather than `ghcr.io/...`. Continues to use
  the same Crane Cloud secret names (`CRANECLOUD_TOKEN`,
  `CRANECLOUD_USER_ID`, `CRANECLOUD_PROJECT_ID`,
  `CRANECLOUD_BACKEND_APP_ID`, `CRANECLOUD_FRONTEND_APP_ID`) that
  HealthSyncUganda's pipeline uses.
- Optional repo-level override: set `vars.DOCKER_IMAGE_OWNER` to point
  at an organisation namespace (e.g. `landguardug`) instead of the
  personal Docker Hub user.

## 2026-05-25 — Crane Cloud CI/CD pipeline + SBOM evidence

- Added `.github/workflows/{ci,build-push,deploy-cranecloud}.yml` — three-
  workflow pipeline mirroring the HealthSync Uganda pattern: PR-gate CI,
  GHCR build-push, operator-led Crane Cloud rollout with hard-fail
  fallback to the local `make update-*` path.
- Added `.github/dependabot.yml` — weekly uv + npm + actions + docker
  scans, Africa/Kampala timezone.
- Added `infra/cranecloud/` — `manifest.yaml` (deploy contract),
  `Makefile` (deploy/update wrappers), `README.md` (operator guide),
  and three environment templates (staging / pilot / production) with
  explicit production-safety posture (blank `BACKEND_IMAGE_TAG`,
  `MULTISIG_ENABLED=true` mandatory, OIDC required).
- Generated first CycloneDX 1.5 SBOM bundle in `evidence/sbom/` —
  backend (139 KB), frontend (1.3 MB, 838 components with full
  provenance), contracts (submodule digest). Each file content-addressed
  with SHA-256.
- `scripts/generate_sbom.sh` made robust to React 19 peer-dep strictness
  via `--ignore-npm-errors`; added `scripts/_sbom_frontend_fallback.py`
  as a stdlib-only fallback when `cyclonedx-npm` is unavailable.
- `.gitignore` updated to include `infra/cranecloud/environments/*.env`
  and `evidence/{lighthouse,load,probes}/` (per-run artefacts), and to
  **un**-ignore `bun.lock` (required for reproducible CI + SBOM).

## 2026-05-25 — Showcase evaluation evidence pack

- `docs/SHOWCASE_EVALUATION_MAPPING.md` — one-page criterion→evidence map.
- `docs/IMPACT_EVIDENCE.md` — reproducible Lighthouse/axe/load methodology
  + TCO + user-research plan.
- `docs/SLA_TARGETS.md` — national-scale SLOs, observability + DPPA §19
  breach SLA.
- `docs/STANDARDS_ALIGNMENT.md` — DPPA / NITA-U / ISO 42001 / NIST AI RMF
  / OWASP ASVS / WCAG 2.2 / World Bank LGAF / OpenHIE-Land mapping.
- `docs/TEAM.md`, `MAINTAINERS.md`, `CODE_OF_CONDUCT.md` — innovator
  capability and governance evidence (no fabricated identities).
- ADR-0002 zero-trust posture (NIST SP 800-207 + Uganda extensions).
- ADR-0003 regional / EAC chain migration path.
- `scripts/{generate_sbom,lighthouse_ci,load_test}.sh` +
  `backend/scripts/load_test.py` — reproducible evidence runners.
- `docs/audit/CODEBASE_MAP.md` — file-by-file inventory of repo state.

## 2026-05-21 — starlette 0.50.0 (CVE-2025-62727)

Commit: `1343660 deps: bump starlette to 0.50.0 (CVE-2025-62727)`

- Bumped `starlette` floor to `>=0.50.0` and ceiling to `<0.51`.
- FastAPI ceiling raised accordingly to `<0.123` so resolution settles on
  the patched starlette line.
- No code changes — pure dependency bump.

## 2026-05-20 — Dependabot batch (16 alerts: 9 high, 5 moderate, 2 low)

Commit: `c7b887e deps: resolve 16 Dependabot alerts (9 high, 5 moderate, 2 low)`

**Frontend** (13 Next.js CVEs — 7 high / 4 moderate / 2 low):
- `next`: `16.2.3` → `^16.2.6`. Covers CVE-2026-44572..82, GHSA-8h8q-6873-q5fj,
  CVE-2026-45109.

**Backend** (3 alerts — 2 high / 1 moderate):
- Starlette CVE-2024-47874 (high) + CVE-2025-54121 (moderate):
  `fastapi 0.111.0` → `>=0.118,<0.120`; explicit `starlette>=0.47.2,<0.49`.
  Final resolution: fastapi 0.119.1 + starlette 0.48.0.
- ecdsa CVE-2024-23342 (high, no upstream patch — Minerva timing attack on
  ECDSA signing): **migrated off `python-jose` to PyJWT**. We never signed
  with ECDSA (JWT is HS256 dev / RS256 OIDC prod), but eliminating the
  transitive dep is cleaner than documenting an inapplicable advisory.

JWT migration details:
- `backend/app/auth/jwt_auth.py` rewritten to use PyJWT 2.12.1+crypto with
  manual JWKS `kid` resolution via `jwt.algorithms.RSAAlgorithm.from_jwk`.
- API surface unchanged (`JWTVerifier.verify`, `make_dev_token`).
- All backend tests pass on the upgraded stack.

Other:
- Pydantic bumped `2.7.4` → `>=2.9,<3` (transitive from new fastapi).
- `backend/Dockerfile`: now copies `README.md` alongside `pyproject.toml`
  so hatchling's readme validation doesn't fail on install.

## 2026-05-20 — Audit-grade documentation pass

Commit: `66a6856 docs: comprehensive audit-grade documentation`

- `backend/README.md`, `frontend/README.md`, `contracts/README.md` —
  full setup, layout, routes, config, tests, security posture.
- `docs/REQUIREMENTS.md` — system + toolchain + external service
  requirements, capacity targets, compliance posture, mapping of the
  seven National Innovator Registry evaluation criteria to evidence files.
- `docs/ARCHITECTURE.md` — data flow diagram, dual-layer trust model,
  tenancy + RLS, fraud detection, resilience, threat model summary,
  observability, testing strategy, migration paths.
- `README.md` — documentation index pointing at every audit-relevant doc.

## 2026-05-20 — Initial commit

Commit: `083e03d Initial commit: LandGuard Uganda`

First public commit. Includes:

- FastAPI 0.111 backend with per-district hash-chained audit ledger,
  IsolationForest + rules fraud scorer (human-in-the-loop), NIRA
  mock + live clients, anchor service with circuit-breaker.
- LandRegistryAnchor.sol + MultiSigRegistrar.sol (3-of-5 named signers).
- Next.js 16 PWA with Officer console, registrar console, auditor
  console, public verifier (smartphone + USSD), demo control panel.
- Dual-Merkle regime (ADR-0001): SHA-256 off-chain + sorted-pair keccak
  on-chain, bridged by `keccak(sha256_hex_leaf)`.
- DPPA-2019 compliance posture: NIN AES-GCM encrypted at rest,
  right-to-erasure tombstones, phone numbers SHA-256 hashed in audit.
- Docker compose for full stack (postgres+postgis, redis, anvil,
  contract-deploy, co-signer, backend, frontend, caddy TLS, prometheus,
  grafana). All containers non-root, `cap_drop:[ALL]`.

---

## How to add an entry

1. Identify the trigger: CVE remediation, dep bump, security-relevant
   refactor, or architectural decision.
2. Add a dated H2 section at the top of this file.
3. Cite the commit short SHA (`git log --oneline -1`) on its own line.
4. Bullet what changed and why — link to ADRs or threat-model entries
   when relevant.
5. Keep entries factual. Marketing copy belongs in `README.md`.
