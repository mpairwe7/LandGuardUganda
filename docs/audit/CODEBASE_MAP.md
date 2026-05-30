# Codebase Map

A single-page, file-by-file index for auditors, evaluators, and new
contributors. Captures the **current state** of the repository as of
the most recent commit. Each entry names the file, what it does, and
where to cross-reference its behaviour.

Last verified: 2026-05-25 (post `1343660 deps: bump starlette to 0.50.0`).

---

## 1. Repository topology

```
LandGuardUganda/
├── backend/        FastAPI 0.119+ · Python 3.12 · uv · async-first
├── frontend/       Next.js 16 (Bun) · React 19 · Tailwind 4 · Zustand
├── contracts/      Foundry · Solidity 0.8.24 · OpenZeppelin v5
├── docs/           Architecture, requirements, audit package, ADRs
├── monitoring/     Prometheus + Grafana + OTel configs
├── scripts/        (currently empty — orchestration goes here)
├── Caddyfile       TLS termination + CSP/STS for production
├── docker-compose.yml / docker-compose.sepolia.yml
├── DEMO_RUNBOOK.md / QUICKSTART.md / README.md
```

Project totals: ~11.7k lines across Python + TypeScript + Solidity. Most
files are deliberately small (≤200 lines) so an auditor can read any
single module end-to-end in one sitting.

---

## 2. Backend — `backend/app/`

### 2.1 Entry & configuration

| File | LoC | Responsibility |
|---|---:|---|
| `main.py` | 145 | FastAPI factory; lifespan starts anchor + fraud workers; middleware chain (RequestId → Idempotency → CORS); router mount order matters (public verify/USSD first) |
| `config.py` | 158 | Pydantic-Settings; `assert_prod_safety()` refuses dev defaults in `APP_ENV=production`; validates JWT secret ≥ 32 chars and PII key ≥ 32 bytes b64-decoded |
| `database.py` | 134 | Thread-local SQLite (WAL) for dev, short-lived psycopg connections for Postgres prod; `apply_migrations()` runs `db/migrations/*.sql` in lex order with idempotent `IF NOT EXISTS` discipline |
| `resilience.py` | 194 | `CircuitBreaker` (CLOSED→OPEN→HALF_OPEN), exponential backoff, `force_open/force_close` for the demo control panel; `retry_with_backoff` for finer-grained transient handling |
| `crypto.py` | 42 | AES-GCM 256 helper using `cryptography.hazmat`; key cached via `lru_cache`; nonce-prefixed ciphertext layout |
| `tracing.py` | — | OTel OTLP-gRPC setup (lazy-imported in lifespan when `OTEL_ENABLED=true`) |
| `bootstrap/__init__.py` | 1 | Marker for the startup-helpers package |
| `bootstrap/seed.py` | ~330 | `seed_districts_and_parcels()`, `seed_demo_state()`, `seed_demo_extras()` (titles + transfer + fraud reviews), `is_db_empty()`, `maybe_seed_on_startup()` — gated by `app_env != "production"` AND empty districts table; idempotent on warm restarts |

### 2.2 Auth — `app/auth/`

| File | Responsibility |
|---|---|
| `models.py` | `Role` enum (CITIZEN/SURVEYOR/LAND_OFFICER/REGISTRAR/AUDITOR/PUBLIC_VERIFIER/ADMIN); frozen `AuthUser` and `AuthContext` dataclasses |
| `jwt_auth.py` | PyJWT (HS256 dev / RS256 OIDC prod); 5-min JWKS cache; `make_dev_token()` for `scripts/issue_dev_tokens.py` only. **Migrated off `python-jose` in commit c7b887e** to eliminate ecdsa CVE-2024-23342 |
| `dependencies.py` | `optional_user`/`require_user`/`require_role(*roles)`; gated `X-Demo-Role`/`X-Demo-District` headers for on-stage role switching (non-prod only) |

### 2.3 Audit — `app/audit/`

| File | Responsibility |
|---|---|
| `ledger.py` | Per-district hash-chained ledger; `row_hash = sha256(prev_hash + payload_hash)`; mutex-guarded append; `erasure_tombstone()` for DPPA §26 |
| `merkle.py` | **Two regimes**: SHA-256 index-ordered (off-chain integrity) + sorted-pair Keccak over `keccak(sha256_hex)` leaves (on-chain) — see ADR-0001 |
| `verifier.py` | `verify_chain(tenant_id)` walks rows in `seq` order; returns `first_corrupt_seq` on mismatch |
| `__init__.py` | `audit_emit()` best-effort facade; failures never crash callers, just bump `audit_failure_total` |

