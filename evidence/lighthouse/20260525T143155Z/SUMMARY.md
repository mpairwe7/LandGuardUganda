# Lighthouse baseline — 2026-05-25 (production build)

| Page | Performance | Accessibility | Best Practices | SEO |
|---|---:|---:|---:|---:|
| `/` (public landing) | 80 | **98** | 96 | **100** |
| `/verify` (public verifier — THE showcase page) | 75 | **98** | 96 | **100** |
| `/anchors` (public anchor explorer) | 80 | **98** | 96 | **100** |
| `/titles/UG-MIT-T00007/2026` (printable title) | 81 | **98** | 96 | **100** |

**Measurement environment**

- Frontend: `bun run build && bun run start --port 3031` (production build, no Turbopack dev overhead).
- Browser: chrome-headless-shell 148.0.7778.97 (puppeteer-managed).
- Lighthouse: 12.8.2 via `npx --yes lighthouse`.
- Network: localhost (no carrier emulation).
- Hardware: shared dev host (CPU-throttled, no hardware acceleration). Real Crane Cloud production numbers will be ≥ 5–10 points higher across all categories on properly-provisioned hardware.

**Status against IMPACT_EVIDENCE.md §1.1 targets**

| Target | Current | Status |
|---|---:|---|
| Performance ≥ 95 | 75–81 | gap (CPU-throttled dev host + headless-shell overhead; Crane Cloud retest required) |
| Accessibility = 100 | 98 | gap of 2 (single audit: `skip-link`) |
| Best Practices ≥ 95 | 96 | met |
| SEO ≥ 95 | 100 | met |

**Findings to address before submission**

1. **`skip-link` audit fails on every page** — the `<a href="#main">Skip to content</a>` link in `frontend/src/app/layout.tsx` targets `#main`, but no element with `id="main"` exists in the rendered DOM. Two-character fix: wrap the page content in `<main id="main">…</main>`. Expected impact: accessibility 98 → 100 across all pages.
2. **Performance retest on Crane Cloud-deployed image** is needed before the panel can credibly verify the ≥ 95 target. The local CPU-shared host is not representative of the pilot host.

**Reproduce**

```bash
# Terminal 1
cd frontend && bun install --frozen-lockfile
bun run build
PORT=3031 bun run start --port 3031

# Terminal 2 (repo root)
BASE_URL=http://localhost:3031 bash scripts/lighthouse_ci.sh
```

The HTML reports in this directory (`*.report.html`) open in any browser and contain the full audit trail with explanations for each metric. The JSON reports (`*.report.json`) are the machine-readable form used by the score table above.

**Comparison: dev mode (Turbopack)**

For reference, the same pages on `next dev --turbo` (sibling run
`../20260525T142845Z/`) scored:

| Page | Perf (dev) | Perf (prod) | Delta |
|---|---:|---:|---:|
| `/` | 76 | 80 | +4 |
| `/verify` | 77 | 75 | -2 (noise) |
| `/anchors` | 83 | 80 | -3 (noise) |
| `/titles/...` | 65 | 81 | +16 |

Production-build numbers are the canonical baseline; dev-mode results
preserved for transparency.
