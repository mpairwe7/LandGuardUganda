# LandGuard Backend

FastAPI 0.111 · Python 3.12+ · uv · async-first · audit-grade.

This document covers everything an auditor or new contributor needs to bring
the backend up locally, understand its layout, run its tests, and migrate
from the development defaults (Anvil, mock NIRA) to production posture
(Sepolia / Postgres / live NIRA).

---

## 1. System requirements

| Requirement | Version | Notes |
| --- | --- | --- |
| Python | 3.12+ | `match` statements and TaskGroup are used |
| uv | ≥ 0.4 | The only supported package manager |
| Docker / Docker Compose | 24.0 / 2.20 | For the full stack |
| Postgres + PostGIS | 16 / 3.4 | Production only; SQLite WAL in dev |
| Redis | 7.4 | Idempotency, rate limits, fraud stream |
| Foundry (anvil, forge) | latest | Only for chain testing |

Recommended host: 4 GB RAM, 4 vCPU. The IsolationForest model train uses ~ 1 GB.

---

## 2. Quick start (Docker)

The fastest path is the project-root docker-compose:

```bash
cd ..                                                  # project root
docker compose --profile anvil up -d postgres redis anvil contract-deploy
docker compose --profile anvil up -d backend
docker compose exec backend python scripts/seed_districts.py
docker compose exec backend python scripts/seed_demo.py
docker compose exec backend python scripts/train_fraud_model.py
docker compose exec backend python scripts/issue_dev_tokens.py
```

The backend listens on `http://localhost:8000`; the OpenAPI doc is at
`/docs` (gated by `ENV=dev`).

---

## 3. Quick start (local uv, no Docker)

```bash
cd backend
uv sync                       # installs into .venv/ from pyproject.toml
uv pip install -e .           # editable install

# minimum env vars for local SQLite WAL run:
export DATABASE_URL="sqlite:///./data_store/landguard.db"
export REDIS_URL="memory://"
export JWT_SECRET="dev-secret-do-not-use-in-prod"
export BLOCKCHAIN_PROVIDER="mock"
export NIRA_PROVIDER="mock"

uv run alembic upgrade head   # or: python -c "from app.db.migrations import apply_all; apply_all()"
uv run python scripts/seed_districts.py
uv run uvicorn app.main:app --reload --port 8000
```

---

## 4. Repository layout