### 2.4 Blockchain — `app/blockchain/`

| File | Responsibility |
|---|---|
| `client.py` | `BlockchainClient` Protocol + factory; multi-sig wrapping when `MULTISIG_ENABLED=true` and provider≠mock |
| `models.py` | `AnchorReceipt`, `MerkleProof` frozen dataclasses |
| `mock_client.py` | Deterministic in-memory chain for tests; tx hash = sha256 of inputs |
| `anvil_client.py` | web3.py AsyncWeb3 + AsyncHTTPProvider; tx lock to serialise nonces; `_to_bytes32` normalisation; reads contract address from `data_store/contract_address.json` |
| `sepolia_client.py` | Same surface as anvil; EIP-1559 fee strategy; production posture |
| `multisig_client.py` | Proxies `commit_batch` via `proposeAndConfirm`; polls inner anchor's `anchors(batch_id)` to detect threshold execution |
| `anchor_service.py` | The heart of the dual-tree flow: builds both SHA-256 and EVM roots, persists `anchors` row, calls `CircuitBreaker.call(client.commit_batch)`, marks events anchored, emits `ANCHOR_COMMITTED`. `build_proof_for_event()` materialises sorted-pair keccak proofs for the public verifier |

### 2.5 Fraud — `app/fraud/`

| File | Responsibility |
|---|---|
| `rules.py` | 7 rules: `geometry_overlap` (w30), `rapid_retransfer` (w20), `nin_reuse` (w15), `size_anomaly` (w10), `watchlist_name` (w20), `consideration_anomaly` (w15), `nira_kyc` (w25). Each rule fail-safes to score=0 |
| `features.py` | 9-feature vector for IsolationForest: hours_since_last_transfer, log1p_consideration, log1p_area, owner_age_days, prior_parcel_count, prior_dispute_count, district_norm_z, hour_of_day, weekday |
| `scorer.py` | Combines rules with IsolationForest (ml × 60 cap); thresholds: ≥75 BLOCK, ≥40 FLAG, else NONE; `SCORER_VERSION = isoforest-rules-v2-20260530` |
| `worker.py` | Redis-streams consumer (`stream:fraud:scoring`) **+ durable `fraud_scoring_jobs` outbox sweep** (eventual scoring even if Redis was down); `score_now()` for synchronous scoring; writes to `fraud_review_queue`; **no parcel state change** — humans only. Per-process consumer name for safe multi-replica scaling |
| `training/train.py` | One-shot model train; emits `isoforest-v1.joblib` |
| `jobs/escalation.py` | 24h escalation — raises review priority to a supervising officer; **never freezes** (charter §1/§8) |
| `jobs/parity.py` | Demographic parity audit + `FRAUD_PARITY_BREACH` alert on >1.5× mean |
| `jobs/scheduler.py` | In-process, Redis-leader-locked scheduler that actually runs escalation (hourly) + parity (≈monthly) |

### 2.6 NIRA — `app/nira/`

| File | Responsibility |
|---|---|
| `client.py` | `NIRAClient` Protocol; `NIRAVerifyResult`, `NIRADemographics`, `NIRABiometricMatch` dataclasses |
| `mock_client.py` | Deterministic in-memory NIN→demographics map for demo seed data |
| `live_client.py` | httpx client for production NIRA API (currently stub; real spec pending MoICT&NG publication) |
| `cache.py` | Redis hot + DB warm cache + breaker; `verify_nin_cached()` returns `{stale: bool}` so callers can degrade gracefully |

### 2.7 Routers — `app/routers/`

