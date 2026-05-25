# Showcase Evaluation Mapping

**Audience:** MoICT&NG National Innovator Registry Showcase panel.
**Purpose:** A one-page navigation aid. For each of the seven official
criteria, find the responsible file, the demonstrable feature, and the
reproducible evidence you can re-run.

**Submission window:** 1 June 2026. **Showcase date:** 25 June 2026.
**Thematic Area:** 3 — Land & Property Administration.

---

## 1. Criterion → Evidence matrix

| # | Criterion | Where it is demonstrated | Verifiable evidence (re-runnable) | Score self-assessment |
|---|---|---|---|---|
| 1 | **Technical soundness** | `contracts/src/LandRegistryAnchor.sol`, `backend/app/audit/{ledger,merkle,verifier}.py`, `backend/app/blockchain/anchor_service.py`, ADR-0001 (dual-Merkle regime) | `cd contracts && forge test -vvv` (≥ 90% line+branch); `cd backend && uv run pytest -q` (32+ tests, all green); `backend/tests/test_merkle_cross.py` proves Python↔TypeScript↔Solidity Merkle equivalence | **5/5** |
| 2 | **Relevance to Government needs** (Thematic Area 3) | `docs/REQUIREMENTS.md` §6 (DPPA, NITA-U), `docs/moa-templates/MoLHUD-Mityana-Pilot-MOU.md`, `docs/GOVERNANCE.md`, `docs/STANDARDS_ALIGNMENT.md` (World Bank LGAF, OpenHIE land) | Draft MOU mapped to NLIS Phase III roadmap items; Mityana district pre-identified; identifiers compatible with existing UPI/NIN format (`backend/app/util/ids.py`) | **5/5** |
| 3 | **Security & compliance** | `docs/audit/THREAT_MODEL.md`, `docs/CUSTODY.md` (3-of-5 multi-sig), `backend/app/auth/jwt_auth.py` (PyJWT — ecdsa CVE eliminated), `backend/app/crypto.py` (AES-GCM for NIN), `CHANGELOG.md` (CVE timeline), `docs/adr/0002-zero-trust-posture.md` | `bash scripts/generate_sbom.sh` produces signed CycloneDX SBOM; Caddy CSP/STS verified; production-safety assert in `Settings.assert_prod_safety()` refuses dev defaults; Foundry tests `test_DirectAnchorBypassFails` proves no single key can anchor | **5/5** |
| 4 | **Scalability** | `docs/SLA_TARGETS.md`, `backend/app/blockchain/anchor_service.py` (per-district queues), `docker-compose.yml` (postgres+postgis ready), `monitoring/prometheus/prometheus.yml`, `docs/adr/0003-regional-chain-migration.md` | `bash scripts/load_test.sh` reproduces ≥ 200 events/sec/district envelope; Prometheus `anchor_queue_depth{district_id="3"}` gauge demonstrates per-district isolation; SQLite→Postgres+PostGIS migration is one env var (`DB_BACKEND=postgres`) | **4/5** |
| 5 | **Usability & accessibility** | `docs/DESIGN_SYSTEM.md`, `docs/IMPACT_EVIDENCE.md`, `frontend/src/app/(public)/verify/page.tsx`, `backend/app/routers/ussd.py`, `docs/USSD_DEPLOYMENT.md` | `bash scripts/lighthouse_ci.sh` produces Lighthouse ≥ 95 / accessibility 100 / axe-core 0 violations on the public verifier; USSD pathway verified on Africa's Talking simulator (`backend/tests/test_ussd.py`); WCAG 2.2 AA per page; offline PWA fallback | **5/5** |
| 6 | **Local innovation value** | `backend/app/routers/ussd.py` (feature-phone inclusion), `docs/AI_ETHICS_CHARTER.md` (Africa-first AI policy), `contracts/src/MultiSigRegistrar.sol` (purpose-built sovereignty primitive), `docs/CUSTODY.md` (national institutional signers) | USSD on Tecno Spark 6 + feature phone; Apache-2.0 license (truly open, not source-available); contract small enough (80 + 117 LoC) for Makerere CSL to audit in a single sitting; no foreign hosted dependencies on the critical path | **5/5** |
| 7 | **Innovator capability** | `docs/TEAM.md`, `MAINTAINERS.md`, `docs/GOVERNANCE.md`, ADR history, `CHANGELOG.md` | Public GitHub with full history; ADR-0001 / ADR-0002 / ADR-0003 demonstrate decision discipline; per-component README + audit package + threat model demonstrate documentation discipline; capacity-building plan with Makerere CSL signed in `docs/TEAM.md` §5 | **4/5** |

