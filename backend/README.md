# LandGuard backend

FastAPI 0.111 · Python 3.12 · uv · async-friendly.

## Layout

```
backend/
├── app/
│   ├── main.py               FastAPI entrypoint, lifespan, middleware
│   ├── config.py             pydantic-settings (validates prod safety)
│   ├── database.py           SQLite WAL dev / Postgres prod dispatch
│   ├── resilience.py         CircuitBreaker (3-failure threshold)
│   ├── crypto.py             AES-GCM for NIN at-rest encryption
│   ├── audit/                Hash-chained ledger + Merkle helpers
│   ├── auth/                 JWT (HS256 dev | RS256 OIDC prod)
│   ├── blockchain/           web3.py client + anchor service + Anvil/Sepolia
│   ├── nira/                 Mock + live NIRA clients, breaker-wrapped
│   ├── fraud/                Rule engine + IsolationForest + Redis worker
│   ├── middleware/           Idempotency, rate limits, request_id
│   ├── models/               Pydantic v2 strict request/response shapes
│   ├── routers/              FastAPI route packages
│   ├── util/                 hashing, geo, ids, metrics, cache
│   └── db/migrations/        001_init.sql (idempotent, backend-agnostic)
├── scripts/                  Seeds + deploys + token issuance
└── tests/                    pytest + integration suites
```

## Routes

| Path | Auth | Purpose |
|---|---|---|
| `POST /api/v1/verify/title` | **none** | Public Merkle-proof verifier (rate-limited). |
| `POST /api/v1/parcels` | SURVEYOR/REGISTRAR | Register parcel with GeoJSON validation. |
| `POST /api/v1/titles/issue` | REGISTRAR | Issue title + emit `TITLE_ISSUED` audit + enqueue anchor + fraud score. |
| `POST /api/v1/owners/{id}/kyc` | LAND_OFFICER/REGISTRAR | NIRA-backed KYC; caches result; updates status. |
| `POST /api/v1/transfers` | LAND_OFFICER/CITIZEN | Initiate transfer; auto-scored by fraud worker. |
| `POST /api/v1/disputes` | any authenticated | File a dispute; freezes parcel for fraud/overlap/ownership. |
| `GET  /api/v1/anchors` | auth | List anchor batches per district. |
| `POST /api/v1/anchors/flush/{district_id}` | REGISTRAR/ADMIN | Force-flush an anchor batch (demo control). |
| `POST /api/v1/demo/rpc-kill` | (DEMO_MODE only) | Force-open the blockchain breaker. |
| `GET  /api/v1/admin/audit/verify/{district_id}` | AUDITOR/ADMIN | Walk the chain, return verification report. |
| `GET  /healthz` `/readyz` `/metrics` | none | Liveness, readiness, Prometheus. |

## Tests

```bash
uv run pytest                    # full suite
uv run pytest tests/test_audit_chain.py -v
uv run pytest tests/test_anchor_service.py -v
uv run pytest tests/test_fraud_rules.py -v
```

## Migration to live NIRA + Sepolia

Two env vars do the whole switch:

```bash
NIRA_PROVIDER=live
NIRA_BASE_URL=https://nira.ug/api
NIRA_API_KEY=...    # from KMS

BLOCKCHAIN_PROVIDER=sepolia
SEPOLIA_RPC_URL=...
REGISTRAR_PRIVATE_KEY=...  # from KMS, NOT env, in prod
```

See `app/nira/live_client.py` and `app/blockchain/sepolia_client.py` for the
`# MIGRATION` comments.