| File | Mount prefix | Auth gate |
|---|---|---|
| `health.py` | `/healthz`, `/readyz`, `/metrics` | open |
| `verify.py` | `/api/v1/verify/title` | **PUBLIC** — rate-limited 20/min/IP (`limit_public_verify`) |
| `ussd.py` | `/api/v1/ussd`, `/api/v1/sms/verify` | **PUBLIC** — phone hashed, never logged in plaintext |
| `parcels.py` | `/api/v1/parcels` | SURVEYOR/REGISTRAR write; any role read |
| `titles.py` | `/api/v1/titles` | REGISTRAR write; any role read; enqueues fraud score on issuance |
| `owners.py` | `/api/v1/owners` | LAND_OFFICER/REGISTRAR write; redacts NIN to last-4 on read |
| `transfers.py` | `/api/v1/transfers` | LAND_OFFICER/CITIZEN create; REGISTRAR/LAND_OFFICER approve; **rejects approval when latest fraud score = BLOCK** |
| `disputes.py` | `/api/v1/disputes` | citizens file; LAND_OFFICER reviews; REGISTRAR resolves; FRAUD/OVERLAP/OWNERSHIP disputes auto-freeze parcels |
| `anchors.py` | `/api/v1/anchors` | any auth user reads; ADMIN/REGISTRAR can force flush |
| `fraud.py` | `/api/v1/fraud` | review affirm/dismiss (LAND_OFFICER/REGISTRAR); appeals (any user files, AUDITOR/REGISTRAR resolves) |
| `nira.py` | `/api/v1/nira/verify` | LAND_OFFICER/REGISTRAR |
| `admin.py` | `/api/v1/admin` | ADMIN only; audit verify is AUDITOR/ADMIN |
| `demo.py` | `/api/v1/demo` | **DISABLED in production**; circuit-breaker force-open/close, manual flush, rescore-pending |

### 2.8 Middleware — `app/middleware/`

| File | Behaviour |
|---|---|
| `request_id.py` | Echoes/assigns `X-Request-Id`; threads `request.state.request_id` |
| `idempotency.py` | 24h Redis dedupe on mutating verbs when `Idempotency-Key` UUID-shape header present; bypasses `/healthz`/`/readyz`/`/metrics`/`/api/v1/verify` |
| `limits.py` | slowapi `Limiter` keyed on remote address; `limit_anon`/`limit_auth`/`limit_admin`/`limit_public_verify` decorators read tiered limits from settings |
| `security_headers.py` | (v0.2.2) HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Cross-Origin-Opener-Policy, Permissions-Policy on every response; CSP on JSON/HTML; rewrites `Server` to `landguard` so uvicorn isn't disclosed (paired with `--no-server-header` in the Dockerfile CMD) |

### 2.9 Models — `app/models/`

Pydantic v2 request/response schemas — one module per domain entity
(`anchors.py`, `disputes.py`, `fraud.py`, `owners.py`, `parcels.py`,
`titles.py`, `transfers.py`, `verify.py`) plus a `common.py` with
`StrictModel` (extra=forbid).

### 2.10 Util — `app/util/`

| File | Responsibility |
|---|---|
| `geo.py` | Shapely Polygon parsing + UTM 36N reprojection for accurate hectares; `overlap_fraction()` for the geometry_overlap fraud rule |
| `ids.py` | `validate_upi/nin`, `make_upi`, `make_title_no`; `DISTRICT_CODES = {1:KCC, 2:WAK, 3:MIT, 4:GUL}` |
| `hashing.py` | `canonical_json` (sorted keys, no whitespace), `content_hash` (sha256 of canonical JSON) |
| `cache.py` | Redis singleton + in-memory fallback for `cache_get/set/setnx`; `stream_publish` for Redis streams |
| `metrics.py` | Prometheus counters/gauges: `anchor_batches_total`, `anchor_breaker_open`, `nira_breaker_open`, `fraud_blocks_total`, `audit_failure_total`, etc. |
| `ussd.py` | USSD session helpers (state machine, response framing) |
| `sql.py` | (v0.2.2) `escape_like_value()` — defensive escape of `%`/`_`/`\\` in LIKE patterns used by the verifier's audit-event fallback lookup. Pairs with `ESCAPE '\\'` in the SQL clause |

### 2.11 Database migrations — `app/db/migrations/`

| File | Adds |
|---|---|
| `001_init.sql` | districts, owners (with `nin_encrypted` BLOB + `nin_hash` UNIQUE), parcels, titles, transfers, disputes, anchors, nira_verifications, staff_users, fraud_scores, fraud_watchlist |
| `002_review_queue.sql` | fraud_review_queue (states: PENDING_REVIEW/HUMAN_AFFIRMED/HUMAN_DISMISSED/AUTO_ESCALATED/EXPIRED), fraud_appeals (OPEN/UNDER_REVIEW/UPHELD/DENIED/WITHDRAWN) |

### 2.12 Scripts — `backend/scripts/`

