# LandGuard Uganda — Architecture

This document is the engineer's-eye view of LandGuard. It explains *why*
the system is shaped the way it is, the boundaries between components,
the data flow that produces a verifiable land title, the trust and
tenancy model, the resilience and degradation behaviour, and the threat
model that drove the security decisions.

For setup and operations, see:

- [`../backend/README.md`](../backend/README.md) — backend
- [`../frontend/README.md`](../frontend/README.md) — frontend
- [`../contracts/README.md`](../contracts/README.md) — smart contracts
- [`./REQUIREMENTS.md`](./REQUIREMENTS.md) — system requirements + evaluation mapping
- [`./DESIGN_SYSTEM.md`](./DESIGN_SYSTEM.md) — UI/UX contract

---

## 1. The system in one diagram

```
                   ┌─────────────────────────────────────────────┐
                   │              Citizens & Auditors            │
                   │                                             │
                   │   smartphone (PWA) ─┐                       │
                   │   feature phone (USSD) ─┐                   │
                   │   printed certificate (QR) ─┐               │
                   │   journalist / NGO (curl /verify) ─┐        │
                   └────────────────────────────┬───────┘        │
                                                │                │
                          ┌─────────────────────┼────────────────┘
                          │                     │
                          ▼                     ▼
            ┌──────────────────────┐   ┌──────────────────────┐
            │  Next.js 16 PWA      │   │ USSD / SMS gateway   │
            │  + Officer console   │   │ (Africa's Talking)   │
            │  (Bun, Tailwind 4)   │   │                      │
            └─────────────┬────────┘   └─────────────┬────────┘
                          │                          │
                          └────────────┬─────────────┘
                                       │ HTTPS (Caddy + ACME)
                                       ▼
            ┌────────────────────────────────────────────────────┐
            │  FastAPI 0.111 backend  (Python 3.12, uv)          │
            │  ────────────────────────────────────────────────  │
            │  Zero-trust JWT auth      RS256 (OIDC) / HS256     │
            │  Per-district audit ledger   hash-chained          │
            │  Tenancy (Postgres RLS)   row-level isolation      │
            │  Fraud worker              IsoForest + rules       │
            │  Anchor service            CircuitBreaker-wrapped  │
            │  NIRA client               mock | live | breaker   │
            └─────────────┬──────────────────────────────────────┘
                          │ web3.py async over HTTPS / WSS
                          ▼
            ┌────────────────────────────────────────────────────┐
            │  MultiSigRegistrar.sol   3-of-5 named signers      │
            │  LandRegistryAnchor.sol  immutable per-batch root  │
            │  ────────────────────────────────────────────────  │
            │  Anvil (local) · Sepolia (one env var) ·           │
            │  any EVM chain (EAC / MoICT&NG permissioned)       │
            └────────────────────────────────────────────────────┘
                          │
                          │  events: AnchorCommitted, ProposalCreated, ...
                          ▼
            ┌────────────────────────────────────────────────────┐
            │  Observability                                     │
            │  OpenTelemetry (OTLP-gRPC) → Jaeger / Tempo        │
            │  Prometheus → Grafana                              │
            │  Structured JSON logs → Loki                       │
            └────────────────────────────────────────────────────┘
```

---

## 2. The dual-layer trust model

Why **off-chain hash chain + on-chain anchor** instead of either alone:

| Approach | Speed | Cost | Tamper-evidence | Public verifiability |
| --- | --- | --- | --- | --- |
| Off-chain DB only | Fast | Cheap | Depends on operator honesty | None |
| On-chain everything | Slow | Expensive | Strong | Strong, but PII leaks |
| **Dual-layer (LandGuard)** | **Fast** | **~Pennies/batch** | **Strong** | **Strong, no PII on-chain** |

### 2.1 Off-chain: per-district hash-chained ledger

`backend/app/audit/ledger.py` implements an append-only ledger keyed on
`tenant_id = str(district_id)`. Each event row carries:

