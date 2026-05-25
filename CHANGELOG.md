# Changelog

Security-relevant changes, dependency bumps, and notable architectural
events. Audit-readable timeline. Entries are reverse-chronological.

The project follows the spirit of [Keep a Changelog](https://keepachangelog.com/);
versioning is calendar-style (`YYYY-MM-DD`) until 1.0.

---

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