```
backend/
├── app/
│   ├── main.py               FastAPI entry: lifespan, middleware chain, router mounts
│   ├── config.py             pydantic-settings; refuses to start in prod with dev defaults
│   ├── database.py           SQLite WAL (dev) / Postgres dispatch + connection pooling
│   ├── resilience.py         CircuitBreaker (3-failure threshold, 30-s cooldown)
│   ├── crypto.py             AES-GCM helpers for NIN at-rest encryption
│   ├── flags.py              Feature-flag indirection (FF_LIVE_NIRA, FF_MULTISIG, ...)
│   ├── tracing.py            OpenTelemetry setup (OTLP-grpc exporter)
│   │
│   ├── audit/                Hash-chained ledger + Merkle helpers
│   │   ├── ledger.py         append() / read_range() / mutex-guarded write
│   │   ├── merkle.py         Bitcoin-style (sha256) + EVM-style (keccak sorted-pair)
│   │   └── verifier.py       walk_and_verify() — auditor-callable
│   │
│   ├── auth/                 JWT auth
│   │   ├── jwt.py            HS256 dev / RS256 OIDC prod dispatch
│   │   ├── deps.py           FastAPI Depends for role-gating
│   │   └── context.py        AuthContext (tenant_id + role + claims)
│   │
│   ├── blockchain/           web3.py client + anchor service
│   │   ├── client.py         BlockchainClient Protocol
│   │   ├── mock_client.py    Deterministic, for tests
│   │   ├── anvil_client.py   Default; http://anvil:8545
│   │   ├── sepolia_client.py One-env-var migration; KMS-held signer
│   │   ├── multisig_client.py 3-of-5 wrapper (MoLHUD, NITA-U, ...)
│   │   ├── anchor_service.py Worker: batches per district, breaker-wrapped
│   │   ├── abi.json          Compiled LandRegistryAnchor ABI
│   │   └── models.py         AnchorReceipt, MerkleProof dataclasses
│   │
│   ├── nira/                 National ID (NIRA) integration
│   │   ├── client.py         NIRAClient Protocol
│   │   ├── mock_client.py    Deterministic on sha256(nin)[:8]
│   │   ├── live_client.py    Real API placeholder; documented swap-in
│   │   └── cache.py          Redis + DB warm cache
│   │
│   ├── fraud/                AI fraud detection
│   │   ├── rules.py          6 hand-coded rule signals
│   │   ├── features.py       Feature vector assembly
│   │   ├── scorer.py         IsolationForest + rule combiner (0–100)
│   │   ├── worker.py         Redis stream consumer (in asyncio task, not Celery)
│   │   └── training/         seed_data + train.py → isoforest-v1.joblib
│   │
│   ├── middleware/
│   │   ├── idempotency.py    Idempotency-Key header → 24h Redis dedupe
│   │   ├── limits.py         slowapi tiers (anon/auth/admin/public_verify)
│   │   ├── request_id.py     X-Request-ID propagation
│   │   └── audit_actor.py    Bind tenant_id into request.state
│   │
│   ├── models/               Pydantic v2 strict request/response shapes
│   ├── routers/              FastAPI route packages — one per aggregate
│   │   ├── parcels.py        Parcel CRUD + geo search
│   │   ├── titles.py         Issuance, revocation, lookup
│   │   ├── owners.py         Owner + KYC + NIN lookups
│   │   ├── transfers.py      5-state machine (INITIATED → COMPLETED)
│   │   ├── disputes.py       File / review / resolve
│   │   ├── anchors.py        Browser + flush admin
│   │   ├── verify.py         Public verifier (no auth)
│   │   ├── fraud.py          Reviews queue + affirm/dismiss
│   │   ├── nira.py           Audited NIRA proxy
│   │   ├── ussd.py           Africa's Talking-compatible USSD pathway
│   │   ├── admin.py          Districts, staff, audit-chain verify
│   │   ├── demo.py           Showcase orchestration (DEMO_MODE only)
│   │   └── health.py         /healthz /readyz /metrics
│   │
│   ├── services/             Orchestration above routers (workflows)
│   ├── util/                 hashing, geo (Shapely), ids (UPI regex), cache
│   └── db/migrations/        001_init.sql + 002_indexes.sql + 003_seed_districts.sql
│
├── scripts/                  One-shots:
│   ├── deploy_contract.py    Deploys LandRegistryAnchor + writes ABI
│   ├── seed_districts.py     Mityana, Wakiso, Kampala Central, Gulu
│   ├── seed_demo.py          Mrs. Nakato + Bwambale fraudster
│   ├── verify_audit_chain.py Auditor's reproduction script
│   ├── issue_dev_tokens.py   Mints HS256 JWTs for each role
│   ├── train_fraud_model.py  IsolationForest train + joblib dump
│   └── co_sign_daemon.py     3-of-5 multisig auto-confirm for live demo
│
└── tests/                    pytest + integration suites
    ├── test_audit_chain.py             1 000 events, chain integrity
    ├── test_anchor_service.py          Mock chain; assert root matches
    ├── test_merkle_proof.py            Cross-language vector against Solidity
    ├── test_fraud_rules.py             Each rule fires/doesn't on known inputs
    ├── test_fraud_scorer.py            Combined scoring; scorer_version idempotency
    ├── test_nira_mock.py               Deterministic results + breaker behaviour
    ├── test_idempotency.py             Same key → cached response
    ├── test_verify_endpoint.py         Public verifier (anon)
    └── integration/
        ├── test_full_title_lifecycle.py  Register → issue → anchor → verify
        └── test_anchor_to_chain.py       Live Anvil contract verifyProof
```

