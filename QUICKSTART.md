# QUICKSTART — LandGuard Uganda

Local end-to-end bring-up in about five minutes. Works on Linux, macOS, and Windows via Docker Desktop.

## Prerequisites

- Docker 24+ with Compose v2
- (Optional, for non-Docker dev) `uv` 0.4+, `bun` 1.1+, and Foundry's `forge` 0.2+

## Path A — Docker only (recommended for the first run)

```bash
# 1. Bring everything up: Anvil, Postgres, Redis, contract-deploy, backend, frontend.
docker compose --profile default up -d --build

# 2. Apply migrations + seed the showcase narrative.
docker compose exec backend python scripts/seed_districts.py
docker compose exec backend python scripts/seed_demo.py

# 3. Train the IsolationForest fraud model (one-shot, ~10 seconds).
docker compose exec backend python scripts/train_fraud_model.py

# 4. (Optional) Mint dev tokens for the demo roles.
docker compose exec backend python scripts/issue_dev_tokens.py
```

That's it. Open:

- **<http://localhost:3000>** — public landing
- **<http://localhost:3000/verify>** — public verifier
- **<http://localhost:3000/demo?demo=1>** — demo control panel (Act 5)
- **<http://localhost:8000/docs>** — backend OpenAPI

## Path B — Native (no Docker for backend + frontend)

Useful when you're iterating on the FastAPI or Next.js code.

```bash
# Backend
cd backend
cp .env.example .env
uv sync
uv run python scripts/seed_districts.py
uv run python scripts/seed_demo.py
uv run python scripts/train_fraud_model.py
uv run uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
cp .env.local.example .env.local
bun install
bun dev   # http://localhost:3000
```

You still need Anvil running if `BLOCKCHAIN_PROVIDER=anvil`:

```bash
docker compose up -d anvil
docker compose run --rm contract-deploy
```

## Path C — Sepolia (real testnet)

```bash
export SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/YOUR_KEY
export SEPOLIA_REGISTRAR_PRIVATE_KEY=0x...   # fund it from a Sepolia faucet
docker compose -f docker-compose.yml -f docker-compose.sepolia.yml up -d --build
```

The contract isn't auto-deployed in this mode. Run:

```bash
cd contracts
forge create --rpc-url $SEPOLIA_RPC_URL --private-key $SEPOLIA_REGISTRAR_PRIVATE_KEY \
    src/LandRegistryAnchor.sol:LandRegistryAnchor \
    --constructor-args $(cast wallet address $SEPOLIA_REGISTRAR_PRIVATE_KEY)
```

Pin the address into `backend/data_store/contract_address.json`:

```json
{"address": "0x...", "sepolia": "0x...", "chain_id": 11155111}
```

## Verify your install

```bash
# Backend tests
cd backend && uv run pytest -q

# Foundry contract tests (requires forge)
cd contracts && forge test -vvv

# Frontend tests
cd frontend && bun run test
```

## Troubleshooting

- **Anvil unhealthy** → Check `docker compose logs anvil`. It typically wants 10 seconds to spin up.
- **Contract address not found** → Re-run `docker compose run --rm contract-deploy`.
- **Postgres credentials** → Defaults are `landguard/landguard/landguard`. Change in `docker-compose.yml`.
- **Tx Pending after RPC kill** → That's the **point** of Act 5 — restore via the demo panel.
- **Permission prompts on macOS** for camera (QR scanner) → grant in System Settings → Privacy → Camera.
