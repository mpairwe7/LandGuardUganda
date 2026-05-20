# LandGuard Architecture

## The dual-layer trust model

Why **off-chain hash chain + on-chain anchor** instead of either alone:

| Approach | Speed | Cost | Tamper-evidence | Public verifiability |
|---|---|---|---|---|
| Off-chain DB only | Fast | Cheap | Depends on operator honesty | None |
| On-chain everything | Slow | Expensive | Strong | Strong, but with PII leakage |
| **Dual-layer (LandGuard)** | **Fast** | **~Pennies/batch** | **Strong** | **Strong, no PII on-chain** |

### Off-chain: per-district hash-chained ledger

`backend/app/audit/ledger.py` implements an append-only ledger keyed on
`tenant_id = str(district_id)`. Each event row:

- `event_id` — UUIDv4
- `event_type` — `TITLE_ISSUED | TRANSFER_INITIATED | TRANSFER_COMPLETED | DISPUTE_FILED | OWNERSHIP_FROZEN | KYC_VERIFIED | KYC_REJECTED | ANCHOR_COMMITTED | FRAUD_BLOCK`
- `payload_json` — canonical (sorted-key, ASCII-safe) JSON
- `seq` — monotonic per-district
- `prev_hash` — `row_hash` of the previous event in this district's chain
- `payload_hash` — `sha256(payload_json)`
- `row_hash` — `sha256(prev_hash + payload_hash)`
- `anchored_in` — FK to `anchors.batch_id` (NULL until anchored)

Verification (`audit/verifier.py`) walks the chain and recomputes both hashes per row; any divergence proves tampering and reports the first corrupt `seq`.

### On-chain: Merkle root anchoring

Every `ANCHOR_FLUSH_INTERVAL_SECONDS` (default 300s) **or** when a district has `ANCHOR_FLUSH_BATCH_SIZE` (default 100) unanchored events, the **AnchorService** in `backend/app/blockchain/anchor_service.py`:

1. Selects unanchored events for the district (`SELECT seq, payload_hash FROM audit_events WHERE tenant_id = ? AND anchored_in IS NULL`).
2. Computes a Bitcoin-style Merkle root over the `payload_hash` leaves (`audit/merkle.compute_merkle_root`).
3. Calls `LandRegistryAnchor.commitBatch(districtId, batchId, merkleRoot)` via `web3.py`. The call is wrapped in a `CircuitBreaker` so RPC outages don't block off-chain writes.
4. On confirmation, writes the `anchors` row and marks the events `anchored_in = batch_id`. Emits an `ANCHOR_COMMITTED` audit event so even the anchor itself is part of the chain.

### On-chain hashing detail

For gas efficiency the **contract** uses keccak256-based Merkle verification with sorted-pair hashing. The **off-chain ledger** uses SHA-256 hex hashes. The bridge:

- Backend computes the SHA-256 Merkle root for ledger integrity.
- For *on-chain* anchoring, the backend builds a parallel tree from `keccak256(sha256_hex_leaf)` leaves and commits *that* root. The Solidity `verifyProof` checks the keccak path.
- Citizens hold a printed proof that includes both forms: the off-chain leaves prove integrity of the audit chain; the keccak form lets the on-chain contract attest to inclusion.

Choosing one hash function on the contract was a deliberate tradeoff: keccak is the EVM-native primitive and costs roughly half the gas of importing a SHA-256 library. The off-chain SHA-256 path is preserved because that's the universal language of audit verifiers and the format used by the sibling FinalYearProject hash-chain we reused.

## Tenancy and row-level isolation

Every business table carries `district_id` and every row is gated by `AuthContext.tenant_id` (`= str(district_id)`). In production Postgres this is enforced by RLS:

```sql
ALTER TABLE titles ENABLE ROW LEVEL SECURITY;
CREATE POLICY titles_tenant ON titles
    USING (district_id = current_setting('app.district_id')::int OR current_setting('app.bypass', true) = 'on');
```

The auth middleware sets `app.district_id` per request; `ADMIN` and `AUDITOR` roles set `app.bypass = on`. In SQLite dev we apply the same filter in the repository layer; both code paths route through `app.database.get_connection` so behaviour is symmetric.

## Fraud detection — explainable by design

`backend/app/fraud/` combines hand-coded rules with an IsolationForest. Why not deep learning:

- Evaluators (judges, district registrars) must read signal explanations in plain English. A neural net's "0.83 anomaly score" isn't acceptable for a state institution making custodial decisions.
- We don't have labeled fraud data at scale yet.
- Rules + IsolationForest is fast to retrain and trivially explainable.

The rule weights (`backend/app/fraud/rules.py`) are tunable per district as norms drift. The IsolationForest contributes up to 60% of the score; rules contribute the rest. `scorer_version` is captured on every score for idempotent re-scoring after model upgrades.

## Resilience and degradation

| Outage | Behaviour |
|---|---|
| Blockchain RPC down | Off-chain writes continue; anchors queue; `anchor_breaker` opens; public verify returns `pending_anchor: true` for unanchored titles. |
| Redis down | Idempotency falls back to per-worker in-memory LRU; rate-limiting falls back to in-process; cache misses cause more NIRA calls but no errors. |
| NIRA down | NIRA breaker opens; cached results returned with `stale: true`; KYC endpoint surfaces 503 + retry hint. |
| Postgres down | Hard fail; readiness goes red; intentional — there's no useful fallback. |

The graceful-degradation tests are in `backend/tests/test_resilience.py`.

## Threat model (abbreviated)

| Threat | Mitigation |
|---|---|
| Insider tampers with a district's DB | Audit chain verifier detects within seconds; on-chain Merkle root would not match recomputed root. |
| Forged title certificate | Public verifier rejects (content_hash + proof don't match anchored root). |
| Stolen NIN used to claim parcel | NIRA biometric mismatch fires + fraud rule `nira_kyc`. |
| Stolen registrar credentials | Per-action audit emission means after-the-fact attribution is forensically reliable; circuit-breaker outage cap limits damage during compromise. |
| Public verifier DoS | `slowapi` rate limit at 20/min/IP; CDN cache layer for repeat queries. |
| Smart contract bug | OZ Pausable kill switch; admin can pause new commits while a fix is deployed; existing anchors remain valid. |

## What is *not* in scope for the prototype

- Real biometric verification (we hash the supplied template; live NIRA biometric matching is documented but not implemented).
- Cross-district transfers (each district anchors independently; cross-district moves need a coordinator service that's intentionally out of scope here).
- A Ugandan Land Information System (ULS) bidirectional sync — we have read-only stubs ready in `app/nira/` shape, but the LIS schema is not public yet.