---

## 5. Routes (audit reference)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/verify/title` | **none** | Public Merkle-proof verifier (20/min/IP). |
| POST | `/api/v1/parcels` | SURVEYOR / REGISTRAR | Register parcel; GeoJSON validation; overlap check. |
| GET | `/api/v1/parcels/{upi}` | auth | Single parcel + status. |
| POST | `/api/v1/parcels/search/geo` | auth | PostGIS / Shapely geo search. |
| POST | `/api/v1/titles/issue` | REGISTRAR | Issue title; emit `TITLE_ISSUED`; enqueue anchor + fraud. |
| GET | `/api/v1/titles/{title_no}` | auth | Title + anchor metadata. |
| POST | `/api/v1/owners` | LAND_OFFICER / REGISTRAR | Create owner record. |
| POST | `/api/v1/owners/{id}/kyc` | LAND_OFFICER / REGISTRAR | NIRA-backed KYC; audited. |
| POST | `/api/v1/transfers` | LAND_OFFICER / CITIZEN | Initiate transfer; auto fraud-scored. |
| POST | `/api/v1/transfers/{id}/approve` | LAND_OFFICER / REGISTRAR | Move to APPROVED state. |
| POST | `/api/v1/disputes` | any | File a dispute; freezes parcel. |
| GET | `/api/v1/anchors` | auth | Browse anchor batches. |
| GET | `/api/v1/anchors/{batch_id}` | auth | Single batch detail. |
| GET | `/api/v1/anchors/title/{title_no}/proof` | none | Materialised Merkle proof. |
| POST | `/api/v1/anchors/flush/{district_id}` | REGISTRAR / ADMIN | Force-flush (demo). |
| GET | `/api/v1/fraud/reviews` | LAND_OFFICER / REGISTRAR | Pending human review queue. |
| POST | `/api/v1/fraud/review/{id}/affirm` | LAND_OFFICER / REGISTRAR | Affirm freeze; only path to FROZEN. |
| POST | `/api/v1/fraud/review/{id}/dismiss` | LAND_OFFICER / REGISTRAR | Dismiss as false positive. |
| POST | `/api/v1/ussd/callback` | AT-signed | USSD session callback (no JWT). |
| GET | `/api/v1/admin/audit/verify/{district_id}` | AUDITOR / ADMIN | Walk chain; return report. |
| POST | `/api/v1/demo/rpc-kill` | DEMO_MODE | Force-open the chain breaker. |
| POST | `/api/v1/demo/rpc-restore` | DEMO_MODE | Close it again. |
| GET | `/healthz` | none | Liveness. |
| GET | `/readyz` | none | Readiness (DB + Redis + breaker). |
| GET | `/metrics` | none | Prometheus exposition. |

OpenAPI 3.1 spec is auto-generated at `/openapi.json` (always) and served
at `/docs` (only when `ENV=dev`).

---

## 6. Configuration (env vars)

`app/config.py` is the source of truth. Settings refuse to load with
production-unsafe defaults when `ENV=prod`.

### Core

| Variable | Default (dev) | Notes |
| --- | --- | --- |
| `ENV` | `dev` | `dev` / `staging` / `prod` — gates safety checks |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `DATABASE_URL` | `sqlite:///./data_store/landguard.db` | Postgres in prod (`postgresql+asyncpg://...`) |
| `REDIS_URL` | `redis://redis:6379/0` | `memory://` for in-process dev |
| `JWT_SECRET` | (must set) | HS256 dev mode |
| `AUTH_MODE` | `hs256` | `hs256` / `oidc` |
| `OIDC_ISSUER` | — | Required when `AUTH_MODE=oidc` |
| `OIDC_AUDIENCE` | — | Required when `AUTH_MODE=oidc` |
| `OIDC_JWKS_URL` | — | Auto-discovered if blank |

### Blockchain