| Column | Type | Purpose |
| --- | --- | --- |
| `event_id` | UUIDv4 | Idempotent identity |
| `tenant_id` | str | District scope (`= str(district_id)`) |
| `event_type` | enum | `TITLE_ISSUED \| TRANSFER_INITIATED \| TRANSFER_COMPLETED \| DISPUTE_FILED \| OWNERSHIP_FROZEN \| KYC_VERIFIED \| KYC_REJECTED \| ANCHOR_COMMITTED \| FRAUD_HUMAN_AFFIRMED` |
| `payload_json` | text | Canonical JSON (sorted keys, ASCII-safe) |
| `seq` | int | Monotonic per district |
| `prev_hash` | hex(64) | `row_hash` of the previous event in this district's chain |
| `payload_hash` | hex(64) | `sha256(payload_json)` |
| `row_hash` | hex(64) | `sha256(prev_hash + payload_hash)` |
| `anchored_in` | uuid | FK to `anchors.batch_id` (NULL until anchored) |
| `created_at` | timestamp | UTC |

The append is mutex-guarded per tenant — see `ledger.py:append()` for
the `asyncio.Lock` keyed on tenant id. Two writes to the same district
serialise; writes to different districts proceed in parallel.

Verification (`audit/verifier.py`) walks the chain and recomputes both
hashes per row. Any divergence proves tampering and reports the first
corrupt `seq` — an auditor running the script does not need to trust
the LandGuard service code, only the verifier code.

### 2.2 On-chain: Merkle root anchoring

Every `ANCHOR_FLUSH_INTERVAL_SECONDS` (default 300s) **or** when a
district has `ANCHOR_FLUSH_BATCH_SIZE` (default 100) unanchored events,
the **AnchorService** in `backend/app/blockchain/anchor_service.py`:

1. Selects unanchored events for the district:
   ```sql
   SELECT seq, payload_hash
   FROM audit_events
   WHERE tenant_id = ? AND anchored_in IS NULL
   ORDER BY seq;
   ```
2. Computes a Bitcoin-style Merkle root over the `payload_hash` leaves
   (`audit/merkle.py:compute_merkle_root_sha256`). Last-leaf
   duplication where the layer width is odd.
3. Computes a parallel **EVM-style** root for on-chain anchoring:
   leaves become `keccak256(sha256_hex_leaf)`, internal nodes use
   sorted-pair `keccak256(min(a,b), max(a,b))` — matching
   OpenZeppelin's `MerkleProof.verify`. Implementation in
   `audit/merkle.py:compute_merkle_root_evm`.
4. Calls `LandRegistryAnchor.commitBatch(districtId, batchId, evmRoot)`
   via `web3.py`. In multi-sig mode the call routes through
   `MultiSigRegistrar.proposeBatch` → 3 confirmations → execute.
5. On confirmation, writes the `anchors` row and marks the events
   `anchored_in = batch_id`. Emits an `ANCHOR_COMMITTED` event so even
   the anchor itself is part of the chain.

The whole call is wrapped in a `CircuitBreaker` (`app/resilience.py`)
so RPC outages don't block off-chain writes — they just queue.

### 2.3 The dual-hash decision (ADR-0001)

We use **SHA-256 off-chain** and **Keccak-256 on-chain**. Why:

- SHA-256 is the universal language of audit verifiers — every
  library, every CLI, every government compliance tool speaks it. The
  off-chain ledger is read by auditors with `sha256sum` and a curl.
- Keccak is the EVM-native primitive. Importing a SHA-256 library
  on-chain doubles gas cost.

The two are bridged by `sha256_leaves_to_keccak()`: at anchor time we
take the SHA-256 leaves and hash each one with Keccak, then build a
sorted-pair Keccak tree. The off-chain proof carries both forms; the
on-chain `verifyProof` checks the Keccak path.

Full rationale at `docs/adr/0001-dual-merkle-regime.md`.

---

## 3. Data flow: from parcel to verified title

The sequence below is the full path Mrs. Sarah Nakato's title takes from
"surveyor draws polygon" to "audience scans QR and verifies on chain."