| Script | Purpose |
|---|---|
| `deploy_contract.py` | Deploys LandRegistryAnchor (always) + MultiSigRegistrar (when `MULTISIG_ENABLED=true`); rotates `REGISTRAR_ROLE` to multisig; writes `data_store/contract_address.json` |
| `seed_districts.py` | Inserts the 4 prototype districts |
| `seed_demo.py` | Inserts Sarah Nakato, Patrick Bwambale, fraud-watchlist entries, and the hero parcel `UG-MIT-024718/2026` |
| `train_fraud_model.py` | One-shot IsolationForest training |
| `issue_dev_tokens.py` | Mints one HS256 JWT per role for the showcase |
| `verify_audit_chain.py` | Chain integrity report for a district |
| `co_sign_daemon.py` | Auto-confirms the demo multi-sig threshold (Anvil accounts 1+2 as MoLHUD+NITA-U personas) |
| `escalate_pending_reviews.py` | CLI wrapper over `app.jobs.escalation`; after 24h raises a review's priority to a supervising officer (**never freezes**). Also run automatically by the in-process scheduler |
| `fraud_parity_audit.py` | CLI wrapper over `app.jobs.parity`; demographic-parity report (district × tenure × gender flag rates) + breach alert. Also run automatically by the in-process scheduler |
| `emit_merkle_vectors.py` | (v0.2.0 Pack A) One-shot generator of the 10-case canonical Merkle fixture at `contracts/test/merkle-parity.json` |

### 2.13 Tests — `backend/tests/`

| Test file | Coverage focus |
|---|---|
| `conftest.py` | Per-test SQLite tmp file; resets module singletons |
| `test_audit_chain.py` | Hash-chain integrity invariants + tampering detection |
| `test_merkle_cross.py` | Python ↔ TypeScript ↔ Solidity proof equivalence on a fixed vector |
| `test_anchor_service.py` | `flush_district()` happy path + breaker-open queueing |
| `test_fraud_rules.py` | Per-rule unit coverage + fail-safe (returns 0 on internal error) |
| `test_fraud_review_workflow.py` | BLOCK score never auto-freezes; affirm → FROZEN; dismiss → no state change |
| `test_nira_mock.py` | Mock client deterministic fixture lookups |
| `test_resilience.py` | CircuitBreaker state transitions + cooldown doubling |
| `test_ussd.py` | USSD state machine; phone is SHA-256-hashed in audit |
| `test_verify_endpoint.py` | Public verifier — online lookup + offline-bundle path; rate limit |
| `test_security_headers.py` | (v0.2.2 Pack F) HSTS / X-CTO / X-Frame / Referrer-Policy / COOP / Permissions-Policy / CSP / Server-scrub contract pinned across 3 endpoints |
| `test_like_escape.py` | (v0.2.2 Pack F) `escape_like_value()` + `ESCAPE '\\'` blocks LIKE-pattern broadening; legitimate UPIs round-trip |
| `test_readyz_enriched.py` | (v0.2.2 Pack F) `/readyz` `.details` includes `fraud_model` + `audit_chain` shape contract |

**Coverage targets**: backend ≥ 80% line via `pytest --cov=app`. Foundry
contracts ≥ 90% line + branch via `forge coverage`. Current backend test
total: **51 / 51 passing** (was 32 / 32 pre-Pack-F).

---

## 3. Smart contracts — `contracts/`

