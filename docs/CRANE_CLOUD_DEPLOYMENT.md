# Crane Cloud Deployment — LandGuard Uganda

Production deployment of LandGuard Uganda on [Crane Cloud](https://cranecloud.io) — Uganda's locally-operated Kubernetes-as-a-Service platform, run by Makerere AI Lab. Adapted from `mpairwe7/MLOPS_V1/docs/22-crane-cloud-deployment.md` which has been battle-tested with `OptiscanAI` since 2026-05-12.

> **Last verified:** 2026-05-26
> **Target cluster:** RENU (`9e81a70e-8460-4e5d-b0a8-17abcac30f68`)
> **Docker Hub namespace:** `landwind` (mpairwe7's pattern)
> **Crane Cloud account:** `mpairwelauben75@gmail.com`

---

## Three-command bootstrap

If your `gh` CLI is authenticated as `mpairwe7` and your Crane Cloud account is in your password manager:

```bash
# 1. Create the project and both apps on Crane Cloud (5–10 minutes).
bash scripts/bootstrap_cranecloud.sh
# (prompts for password via read -s; never echoes)

# 2. Populate GitHub secrets — uses values written by step 1, prompts only for actual secrets.
bash scripts/setup_github_secrets.sh

# 3. Tag and push — triggers build-push.yml → deploy-cranecloud.yml.
git tag v0.1.0-showcase
git push origin main v0.1.0-showcase
```

End-to-end wall-clock from `git push` to `/verify` page live on Crane Cloud: **~6–8 minutes**.

---

## 1. Why Crane Cloud

Three reasons specific to LandGuard's claim space:

1. **Data sovereignty.** LandGuard mediates Ugandan statutory records (DPPA-2019 §17 applies). Crane Cloud is operated within Uganda by Makerere AI Lab — no foreign hyperscale on the critical path. See `docs/STANDARDS_ALIGNMENT.md` §1.2.
2. **Cost.** RENU cluster pricing is a fraction of equivalent AWS/GCP capacity, which matters for the pilot Y1 envelope in `docs/IMPACT_EVIDENCE.md` §5.3.
3. **Capacity-building alignment.** Hosting on Makerere infrastructure is consistent with the academic-partnership commitments in `docs/TEAM.md` §5.

The trade: Crane Cloud has **no volume-mount support, no GPU on the RENU cluster, and a smaller op team than the hyperscalers.** LandGuard accommodates all three:

- No volume mounts → `LandRegistryAnchor` contract address baked at image build time, SQLite WAL inside the container (acceptable for pilot; Postgres for production scale).
- No GPU → the fraud scorer's IsolationForest runs on CPU (already designed that way).
- Smaller op team → the circuit-breaker in `app/resilience.py` makes off-chain operation tolerant of Crane Cloud-level transients.

---

## 2. Available clusters

(verified 2026-05-12 by the MLOPS_V1 team — see lessons-learned in §10)

| Cluster | ID | Subdomain | Status | Notes |
|---------|-----|-----------|--------|-------|
| **RENU** | `9e81a70e-8460-4e5d-b0a8-17abcac30f68` | `renu-01.cranecloud.io` | Active | **Recommended** — stable, fast pod scheduling |
| AHUMAIN ML | `df2eeac2-b36d-4bbd-a734-eb03754cd175` | `ahumain.cranecloud.io` | Active | Pods stuck in "unknown" status — avoid until cluster-level scheduling issue resolves |
| Makerere-1 | `f3068db2-a981-4308-8c57-64112a792365` | `cranecloud.io` | Disabled | Legacy |

LandGuard targets **RENU exclusively** for the pilot. AHUMAIN advertises `supports_ml: true` and would be useful when scoring throughput grows, but the scheduling-failure pattern from OptiscanAI's 2026-05-12 attempts has not yet been confirmed resolved.

---

## 3. Crane Cloud API reference

Base: `https://api.cranecloud.io`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/users/login` | POST | `{email, password}` → `{data: {access_token, id}}` |
| `/projects` | GET | List projects this user owns/collaborates on |
| `/projects` | POST | Create — `{name, cluster_id, owner_id, description}` |
| `/projects/{id}/apps` | GET | List apps in project |
| `/projects/{id}/apps` | POST | Deploy — `{name, image, port, replicas, env_vars}` |
| `/apps/{id}` | GET | App details (`app_running_status`, `pod_statuses`, env) |
| `/apps/{id}` | PATCH | Update image / env / replicas (MERGES env, doesn't replace) |
| `/apps/{id}` | DELETE | Remove app |
| `/clusters` | GET | List clusters and capabilities |

**Two gotchas confirmed by MLOPS_V1's deployment history:**

1. **Email is case-sensitive at login.** Use lowercase (`mpairwelauben75@gmail.com`, not `Mpairwelauben75@…`).
2. **PATCH `/apps/{id}` merges env vars**, it does not replace. To remove an env var you must DELETE + POST a fresh app.

---

## 4. Image-tagging discipline (SHA suffix is mandatory)

Crane Cloud diffs the `image` field on PATCH as a **string**. PATCHing the same `:latest` or `:v0.1.0-showcase` tag is a no-op — the pod is not restarted, the image is not re-pulled, the new code does not deploy.

LandGuard's `build-push.yml` publishes every image with TWO tags on every CI run:

| Tag form | Example | Purpose |
|---|---|---|
| Floating | `landwind/landguard-uganda-backend:v0.1.0-showcase` | Human-readable, points at the latest build for a version |
| SHA-suffixed | `landwind/landguard-uganda-backend:v0.1.0-showcase-abc1234` | What the deploy workflow PATCHes — every push produces a fresh image string Crane Cloud sees as new |

`deploy-cranecloud.yml` always PATCHes the SHA-suffixed form. The floating tag exists only for humans pulling the image manually.

---

## 5. GitHub secrets — what each one is and where it goes

All set via `bash scripts/setup_github_secrets.sh`. The script uses `gh secret set NAME --body -` reading the value from a `read -s` prompt — no echo, no argv exposure, no shell history.

| Secret | Scope | Source |
|---|---|---|
| `DOCKERHUB_USERNAME` | Repository | `landwind` (mpairwe7's pattern; pre-filled as default) |
| `DOCKERHUB_TOKEN` | Repository | hub.docker.com → Account Settings → PATs (Read/Write/Delete on `landwind/*`) |
| `CRANE_CLOUD_EMAIL` | `production` env | `mpairwelauben75@gmail.com` (pre-filled) |
| `CRANE_CLOUD_PASSWORD` | `production` env | Your password — generate fresh / rotate annually |
| `CRANE_CLOUD_BACKEND_APP_ID` | `production` env | Returned by `bootstrap_cranecloud.sh` |
| `CRANE_CLOUD_FRONTEND_APP_ID` | `production` env | Returned by `bootstrap_cranecloud.sh` |
| `CRANE_CLOUD_BACKEND_URL` | `production` env | Returned by `bootstrap_cranecloud.sh` — used for `/healthz` polling |
| `CRANE_CLOUD_FRONTEND_URL` | `production` env | Returned by `bootstrap_cranecloud.sh` — used for `/api/health` polling |

---

## 6. Environment variables passed to the Crane Cloud apps

Backend (`landguard-uganda-backend`):

| Key | Value | Why |
|---|---|---|
| `APP_ENV` | `production` | Triggers `Settings.assert_prod_safety()` — startup refuses dev defaults |
| `LOG_LEVEL` | `INFO` | Standard production verbosity |
| `DEMO_MODE` | `false` | Required by `assert_prod_safety` when `APP_ENV=production` |
| `DB_BACKEND` | `sqlite` (pilot) → `postgres` (scale) | Pilot fits comfortably in SQLite WAL; switch is one env var |
| `REDIS_URL` | `memory://` (pilot) → `redis://…` | In-memory cache for pilot; Crane Cloud Redis add-on for scale |
| `AUTH_MODE` | `dev` (pilot) → `oidc` (NITA-U integration) | Pilot uses HS256 dev tokens until NITA-U IdP is provisioned |
| `JWT_HS256_SECRET` | 32+ char random | **Rotate via Crane Cloud dashboard after bootstrap — the script defaults are intentionally weak** |
| `BLOCKCHAIN_PROVIDER` | `mock` (pilot smoke test) → `sepolia` → permissioned chain | See ADR-0003 |
| `NIRA_PROVIDER` | `mock` → `live` | Live mode requires NIRA API credentials |
| `PII_ENCRYPTION_KEY` | base64-encoded 32 random bytes | **Rotate via Crane Cloud dashboard after bootstrap** |
| `PROMETHEUS_METRICS_ENABLED` | `true` | `/metrics` for Crane Cloud scrape |

Frontend (`landguard-uganda-frontend`):

| Key | Value | Why |
|---|---|---|
| `NEXT_PUBLIC_APP_NAME` | `LandGuard Uganda` | Page chrome |
| `NEXT_PUBLIC_DEMO_MODE` | `false` | Hides demo control panel |
| `NEXT_PUBLIC_DEFAULT_DISTRICT_ID` | `3` (Mityana) | Pilot district |

> **Critical for Crane Cloud:** no spaces in keys or values (`KEY=value`, not `KEY = value` or `KEY= value`). The PATCH endpoint stores them verbatim and lookups will silently miss. Verified failure mode in MLOPS_V1 docs §"Troubleshooting → Environment variable keys have spaces".

---

## 7. CI/CD pipeline

```
git push v0.1.0-showcase
    ↓
build-push.yml
    ├─ validates DOCKERHUB_USERNAME + DOCKERHUB_TOKEN
    ├─ docker buildx build + push (backend + frontend in parallel matrix)
    │   → docker.io/landwind/landguard-uganda-{backend,frontend}:v0.1.0-showcase
    │   → docker.io/landwind/landguard-uganda-{backend,frontend}:v0.1.0-showcase-abc1234
    └─ workflow_dispatch trigger → deploy-cranecloud.yml
                                       ↓
                                deploy-cranecloud.yml (environment: production)
                                       ├─ validates CRANE_CLOUD_* secrets
                                       ├─ POST /users/login → JWT
                                       ├─ PATCH /apps/$BACKEND_APP_ID  { image: ":v0.1.0-showcase-abc1234" }
                                       ├─ PATCH /apps/$FRONTEND_APP_ID { image: ":v0.1.0-showcase-abc1234" }
                                       ├─ poll $BACKEND_URL/healthz   for 200 (up to 5 min)
                                       └─ poll $FRONTEND_URL/api/health for 200 (up to 5 min)
```

The deploy job uses `environment: production` so GitHub's required-reviewers protection can be wired in via the Settings UI without touching code.

---

## 8. Deploy-only flow (env-var change without rebuild)

To redeploy with new env vars but the same image (e.g. rotating `JWT_HS256_SECRET`):

1. Update the env var in the Crane Cloud dashboard (Apps → landguard-backend → Environment).
2. **Crane Cloud does NOT auto-restart on env change.** Manually restart the pod via the dashboard, OR PATCH the app's `image` field to the SHA-suffixed tag again to force a re-pull.

Alternative: Actions tab → **Deploy to Crane Cloud** → **Run workflow** → enter the existing `image_tag` value. The workflow re-PATCHes the image string with the current SHA, which Crane Cloud sees as new and pulls.

---

## 9. Troubleshooting (lessons from OptiscanAI deployments)

### Pod status "unknown"

**Cause:** Cluster-level scheduling issue (confirmed on AHUMAIN 2026-05-12). **Fix:** Delete the app, recreate on RENU. The bootstrap script targets RENU by default.

### `model_loaded: false` in `/healthz`

**Cause:** Backend started but couldn't reach Postgres or load a needed file. **Fix:** Check Crane Cloud pod logs for the actual error; the most common is wrong `POSTGRES_DSN` when `DB_BACKEND=postgres`.

### CrashLoopBackOff immediately after deploy

**Cause:** `Settings.assert_prod_safety()` is refusing to start with dev defaults. **Fix:** Set `APP_ENV=production` AND `DEMO_MODE=false` AND a real (non-`change-me`) `JWT_HS256_SECRET` AND a real `PII_ENCRYPTION_KEY` AND `BLOCKCHAIN_PROVIDER != mock`. The bootstrap script's defaults intentionally fail the assertion so you remember to rotate them.

### `/healthz` times out within Crane Cloud's readiness window

**Cause:** First-request latency includes audit-ledger schema creation, fraud-model load, and contract-address resolution. **Fix:** Crane Cloud's default readiness timeout works for SQLite-backed pilots. For Postgres, add `start_period=60s` semantics by adjusting the Dockerfile `HEALTHCHECK --start-period`.

### Environment variable keys have spaces

**Cause:** Crane Cloud passes env vars verbatim; ` DEVICE ` is not `DEVICE`. **Fix:** Inspect via `GET /apps/{id}` — the bootstrap script never injects spaces, but the Crane Cloud dashboard's manual env editor can.

### Image pull too slow

**Cause:** Image bloat. **Fix:** LandGuard's backend image is ~250 MB (FastAPI + uv + scikit-learn), frontend is ~150 MB (Next.js standalone) — both pull in well under a minute on RENU. If a future change pushes either past 1 GB, investigate.

---

## 10. Trust assumptions

1. **The Crane Cloud control plane** is honest about which images it has pulled and which pods are healthy. Mitigated by the public verifier and on-chain Merkle anchor — even if Crane Cloud lied, the cryptographic integrity claims hold.
2. **The RENU cluster** has reasonable physical-security and network-isolation posture as a Makerere-operated facility. NITA-U Tier-III certification process is the next step (`docs/STANDARDS_ALIGNMENT.md` §5).
3. **No Crane Cloud operator** can read citizen NIN values directly — they're AES-GCM encrypted at rest with a key the operator does not have (key rotation procedure: Crane Cloud dashboard → secret manager → rotate; backend re-encrypts background jobs).

These trust assumptions are **bounded by the on-chain anchor** — anchored Merkle roots remain verifiable independently of Crane Cloud forever. See `docs/audit/THREAT_MODEL.md` "Out of scope (declared)" for the formal statement.

---

## 11. Cross-references

- Source workflow patterns: `mpairwe7/MLOPS_V1/.github/workflows/docker-publish.yml`, `mpairwe7/OptiscanAI/.github/workflows/docker-publish.yml`
- Source documentation: `mpairwe7/MLOPS_V1/docs/22-crane-cloud-deployment.md`
- LandGuard CI workflows: [`.github/workflows/build-push.yml`](../.github/workflows/build-push.yml), [`.github/workflows/deploy-cranecloud.yml`](../.github/workflows/deploy-cranecloud.yml)
- Bootstrap script: [`../scripts/bootstrap_cranecloud.sh`](../scripts/bootstrap_cranecloud.sh)
- Secrets setup script: [`../scripts/setup_github_secrets.sh`](../scripts/setup_github_secrets.sh)
- SLOs the deploy must meet: [`SLA_TARGETS.md`](./SLA_TARGETS.md)
- Threat model: [`audit/THREAT_MODEL.md`](./audit/THREAT_MODEL.md)
- ADR-0003 regional chain migration: [`adr/0003-regional-chain-migration.md`](./adr/0003-regional-chain-migration.md)