```
┌──────────────────┐ 1. SURVEYOR        ┌──────────────────┐
│ surveyor (laptop)│ POST /parcels      │ FastAPI :8000    │
│ MapParcelDrawer  ├───────────────────▶│ parcels router   │
└──────────────────┘  GeoJSON polygon   └────────┬─────────┘
                                                 │
                                                 │ 2. Shapely is_valid +
                                                 │    Turf overlap check
                                                 │ 3. INSERT INTO parcels
                                                 │ 4. audit/ledger.append(
                                                 │    PARCEL_REGISTERED, district_id)
                                                 ▼
                                        ┌──────────────────┐
                                        │ Postgres / SQLite│
                                        │  parcels table   │
                                        │  audit_events    │
                                        └──────────────────┘

┌──────────────────┐ 5. REGISTRAR       ┌──────────────────┐
│ registrar console│ POST /titles/issue │ FastAPI titles   │
│ Issue button     ├───────────────────▶│ + services/title_│
└──────────────────┘                    │ issuance.py      │
                                        └────────┬─────────┘
                                                 │ 6. compute content_hash
                                                 │ 7. INSERT titles
                                                 │ 8. audit append TITLE_ISSUED
                                                 │ 9. enqueue fraud scoring
                                                 │ 10. enqueue anchor flush check
                                                 ▼
                                        ┌──────────────────┐
                                        │ Redis stream     │
                                        │ stream:fraud:    │
                                        │   scoring        │
                                        └────────┬─────────┘
                                                 │ 11. async task consumes
                                                 ▼
                                        ┌──────────────────┐
                                        │ fraud/worker.py  │
                                        │ rules + IsoForest│
                                        │ → fraud_scores +  │
                                        │   fraud_review_q │
                                        └──────────────────┘

  (parallel — every 5 min OR ≥ 100 events per district)
                                        ┌──────────────────┐
                                        │ anchor_service.py│
                                        │ 12. SELECT unanchored events │
                                        │ 13. compute SHA-256 root      │
                                        │ 14. compute EVM-keccak root   │
                                        │ 15. call MultiSig.proposeBatch│
                                        └────────┬─────────┘
                                                 │ 16. 3 of 5 confirmations
                                                 │ 17. executeProposal()
                                                 │ 18. LandRegistryAnchor
                                                 │     .commitBatch(districtId,
                                                 │       batchId, root)
                                                 ▼
                                        ┌──────────────────┐
                                        │ Anvil / Sepolia  │
                                        │ AnchorCommitted  │
                                        │ event emitted    │
                                        └────────┬─────────┘
                                                 │ 19. tx receipt
                                                 ▼
                                        ┌──────────────────┐
                                        │ UPDATE anchors,  │
                                        │ audit_events     │
                                        │ append ANCHOR_   │
                                        │ COMMITTED        │
                                        └──────────────────┘

┌──────────────────┐ 20. AUDIENCE       ┌──────────────────┐
│ smartphone       │ POST /verify/title │ verify router    │
│ scans QR         ├───────────────────▶│ (no auth, 20/min)│
└──────────────────┘  title_no in body  └────────┬─────────┘
                                                 │ 21. SELECT title +
                                                 │     content_hash
                                                 │ 22. SELECT anchor batch
                                                 │ 23. build Merkle proof
                                                 │ 24. ContractAnchor
                                                 │     .verifyProof(...)
                                                 │     (free view call)
                                                 ▼
                                        ┌──────────────────┐
                                        │ Returns          │
                                        │ { valid: true,   │
                                        │   block_number,  │
                                        │   tx_hash,       │
                                        │   batch_id }     │
                                        └──────────────────┘
```

Every step in the diagram has a corresponding audit event. The chain of
events for one title looks like:

```
PARCEL_REGISTERED (seq 1041)
  → TITLE_ISSUED (seq 1042)
  → ANCHOR_COMMITTED batch=8f3a..., includes seqs 1042..1099 (seq 1100)
  → TRANSFER_INITIATED (seq 1187)
  → TRANSFER_COMPLETED (seq 1188)
  → ANCHOR_COMMITTED batch=c127..., includes seqs 1188..1241 (seq 1242)
```

Three of these events (the `ANCHOR_COMMITTED` rows) reference the
on-chain transaction; the rest are pure off-chain ledger entries. The
title's `content_hash` participated in both batches via inclusion in the
seq ranges.

---

## 4. Tenancy and row-level isolation

Every business table carries `district_id` and every row is gated by
`AuthContext.tenant_id` (`= str(district_id)`).

### 4.1 Postgres (production)

Row-level security policies are enforced by Postgres:

```sql
ALTER TABLE titles ENABLE ROW LEVEL SECURITY;

CREATE POLICY titles_tenant ON titles
    USING (
        district_id = current_setting('app.district_id')::int
        OR current_setting('app.bypass', true) = 'on'
    );
```

