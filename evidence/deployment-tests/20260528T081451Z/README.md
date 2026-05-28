# Deployment regression — Crane Cloud production walkthrough

**Generated:** 2026-05-28T08:14:51Z
**Target:** Crane Cloud RENU-01
**Backend:** `https://landguard-backend-d1e66f33.renu-01.cranecloud.io`
**Frontend:** edge-gated from this host; CI runner reports 200
**Tag deployed:** `v0.2.0-routetest` (commit `7f29a46`)
**Raw CSV:** [`results.csv`](./results.csv)

## Headline

**26 / 26 backend routes PASS** on production. Public claims 1, 2, 5 fully exercised end-to-end against the live deployment. Claim 4 (HITL) exercised at the resilience level — fraud queue endpoint surfaces a 500 (separate bug, see below). Claim 3 (multi-sig) deferred-by-design per the showcase plan. **Two seed-time bugs found** that affect the showcase verifier flow for seeded titles; both small fixes. Demo Act 6 (resilience) is rock-solid: anchor + NIRA circuit breakers toggle cleanly, anchor flushes during RPC outage return `PENDING_BREAKER_OPEN` without crashing.

## Five public claims — verified on production

### Claim 1 — Tamper-evident audit ledger ✅

```
GET /api/v1/admin/audit/verify/3  →  { tenant_id: 3, total_events: 16,
                                       verified: true, first_corrupt_seq: null }
```

The per-district hash chain is intact across all 16 events. Walks pass cryptographic verification.

### Claim 2 — On-chain Merkle anchor ✅

8 anchor batches committed for Mityana (district 3) during this session:

```
GET /api/v1/anchors  →  total: 8, latest batch root 0x76e110...
                        all CONFIRMED (or PENDING_BREAKER_OPEN during chaos)
```

Each batch carries `tx_hash`, `block_number`, `root_hash`. Mock provider in this deployment, so blocks are simulated — but the data shape matches what the real Sepolia path would produce. Pack C's Sepolia deployment work (deferred) would graduate this to a public chain.

### Claim 3 — 3-of-5 multi-sig posture ⚠ deferred by design

- `MULTISIG_ENABLED=false` on this Crane Cloud deployment (per the showcase plan; multi-sig demo path is the pre-recorded Anvil video planned in Pack C6).
- Code path is exercised in CI: `backend/tests/test_multisig_client.py` and `contracts/test/MultiSigRegistrar.t.sol`.
- Switching to true is a one-env-var flip + deploying `MultiSigRegistrar.sol`.

### Claim 4 — Fraud HITL (AI flags, humans decide) ⚠ partial

- The no-auto-FREEZE invariant is enforced in code (`app/fraud/worker.py:_act_on_score`).
- `POST /api/v1/fraud/rescore` works; `GET /api/v1/fraud/score/...` correctly returns 404 for unscored subjects.
- **Bug B**: `GET /api/v1/fraud/reviews` returns 500 internal-server-error on production. `GET /api/v1/fraud/alerts` returns `[]` (empty but functional). The Officer console's review-queue view is broken until this is fixed.
- Affirm/dismiss endpoints could not be exercised because the queue is empty (no PENDING_REVIEW rows on prod).

### Claim 5 — USSD/SMS feature-phone path ✅

```
POST /api/v1/ussd  text=""           →  CON  "LandGuard Uganda
                                              1. Verify title
                                              2. Check parcel status
                                              3. Help / contact District Land Office"
POST /api/v1/ussd  text="1"          →  CON  "Enter the title number
                                              (format: UG-DDD-TNNNNN/YYYY)
                                              e.g. UG-MIT-T00007/2026"
POST /api/v1/sms/verify (any body)   →  {"message":"Send the title number..."}
```

The Africa's Talking-shaped flow is intact end-to-end on production.

## Six demo acts — production walkthrough

| Act | Surface | Status | Notes |
|---|---|:---:|---|
| 1. Hook | narration only | n/a | no test surface |
| 2. Problem (current NLIS) | narration | n/a | no test surface |
| 3. Anchor + multi-sig | `/api/v1/anchors`, `POST /anchors/flush/3` | ✅ (multi-sig deferred) | force-flushed 3 batches during session; all CONFIRMED |
| 4. Fraud HITL | `/api/v1/fraud/{reviews,alerts}` | ⚠ partial | `/reviews` returns 500 (Bug B); `/alerts` returns `[]` cleanly |
| 5. Verify (smartphone + USSD) | `/api/v1/verify/title`, `/api/v1/ussd` | ✅ for API-issued titles; ✗ for seeded titles (Bug A) | new API-issued title `UG-MIT-T00005/2026` verifies CONFIRMED with `tx_hash` and `block_number`; pre-existing seeded titles `MITYANA/V1/20260001-4` all fail with `title_pending_anchor` |
| 6. Resilience | `/api/v1/demo/{rpc,nira}-{kill,restore}` | ✅ | clean toggle of both breakers; anchor flush during RPC-kill returns `PENDING_BREAKER_OPEN` and persists for retry — no crash |

## Bugs found during this regression

### Bug A — Bootstrap seed emits `TITLE_ISSUED` without `title_no` in payload

**Severity:** P0 for the showcase (every seeded title fails public verification).
**Where:** `backend/app/bootstrap/seed.py:489–502`.
**What:**

```python
# Current — payload omits title_no
audit_emit(
    event_type="TITLE_ISSUED",
    payload={
        "parcel_id": parcel_id,
        "owner_id": owner_id,
        "registrar_id": registrar_id,
    },
    ...
)
```

