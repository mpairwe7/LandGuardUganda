# Crane Cloud deployment — LandGuard Uganda

**Audience:** SREs, DevOps engineers, MoLHUD / NITA-U IT staff operating a Crane Cloud-hosted instance of LandGuard Uganda.
**CLI required:** [`cranecloud`](https://docs.cranecloud.io/) installed and authenticated on the operator's interactive shell.
**Last reviewed:** 2026-05-25.

This directory is the **deployment surface** for [Crane Cloud](https://cranecloud.io/) — Uganda's locally-operated Platform-as-a-Service, run by Makerere AI Lab. It wraps the `cranecloud` CLI's per-app commands behind a Make-based environment-aware workflow so the same deploy story works across **staging**, **pilot**, and **production** without bespoke scripts.

Choosing Crane Cloud is itself an architectural decision: LandGuard processes Ugandan statutory records, so the hosting plane must be sovereign. Crane Cloud satisfies that constraint without sacrificing operator ergonomics.

```
infra/cranecloud/
├── README.md                              ← this file
├── manifest.yaml                          ← deployment manifest (image, port, env names)
├── Makefile                               ← deploy / update / list wrappers
└── environments/
    ├── staging.env.example                ← committed template
    ├── pilot.env.example                  ← committed template
    └── production.env.example             ← committed template
    # staging.env, pilot.env, production.env are GIT-IGNORED.
```

---

## 1. Prerequisites

1. **`cranecloud` CLI installed** and on `$PATH`. See <https://docs.cranecloud.io/>.
2. **Authenticated** via `cranecloud auth login`. The session token lives in the OS keyring; deploys must therefore run from an **interactive shell with keyring access** — that's why CI does not deploy directly. The GitHub Actions workflow seeds the token via a GitHub Environment secret (see §9).
3. **Container images** for the two apps are reachable from Crane Cloud's pull side:
   - `ghcr.io/mpairwe7/landguard-uganda-backend:<tag>`
   - `ghcr.io/mpairwe7/landguard-uganda-frontend:<tag>`
   - Either make the GHCR packages public, or grant Crane Cloud's registry-puller read access.
4. **Postgres + Redis** are provisioned — either as Crane Cloud add-ons (recommended for pilot) or pointing at external managed services. You'll paste the `postgresql+asyncpg://…` and `redis://…` URLs into the `.env` file.
5. **(Pilot+)** A deployed `LandRegistryAnchor.sol` on the target chain. For pilot we recommend Sepolia until a permissioned chain is operational; see [ADR-0003](../../docs/adr/0003-regional-chain-migration.md) for the long-term path.

---

## 2. One-time setup per environment

Replace `<env>` with `staging`, `pilot`, or `production`:

```bash
cd infra/cranecloud
make init ENV=<env>          # prints the checklist below

# 1) Confirm authentication and find/create the Crane Cloud project
cranecloud auth user
cranecloud projects list
# If the project doesn't exist:
cranecloud projects create   # suggested name: landguard-uganda-<env>

# 2) Copy the env template and fill in real values
cp environments/<env>.env.example environments/<env>.env
$EDITOR environments/<env>.env
# At minimum set:
#   - CRANECLOUD_PROJECT_ID            (from `cranecloud projects list`)
#   - JWT_HS256_SECRET                 (32+ chars; see step 3 below)
#   - PII_ENCRYPTION_KEY               (base64-encoded 32 random bytes; see step 3)
#   - DATABASE_URL / POSTGRES_DSN
#   - REDIS_URL
#   - NIRA_*                           (real URLs for pilot/production; mocks OK for staging)
#   - BLOCKCHAIN_PROVIDER + SEPOLIA_RPC_URL (or your permissioned chain endpoint)
#   - REGISTRAR_PRIVATE_KEY            (PILOT ONLY in env; production uses HSM-backed secret manager)

# 3) Generate the secrets
python -c "import secrets; print(secrets.token_urlsafe(32))"            # JWT_HS256_SECRET
python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"   # PII_ENCRYPTION_KEY
```

The `.env` file stays on your machine (gitignored). It is **the** source of truth for values; the manifest declares which names are expected.

---

## 3. First deploy

```bash
cd infra/cranecloud
make deploy ENV=<env>
# Equivalent: make deploy-backend ENV=<env> && make deploy-frontend ENV=<env>
```

The CLI returns an **APP_ID (UUID)** for each app. Capture them back into your `.env`:

```bash
# environments/<env>.env
BACKEND_APP_ID=<uuid-from-cli>
FRONTEND_APP_ID=<uuid-from-cli>
```

These IDs are what `make update-*` targets later — without them you'd accidentally create duplicate apps.

---

## 4. Subsequent rollouts

A code change → new image tag → roll out:

```bash
# Update the image tag (and optionally the replica count) in your env file
$EDITOR environments/<env>.env       # bump BACKEND_IMAGE_TAG / FRONTEND_IMAGE_TAG

make update-backend ENV=<env>
make update-frontend ENV=<env>
```

Crane Cloud performs a rolling update against the existing app — no downtime if `replicas >= 2` (which is the default for pilot+).

---

## 5. Listing and inspecting

```bash
make list ENV=<env>                       # list all apps in the project
make info ENV=<env> APP_ID=<uuid>         # detail one app
```

---

## 6. What lives where

| Concern | Where it lives | Tracked in git? |
| --- | --- | --- |
| Which apps exist + how they are shaped | `manifest.yaml` | ✅ committed |
| Per-environment values (URLs, tags, replica counts) | `environments/<env>.env` | ❌ gitignored (`.env.example` committed as template) |
| Secrets (`JWT_HS256_SECRET`, `PII_ENCRYPTION_KEY`, `REGISTRAR_PRIVATE_KEY`, `NIRA_API_KEY`, DB password embedded in `POSTGRES_DSN`) | `environments/<env>.env` *or* Crane Cloud secret manager | ❌ never committed |
| Resulting APP_IDs | `environments/<env>.env` after first deploy | ❌ gitignored |
| Operational SLOs the deploy must meet | [`docs/SLA_TARGETS.md`](../../docs/SLA_TARGETS.md) | ✅ committed |
| Audit-grade evidence (SBOM, Lighthouse, load) | `evidence/` | ✅ committed (selectively) |

---

## 7. Secret handling — limitations of the CLI

The `cranecloud apps deploy/update -e KEY=value` flag places secret values on the command line. They are visible to:

- Anyone with shell access to the host running the deploy (via `ps`, `/proc/<pid>/cmdline`).
- The terminal's history file unless `set +o history` (or zsh `setopt hist_ignore_space` + leading space) is used.

For **highly sensitive** secrets (production `REGISTRAR_PRIVATE_KEY`, `PII_ENCRYPTION_KEY`, `JWT_HS256_SECRET`, real DB passwords), prefer:

1. **Set them once via Crane Cloud's web-dashboard secret manager.** Then remove them from your local `.env` after the initial deploy.
2. **Use environment variables sourced from a password manager** (1Password CLI, Bitwarden CLI) at deploy time:
   ```bash
   export REGISTRAR_PRIVATE_KEY=$(op read "op://landguard/production/REGISTRAR_PRIVATE_KEY")
   make deploy-backend ENV=production
   ```
3. **Do not commit** any `.env` file containing real secret values. The `.gitignore` rule explicitly excludes `infra/cranecloud/environments/*.env`.

For production the `REGISTRAR_PRIVATE_KEY` should ultimately be **inside an HSM, not in any env var**. The current shape is the prototype path; the destination is the 3-of-5 custody model in [`docs/CUSTODY.md`](../../docs/CUSTODY.md).

---

## 8. Production-only safeguards

For `ENV=production` we observe the policies in [`MAINTAINERS.md`](../../MAINTAINERS.md) "Out-of-band review escalation" and [`docs/CUSTODY.md`](../../docs/CUSTODY.md):

- **Two-person sign-off** on every production deploy. The deploying operator records the deploy intent in `docs/rehearsal/deploy-YYYY-MM-DD.md` with the version tag, the reviewer's name, and the rollback plan.
- **No `latest` tags.** Production images are tagged with the release version (e.g. `v0.1.0-showcase`). The `production.env.example` enforces this by leaving `BACKEND_IMAGE_TAG=` blank — the deploy fails fast if you forget to set it.
- **DPO sign-off** for deploys that touch privacy-relevant invariants (audit log shape, right-to-erasure flow, role hierarchy, PII inventory). Per [`docs/GOVERNANCE.md`](../../docs/GOVERNANCE.md).
- **MULTISIG_ENABLED=true** in production. The single-signer path is a prototype convenience only.
- **APP_ENV=production + AUTH_MODE=oidc + DEMO_MODE=false.** Combined these make `Settings.assert_prod_safety()` allow startup. Any dev defaults still present and the backend refuses to start.

---

## 9. CI/CD pipeline

Three GitHub Actions workflows automate the parts of the rollout that are safe to automate:

### 9.1 `.github/workflows/ci.yml` — every push / PR

- Backend (uv + ruff + mypy + pytest)
- Contracts (forge build + forge test)
- Frontend (bun typecheck + lint + build)
- OSV-Scanner against `uv.lock` + `bun.lock` (continue-on-error so transient advisory-feed issues don't block PRs; alerts surface in checks)
- Docker build verify (both Dockerfiles, no push)
- SBOM generation + 90-day artefact retention

### 9.2 `.github/workflows/build-push.yml` — fully automated GHCR push

- **Triggers:** push to `main`, push of `v*` tags, manual `workflow_dispatch`.
- **What it does:** builds `backend/` and `frontend/` images via `docker/build-push-action` and pushes to `ghcr.io/mpairwe7/landguard-uganda-{backend,frontend}` with derived tags (`main`, `sha-<short>`, version, `latest` on non-prerelease releases).
- **Auth:** `GITHUB_TOKEN` (no extra secret).
- **After successful build on `main` / `v*`:** dispatches `deploy-cranecloud.yml` automatically — `main` → `staging`, `v*` → `pilot`. Production deploys are *never* automatic; they are operator-triggered via `workflow_dispatch`.

### 9.3 `.github/workflows/deploy-cranecloud.yml` — operator-led

- **Triggers:** `workflow_dispatch` only (manual); also invoked by `build-push.yml` for staging / pilot.
- **Inputs:** `env` (staging/pilot/production), `target` (backend/frontend/both), `image_tag`.
- **Auth path:** pip-installs `cranecloud`, sets `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` so the CLI does not require D-Bus / SecretService, and seeds `~/.cranecloud/token` from the environment secret `CRANECLOUD_TOKEN`.
- **Environment protection:** uses GitHub Environments (`cranecloud-staging`, `cranecloud-pilot`, `cranecloud-production`) so production deploys can require manual reviewer approval per MAINTAINERS.md.
- **Fallback:** if the CLI cannot authenticate (e.g. a future cranecloud version re-introduces a keyring dependency that the null backend cannot satisfy), the job fails loudly and posts the manual-deploy command to the run summary so the operator can run the same rollout from their interactive shell via `make update-*`.

### 9.4 Required GitHub secrets

These are configured per environment (Settings → Environments → cranecloud-<env> → Environment secrets). They are *not* repository-wide secrets because each environment has distinct values.

| Secret name | Where to get it | Notes |
| --- | --- | --- |
| `CRANECLOUD_TOKEN` | `cat ~/.cranecloud/token` after `cranecloud auth login` | Treat as bearer credential. Rotate annually or on incident. |
| `CRANECLOUD_USER_ID` | `cat ~/.cranecloud/user_id` | |
| `CRANECLOUD_PROJECT_ID` | `cranecloud projects list` (UUID column) | Per-environment value. |
| `CRANECLOUD_BACKEND_APP_ID` | After first `make deploy-backend ENV=<env>` — captured from CLI output | Per-environment value. |
| `CRANECLOUD_FRONTEND_APP_ID` | After first `make deploy-frontend ENV=<env>` | Per-environment value. |

Runtime env vars for the apps (DATABASE_URL, JWT_HS256_SECRET, NIRA_*, REGISTRAR_PRIVATE_KEY) live in **Crane Cloud's web-dashboard secret manager**, not in GitHub Actions secrets. The CI deploy only updates the *image*, not the env vars. This minimises the secret surface in GitHub.

### 9.5 Typical flow

```
git tag v0.1.0-showcase
git push origin v0.1.0-showcase
   ↓ triggers build-push.yml
   ↓ builds + pushes backend + frontend images to GHCR
   ↓ dispatches deploy-cranecloud.yml (env=pilot, tag=v0.1.0-showcase)
   ↓ deploy-cranecloud.yml updates the existing Crane Cloud apps
   ↓ /healthz + /readyz become green on the new image
```

Production deploys deliberately skip the auto-dispatch — to roll out to production, an operator goes to the Actions tab → **Deploy to Crane Cloud** → **Run workflow** → `env=production` → `image_tag=v0.1.0-showcase`. The environment's required-reviewers rule then enforces the two-person sign-off from MAINTAINERS.md.

---

## 10. Rollback

Crane Cloud retains image history per app. To roll back:

```bash
# Find the previous image tag (from git tags or the GHCR registry):
git tag -l 'v*' | sort -V | tail -10

# Update the env file with the previous tag:
$EDITOR environments/<env>.env       # set BACKEND_IMAGE_TAG=<previous>
make update-backend ENV=<env>
```

If the rollback target is older than the most recent DB migration, **restore the database first** per [`docs/SLA_TARGETS.md`](../../docs/SLA_TARGETS.md) §9. Application-code rollback without DB rollback can leave the schema ahead of the code — fix-forward unless your error is bounded.

For on-chain rollback there is **none** — anchored Merkle roots are immutable. A bad anchor is corrected by pausing the contract (`LandRegistryAnchor.pause()` under `DEFAULT_ADMIN_ROLE`) and submitting corrective audit events to a fresh batch. See [`docs/audit/THREAT_MODEL.md`](../../docs/audit/THREAT_MODEL.md) "Smart-contract bug" row.

---

## 11. Common errors

| Symptom | Cause | Fix |
| --- | --- | --- |
| `secretstorage.exceptions.ItemNotFoundException` from `cranecloud` | Running from a non-interactive shell without D-Bus / keyring | Run the deploy from your own terminal, not from CI / SSH-without-tty |
| `Missing environments/<env>.env` | `.env` file not created | `cp environments/<env>.env.example environments/<env>.env` and fill in values |
| `BACKEND_APP_ID is not set` on `make update-backend` | First deploy never recorded the APP_ID back into `.env` | Run `make list` to find the UUID, paste into `.env` |
| Backend starts but `/readyz` is 503 | Backend cannot reach Postgres / Redis | Confirm `POSTGRES_DSN` / `REDIS_URL` resolve from Crane Cloud's network; check Crane Cloud add-on bindings |
| Backend refuses to start with `production configuration uses dev defaults for: ...` | `Settings.assert_prod_safety()` tripped | Address each listed key — they're real production-safety blockers |
| 401 from authenticated endpoints | Wrong `JWT_HS256_SECRET` between deploy and consumer | The JWT signing key changed; users must re-authenticate. If unintended, redeploy with the previous secret |
| CORS errors in the browser | `CORS_ALLOW_ORIGINS` doesn't include the frontend URL | Edit the env file, redeploy backend |
| Anchor batches not advancing | RPC unreachable | Check `/readyz` `blockchain.ok`; verify `SEPOLIA_RPC_URL`; the circuit breaker queues batches but eventually the queue grows — investigate quickly |

---

## 12. Cross-references

- [`manifest.yaml`](./manifest.yaml) — the source of truth for what gets deployed.
- [`Makefile`](./Makefile) — `make help` from this directory lists all targets.
- [`../../.github/workflows/ci.yml`](../../.github/workflows/ci.yml) — pull-request gate.
- [`../../.github/workflows/build-push.yml`](../../.github/workflows/build-push.yml) — GHCR build + push automation.
- [`../../.github/workflows/deploy-cranecloud.yml`](../../.github/workflows/deploy-cranecloud.yml) — CI-driven deploy to Crane Cloud.
- [`../../docs/SLA_TARGETS.md`](../../docs/SLA_TARGETS.md) — what "healthy" looks like after deploy.
- [`../../docs/audit/THREAT_MODEL.md`](../../docs/audit/THREAT_MODEL.md) — security baseline.
- [`../../docs/adr/0002-zero-trust-posture.md`](../../docs/adr/0002-zero-trust-posture.md) — the zero-trust posture the deploy must preserve.
- [`../../docs/adr/0003-regional-chain-migration.md`](../../docs/adr/0003-regional-chain-migration.md) — chain-migration optionality the manifest preserves.