The auth middleware (`app/middleware/audit_actor.py`) sets
`SET LOCAL app.district_id = <id>` at the start of every request inside
a transaction. `ADMIN` and `AUDITOR` roles additionally set
`SET LOCAL app.bypass = 'on'` so cross-district auditing works.

### 4.2 SQLite (development)

SQLite has no RLS. The same isolation is enforced in the repository
layer:

```python
def list_titles(conn: Connection, tenant_id: str) -> list[Title]:
    cur = conn.execute(
        "SELECT * FROM titles WHERE district_id = ?", (int(tenant_id),)
    )
    return [Title(**row) for row in cur.fetchall()]
```

Both code paths route through `app/database.py:get_connection()` so
behaviour is symmetric: the same router code works against either
backend without conditionals.

### 4.3 Role taxonomy

| Role | Description | Default tenant scope |
| --- | --- | --- |
| `CITIZEN` | Owner viewing their own parcels / titles | Own district only |
| `SURVEYOR` | Field surveyor registering parcels | Assigned district |
| `LAND_OFFICER` | KYC + transfer review + fraud queue | Assigned district |
| `REGISTRAR` | Title issuance + dispute resolution | Assigned district |
| `AUDITOR` | Chain integrity + audit-trail review | All districts (RLS bypass) |
| `PUBLIC_VERIFIER` | Anonymous verification | N/A (public route) |
| `ADMIN` | District + staff management | All districts (RLS bypass) |

---

## 5. Fraud detection — explainable by design

`backend/app/fraud/` combines hand-coded rules with an
IsolationForest. Why not deep learning:

- Evaluators (judges, district registrars) must read signal explanations
  in plain English. A neural net's "0.83 anomaly score" isn't acceptable
  for a state institution making custodial decisions.
- We don't have labelled fraud data at scale yet.
- Rules + IsolationForest is fast to retrain and trivially explainable.

### 5.1 The rule set

| Rule | Weight | Fires when |
| --- | --- | --- |
| `geometry_overlap` | 30 | Shapely intersection > 5% with any active parcel |
| `rapid_retransfer` | 20 | > 2 transfers in 90 days on the same parcel |
| `nin_reuse` | 15 | NIN used in > 5 × district-median transactions in 30 days |
| `size_anomaly` | 10 | abs(z-score) > 3 against district size norm |
| `watchlist_name_similarity` | 20 | RapidFuzz token-set ratio > 85 vs `fraud_watchlist` |
| `consideration_anomaly` | 15 | UGX/ha z-score extreme against district norm |
| `nira_kyc` | 25 | NIRA returns no match for the supplied NIN |

Each rule returns a `RuleSignal(name, weight, score, explanation)`. The
`explanation` is plain-English copy that surfaces directly in the
officer review UI.

### 5.2 The ML side

`scorer.py` loads an `IsolationForest(n_estimators=200, contamination=0.05)`
trained on `seed_data` (synthetic transfers) + accumulated real data
once available. Feature vector:

```python
[
    hours_since_last_transfer,
    log1p(consideration),
    log1p(area_ha),
    owner_age_days,
    prior_parcel_count,
    prior_dispute_count,
    district_norm_z,
    hour_of_day,
    weekday,
]
```

The score combines into:

```python
risk_score = min(100, int(60 * iso_score + sum(rule.weight * rule.score for rule in fires)))
action = "BLOCK" if risk_score >= 75 else "FLAG" if risk_score >= 40 else "NONE"
```

### 5.3 Human-in-the-loop is mandatory

`fraud/worker.py` writes to `fraud_review_queue` — it **never** freezes
a parcel directly. The only path to FROZEN is
`POST /api/v1/fraud/review/{id}/affirm` by a `LAND_OFFICER` or
`REGISTRAR`. The audit chain records `FRAUD_HUMAN_AFFIRMED` with the
officer's user id.

This is the visual / behavioural anchor of the AI Ethics Charter. See
`docs/AI_ETHICS_CHARTER.md` for the full policy.

### 5.4 Demographic-parity audit

