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

- **`backend/`** — FastAPI service: routes, audit ledger, fraud scorer with
  human-in-the-loop, NIRA client, blockchain client (mock/anvil/sepolia/multisig),
  USSD + SMS verifier. See [`backend/README.md`](./backend/README.md).
- **`frontend/`** — Next.js 16 (Bun) UI: public verifier, citizen portal,
  surveyor map drawer, officer review queue, registrar console, auditor console,
  demo control panel, printable title certificate with QR.
- **`contracts/`** — `LandRegistryAnchor.sol` + `MultiSigRegistrar.sol` with
  Foundry tests.
- **`docs/`** — Architecture, custody model, AI ethics charter, MOU template,
  audit package, threat model, USSD deployment guide, ADRs.
- **`scripts/`** — Cross-cutting dev/demo orchestration.
- **`monitoring/`** — Prometheus + Grafana for showcase observability.

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

**LandGuard Uganda Team** · `kalemaaaaaaaa@gmail.com`