| Variable | Default | Notes |
| --- | --- | --- |
| `BLOCKCHAIN_PROVIDER` | `anvil` | `mock` / `anvil` / `sepolia` |
| `RPC_URL` | `http://anvil:8545` | Override for Sepolia / private chain |
| `CONTRACT_ADDRESS_FILE` | `data_store/contract_address.json` | Written by deploy script |
| `REGISTRAR_PRIVATE_KEY` | (Anvil account 0) | **NEVER set in prod** — use KMS / signer |
| `ANCHOR_FLUSH_INTERVAL_SECONDS` | `300` | 5 min |
| `ANCHOR_FLUSH_BATCH_SIZE` | `100` | Events per district before forced flush |
| `MULTISIG_ENABLED` | `false` | `true` activates 3-of-5 wrapper |
| `MULTISIG_ADDRESS` | — | Required when `MULTISIG_ENABLED=true` |

### NIRA

| Variable | Default | Notes |
| --- | --- | --- |
| `NIRA_PROVIDER` | `mock` | `mock` / `live` |
| `NIRA_BASE_URL` | — | Required when `live` |
| `NIRA_API_KEY` | — | Required when `live` — must come from KMS |
| `NIRA_CACHE_TTL` | `86400` | 24 h |

### Rate limits

| Variable | Default |
| --- | --- |
| `RATE_LIMIT_ANON` | `10/min` |
| `RATE_LIMIT_AUTH` | `60/min` |
| `RATE_LIMIT_ADMIN` | `300/min` |
| `RATE_LIMIT_PUBLIC_VERIFY` | `20/min/IP` |

### Demo mode

| Variable | Default | Notes |
| --- | --- | --- |
| `DEMO_MODE` | `false` | Enables `/api/v1/demo/*` routes |
| `DEMO_TOKEN` | — | Shared secret if you want to gate the panel |

### Observability

| Variable | Default | Notes |
| --- | --- | --- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | gRPC OTLP |
| `OTEL_SERVICE_NAME` | `landguard-backend` | |
| `PROMETHEUS_ENABLED` | `true` | Exposes `/metrics` |

---

## 7. Running tests

```bash
uv run pytest                              # full suite
uv run pytest -k "not integration"         # unit only
uv run pytest tests/integration/ -v        # integration (needs anvil + postgres)
uv run pytest --cov=app --cov-report=term  # with coverage
```

The integration tests spin up Anvil and the contract deploy automatically
via fixtures. CI runs the full suite in ~ 90 seconds.

For cross-language Merkle proof verification (Python ⇄ Solidity), see
`tests/test_merkle_proof.py` — it generates a proof in Python and verifies
it in Solidity via Foundry's `forge test --match-test`.

---

## 8. Database migrations

Migrations live in `app/db/migrations/`:

```
001_init.sql           Districts, owners, parcels, titles, transfers,
                       disputes, anchors, nira_verifications,
                       staff_users, audit_events, fraud_scores,
                       fraud_review_queue, fraud_watchlist
002_indexes.sql        GiST spatial index (Postgres) + B-tree indexes
003_seed_districts.sql Mityana, Wakiso, Kampala Central, Gulu
```

Apply with:

```bash
uv run python -c "from app.db.migrations import apply_all; apply_all()"
```

On SQLite WAL the GiST line is auto-skipped (raster check); on Postgres
PostGIS it applies.

---

## 9. Logging and observability

Structured JSON via `structlog`. Every line carries:

- `request_id` (from `X-Request-Id` header, generated if absent)
- `tenant_id` (the active district id; `-` for unauthenticated)
- `user_id` (for audit-relevant events)
- `event_type` (only present in audit-side messages)

Sensitive fields are never logged — `crypto.py:redact()` is applied to NIN,
phone numbers, and JWT bodies before structlog binding.

OpenTelemetry traces export via OTLP-gRPC (configured in `tracing.py`).
The included `monitoring/` directory has a working Prometheus + Grafana +
Jaeger stack:

```bash
docker compose --profile monitoring up -d
# Grafana: http://localhost:3001 (admin/admin)
# Jaeger:  http://localhost:16686
```

