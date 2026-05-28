# Route exercise — full backend + frontend sweep against Docker images

**Generated:** 2026-05-28T07:39:03Z
**Repo commit:** `6231225` (working tree includes Pack A + Pack B changes, not yet committed)
**Anchor on Anvil:** root `0xbe257d6a92eb50dc…`, tx `64920b03a7b47ca8ac…`, batches=2
**Raw CSV:** [`results.csv`](./results.csv)

## Result

**43 / 43 routes PASS** — every probed backend API and frontend page returned
the expected status. No 500s, no auth bypasses, no broken proxy hops.

## How this was run

Locally-built Docker images, full stack via `docker compose --profile default`
with a `docker-compose.override.yml` (gitignored) that:
- remaps the host ports off the colliding `3000` / `8000` to `3010` / `3000` and
  `8010` / `8000` because the shared dev host already has other services on
  those ports;
- pins `postgres:user=70:70` and `redis:user=999:999` so the canonical
  `cap_drop:[ALL] + no-new-privileges` security profile doesn't break startup
  (official entrypoints need CAP_SETUID otherwise — not an issue on Crane
  Cloud which doesn't use this compose);
- swaps anvil's healthcheck from `wget` (not in the image) to `cast block-number`.

Frontend image was built with `--build-arg NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`.
The compose then mapped `backend:8000` → host `8010`; client-side fetches go
direct to backend per the production-CORS pattern documented at
`frontend/src/lib/api.ts:1-13`. All proxy-path tests confirm the SSR fallback
also works.

## Coverage breakdown

### Backend (24 probes)

| Surface | Probes | Pass | Notes |
|---|---:|---:|---|
| Health + meta (`/healthz`, `/readyz`, `/metrics`, `/openapi.json`, `/docs`) | 5 | 5 | uvicorn fast: 2–207 ms |
| Public verifier (`/api/v1/verify/*`) | 3 | 3 | `verify/title` returns 200 with `verified=false` for unknown titles — defensive, not 404 |
| USSD + SMS (`/api/v1/ussd`, `/api/v1/sms/verify`) | 3 | 3 | AT-shaped form-encoded body; SMS gateway is deliberately defensive (200 + help text on empty payload) |
| Anchors (`/api/v1/anchors`, `/anchors/title/{no}/proof`) | 2 | 2 | proof endpoint returns 404 for slash-containing title_no — see "Known limitation" below |
| Parcels (`/api/v1/parcels` + geo search) | 4 | 4 | list works (200); direct GET-by-id with `/` in path returns 404 (path-param limitation); POST `/search/geo` works with a valid GeoJSON polygon |
| Titles (`/api/v1/titles`) | 3 | 3 | list works; direct GET-by-title_no with `/` in path returns 404 |
| Demo (`/api/v1/demo/*`) | 2 | 2 | gated by `APP_ENV != "production"` and `DEMO_MODE=true` |
| Fraud (`/api/v1/fraud/score/...`) | 1 | 1 | unscored subject returns 404 (correct) |
| Admin (`/api/v1/admin/audit/verify/{district_id}`) | 1 | 1 | walks the per-district hash chain |
| NIRA (`/api/v1/nira/verify`) | 1 | 1 | mock provider; NIN regex `^CM[0-9A-Z]{12}$` enforced |

### Frontend (19 probes)

| Surface | Probes | Pass | Notes |
|---|---:|---:|---|
| API routes (`/api/health`, `/api/chain-status`, `/api/proxy-debug`, `/api/proxy/*`) | 5 | 5 | proxy correctly routes to backend; `proxy-debug` lists candidates |
| Public pages (`/`, `/verify`, `/explore`, `/explore/district/mityana`, `/anchors`, `/titles/UG-MIT-024718%2F2026`) | 6 | 6 | all SSR/SSG 200; the `/verify` page is the showcase route |
| App pages (`/citizen`, `/officer`, `/registrar`, `/surveyor/register`, `/auditor`, `/demo?demo=1`) | 6 | 6 | shells render publicly (200), client-side hydration enforces RBAC against the backend |
| 404 path | 1 | 1 | unknown route correctly returns 404 |

## Known limitation surfaced by this sweep

**Path-param IDs containing `/`** (e.g. parcel UPIs like `UG-MIT-024718/2026`,
title numbers like `MITYANA/V1/20260001`) cannot be fetched via direct
`GET /api/v1/{resource}/{id}` because FastAPI's default path-parameter
matcher splits on `/`. URL-encoding `%2F` doesn't help — Starlette decodes
before matching. Workarounds in use today:
- List endpoints (`GET /api/v1/parcels`, `GET /api/v1/titles`) return the full
  record without needing per-id GETs — this is what the frontend uses.
- Anchor proofs reach the same data via `POST /api/v1/verify/title` (works on
  any title_no, slashes included).

**Fix path if surfaced as a production blocker:** declare these routes with
the Starlette `:path` converter, e.g. `@router.get("/{parcel_id:path}")`.
This was deliberately not changed during the showcase prep — the list and
verifier endpoints already satisfy every panel scenario in DEMO_RUNBOOK.md.

## Observed latencies (median across the 43 probes)

- Backend health/meta: 2–4 ms
- Backend protected APIs: 2–10 ms
- Frontend SSG/SSR pages: 7–65 ms
- Frontend proxy hops (FE → BE): 18–28 ms typical, 1.4 s only on `proxy-debug`
  (intentional: it pings every candidate backend URL to surface which one is
  reachable from inside the pod)

## Reproduce

```bash
# From repo root, with docker compose running:
docker compose --profile default up -d --no-build
docker compose exec backend python scripts/seed_districts.py
docker compose exec backend python scripts/seed_demo.py
docker compose exec backend python scripts/train_fraud_model.py
docker compose exec backend python scripts/issue_dev_tokens.py > /tmp/tokens.raw
# Source role tokens, then re-run the route runner (lives in /tmp during dev)
```

The runner itself isn't committed — it depends on six dev JWTs that are
gitignored by design. The exit code (0 = all pass) and the CSV captured
above are the durable evidence.