| File | Lines | Notes |
|---|---:|---|
| `src/LandRegistryAnchor.sol` | 88 | `AccessControl` + `Pausable`; `commitBatch(districtId, batchId, root)` gated on `REGISTRAR_ROLE`; `verifyProof` uses sorted-pair keccak; `pause()`/`unpause()` under `DEFAULT_ADMIN_ROLE`; reverts `DuplicateBatch` + `EmptyRoot` |
| `src/MultiSigRegistrar.sol` | 117 | k-of-n threshold (default 3-of-5); `proposalIdOf(districtId, batchId, root)` deterministic; events `ProposalCreated`/`ProposalConfirmed`/`ProposalExecuted`; reverts `NotASigner`/`AlreadyConfirmed`/`AlreadyExecuted`/`InvalidThreshold`/`InsufficientSigners` |
| `test/LandRegistryAnchor.t.sol` | 107 | Happy path + duplicate rejection + empty-root rejection + non-registrar revert + pause behaviour + 3-leaf Merkle vector test (cross-checks Python `test_merkle_cross.py`) |
| `test/MultiSigRegistrar.t.sol` | 89 | 3-of-5 quorum execution; non-signer rejection; double-confirm rejection; post-execution confirm rejection; direct-anchor bypass rejected |
| `test/MerkleParity.t.sol` | 100 | (v0.2.0 Pack A) Loads `merkle-parity.json` via `stdJson` + `vm.readFile`; for every case (10) commits the batch then asserts `verifyProof` accepts each leaf and rejects a tampered one. Pins `schema_version` + `CASE_COUNT` so silent fixture drift fails loudly |
| `test/merkle-parity.json` | 62 KB | Canonical fixture: 10 cases (empty, single-leaf, 2/3/4/5/8/16-leaf, permuted, real-Uganda-batch) plus a hand-derived 2-leaf case with step-by-step keccak in its `_comment` |
| `foundry.toml` | 24 | Solc 0.8.24, optimizer 200 runs; OZ remap; `[profile.ci]` fuzz=1024; `fs_permissions = [{access="read", path="./test"}]` to let MerkleParity.t.sol read the fixture |
| `lib/openzeppelin-contracts/` | submodule | OZ v5 (AccessControl, Pausable) |
| `lib/forge-std/` | submodule | forge-std test helpers |

**Solidity custody invariant** (verified by `test_DirectAnchorBypassFails`):
when `MULTISIG_ENABLED=true`, `REGISTRAR_ROLE` is granted to the multi-sig
and revoked from the deployer in `scripts/deploy_contract.py`, so no
single EOA can call `commitBatch` directly.

---

## 4. Frontend — `frontend/src/`

### 4.1 Routes — `app/`