`backend/scripts/fraud_parity_audit.py` is the quarterly tool. It
computes the false-positive rate of `FLAG` and `BLOCK` actions, broken
down by district and tenure type, and outputs a report. If parity
divergence exceeds a configurable threshold, the report flags the
scorer version for retraining.

---

## 6. Resilience and degradation

The system is designed so that the **off-chain ledger never blocks on
the on-chain anchor**. This is the architectural argument behind Act 5
of the showcase ("kill the blockchain, system keeps working").

| Outage | Behaviour |
| --- | --- |
| Blockchain RPC down | Off-chain writes continue; anchors queue per district; `anchor_breaker` opens; public verify returns `pending_anchor: true` for unanchored titles |
| Redis down | Idempotency falls back to per-worker in-memory LRU; rate-limiting falls back to in-process; cache misses cause more NIRA calls but no errors |
| NIRA down | NIRA breaker opens; cached results returned with `stale: true`; KYC endpoint surfaces 503 + retry hint |
| Postgres down | Hard fail; readiness goes red; intentional — there's no useful fallback |
| OIDC IdP down | Cached JWKS used for up to 1 h; new authentications fail closed |
| Venue Wi-Fi down (showcase) | PWA verifies against cached proofs; Mi-Fi backup; USSD path unaffected (Africa's Talking is over GSM) |

The graceful-degradation tests live in `backend/tests/test_resilience.py`.

### 6.1 Circuit breaker tuning

`app/resilience.py:CircuitBreaker`:

| Parameter | Default | Reasoning |
| --- | --- | --- |
| `failure_threshold` | 3 | Three consecutive failures opens |
| `recovery_timeout` | 30 s | Half-open probe after 30 s |
| `success_threshold` | 2 | Two consecutive successes closes |
| `expected_exception` | `Web3Exception` / `httpx.RequestError` | Only these trip the breaker |

The breaker state is exposed via the `/readyz` endpoint and via the
`anchor_breaker_open` / `nira_breaker_open` Prometheus gauges.

---

## 7. Threat model (abbreviated)

Full threat model at `docs/audit/THREAT_MODEL.md`. The abbreviated form:

| Threat | Mitigation |
| --- | --- |
| Insider tampers with a district's DB | Audit chain verifier detects within seconds; on-chain Merkle root would not match recomputed root |
| Forged title certificate | Public verifier rejects (`content_hash` + proof don't match anchored root) |
| Stolen NIN used to claim parcel | NIRA biometric mismatch fires + fraud rule `nira_kyc` |
| Stolen registrar credentials | Per-action audit emission means after-the-fact attribution is forensically reliable; circuit-breaker outage cap limits damage during compromise; 3-of-5 multi-sig means a stolen key alone cannot anchor |
| Public verifier DoS | `slowapi` rate limit at 20/min/IP; CDN cache layer for repeat queries |
| Smart contract bug | OpenZeppelin Pausable kill switch; admin can pause new commits while a fix is deployed; existing anchors remain valid |
| Side-channel via timing | All hash comparisons use `hmac.compare_digest`; auth uses constant-time paths |
| Replay of mutating requests | Idempotency-Key UUIDv4 required on every mutation; 24 h Redis dedupe |
| PII leak via logs | `crypto.py:redact()` applied to NIN, phone, JWT bodies before structlog binding |
| Cross-district information leakage | Postgres RLS; SQLite repository-layer filter; both validated by `test_tenancy.py` |

---

## 8. Observability

Three signal types, each with a dedicated path:

### 8.1 Metrics (Prometheus)

| Metric | Type | Use |
| --- | --- | --- |
| `anchor_batches_total{district,status}` | counter | Anchor success / fail by district |
| `anchor_failures_total` | counter | Includes breaker-open and tx-failure |
| `anchor_breaker_open` | gauge | 1 when the breaker is open |
| `fraud_blocks_total{district}` | counter | Officer-affirmed freezes |
| `fraud_flags_total{district}` | counter | ML flags (not yet affirmed) |
| `nira_calls_total{result}` | counter | success / cached / failed |
| `audit_failure_total` | counter | Failed audit-event appends (should be 0) |
| `verify_requests_total{result}` | counter | Public verifier outcomes |
| `http_request_duration_seconds` | histogram | All HTTP handlers |

### 8.2 Traces (OpenTelemetry)

Every HTTP request becomes a root span. The span tree for
`POST /titles/issue` looks like:

```
POST /titles/issue
├── auth.verify_jwt
├── db.transaction
│   ├── parcels.lookup
│   ├── titles.insert
│   └── audit.append (TITLE_ISSUED)
├── redis.publish (stream:fraud:scoring)
└── anchor_service.maybe_flush_check
```

Spans carry the `request_id`, `tenant_id`, and `user_id` attributes.
Exported via OTLP-gRPC to Jaeger / Tempo.

### 8.3 Logs (structlog → JSON → Loki)

Every line carries:

- `timestamp` (UTC, RFC 3339)
- `level`
- `request_id`
- `tenant_id` (or `-`)
- `user_id` (when applicable)
- `event` (the message)
- Any keyed context

PII is redacted before binding (`crypto.py:redact()`).

---

## 9. Testing strategy

| Layer | Tool | Lives at |
| --- | --- | --- |
| Backend unit + repository | pytest | `backend/tests/test_*.py` |
| Backend integration | pytest-asyncio + httpx | `backend/tests/integration/` |
| Smart contract | Foundry forge | `contracts/test/*.t.sol` |
| Cross-language Merkle | both | `backend/tests/test_merkle_proof.py` + `contracts/test/LandRegistryAnchor.t.sol` |
| Frontend unit | Vitest | `frontend/src/__tests__/` |
| Frontend E2E | Playwright | `frontend/e2e/*.spec.ts` |
| Nightly demo rehearsal | Playwright | `frontend/e2e/demo-storyboard.spec.ts` |
| Resilience / degradation | pytest with fault injection | `backend/tests/test_resilience.py` |

The full suite (unit + integration + contract + frontend unit + E2E)
runs in ~ 5 minutes in CI.

The cross-language Merkle test is the most important single test in the
codebase: it asserts that a Merkle proof generated by the Python ledger
verifies byte-for-byte in the Solidity contract. If that test passes,
the dual-hash regime is sound.

---

## 10. Migration paths

### 10.1 Dev → staging

```
DEMO_MODE=false                          # disable /api/v1/demo/*
DATABASE_URL=postgresql+asyncpg://...    # SQLite → Postgres + PostGIS
REDIS_URL=rediss://...                   # in-memory → real Redis
BLOCKCHAIN_PROVIDER=sepolia              # mock/Anvil → Sepolia
ENV=staging                              # gate prod safety checks
AUTH_MODE=oidc                           # HS256 → OIDC against NITA-U
NIRA_PROVIDER=live                       # mock → live (when API published)
MULTISIG_ENABLED=true                    # single key → 3-of-5
```

### 10.2 Staging → production

Same env diff, plus:

- `ENV=prod` activates safety checks (`config.py` refuses to start if
  `JWT_SECRET` is the dev default, if RPC URL is localhost, etc.)
- TLS via Caddy with auto-ACME
- Registrar private key moves to KMS / HSM-backed signer
- Observability stack (Prometheus + Grafana + Jaeger) becomes
  production infrastructure with retention + alerting

### 10.3 Sepolia → MoICT&NG permissioned chain

The contracts are EVM-only with no chain-specific code. The migration:

1. Deploy both contracts to the new chain.
2. Re-anchor the existing event ranges (idempotent — same batch IDs).
3. Update `BLOCKCHAIN_PROVIDER` env to point at the new chain.
4. Run the cross-language Merkle verification (`forge test --rpc-url <new>`).
5. Decommission the Sepolia anchors (they remain valid for historical
   verification but no new batches are committed there).

---

## 11. What is *not* in scope for the prototype

- Real biometric verification (we hash the supplied template; live
  NIRA biometric matching is documented but not implemented).
- Cross-district transfers (each district anchors independently;
  cross-district moves need a coordinator service that's intentionally
  out of scope here).
- Bidirectional sync with the existing Ugandan Land Information
  System (ULS) — we have read-only stubs in `app/nira/` shape, but the
  LIS schema is not public yet.
- Multi-language UI beyond English — Luganda translation is on the
  post-pilot roadmap.
- Mobile-app native build — the PWA is the only mobile target.

These omissions are deliberate. Each one is a real engineering project
in its own right and adding it now would dilute the showcase. See
`docs/REQUIREMENTS.md` § 9 for the explicit "out of scope" list.
