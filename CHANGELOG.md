# Changelog

Security-relevant changes, dependency bumps, and notable architectural
events. Audit-readable timeline. Entries are reverse-chronological.

The project follows the spirit of [Keep a Changelog](https://keepachangelog.com/);
versioning is calendar-style (`YYYY-MM-DD`) until 1.0.

---

## 2026-05-31 — `v0.2.5-model-bake` — fraud model baked into the image

Deploy fix found while verifying the `v0.2.4-pack-g` rollout: live `/readyz`
reported `fraud_model.loaded: false`. The IsolationForest artifact
(`isoforest-v1.joblib`) is gitignored and was never trained during the Docker
build, so the deployed image lacked it and the scorer ran **rules-only** on the
live demo — the IsolationForest component, and the v2 `district_norm_z` fix,
were dormant in production. `backend/Dockerfile` now runs a deterministic
`python scripts/train_fraud_model.py` (seed `20260620`) before the chown, so
the full ML + rules hybrid runs in prod. Matches the ML-container rule: bake
weights at build, never download/train at container start.

## 2026-05-31 — Pack G (fraud-integrity hardening) + dependency refresh

Cut as `v0.2.4-pack-g` through the build-push → deploy-cranecloud chain.
Backend **62 / 62** pytest, frontend **84 / 84** vitest, cross-language
Merkle parity **48 / 48**, ruff clean.

### `v0.2.4-pack-g`

**Pack G — critical-gap hardening** (gap analysis beyond the published
roadmap; PR #25):

- **G1 / G8 fail-closed fraud gate.** `approve_transfer` refuses to complete
  a transfer with no current fraud score — it scores synchronously on demand
  rather than approving blind when the worker lagged or Redis was down. New
  `fraud_scoring_jobs` transactional outbox (migration 003) + worker sweep
  guarantee eventual scoring.
- **G2 escalation never freezes.** The 24h escalation job
  (`app/jobs/escalation.py`) now raises a review's priority to a supervising
  officer and emits `FRAUD_REVIEW_ESCALATED` — it no longer auto-FREEZEs.
  Reconciles AI Ethics Charter §1/§8: the no-auto-FREEZE invariant is now
  absolute (a human is the only path to FROZEN). Migration 004 adds
  `escalated_at`.
- **G4 governance jobs actually run.** New replica-safe in-process scheduler
  (`app/jobs/scheduler.py`, Redis leader-lock) runs escalation (hourly) and
  the demographic-parity audit (`app/jobs/parity.py`, with a
  `FRAUD_PARITY_BREACH` alert) — previously neither was scheduled anywhere.
- **G3 worker scales horizontally.** Per-process Redis consumer name +
  `run_fraud_worker` gate so multiple API replicas don't collide on the stream.
- **G5 revived dead ML feature.** `district_norm_z` was hardcoded `0.0` at
  inference (train/serve skew) — now computed from district price history.
  `SCORER_VERSION` → `isoforest-rules-v2-20260530` (model-card + §7 go-live
  note; artefact unchanged — it was always trained for the 9-feature layout).
- **G6 prod-safety.** `assert_prod_safety()` now rejects the committed Anvil
  dev signing key and single-signer custody in production.
- **G7** 11 backend regression tests (62 total) pin the gate, the
  escalation-never-freezes behaviour, prod-safety, the feature, and the
  per-process consumer name.

**Dependency refresh** (full Dependabot backlog cleared, every merge CI-gated):

- Backend: redis 5→7.4, uvicorn 0.30→0.48, psycopg→3.3.4, pyjwt→2.13,
  passlib→1.7.4, + backend patch-minor group. Validated: 62 pytest, app
  import, redis async client construct.
- Frontend: zod 3→4, recharts 2→3, vitest 2→4, typescript 5→6, eslint 9→10,
  maplibre-gl 4→5, framer-motion 11→12, @hookform/resolvers 3→5, tailwind-merge
  2→3 (correct Tailwind-4 pairing), react/react-dom 19.2.6, zustand 5.0.14.
  **Dockerfile `oven/bun` 1.1→1.3** (user creation switched to
  `groupadd`/`useradd` — the new Debian base dropped the `adduser` wrappers).
  Validated: tsc 6 clean, vitest 84, `next build` OK, frontend Docker build green.
- CI actions: checkout@6, setup-node@6, upload-artifact@7, build-push-action@7,
  github-script@9. **Dropped:** the python 3.14-slim bump (breaks the asyncpg
  build; the project stays on 3.12).

> Supersedes the Pack-F-era "no new dependencies" note — this release
> deliberately refreshes the dependency tree. The five public claims, the
> dual-Merkle equivalence rule, and the no-auto-FREEZE invariant are unchanged
> (G2 strengthens the latter).

## 2026-05-28 — Post-submission hardening cascade (Packs A → F)

Four tagged releases shipped same-day, each through the documented
build-push → deploy-cranecloud CI/CD chain. Production-verified live
on Crane Cloud RENU-01 after each cut.

### `v0.2.3-server-header` — `9678d7c`

Follow-up to v0.2.2 — `scripts/probe_security_headers.sh` against the
fresh pod showed `Server: uvicorn` still present (uvicorn's protocol
layer overrides ASGI middleware). Dockerfile CMD now passes
`--no-server-header` so the `SecurityHeadersMiddleware`
`Server: landguard` value is the only one emitted. Probe now reports
**23 / 23 hardening checks PASS** on production.

### `v0.2.2-hardening` — `fbc4536` (Pack F)

Defense-in-depth at the app layer. Crane Cloud serves the backend pod
directly with no Caddy in front, so the existing Caddyfile hardening
doesn't apply to live traffic.

- **F1 SecurityHeadersMiddleware** (`backend/app/middleware/security_headers.py`).
  Emits HSTS / X-Content-Type-Options / X-Frame-Options /
  Referrer-Policy / Cross-Origin-Opener-Policy / Permissions-Policy on
  every response, Content-Security-Policy on JSON/HTML responses.
  Mirrors the Caddyfile values for parity.
- **F2 LIKE-injection defensive escape** (`backend/app/util/sql.py`).
  `escape_like_value()` + `ESCAPE '\'` clause applied at every
  `payload_json LIKE` call-site introduced by the v0.2.1 verifier
  fallback (`verify.py`, `anchors.py`, `titles.py`). UPI_REGEX
  already prevents `%`/`_`/`\` in legitimate parcel_id values, but
  if the regex is ever loosened, an attacker who could write a
  parcel_id with `%` would broaden the audit-event match.
- **F3 `/readyz` enrichment** (`backend/app/routers/health.py`). Two
  new `.details` fields: `fraud_model` (joblib presence) and
  `audit_chain` (per-district hash-chain walk via
  `audit.verifier.verify_chain`). Reports each district's event
  count + cryptographic verification result; degrades readiness
  (200 + `degraded: true`) if any district's chain is corrupt.
- **F4 PII-in-logs audit** (read-only). Grep'd every `logger.*` call
  + format string; NIN appears only as `nin_hash` (sha256), phones
  as `sha256(phone)[:8]`, owner names via the masking helper. No
  PII in plaintext anywhere in `app/`.
- **F5 Production probe** (`scripts/probe_security_headers.sh`).
  Asserts each header on three representative endpoints + the
  enriched `/readyz` fields. Returns 0 on full pass.
- **F6 Tests** (`backend/tests/test_security_headers.py` — 12,
  `test_like_escape.py` — 4, `test_readyz_enriched.py` — 3).
  Backend pytest: 51 / 51 (was 32 / 32), ruff clean.

### `v0.2.1-prodfix` — `4f77fdf`

Three production bugs surfaced by the v0.2.0-routetest live
regression (`evidence/deployment-tests/20260528T081451Z/`).

- **Bug A — public verifier returns valid=false for every seeded
  title.** Bootstrap seed emitted `TITLE_ISSUED` audit events with a
  payload that omitted `title_no`. The verifier matches the audit
  event via `payload_json LIKE '%"title_no": "..."%'` — which never
  hit for seeded data. Forward fix: `seed.py` now writes `title_no`
  in the payload. Backward fix: `verify.py` / `anchors.py` /
  `titles.py` fall back to `parcel_id` lookup when the `title_no`
  match misses. Live result on prod: all four seeded titles
  (`MITYANA/V1/2026000{1..4}`) verify successfully without a
  DB wipe.
- **Bug B — `GET /api/v1/fraud/reviews` returned 500.** Seed wrote
  review-queue rows with the legacy signal shape
  `{rule, score (0–100), evidence}`; the runtime serialises via
  `FraudSignalResponse {name, weight, score (0–1), explanation}`,
  so strict pydantic validation 500'd the whole list. Forward fix:
  `seed.py` review_plan uses the new schema with realistic weights
  matching the canonical rule definitions in `app/fraud/rules.py`.
  Backward fix: `_coerce_signal()` in `routers/fraud.py` maps any
  persisted shape to the API model (rule→name, evidence→explanation,
  rescales 0–100 → 0–1). Applied at all three signal-load
  call-sites.
- **Bug C — slash-in-path-param 404s.** FastAPI/Starlette's
  segment-aware router 404'd on `GET /api/v1/{titles,parcels,
  anchors/title}/{id}` whenever the ID contained `/` (every UPI
  like `UG-MIT-024718/2026`, every title number like
  `MITYANA/V1/20260001`). URL-encoding `%2F` didn't help. Fix:
  declare those routes with the Starlette `:path` converter.

### `v0.2.0-routetest` — `7f29a46` + `45d90aa`

Showcase closure Packs A & B.

- **Pack A — cross-language Merkle parity + offline verifier.**
  Closes the testability gap where `frontend/src/lib/merkle.ts`
  claimed byte-for-byte parity with Python + Solidity but had zero
  unit tests to enforce it. New artefacts:
  `backend/scripts/emit_merkle_vectors.py` (10 canonical cases),
  `contracts/test/merkle-parity.json` (62 KB) +
  `contracts/test/MerkleParity.t.sol` (Foundry parity assertion,
  scoped `fs_permissions` for `./test`),
  `frontend/src/__tests__/merkle.test.ts` +
  `merkle.parity.test.ts` (84 / 84 Vitest passing locally),
  `frontend/vitest.config.ts`,
  `scripts/verify_offline.py` (standalone audit-grade verifier,
  pure stdlib + eth-utils, 48 / 48 proofs verified). All three
  language test paths wired into existing CI (`.github/workflows/ci.yml`).
  Print stylesheet (`frontend/src/styles/print.css`) finalised
  with print-color-adjust + no-pulse-on-print + neutralised
  header/footer negative margins.
- **Pack B — evidence + compliance + a11y + route tests.**
  - `docs/model-cards/fraud-scorer.md` — Mitchell-et-al. model
    card following NIST AI RMF / ISO 42001 structure. Linked from
    `AI_ETHICS_CHARTER §7` and README §14b.
  - `docs/security/{README,KEYGEN_CEREMONY}.md` + `.gitignore`
    guards — maintainer PGP keygen ceremony documented; actual
    keygen deferred to the maintainer.
  - `evidence/fraud-parity/20260528T064946Z/` — real audit run
    against 60 synthetic transfers; 2 districts hit the 1.5×
    threshold, proving the AI Ethics Charter §5 plumbing works.
  - `evidence/sbom/*` — regenerated as pre-showcase artefact.
  - **Accessibility 98 → 100 on all four audited Lighthouse pages.**
    Root cause was the skip-link target `<main id="main">` being
    nested inside `/verify`'s Suspense bailout boundary; axe's
    static DOM scan saw no `#main`. Moved target to a
    layout-level `<div id="main" tabIndex={-1} className="contents">`
    in `src/app/layout.tsx`. Bonus heading-order fix on `/anchors`
    (h3 → h2 in `AnchorTimeline.tsx`). New evidence:
    `evidence/lighthouse/20260528T070440Z/SUMMARY.md`.
  - `scripts/probe_verifier.py` — single-file, stdlib-only
    synthetic availability probe for the T1 verifier SLO.
    `docs/SLA_TARGETS.md §10` TODO marker replaced.
  - `evidence/route-tests/20260528T073903Z/` — 43 / 43 routes
    pass against the locally-built Docker stack.

### Production regression evidence

`evidence/deployment-tests/20260528T081451Z/` — 26 / 26 backend
routes pass on Crane Cloud production. Audit-chain integrity
`verified: true` (14+ events). Anchor batches confirmed on
Mityana (7+). Resilience toggles cycle cleanly; anchor flush
during RPC-kill returns `PENDING_BREAKER_OPEN` and recovers
without crash.

---

## 2026-05-26 — CI/CD failure cascade resolved + tag-push deploy contract

Five distinct pipeline failures surfaced during a single tagged-release
push and were each fixed. Commits: `e80ac8a`, `6d66445`, `8ccb03c`,
plus tag-retag → `8ccb03c`.

  - **Backend ruff: 96 lint errors blocking CI.** Local ruff was
    `0.6.0`; the CI lockfile pins `0.15.13`, which added several new
    rules. Fix: extended `[tool.ruff.lint].ignore` with eight
    codebase-intentional rules (`PLW0603` singleton pattern, `S311`
    non-crypto random, `S608` parameterised SQL false positives,
    `PLR0911` guard-clause returns, `S105` test JWT, `S110/S112`
    best-effort suppression, `PLC0415` in-function imports for
    circular-import avoidance, `UP042/UP046/UP047` PEP 695 syntax
    that requires py3.13+). Per-file `N803` for
    `app/routers/ussd.py` (webhook contracts). Plus 11 genuine
    cleanups (PLW2901 / SIM102 / F841 / N814 / N806 / C416 /
    3× SIM105 → `contextlib.suppress` / ERA001) and 47 `ruff --fix`
    auto-corrections.

  - **`Failed to spawn: ruff` in CI.** `uv sync --frozen` installs
    only main dependencies, not `[project.optional-dependencies].dev`
    where ruff/mypy/pytest live. Fix in `.github/workflows/ci.yml`:
    `uv sync --frozen --extra dev`.

  - **mypy: `app.util.metrics` not in a package.** Fix: invoke as
    `uv run mypy --explicit-package-bases app` (still
    `continue-on-error: true` while the strict baseline is paid down).

  - **Frontend Lint: `next lint` removed in Next.js 16.** Stubbed
    `frontend/package.json` `lint` script with an informative echo +
    `exit 0`; documented `eslint-config-next` + ESLint v9 flat-config
    as a follow-up.

  - **Crane Cloud PATCH 404: `image does not exist`.** The
    `docker/metadata-action` only emits the semver-suffixed tag
    `:0.1.0-showcase-<sha7>` when a `v*` git tag is pushed —
    main-branch pushes only yield `:main`, `:main-<sha>`, `:sha-<sha>`.
    `deploy-cranecloud.yml` expects the semver form. Resolution: push
    `git tag v0.1.0-showcase` → `8ccb03c` to trigger the right
    Build & push tag set. The auto-dispatched Deploy then chained
    green. Documented this contract in
    `docs/CRANE_CLOUD_DEPLOYMENT.md`.

Final state on `8ccb03c`: CI ✓ (8/8 jobs), Build & push ✓,
Deploy to Crane Cloud ✓ (9/9 steps). Live `/readyz` returns
`db=ok, anchor_breaker=closed, block=1000001`.

## 2026-05-26 — Manual Crane Cloud redeploy during GitHub Actions outage

GitHub Actions had a `major_outage` for ~40 min that prevented
`docker/setup-buildx-action` and friends from downloading their
archives from `codeload.github.com`. The Build & push job failed
on multiple commits, leaving Docker Hub without the SHA-tagged
images that `deploy-cranecloud.yml` expects.

The fallback procedure (documented in
`docs/CRANE_CLOUD_DEPLOYMENT.md` §Manual deploy during Actions
outage):

  1. `docker build --platform linux/amd64 -t <ns>/landguard-uganda-backend:0.1.0-showcase-<sha7> -f backend/Dockerfile backend/`
  2. `docker push <ns>/landguard-uganda-backend:0.1.0-showcase-<sha7>`
  3. Same for the frontend, with
     `--build-arg NEXT_PUBLIC_BACKEND_URL=...` so the runtime CORS
     target is baked into the client bundle.
  4. `gh workflow run deploy-cranecloud.yml --ref main --field target=both --field image_tag=v0.1.0-showcase` —
     uses the existing `CRANE_CLOUD_PASSWORD` GitHub secret; no
     plaintext enters argv or transcript.

Restored deploy on commit `9dc3e4d` (run `26449175328`) before the
auto-pipeline came back. The image digests are recorded in the
commit message.

## 2026-05-26 — Mobile responsiveness pass

The whole UI was desktop-only. `(app)/layout.tsx` hard-coded a 16 rem
sidebar that ate 68 % of a Pixel 5 viewport, and `(public)/layout.tsx`
crammed a five-element nav onto a single row. Commit `62ebb86` +
follow-up `830ca11`.

  - `frontend/src/components/layout/MobileMenu.tsx` — reusable
    headless drawer (focus-trap close button, Esc-to-close, body
    scroll lock, backdrop tap, auto-close on link click inside the
    panel).
  - `(app)/layout.tsx` — `lg:grid-cols-[16rem_1fr]`; sidebar hidden
    below lg, exposed via MobileMenu in the header. Single
    `<Sidebar>` component renders the nav in two themes (dark default
    + light mobile).
  - `(public)/layout.tsx` — inline nav at sm:+, right-side hamburger
    below; chain-status beacon stays visible in every header at every
    width.
  - `app/page.tsx` (landing) — inline nav md:+, phone gets a compact
    "Verify" primary CTA + hamburger.
  - `components/chain/AnchorTimeline` — rigid 3-col grid → stacked
    flex below sm.
  - `components/chain/MerkleProofVisualizer` — label column 7 rem →
    5.5 rem on phones, drops trailing "On chain" column.
  - `(app)/citizen` parcel rows — 4-col rigid → wrapped flex; UPI now
    `break-all`.
  - `components/layout/RoleSwitcher` — label `sr-only` below sm.

E2E coverage: `playwright.config.ts` gains a `mobile-chromium`
project (Pixel 5 viewport) running `e2e/mobile.spec.ts` —
horizontal-overflow regression on four public routes, both
hamburger drawers (public + console), axe-core a11y on `/verify`.
8/8 mobile + 24/24 desktop green.

## 2026-05-26 — WCAG 2.2 AA colour-contrast resolution

axe-core flagged six pages with `[serious]` colour-contrast
violations. Three classes of issues; commit `f98203f`.

  - `.pill-verified` text — `status.verified` `#15803d` on
    `bg-status-verified/10` was 4.38:1 (need 4.5:1). Token darkened
    to `#14532d` (~7.0:1).
  - `.pill-pending` text — `status.pending` `#b45309` was 4.38:1.
    Darkened to `#854d0e` (~6.4:1). `.pill-flag` and `.pill-frozen`
    preemptively darkened by one shade (same contrast math).
  - `(app)/layout.tsx` NavGroup labels — `text-slate-500` on
    `guard-900` dark sidebar was 2.74:1. Lifted to `text-slate-300`
    (~8.8:1) while keeping the quiet header hierarchy.

`accessibility.spec.ts` `waitUntil: "networkidle"` never settled
(ChainStatusBeacon polls every 5 s); switched to `"load"` + a
1.5 s mount wait, raised `test.setTimeout` to 60 s for the network
round-trip to Crane Cloud plus axe analysis. 6/6 pages WCAG 2.2 AA
clean (was 1/6).

## 2026-05-26 — Showcase polish: seed enrichment, i18n stub, demo-router fix

Commits `44a7d1f`, `2cdb6e0`, `b805591`.

  - **`seed_demo_extras()`** in `backend/app/bootstrap/seed.py` issues
    four titles (hero + three on background Mityana parcels), one
    completed Okello→Namatovu SALE transfer, and three
    `PENDING_REVIEW` fraud-review-queue rows with realistic signals
    (watchlist match, rapid resale, duplicate NIN). Idempotent per
    row. Adds five audit events on top of the existing two so the
    anchor loop produces a richer timeline on cold boot.

  - **Luganda i18n stub** for `/verify`. New
    `frontend/src/lib/i18n/messages.ts` catalogue (en + lg), Zustand-
    shared store at `src/store/useLocaleStore.ts`, hook at
    `src/lib/i18n/useLocale.ts`, picker at
    `src/components/layout/LocaleSwitcher.tsx`. Luganda strings are
    best-effort working drafts pending native-speaker review before
    the Mityana pilot (flagged in the catalogue header). Cookie-
    persisted (`lg_locale`, 1 year, `SameSite=Lax`).

  - **Demo router gate simplified** to `app_env != "production"` only
    (was double-gated on `demo_mode` AND `app_env`). The combination
    created a deployment footgun where the bootstrap setting
    `DEMO_MODE=false` silently disabled the entire `/api/v1/demo/*`
    router and the `X-Demo-Role` header, breaking Acts 1–5 of the
    showcase storyboard on the live deploy. `Settings.assert_prod_safety()`
    still rejects `demo_mode=true` on production builds, so
    runtime gating on `app_env` alone is sufficient and
    less footgun-prone.

  - **a11y CI scoped to accessibility.spec.ts** —
    `.github/workflows/ci.yml` invokes
    `bunx playwright test accessibility.spec.ts` directly so the
    smoke+flows specs (which need a deployed backend over CORS)
    don't fail in CI's localhost-only environment.

## 2026-05-26 — On-startup seed + browser-direct CORS architecture

Commits `08aa4bd`, `6357159`, `185fb2f`, `9f21039`,
`6927b8a`, `e4b128b`, `3821a17`.

  - **`app.bootstrap.seed.maybe_seed_on_startup()`** called from
    `lifespan` after `apply_migrations()`. Two guards: skip when
    `APP_ENV == "production"`; skip when the `districts` table
    already has rows. Each individual seed function is idempotent
    (`INSERT OR IGNORE`, existence checks). CLI shims in
    `backend/scripts/seed_*.py` now import from the new module so the
    operator-driven re-seed path uses identical code.

  - **Browser-direct CORS to backend** because Crane Cloud RENU pods
    have zero outbound internet egress (verified via
    `frontend/src/app/api/proxy-debug/route.ts`: Google, 1.1.1.1, and
    `api.cranecloud.io` all timed out from inside the frontend pod).
    `frontend/Dockerfile` bakes `NEXT_PUBLIC_BACKEND_URL` into the
    client bundle at build time. `frontend/src/lib/api.ts` uses
    `${NEXT_PUBLIC_BACKEND_URL}/api` when set, else falls back to
    `/api/proxy` (the runtime route handler) for local development.
    `backend/app/config.py` adds the deployed frontend origin to the
    CORS allowlist.

  - **`/explore/district/[code]`** drill-down with
    `generateStaticParams` + `dynamicParams: false`, so the four
    pilot/planned districts render statically and unknown codes 404
    deterministically. Closes the broken-link issue surfaced by the
    e2e smoke run.

  - **`GET /api/v1/anchors*` made public** (no `require_user`). The
    on-chain anchor metadata (root hash, leaf count, tx hash, block
    number, Merkle proof) is the publicly-verifiable evidence
    surface; gating it behind auth contradicted the design intent.

  - **End-to-end test suite stabilised** —
    `frontend/e2e/{smoke,flows,accessibility}.spec.ts` with a
    `chrome-headless-shell` launcher (the shared dev box SIGTRAPs on
    full chromium), transient-net retry pattern, and `TRANSIENT_NET`
    allow-pattern for `ERR_NETWORK_CHANGED`/`ERR_FAILED` jitter on
    long-haul requests to Crane Cloud RENU. 24/24 desktop
    consistently green across runs.



Operationalises the CI/CD pipeline with two scripts and a deployment
reference, all adapted from `mpairwe7/MLOPS_V1`'s 676-line
`docs/22-crane-cloud-deployment.md` and proven against the same
Crane Cloud account (`mpairwelauben75@gmail.com`) and Docker Hub
namespace (`landwind`) used by OptiscanAI:

  - `scripts/bootstrap_cranecloud.sh` — one-shot API-driven creation
    of the LandGuard project on RENU cluster + both apps
    (`landguard-backend`, `landguard-frontend`). No CLI dependency.
    Prompts for password via `read -s` (no echo, never enters argv
    or transcript). Writes non-secret UUIDs + URLs to
    `/tmp/landguard-cranecloud-bootstrap.env` for the next script.

  - `scripts/setup_github_secrets.sh` enhanced to:
      - Source `/tmp/landguard-cranecloud-bootstrap.env` automatically
        when present — UUIDs and URLs are pre-filled so the operator
        only types the 3 actual secrets (DOCKERHUB_TOKEN,
        CRANE_CLOUD_PASSWORD).
      - Pre-fill known mpairwe7 defaults: DOCKERHUB_USERNAME=`landwind`,
        CRANE_CLOUD_EMAIL=`mpairwelauben75@gmail.com` (lowercase as
        required by api.cranecloud.io's case-sensitive login).
      - Distinguish secret vs non-secret prompts: non-secrets echo so
        the operator can see what they're confirming; secrets never
        echo.

  - `docs/CRANE_CLOUD_DEPLOYMENT.md` — LandGuard-specific operator
    guide. Documents:
      - Three-command bootstrap (~6–8 min to live deploy)
      - Available clusters (RENU vs AHUMAIN — current health status)
      - Full API reference (POST /users/login, PATCH /apps/{id} etc.)
      - SHA-suffix tagging discipline (why floating tags don't trigger
        pod rollover and the workflow always PATCHes
        `:<tag>-<sha7>`)
      - All env vars passed to each Crane Cloud app + why
      - Deploy-only flow for env-var changes without rebuild
      - Troubleshooting per the OptiscanAI deployment history

The bootstrap script intentionally seeds the backend with weak
JWT_HS256_SECRET and PII_ENCRYPTION_KEY values that trip
`Settings.assert_prod_safety()` at startup — so the operator
MUST rotate them via the Crane Cloud dashboard after bootstrap
before the backend will accept production traffic. The dashboard
rotation is a one-time-per-environment step.

## 2026-05-26 — CI/CD rewired to direct Crane Cloud HTTP API (OptiscanAI pattern)

The previous `deploy-cranecloud.yml` depended on the `cranecloud` Python
CLI inside the runner. That CLI requires an OS keyring backend
(D-Bus / SecretService) which GitHub-hosted runners don't provide, and
fighting the keyring with `PYTHON_KEYRING_BACKEND=null` plus token-file
seeding proved brittle across CLI versions.

The replacement, ported from `mpairwe7/OptiscanAI`'s production
`docker-publish.yml`, uses **direct curl calls to api.cranecloud.io**:

  1. `POST /users/login` with email+password in JSON body → JWT in
     `data.access_token`.
  2. `PATCH /apps/{app_id}` with `{"image": "<docker.io path>:<tag>-<sha7>"}`
     → triggers Crane Cloud pod rollover.
  3. `GET <public-url>/healthz` (or `/api/health`) polled for up to 5 min.

Why SHA-suffixed tags? Crane Cloud diffs the `image` field as a
string. PATCHing the same `:latest` or `:v0.1.0-showcase` tag is a
no-op. We push both the floating tag AND a `<tag>-<sha7>` variant on
every build; the deploy step PATCHes the SHA-suffixed form so every
push produces a fresh image string Crane Cloud sees as new.

Secret-name convention mirrors OptiscanAI:

  Repository-level (`gh secret set NAME --repo …`):
    DOCKERHUB_USERNAME, DOCKERHUB_TOKEN

  `production` environment (`gh secret set NAME --env production`):
    CRANE_CLOUD_EMAIL, CRANE_CLOUD_PASSWORD
    CRANE_CLOUD_BACKEND_APP_ID, CRANE_CLOUD_FRONTEND_APP_ID
    CRANE_CLOUD_BACKEND_URL, CRANE_CLOUD_FRONTEND_URL  (optional, for health-check)

`scripts/setup_github_secrets.sh` walks the operator through setting
all eight via `gh secret set NAME --body -` with `read -s` for the
value, so no secret value ever enters argv, history, or stdout. Use
`--rotate` to force-overwrite already-set values.

`.github/workflows/build-push.yml` simplified: no more
`vars.DOCKER_IMAGE_OWNER` override path; images go to
`docker.io/${DOCKERHUB_USERNAME}/landguard-uganda-{backend,frontend}`
directly. Auto-dispatches `deploy-cranecloud.yml` only on `v*` tag
pushes (`main`-branch pushes only build, never deploy — matches the
production-deploy posture in MAINTAINERS.md).

`production` GitHub environment created via
`gh api -X PUT repos/mpairwe7/LandGuardUganda/environments/production`.
Reviewer protection rules can be added in the GitHub UI later
(Settings → Environments → production → Required reviewers).

The previous CLI-based workflow + `infra/cranecloud/` Makefile path
remain available for operator-led local deploys (first-time app
creation, ad-hoc rollouts, debugging) but are no longer the canonical
CI path.

## 2026-05-25 — Pre-submission deliverables (axe spec, pentest scope, breach runbook)

- `frontend/e2e/accessibility.spec.ts` (new) — Playwright +
  `@axe-core/playwright` spec asserting zero critical / zero serious
  WCAG 2.2 AA violations across six citizen-critical routes. Findings
  attach as JSON to the Playwright HTML report. Bound to a new CI
  job in `.github/workflows/ci.yml` (`accessibility`) that builds the
  frontend, runs the production server, installs Playwright Chromium,
  executes the spec, and uploads the report as a 90-day artefact.
- `frontend/playwright.config.ts` (new) — standard Playwright config
  driving the spec; `BASE_URL` envvar drives the target (defaults to
  localhost prod build on :3031).
- Added `@axe-core/playwright` + `axe-core` to frontend devDeps.
- `docs/audit/PENTEST_SCOPE.md` (new) — OWASP ASVS L2 scope of work
  for the pilot-launch pen-test: in-scope surfaces (web/API, crypto
  invariants, smart contracts, deployment surface, UX), explicit
  out-of-scope list, five-phase methodology, deliverables,
  findings-classification SLAs, budget envelope (UGX 17–23M), retest
  cadence, vendor shortlist (Makerere CSL preferred).
- `docs/runbooks/dppa-breach-notification.md` (new) — DPPA-2019 §19
  72-hour breach-notification procedure: trigger criteria, hour-by-
  hour timeline, decision tree, role separation, containment
  procedures (PII / chain / multi-sig key), PDPO + SMS notification
  templates, audit-chain emission schema, quarterly drill cadence.
- `docs/audit/CODEBASE_MAP.md` §8 updated: closes four prior-known
  gaps (frontend/e2e, scripts/ root, SBOM, pentest scope, DPPA
  runbook) and re-states the remaining honest gaps.

## 2026-05-25 — Lighthouse baseline + a11y skip-link fix

- Generated the first measured Lighthouse baseline against a local
  production build (`evidence/lighthouse/20260525T143155Z/`). Per-page
  scores: P 75–81 / A11y 98 / BP 96 / SEO 100. Measurement environment
  documented in `SUMMARY.md` alongside reproduction commands; honest
  delta to targets called out in `docs/IMPACT_EVIDENCE.md` §1.1.
- Fixed the single failing accessibility audit (`skip-link`) by wrapping
  the page tree in `<main id="main">` in `frontend/src/app/layout.tsx`.
  The skip-link in the layout targets `#main`; the next Lighthouse run
  expected to score Accessibility = 100.
- Hardened `scripts/lighthouse_ci.sh` to work on sandboxed runners:
  prefer `npx` over `bunx` (bunx ENOTSUP on certain filesystems);
  auto-discover Chrome from `~/.cache/puppeteer/chrome-headless-shell`;
  pre-launch Chrome on a fixed devtools port with a writable
  `user-data-dir`; `--disable-storage-reset` to work around
  `Storage.getUsageAndQuota` not supported in chrome-headless-shell.

## 2026-05-25 — CI/CD switches to Docker Hub (reuses FYP/HSU secrets)

- `.github/workflows/build-push.yml` rewritten to push to
  `docker.io/<DOCKERHUB_USERNAME>/landguard-uganda-{backend,frontend}`
  instead of GHCR. Authenticates with `DOCKERHUB_USERNAME` +
  `DOCKERHUB_TOKEN` — the same secret names already configured for
  `Mpairwe7/FinalYearProject` and `Mpairwe7/HealthSyncUganda`, so no
  new secrets need to be created.
- `.github/workflows/deploy-cranecloud.yml` updated to pull from
  `docker.io/<owner>/...` rather than `ghcr.io/...`. Continues to use
  the same Crane Cloud secret names (`CRANECLOUD_TOKEN`,
  `CRANECLOUD_USER_ID`, `CRANECLOUD_PROJECT_ID`,
  `CRANECLOUD_BACKEND_APP_ID`, `CRANECLOUD_FRONTEND_APP_ID`) that
  HealthSyncUganda's pipeline uses.
- Optional repo-level override: set `vars.DOCKER_IMAGE_OWNER` to point
  at an organisation namespace (e.g. `landguardug`) instead of the
  personal Docker Hub user.

## 2026-05-25 — Crane Cloud CI/CD pipeline + SBOM evidence

- Added `.github/workflows/{ci,build-push,deploy-cranecloud}.yml` — three-
  workflow pipeline mirroring the HealthSync Uganda pattern: PR-gate CI,
  GHCR build-push, operator-led Crane Cloud rollout with hard-fail
  fallback to the local `make update-*` path.
- Added `.github/dependabot.yml` — weekly uv + npm + actions + docker
  scans, Africa/Kampala timezone.
- Added `infra/cranecloud/` — `manifest.yaml` (deploy contract),
  `Makefile` (deploy/update wrappers), `README.md` (operator guide),
  and three environment templates (staging / pilot / production) with
  explicit production-safety posture (blank `BACKEND_IMAGE_TAG`,
  `MULTISIG_ENABLED=true` mandatory, OIDC required).
- Generated first CycloneDX 1.5 SBOM bundle in `evidence/sbom/` —
  backend (139 KB), frontend (1.3 MB, 838 components with full
  provenance), contracts (submodule digest). Each file content-addressed
  with SHA-256.
- `scripts/generate_sbom.sh` made robust to React 19 peer-dep strictness
  via `--ignore-npm-errors`; added `scripts/_sbom_frontend_fallback.py`
  as a stdlib-only fallback when `cyclonedx-npm` is unavailable.
- `.gitignore` updated to include `infra/cranecloud/environments/*.env`
  and `evidence/{lighthouse,load,probes}/` (per-run artefacts), and to
  **un**-ignore `bun.lock` (required for reproducible CI + SBOM).

## 2026-05-25 — Showcase evaluation evidence pack

- `docs/SHOWCASE_EVALUATION_MAPPING.md` — one-page criterion→evidence map.
- `docs/IMPACT_EVIDENCE.md` — reproducible Lighthouse/axe/load methodology
  + TCO + user-research plan.
- `docs/SLA_TARGETS.md` — national-scale SLOs, observability + DPPA §19
  breach SLA.
- `docs/STANDARDS_ALIGNMENT.md` — DPPA / NITA-U / ISO 42001 / NIST AI RMF
  / OWASP ASVS / WCAG 2.2 / World Bank LGAF / OpenHIE-Land mapping.
- `docs/TEAM.md`, `MAINTAINERS.md`, `CODE_OF_CONDUCT.md` — innovator
  capability and governance evidence (no fabricated identities).
- ADR-0002 zero-trust posture (NIST SP 800-207 + Uganda extensions).
- ADR-0003 regional / EAC chain migration path.
- `scripts/{generate_sbom,lighthouse_ci,load_test}.sh` +
  `backend/scripts/load_test.py` — reproducible evidence runners.
- `docs/audit/CODEBASE_MAP.md` — file-by-file inventory of repo state.

## 2026-05-21 — starlette 0.50.0 (CVE-2025-62727)

Commit: `1343660 deps: bump starlette to 0.50.0 (CVE-2025-62727)`

- Bumped `starlette` floor to `>=0.50.0` and ceiling to `<0.51`.
- FastAPI ceiling raised accordingly to `<0.123` so resolution settles on
  the patched starlette line.
- No code changes — pure dependency bump.

## 2026-05-20 — Dependabot batch (16 alerts: 9 high, 5 moderate, 2 low)

Commit: `c7b887e deps: resolve 16 Dependabot alerts (9 high, 5 moderate, 2 low)`

**Frontend** (13 Next.js CVEs — 7 high / 4 moderate / 2 low):
- `next`: `16.2.3` → `^16.2.6`. Covers CVE-2026-44572..82, GHSA-8h8q-6873-q5fj,
  CVE-2026-45109.

**Backend** (3 alerts — 2 high / 1 moderate):
- Starlette CVE-2024-47874 (high) + CVE-2025-54121 (moderate):
  `fastapi 0.111.0` → `>=0.118,<0.120`; explicit `starlette>=0.47.2,<0.49`.
  Final resolution: fastapi 0.119.1 + starlette 0.48.0.
- ecdsa CVE-2024-23342 (high, no upstream patch — Minerva timing attack on
  ECDSA signing): **migrated off `python-jose` to PyJWT**. We never signed
  with ECDSA (JWT is HS256 dev / RS256 OIDC prod), but eliminating the
  transitive dep is cleaner than documenting an inapplicable advisory.

JWT migration details:
- `backend/app/auth/jwt_auth.py` rewritten to use PyJWT 2.12.1+crypto with
  manual JWKS `kid` resolution via `jwt.algorithms.RSAAlgorithm.from_jwk`.
- API surface unchanged (`JWTVerifier.verify`, `make_dev_token`).
- All backend tests pass on the upgraded stack.

Other:
- Pydantic bumped `2.7.4` → `>=2.9,<3` (transitive from new fastapi).
- `backend/Dockerfile`: now copies `README.md` alongside `pyproject.toml`
  so hatchling's readme validation doesn't fail on install.

## 2026-05-20 — Audit-grade documentation pass

Commit: `66a6856 docs: comprehensive audit-grade documentation`

- `backend/README.md`, `frontend/README.md`, `contracts/README.md` —
  full setup, layout, routes, config, tests, security posture.
- `docs/REQUIREMENTS.md` — system + toolchain + external service
  requirements, capacity targets, compliance posture, mapping of the
  seven National Innovator Registry evaluation criteria to evidence files.
- `docs/ARCHITECTURE.md` — data flow diagram, dual-layer trust model,
  tenancy + RLS, fraud detection, resilience, threat model summary,
  observability, testing strategy, migration paths.
- `README.md` — documentation index pointing at every audit-relevant doc.

## 2026-05-20 — Initial commit

Commit: `083e03d Initial commit: LandGuard Uganda`

First public commit. Includes:

- FastAPI 0.111 backend with per-district hash-chained audit ledger,
  IsolationForest + rules fraud scorer (human-in-the-loop), NIRA
  mock + live clients, anchor service with circuit-breaker.
- LandRegistryAnchor.sol + MultiSigRegistrar.sol (3-of-5 named signers).
- Next.js 16 PWA with Officer console, registrar console, auditor
  console, public verifier (smartphone + USSD), demo control panel.
- Dual-Merkle regime (ADR-0001): SHA-256 off-chain + sorted-pair keccak
  on-chain, bridged by `keccak(sha256_hex_leaf)`.
- DPPA-2019 compliance posture: NIN AES-GCM encrypted at rest,
  right-to-erasure tombstones, phone numbers SHA-256 hashed in audit.
- Docker compose for full stack (postgres+postgis, redis, anvil,
  contract-deploy, co-signer, backend, frontend, caddy TLS, prometheus,
  grafana). All containers non-root, `cap_drop:[ALL]`.

---

## How to add an entry

1. Identify the trigger: CVE remediation, dep bump, security-relevant
   refactor, or architectural decision.
2. Add a dated H2 section at the top of this file.
3. Cite the commit short SHA (`git log --oneline -1`) on its own line.
4. Bullet what changed and why — link to ADRs or threat-model entries
   when relevant.
5. Keep entries factual. Marketing copy belongs in `README.md`.