---

## 10. Audit chain reproduction

An auditor wanting to verify the integrity of a district's chain
independently:

```bash
# Pull all audit events for district 3 (Mityana) as canonical JSON:
curl -H "Authorization: Bearer $AUDITOR_TOKEN" \
  http://localhost:8000/api/v1/admin/audit/verify/3

# Or reproduce locally with the open-source verifier:
uv run python scripts/verify_audit_chain.py --district 3 --rpc-url $RPC_URL
```

The script reads each row, recomputes `row_hash = sha256(prev_hash + payload_hash)`,
walks forward, and reports the first divergence. It does not need to
trust the LandGuard backend code — only `audit/verifier.py` and the
database snapshot.

For the on-chain side, the same script then walks every `anchors` row,
recomputes the Merkle root from `audit_events.payload_hash` leaves, and
compares to the value the contract holds via `verifyProof`.

---

## 11. Migration to live infrastructure

| Component | Dev default | Production swap |
| --- | --- | --- |
| Database | SQLite WAL | Postgres 16 + PostGIS 3.4 — `DATABASE_URL=postgresql+asyncpg://...` |
| Cache | `memory://` LRU | Redis 7.4 — `REDIS_URL=rediss://...` |
| Blockchain | Anvil local | Sepolia (or future MoICT&NG permissioned chain) — `BLOCKCHAIN_PROVIDER=sepolia` |
| Signer | Anvil account 0 | KMS-held key with HSM custody — replace `REGISTRAR_PRIVATE_KEY` |
| NIRA | Mock client | Live API once MoICT&NG publishes the 2026 spec — `NIRA_PROVIDER=live` |
| Auth | HS256 + dev secret | RS256 OIDC against NITA-U IDP — `AUTH_MODE=oidc` |
| Custody | Single key | 3-of-5 `MultiSigRegistrar` — `MULTISIG_ENABLED=true` |

Each swap is documented inline at the top of the corresponding module
under a `# MIGRATION:` comment.

---

## 12. Security posture

- **PII at rest**: NIN encrypted with AES-GCM; only `sha256(nin)` is
  queryable. Decryption gated by role + audit-emitted on every read.
- **Audit trail**: every mutation, every NIRA call, every login, every
  fraud action ≠ NONE, every NIN decryption.
- **Tenancy**: per-district row-level isolation. Postgres RLS in prod;
  repository-layer filter in SQLite dev. Auth context sets
  `app.district_id` per request.
- **Rate limiting**: tiered slowapi (`anon=10/min`, `auth=60/min`,
  `admin=300/min`, `public_verify=20/min/IP`).
- **Idempotency**: `Idempotency-Key` UUIDv4 required on every mutating
  verb; 24 h Redis dedupe.
- **Resilience**: CircuitBreaker on the chain client and the NIRA client
  — RPC outages queue anchors but never block off-chain writes.
- **Inputs**: Pydantic v2 strict with `extra='forbid'`; UPI / NIN regex;
  Shapely `is_valid` + `is_simple` on GeoJSON; area sanity bounds.

A full threat model lives at `docs/audit/THREAT_MODEL.md`.

---

## 13. Common operations

```bash
# Add a new district
uv run python -c "from app.db.queries.districts import insert; \
  insert(code='MUK', name='Mukono', region='Central')"

# Recompute fraud scores for an existing transfer batch
uv run python -c "from app.fraud.scorer import rescore_all; rescore_all()"

# Force-anchor a district immediately
curl -X POST -H "Authorization: Bearer $REGISTRAR_TOKEN" \
  http://localhost:8000/api/v1/anchors/flush/3

# Rotate the registrar key (production)
# 1. Generate new key in KMS, write its public address
# 2. Add new key to MultiSigRegistrar via 3-of-5 vote
# 3. Update REGISTRAR_PRIVATE_KEY env / KMS reference
# 4. Remove old key via second 3-of-5 vote
# See docs/CUSTODY.md
```