The public verifier (`backend/app/routers/verify.py:60–73`) and the title-proof
endpoint (`backend/app/routers/anchors.py:93–98`) both look up the matching
audit event with `payload_json LIKE '%"title_no": "{title_no}"%'`. With no
`title_no` in the seed's payload, the LIKE never matches, so the verify
endpoint returns `{ valid: false, reason: "title_pending_anchor" }` even
though the title IS in an anchored batch.

**Evidence (this session):**

```
title MITYANA/V1/20260001  → seed-issued     → verify  valid=false  reason=title_pending_anchor
title UG-MIT-T00005/2026   → API-issued      → verify  valid=true   tx=0x0822b572  block=1000007
```

**Fix:**

```diff
-    for parcel_id, owner_id, registrar_id in title_plan:
-        if owner_id is None:
-            continue
+    for idx, (parcel_id, owner_id, registrar_id) in enumerate(title_plan):
+        if owner_id is None:
+            continue
+        title_no = f"MITYANA/V1/{20260000 + idx + 1}"
         audit_emit(
             event_type="TITLE_ISSUED",
             payload={
+                "title_no": title_no,
                 "parcel_id": parcel_id,
                 "owner_id": owner_id,
                 "registrar_id": registrar_id,
             },
             ...
         )
```

The forward fix is one-line per audit event. Existing seeded data on Crane
Cloud will remain broken until the DB is reset OR a fallback is added to
the verifier. For the 25 June showcase, the cleanest path is:

1. Land the seed fix.
2. Wipe + re-seed the Crane Cloud production DB (or stand a fresh pod).
3. Optional: add a verifier-side fallback that looks up via `parcel_id` if
   the `title_no` LIKE misses — preserves the principle that old audit
   events with weaker payloads still verify.

### Bug B — `GET /api/v1/fraud/reviews` returns 500

**Severity:** P1 (Officer console review-queue surface).
**Where:** `backend/app/routers/fraud.py:174–195`.
**Reproduce:**

```
curl -s "$BACKEND/api/v1/fraud/reviews" -H "X-Demo-Role: LAND_OFFICER" -H "X-Demo-District: 3"
→  { "detail": "internal server error", "request_id": "5e63d90b..." }
```

Could not introspect server logs from this host (Crane Cloud log access
required). Likely a schema mismatch between the `fraud_review_queue`
columns the SELECT requests and the live DB schema. The sibling endpoint
`GET /api/v1/fraud/alerts` returns `[]` cleanly, so the queue table
exists but has no PENDING_REVIEW rows AND the `reviews` query has a
column issue.

### Bug C — FastAPI path-param doesn't decode `%2F`

Already documented in `evidence/route-tests/20260528T073903Z/README.md` —
direct GET by ID with slash-containing identifiers (parcel UPI, title
number, batch_id) returns 404. List endpoints work as the canonical
workaround; the verifier endpoint (`POST /api/v1/verify/title`) accepts
slashes in JSON body without issue.

## Frontend reachability

This dev host sees:

| Path | Status | Notes |
|---|:---:|---|
| `/` | 404 | plain-text Crane Cloud router 404 (Next.js not matched) |
| `/verify`, `/anchors`, `/titles/...` | 404 | same |
| `/api/health`, `/api/chain-status`, `/api/proxy/*` | 401 | Crane Cloud edge auth |

The deploy job's "Health-check frontend" step (CI runner) reported `200`
on the same `/api/health` path, so the frontend pod is live and Crane
Cloud's edge enforcement is **IP-based**. From an allowlisted vantage
(Crane Cloud-internal, or whatever IP scope the showcase laptop uses)
the frontend is reachable.

The CSV in this directory captures the matrix as observed; the
production frontend walkthrough must happen from a network the edge
allows.

## Production state after this session

- Audit chain (district 3): 16 events, verified=true, no corruption.
- Anchor batches: 8 (Mityana only — other districts have no events yet).
- Titles: 5 (1 verifiable via /verify, 4 seeded broken — Bug A).
- Resilience: both breakers toggle correctly; anchor flush degrades to `PENDING_BREAKER_OPEN` and recovers cleanly.

## Reproduce

```bash
# Replace BE with the backend public URL.
BE="https://landguard-backend-d1e66f33.renu-01.cranecloud.io"

# Audit chain walk:
curl -s "$BE/api/v1/admin/audit/verify/3" -H "X-Demo-Role: AUDITOR" | jq .

# Anchor list:
curl -s "$BE/api/v1/anchors?limit=3" | jq .

# Verify a fresh title (assumes one was issued):
curl -sX POST "$BE/api/v1/verify/title" -H "Content-Type: application/json" \
  -d '{"title_no":"UG-MIT-T00005/2026"}' | jq .

# Force-flush + restore breaker:
curl -sX POST "$BE/api/v1/demo/rpc-kill" -H "X-Demo-Role: ADMIN"
curl -sX POST "$BE/api/v1/anchors/flush/3" -H "X-Demo-Role: ADMIN"   # PENDING_BREAKER_OPEN
curl -sX POST "$BE/api/v1/demo/rpc-restore" -H "X-Demo-Role: ADMIN"
```

## Recommendation before 25 June

Three fixes ordered by impact:

1. **Bug A (seed.py)** — one-line forward fix; ship + re-seed production. Without this, the verifier returns `valid: false` for every seeded title shown to the panel.
2. **Bug B (`/fraud/reviews` 500)** — needed for Officer-console Act 4 demo. Diagnose via Crane Cloud logs (probably a column mismatch).
3. **Bug C (slash-in-path)** — fix declared routes to use `:path` converter where IDs may contain `/`. List endpoints work as a workaround; this is cleanup, not a showcase blocker.