| Route | File | Role/scope |
|---|---|---|
| `/` | `app/page.tsx` | Public landing — institutional voice, hero CTA → `/verify` |
| `/verify` | `app/(public)/verify/page.tsx` | Public verifier — title input + QR scanner + Merkle visualizer |
| `/anchors` | `app/(public)/anchors/page.tsx` | Anchor explorer (read-only) |
| `/anchors/[batchId]` | `app/(public)/anchors/[batchId]/page.tsx` | Batch detail (root, tx, block) |
| `/explore` | `app/(public)/explore/page.tsx` | District-scoped registry browser |
| `/citizen` | `app/(app)/citizen/page.tsx` | Owner's parcel list |
| `/surveyor/register` | `app/(app)/surveyor/register/page.tsx` | MapLibre + mapbox-gl-draw polygon drawer; Turf overlap check |
| `/officer` | `app/(app)/officer/page.tsx` | Fraud review queue (affirm/dismiss) |
| `/registrar` | `app/(app)/registrar/page.tsx` | Title issuance console |
| `/auditor` | `app/(app)/auditor/page.tsx` | Audit chain verify + appeals resolver |
| `/titles/[upi]` | `app/titles/[upi]/page.tsx` | Printable title certificate with on-page QR |
| `/demo` | `app/demo/page.tsx` | Demo control panel (gated by `?demo=1`) |
| `/explore/district/[code]` | `app/(public)/explore/district/[code]/page.tsx` | SSG drill-down (mityana / wakiso / kampala-central / gulu); unknown codes 404 via `dynamicParams: false` |
| `/api/proxy/[...path]` | `app/api/proxy/[...path]/route.ts` | Runtime backend proxy (route handler, not rewrite — Crane Cloud pod can't honour build-time targets). Falls through to candidate list in `lib/backendUrl.ts` |
| `/api/proxy-debug` | `app/api/proxy-debug/route.ts` | Diagnostic: probes every backend candidate + external egress so the pod's networking can be characterised from outside |
| `/api/chain-status` | `app/api/chain-status/route.ts` | Server-side proxy for backend `/readyz` (used by `ChainStatusBeacon` when `NEXT_PUBLIC_BACKEND_URL` isn't baked in) |
| `/api/health` | `app/api/health/route.ts` | Frontend liveness |

### 4.2 Components — `components/`

| Group | Files of note |
|---|---|
| `chain/` | `AnchorTimeline.tsx`, `ChainStatusBeacon.tsx`, `LatestAnchorBadge.tsx`, `MerkleProofVisualizer.tsx` (animated leaf→root traversal), `PendingAnchorBadge.tsx` |
| `certificate/` | `TitleCertificate.tsx` — A4 print layout with QR + Merkle path |
| `common/` | `Button.tsx`, `HashDisplay.tsx`, `StatusPill.tsx` |
| `demo/` | `DemoControlPanel.tsx` (214 lines — RPC kill, NIRA kill, force flush) |
| `fraud/` | `FraudExplainer.tsx`, `ReviewQueue.tsx` (207 lines — affirm/dismiss with mandatory notes) |
| `layout/` | `MinistryHeader.tsx`, `CoatOfArmsMark.tsx`, `DistrictPicker.tsx`, `RoleSwitcher.tsx`, `RedactToggle.tsx`/`RedactShell.tsx`, `LocaleSwitcher.tsx`, `MobileMenu.tsx` (reusable headless drawer — focus-trap close, Esc, body scroll lock, auto-close on link click; used by all three top-level layouts for the hamburger pattern) |
| `map/` | `MapParcelDrawer.tsx` |
| `verify/` | `QrScanner.tsx` |

### 4.3 Libs & state

| File | Role |
|---|---|
| `lib/api.ts` | `${NEXT_PUBLIC_BACKEND_URL}/api` when baked at build time (Crane Cloud production path — browser → backend ingress directly over CORS), else `/api/proxy` (local-dev runtime route). Auto-attaches Bearer + `X-Demo-Role` + `Idempotency-Key` |
| `lib/backendUrl.ts` | Candidate-list probe for the runtime proxy route — tries `BACKEND_URL`, k8s short names, and the public ingress in turn. Caches the first that returns 200 on `/healthz` |
| `lib/merkle.ts` | TypeScript mirror of `backend/app/audit/merkle.py` — both regimes; cross-checked via shared vectors |
| `lib/format.ts`, `lib/cn.ts` | Date/number formatting; `clsx`+`tailwind-merge` |
| `lib/i18n/messages.ts` | en + lg (Luganda) catalogue for the `/verify` page. Luganda strings flagged as best-effort working drafts pending native-speaker review |
| `lib/i18n/useLocale.ts` | Hook over `useLocaleStore`; cookie-hydrates on mount, exposes `{locale, setLocale, t}` |
| `store/useAuthStore.ts` | Zustand — JWT, demoRole, demoDistrictId |
| `store/useDistrictStore.ts` | Active district selector |
| `store/useChainStatusStore.ts` | Live anchor breaker state |
| `store/useDemoStore.ts` | Demo-control state |
| `store/useLocaleStore.ts` | Shared `en`/`lg` locale, persisted to `lg_locale` cookie (SameSite=Lax, 1 year) |
| `store/useRedactStore.ts` | NIN/phone redact toggle for the auditor console |

### 4.4 Build & runtime

| File | Notes |
|---|---|
| `next.config.mjs` | `output: "standalone"`; security headers (X-Frame-Options=DENY, nosniff, strict-origin Referrer-Policy, camera=self); `/api/proxy/:path*` → `BACKEND_URL/api/:path*` |
| `vitest.config.ts` | (v0.2.0 Pack A) `@/` alias to `./src`; node env; picks up `src/__tests__/**/*.test.ts` |
| `src/__tests__/merkle.test.ts` | (v0.2.0 Pack A) 12 unit tests pinning every `lib/merkle.ts` exported function in isolation |
| `src/__tests__/merkle.parity.test.ts` | (v0.2.0 Pack A) 72 assertions across the 10-case `contracts/test/merkle-parity.json` fixture — TS verifier must agree with Python + Solidity on every leaf + proof |
| `tailwind.config.ts` | Custom palette (`guard-*`, `seal-*`, `status-*`); IBM Plex font wiring |
| `package.json` | Next 16.2.6 (post Dependabot bump), React 19.2, Tailwind 4, zustand 5, @tanstack/react-query 5, @noble/hashes (for keccak in lib/merkle.ts), maplibre-gl + mapbox-gl-draw + turf, xstate, sonner |
| `public/sw.js`, `public/manifest.json` | PWA: offline-cached verifier shell |

---

## 5. Infrastructure & ops

### 5.1 Top-level `scripts/` (cross-cutting dev/demo orchestration)

| Script | Purpose |
|---|---|
| `generate_sbom.sh` | CycloneDX 1.5 emit + content-addressing for `evidence/sbom/` |
| `lighthouse_ci.sh` | Headless Chrome + Lighthouse against /, /verify, /anchors, /titles |
| `load_test.sh` | k6 perf harness |
| `bootstrap_cranecloud.sh` | One-shot Crane Cloud app provisioner |
| `setup_github_secrets.sh` | gh-CLI helper for DOCKERHUB_*, CRANE_CLOUD_* secrets |
| `verify_offline.py` | (v0.2.0 Pack A) Standalone audit-grade Merkle proof verifier — stdlib + eth-utils only, ~170 LoC. Backs Public Claim 1 ("anyone, anywhere"). 48/48 proofs against `contracts/test/merkle-parity.json` |
| `probe_verifier.py` | (v0.2.0 Pack B) Cron-runnable T1 verifier-availability SLO probe; stdlib only |
| `probe_security_headers.sh` | (v0.2.2 Pack F) Production assertion of the six hardening headers + enriched `/readyz` shape. **23/23 PASS** on v0.2.3-server-header |

### 5.2 Docker + compose

| File | Purpose |
|---|---|
| `docker-compose.yml` | postgres (postgis 16-3.4), redis 7.4, anvil (foundry latest), contract-deploy (one-shot), co-signer (multisig profile), backend, frontend, caddy (tls profile), prometheus + grafana (monitoring profile). All services `cap_drop:[ALL]` + `no-new-privileges:true` |
| `docker-compose.sepolia.yml` | Override: disables anvil/contract-deploy, switches backend to `BLOCKCHAIN_PROVIDER=sepolia` |
| `Caddyfile` | TLS termination; CSP locks scripts to self, frame-ancestors=none; STS 1 year preload; routes `/api/*` `/healthz` `/readyz` `/metrics` to backend, everything else to frontend |
| `backend/Dockerfile` | python:3.12-slim base; uv install; non-root user `landguard:10001`; healthcheck on `/healthz`; `--no-server-header` so `SecurityHeadersMiddleware` is the sole authority on the `Server:` response header (v0.2.3) |
| `frontend/Dockerfile` | Multi-stage Bun 1.1 deps→builder→runner; `output: standalone`; non-root user `landguard:10001`; healthcheck on `/api/health` |
| `monitoring/prometheus/prometheus.yml` | Scrapes `backend:8000/metrics` every 15s |
| `monitoring/grafana/`, `monitoring/otel/` | Empty placeholders for dashboards + OTel collector pipeline |

---

## 6. Documentation

| Document | Audience | What it covers |
|---|---|---|
| `README.md` | First read | Five claims + receipts, architecture diagram, 5-min setup, governance posture |
| `QUICKSTART.md` | New contributor | Docker + native + Sepolia paths |
| `DEMO_RUNBOOK.md` | Showcase operator | 8–12 min script, day-of checklist, failure-mode tiers, seed crib sheet, evaluation-criteria mapping |
| `docs/REQUIREMENTS.md` | Evaluator | Host + toolchain + external service requirements; capacity targets; compliance posture; seven evaluation criteria mapped to evidence |
| `docs/ARCHITECTURE.md` | Engineer | Component diagram, dual-layer trust model, data flow, tenancy, fraud, resilience, threat-model summary, observability, testing, migration paths |
| `docs/DESIGN_SYSTEM.md` | Designer / front-end engineer | Ugandan-government visual identity, IBM Plex typography, button discipline, AI-ethics colour rules |
| `docs/AI_ETHICS_CHARTER.md` | Steering committee + auditor | Human-in-the-loop, explainability, appeals, parity audits, model lineage |
| `docs/CUSTODY.md` | Cryptographic auditor + signer | 5 named signers, threshold rationale, ceremony flow, prod posture checklist |
| `docs/GOVERNANCE.md` | DPO / legal | DPPA-2019 compliance map, right-to-erasure mechanism |
| `docs/USSD_DEPLOYMENT.md` | Ops | Africa's Talking integration, shortcode assignment process |
| `docs/audit/AUDIT_PACKAGE.md` | Independent auditor | One-page index of artefacts + crypto invariants + reproduction steps |
| `docs/audit/THREAT_MODEL.md` | Security reviewer | STRIDE-style asset × adversary × mitigation matrix |
| `docs/audit/CODEBASE_MAP.md` (this file) | Future auditor | File-by-file inventory |
| `docs/adr/0001-dual-merkle-regime.md` | Cryptographic auditor | Why SHA-256 off-chain + sorted-pair keccak on-chain; rejected alternatives |
| `docs/moa-templates/MoLHUD-Mityana-Pilot-MOU.md` | MoLHUD legal | Draft pilot MOU |
| `docs/model-cards/` | (empty placeholder) | Per-`SCORER_VERSION` model cards land here |

---

## 7. Cross-cutting invariants worth re-checking each audit

1. **Single source of truth for verifier proofs.** `verify_merkle_proof_evm`
   (Python), `verifyMerkleProofEvm` (TypeScript), and
   `LandRegistryAnchor.verifyProof` (Solidity) MUST agree on every test
   vector. Drift = silent verification failures.
2. **No auto-FREEZE.** `app/fraud/worker.py` may only write to
   `fraud_review_queue`. Any path that flips `parcels.status='FROZEN'`
   without a `FRAUD_HUMAN_AFFIRMED` audit event is a charter violation.
3. **No raw PII on chain.** Anchors store `bytes32 merkleRoot` only.
   No NIN, no phone number, no name. `audit_emit` payloads carrying
   PII must hash it first (see `routers/owners.py:_redact`,
   `routers/ussd.py:_hash_phone`).
4. **Production-safety assert.** `Settings.assert_prod_safety()`
   refuses to start when `APP_ENV=production` AND any of:
   `JWT_HS256_SECRET` contains "change-me", `AUTH_MODE=dev`,
   `DEMO_MODE=true`, `BLOCKCHAIN_PROVIDER=mock`, dev PII key.
5. **Migrations idempotent.** All `CREATE TABLE` use `IF NOT EXISTS`;
   re-running migrations on an existing DB is a no-op.

---

## 8. Known gaps (call these out in any audit report)

Closed since the prior revision:

- ✅ ~~`scripts/` (project root) is empty~~ — now carries
  `generate_sbom.sh`, `lighthouse_ci.sh`, `load_test.sh`, and
  `_sbom_frontend_fallback.py`.
- ✅ ~~`frontend/e2e/` is empty~~ — four specs now cover the deploy:
  `accessibility.spec.ts` (axe-core / WCAG 2.2 AA on six citizen-
  critical routes — 6/6 clean as of 2026-05-26 commit `f98203f`),
  `smoke.spec.ts` (10 routes, page-status + console/page-error +
  failed-request capture), `flows.spec.ts` (8 click-through user
  journeys including sidebar-link enumeration), `mobile.spec.ts`
  (Pixel 5 viewport — horizontal-overflow regression + both
  hamburger drawers + axe-core on `/verify`). The CI accessibility
  job runs `accessibility.spec.ts` only; smoke / flows / mobile are
  meant for the live-deploy URL.
- ✅ ~~`docs/sbom.json` referenced but does not exist~~ — CycloneDX 1.5
  bundle in `evidence/sbom/` (backend + frontend + contracts), each
  content-addressed with SHA-256.
- ✅ ~~Penetration-test scope referenced in IMPACT_EVIDENCE but no
  document~~ — `docs/audit/PENTEST_SCOPE.md` published (OWASP ASVS L2
  scope, methodology, deliverables, budget).
- ✅ ~~DPPA §19 breach runbook referenced in SLA_TARGETS but no
  document~~ — `docs/runbooks/dppa-breach-notification.md` published
  (72-h decision tree, PDPO + data-subject templates, audit-emission
  schema, quarterly drill cadence).

Still open:

- `docs/model-cards/` holds the fraud-scorer card (`fraud-scorer.md`) and
  the v2 go-live note (`isoforest-rules-v2-20260530.md`); pilot go-live still
  needs the two §7 sign-offs (project lead + independent reviewer).
- `monitoring/grafana/` and `monitoring/otel/` are empty — dashboards
  and OTel collector pipeline still TODO.
- `backend/tests/integration/` is empty; only unit tests exist today.
- `backend/app/services/` is empty (placeholder for future
  domain-service extraction).
- `frontend/src/components/{forms,dispute,kyc,transfer}/` are empty
  placeholders — current screens inline their forms.
- `AUDIT_PACKAGE.md` previously referenced
  `backend/tests/test_idempotency.py`; that file does not exist —
  idempotency is exercised indirectly via `test_anchor_service.py`
  and `test_verify_endpoint.py`. **Track**: add dedicated unit test.
- Synthetic public-verifier probe (`scripts/synthetic_probe.py`) — see
  `docs/SLA_TARGETS.md` §10. Pilot-scope deliverable.