**Composite self-assessment: 33/35 (94.3%).** The 2 remaining points are
honest gaps: pilot-phase real benchmark numbers (vs. modelled envelopes)
and a third-party smart-contract audit report — both budgeted and dated
in the post-showcase roadmap (`README.md` §Roadmap).

---

## 2. Three-minute panel demo path

If a panellist has only three minutes to verify the strongest claims:

1. **`/verify?title=UG-MIT-T00007/2026`** in a browser — single QR scan, no
   credentials, on-chain proof verification rendered live.
2. **`*247*256#`** on a feature phone — same verification path, no
   smartphone required.
3. **`docs/audit/AUDIT_PACKAGE.md` §"How to reproduce"** — eight `bash`
   commands that recompute every cryptographic claim from a clean clone.

---

## 3. Eight-minute deeper panel demo

The full Act 1–6 storyboard is in `DEMO_RUNBOOK.md`; that runbook is
indexed to the seven criteria in §"Mapping demo acts → evaluation
criteria".

---

## 4. Where to look first if you're a …

| You are a … | Start here |
|---|---|
| Cryptographic auditor | `docs/adr/0001-dual-merkle-regime.md`, then `backend/tests/test_merkle_cross.py` |
| Security reviewer | `docs/audit/THREAT_MODEL.md`, then `docs/adr/0002-zero-trust-posture.md` |
| Compliance officer (DPPA / NITA-U) | `docs/GOVERNANCE.md`, then `docs/STANDARDS_ALIGNMENT.md` |
| AI ethics reviewer | `docs/AI_ETHICS_CHARTER.md`, then `backend/app/fraud/worker.py` |
| Smart-contract auditor | `contracts/src/`, then `contracts/test/` (`forge coverage`) |
| MoLHUD / NITA-U policy lead | `docs/moa-templates/MoLHUD-Mityana-Pilot-MOU.md` |
| Independent observer (Makerere CSL) | `docs/CUSTODY.md`, then `docs/TEAM.md` §5 (capacity-building) |
| Procurement / sustainability | `docs/SLA_TARGETS.md`, then `docs/IMPACT_EVIDENCE.md` §5 (TCO model) |
| Investor / sustainability committee | `docs/IMPACT_EVIDENCE.md`, then `README.md` Roadmap |

---

## 5. Open evidence index (one click each)

- Source: <https://github.com/mpairwe7/LandGuardUganda>
- Architecture: [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md)
- Requirements + compliance map: [`docs/REQUIREMENTS.md`](./REQUIREMENTS.md)
- Threat model: [`docs/audit/THREAT_MODEL.md`](./audit/THREAT_MODEL.md)
- Audit package (re-run everything): [`docs/audit/AUDIT_PACKAGE.md`](./audit/AUDIT_PACKAGE.md)
- Codebase map: [`docs/audit/CODEBASE_MAP.md`](./audit/CODEBASE_MAP.md)
- Standards alignment: [`docs/STANDARDS_ALIGNMENT.md`](./STANDARDS_ALIGNMENT.md)
- Impact evidence: [`docs/IMPACT_EVIDENCE.md`](./IMPACT_EVIDENCE.md)
- SLA targets: [`docs/SLA_TARGETS.md`](./SLA_TARGETS.md)
- Team & governance: [`docs/TEAM.md`](./TEAM.md), [`MAINTAINERS.md`](../MAINTAINERS.md)
- Demo runbook: [`DEMO_RUNBOOK.md`](../DEMO_RUNBOOK.md)
- Changelog (CVE timeline): [`CHANGELOG.md`](../CHANGELOG.md)
