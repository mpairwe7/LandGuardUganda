# LandGuard Frontend

Next.js 16.2.3 · React 19.2.0 · TypeScript strict · Bun · Tailwind 4 · IBM Plex.

This document covers the development workflow, build/run procedures, and
the design-system contract the UI must satisfy. The visual contract itself
is specified in [`../docs/DESIGN_SYSTEM.md`](../docs/DESIGN_SYSTEM.md);
this README focuses on the engineering side.

---

## 1. System requirements

| Requirement | Version | Notes |
| --- | --- | --- |
| Bun | ≥ 1.1.45 | Primary runtime + package manager |
| Node compatibility | 20+ | For tooling that doesn't run on Bun yet |
| Docker / Docker Compose | 24.0 / 2.20 | For the production build |

Bun is used both for `bun install` and `bun run` (Next.js dev server,
build, tests). The lockfile is **not** committed (see `.gitignore`); CI
regenerates it via `bun install`.

Recommended host: 8 GB RAM (Next 16's Turbopack is memory-hungry), 4 vCPU.

---

## 2. Quick start (local)

```bash
cd frontend
bun install
bun dev                     # http://localhost:3000
```

The dev server runs against the backend at `http://backend:8000` by
default (matches docker-compose). For a local backend:

```bash
BACKEND_URL=http://localhost:8000 bun dev
```

---

## 3. Quick start (Docker)

```bash
cd ..                                          # project root
docker compose --profile anvil up -d frontend  # builds and serves
# → http://localhost:3000
```

The image is multi-stage: build under `oven/bun:1.1.45`, runtime under
the same with a non-root `landguard` user. Next.js standalone output is
used so the runtime image is ~ 250 MB.

---

## 4. Repository layout

```
frontend/
├── package.json bun.lock next.config.mjs tsconfig.json
├── tailwind.config.ts postcss.config.mjs eslint.config.mjs
├── playwright.config.ts vitest.config.ts Dockerfile
├── .env.local.example
│
├── public/
│   ├── sw.js manifest.json favicon.svg
│   ├── icons/{192,512,maskable}.png
│   ├── fonts/                       (self-hosted IBM Plex at build time)
│   └── static-maps/{mityana,wakiso,kampala-central,gulu}.png
│
├── e2e/                             Playwright nightly storyboard tests
│   ├── landing.spec.ts
│   ├── verify-offline.spec.ts
│   └── demo-storyboard.spec.ts
│
└── src/
    ├── app/                         Next.js App Router tree
    │   ├── layout.tsx page.tsx loading.tsx error.tsx not-found.tsx
    │   ├── manifest.ts robots.ts sitemap.ts
    │   ├── (public)/                Public route group
    │   │   ├── layout.tsx
    │   │   ├── verify/page.tsx      Showcase Act 1 + 4
    │   │   ├── explore/page.tsx     District browser
    │   │   ├── anchors/page.tsx     Public anchor explorer
    │   │   └── anchors/[batchId]/page.tsx
    │   ├── (app)/                   Authenticated route group
    │   │   ├── layout.tsx           Officer console chrome
    │   │   ├── citizen/page.tsx
    │   │   ├── surveyor/register/page.tsx (Act 2)
    │   │   ├── officer/page.tsx     (Act 3)
    │   │   ├── registrar/page.tsx   (Act 2)
    │   │   └── auditor/page.tsx     (Act 6)
    │   ├── titles/[upi]/
    │   │   ├── page.tsx             Printable certificate
    │   │   ├── qr/route.ts          PNG QR
    │   │   └── pdf/route.ts         Server-rendered PDF
    │   ├── demo/page.tsx            (Act 5 — gated by ?demo=1)
    │   └── api/
    │       ├── health/route.ts
    │       └── proxy/[...path]/route.ts   Same-origin proxy to FastAPI
    │
    ├── components/
    │   ├── certificate/             TitleCertificate.tsx (A4 print)
    │   ├── chain/                   MerkleProofVisualizer + AnchorTimeline +
    │   │                            ChainStatusBeacon + PendingAnchorBadge
    │   ├── common/                  Button + StatusPill + HashDisplay
    │   ├── demo/                    DemoControlPanel
    │   ├── fraud/                   FraudExplainer + ReviewQueue
    │   ├── kyc/                     KycForm (NIRA flow)
    │   ├── map/                     MapParcelDrawer + MapParcelViewer
    │   ├── transfer/                TransferFlow (XState)
    │   ├── dispute/                 DisputeFilingForm
    │   ├── verify/                  QrScanner + OfflineVerifyBanner
    │   ├── forms/                   CitizenIdField (NIN checksum)
    │   ├── layout/                  MinistryHeader + CoatOfArmsMark +
    │   │                            RedactToggle + RedactShell +
    │   │                            DistrictPicker + RoleSwitcher
    │   ├── Providers.tsx            QueryClientProvider + ToastProvider
    │   └── ServiceWorkerRegistrar.tsx
    │
    ├── store/                       Zustand stores (7)
    │   ├── useAuthStore.ts          persist, encrypted localStorage
    │   ├── useDistrictStore.ts      persist
    │   ├── useDemoStore.ts          sessionStorage
    │   ├── useChainStatusStore.ts   no persist; 5-s poll
    │   ├── useOfflineVerifyStore.ts IndexedDB via idb-keyval
    │   ├── useDraftParcelStore.ts   persist
    │   └── useRedactStore.ts        no persist (officer privacy)
    │
    ├── hooks/                       useApi, useChainStatus, useMerkleProof,
    │                                useOverlapDetection, useOfflineQueue,
    │                                useRoleGate, useDemoStep
    │
    ├── lib/                         api.ts authSession.ts idb.ts hash.ts
    │                                merkle.ts qr.ts format.ts district.ts
    │                                featureFlags.ts analyticsConsent.ts
    │                                logger.ts cn.ts
    │
    ├── services/                    titlesService, parcelsService, transfersService,
    │                                kycService, fraudService, anchorsService,
    │                                verifyService, demoService
    │
    ├── types/                       api.ts (OpenAPI-generated) + domain.ts
    │
    └── styles/                      globals.css + print.css
```

---

## 5. Configuration (env vars)

Place these in `.env.local` (not committed) — see `.env.local.example`.

| Variable | Default | Notes |
| --- | --- | --- |
| `BACKEND_URL` | `http://backend:8000` | Used by the `/api/proxy/*` rewrite |
| `NEXT_PUBLIC_CHAIN_ID` | `31337` | Anvil; `11155111` for Sepolia |
| `NEXT_PUBLIC_USSD_CODE` | `*247*256#` | Shown on the verifier surface |
| `NEXT_PUBLIC_PWA_ENABLED` | `true` | Registers the service worker |
| `NEXT_PUBLIC_DEMO_GATING` | `false` | Hides `/demo` link in nav when `false` |

The frontend never holds an Anthropic / OpenAI / Google API key — all
AI-side calls go through the backend.

---

## 6. The design-system contract (summary)

Full spec at [`../docs/DESIGN_SYSTEM.md`](../docs/DESIGN_SYSTEM.md).
TL;DR for engineers writing UI code:

- **Colour**: three palettes only — `guard` (Forest Green), `seal` (Gold),
  `status` (verified/pending/flag/frozen/chain/neutral). Plus `slate-*`.
  No other brand colours.
- **Gold is rationed**: only on certificate seals, on-chain confirmation
  pills, and ministry attribution. Three gold elements on one screen = bug.
- **Status colour discipline**: `status-flag` (orange) is for ML-flagged
  items; `status-frozen` (red) is only for human-affirmed freezes. This
  is the visual proof of the AI Ethics Charter.
- **Buttons**: four variants only (`primary`, `secondary`, `tertiary`,
  `destructive`) via `src/components/common/Button.tsx`. Ad-hoc
  `<button class="bg-...">` styles are a code-review smell.
- **Status pills**: always via `src/components/common/StatusPill.tsx` —
  colour + icon + `aria-label`. Never `<span class="text-green-700">✓</span>`.
- **Hashes / IDs**: always via `src/components/common/HashDisplay.tsx` —
  head + ellipsis + tail, copy-to-clipboard, `redactable` aware.
- **Two canvases**: `max-w-citizen` (896 px) for citizen reading
  surfaces; `max-w-officer` (1280 px) for officer triage / landing pages.
- **PII fields are `redactable`**: anything that's another citizen's NIN,
  name, registrar id, or officer notes gets the `redactable` class. The
  `RedactToggle` in the officer header blurs them all in one click.

---

## 7. State management

- **TanStack Query v5** for all server state. Query keys live in
  `src/services/*` next to the request functions. Stale times are
  tuned per-endpoint — see `frontend/src/services/titlesService.ts`
  for the canonical pattern.
- **Zustand 5** for client state (auth, district, redact mode, draft
  parcel). Persisted stores use `partialize` to keep raw tokens out of
  localStorage.
- **XState** is used only for `TransferFlow` (the 5-step transfer
  wizard) — the rest of the app doesn't need a state machine.
- **No Redux. No Context for server data.** TanStack Query owns it.

---

## 8. Running tests

```bash
bun test                                  # vitest unit tests
bun test src/__tests__/lib/merkle.test.ts # cross-language merkle parity
bunx playwright test                      # E2E (requires running stack)
bunx playwright test demo-storyboard.spec.ts  # the showcase rehearsal
```

The `demo-storyboard.spec.ts` test plays all five acts on a 60 s timer
and fails CI if any step times out — used as a nightly dress rehearsal
in the week leading up to 25 June 2026.

---

## 9. Production build

```bash
bun run build                            # Turbopack production build
bun run start                            # Standalone server
```

The standalone output (`.next/standalone/`) is what the Docker image
ships. Initial JS budget is ≤ 180 KB gz for `/` and `/verify` —
checked in CI via Next's build report.

---

## 10. PWA + offline verifier

`public/sw.js` is a hand-rolled Workbox-style service worker that caches
the `/verify` route shell and the last 50 `['proof', proofId]` query
results into IndexedDB via `idb-keyval`. The `OfflineVerifyBanner`
component surfaces the cached state to the user.

This is the load-bearing inclusion feature: a citizen at a rural land
office can verify a title on a phone that lost connectivity 30 minutes
ago, against a proof cached at the start of the day.

---

## 11. Common operations

```bash
# Regenerate the OpenAPI types from the backend
bunx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts

# Add a shadcn/ui component (only the parts we actually use)
bunx shadcn-ui add toast

# Update Tailwind tokens
# 1. Edit tailwind.config.ts
# 2. Update globals.css component layer if the token changes a class
# 3. Update docs/DESIGN_SYSTEM.md
# 4. Run `bun run build` to verify the production CSS

# Refresh the production CSS bundle
bun run build && grep -oE '\.(btn-|pill-|card-|state-)[a-z]+' .next/static/css/*.css | sort -u
```

---

## 12. Accessibility checklist (every new PR)

- [ ] Visible `:focus-visible` ring on every focusable element
- [ ] Status pills use `<StatusPill>` (icon + colour + `aria-label`)
- [ ] No colour-only state communication
- [ ] Tab order matches reading order
- [ ] Form inputs have `<label>` (not placeholder-only)
- [ ] All images / SVGs have `alt` / `aria-label` / `aria-hidden`
- [ ] Lighthouse a11y score ≥ 95 on the public landing and verifier

---

## 13. Anti-patterns (forbidden)

- Dark mode (out of scope for the institutional brief)
- Gradients, glow, neon, glassmorphism, backdrop-blur on chrome
- Custom `<button>` styles (use `Button.tsx`)
- Custom status colours (use `StatusPill.tsx`)
- Emoji in user-facing copy
- Animated number counters
- Floating action buttons / bottom-sheets / drawer UI
- `as never` casts on `Link href` except for routes that legitimately
  don't exist yet — comment-flagged at the call site
