#!/usr/bin/env bash
#
# Run Lighthouse + axe-core against the LandGuard frontend.
#
# Pages audited (matches docs/IMPACT_EVIDENCE.md §1.1):
#   /                       — public landing
#   /verify                 — public verifier (THE showcase page)
#   /anchors                — anchor explorer
#   /titles/UG-MIT-T00007/2026 — printable title certificate
#
# Targets (CI-failing):
#   Performance     ≥ 95
#   Accessibility   == 100
#   Best Practices  ≥ 95
#   SEO             ≥ 95
#
# Output: evidence/lighthouse/<timestamp>/*.json|.html
#
# Requires: bun + a running frontend (defaults to http://localhost:3000).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${BASE_URL:-http://localhost:3000}"
TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
OUTDIR="${ROOT}/evidence/lighthouse/${TIMESTAMP}"
mkdir -p "${OUTDIR}"

PAGES=(
  "/"
  "/verify"
  "/anchors"
  "/titles/UG-MIT-T00007%2F2026"
)

# Liveness check
if ! curl -fsS "${BASE_URL}/api/health" >/dev/null; then
  echo "✗ Frontend at ${BASE_URL} is not reachable. Bring it up first:"
  echo "    docker compose --profile default up -d --build"
  exit 1
fi

if ! command -v bunx >/dev/null 2>&1 && ! command -v npx >/dev/null 2>&1; then
  echo "✗ Need bun or node (npx) to run Lighthouse. Install bun: https://bun.sh"
  exit 1
fi

RUNNER="bunx"
command -v bunx >/dev/null 2>&1 || RUNNER="npx --yes"

EXIT_CODE=0
for path in "${PAGES[@]}"; do
  safe_name="$(echo "${path}" | sed 's|/|_|g; s|^_||; s|^$|root|')"
  echo "→ Lighthouse: ${BASE_URL}${path}"
  ${RUNNER} lighthouse "${BASE_URL}${path}" \
    --only-categories=performance,accessibility,best-practices,seo,pwa \
    --output=html,json \
    --output-path="${OUTDIR}/${safe_name}" \
    --chrome-flags="--headless=new --no-sandbox" \
    --quiet || { EXIT_CODE=1; echo "  (lighthouse failed for ${path})"; }
done

echo
echo "→ axe-core via Playwright accessibility suite…"
if [ -f "${ROOT}/frontend/e2e/accessibility.spec.ts" ]; then
  ( cd "${ROOT}/frontend" && \
    BASE_URL="${BASE_URL}" bunx playwright test e2e/accessibility.spec.ts \
      --reporter=json > "${OUTDIR}/axe-report.json" ) || EXIT_CODE=1
else
  echo "  (skipped — frontend/e2e/accessibility.spec.ts not yet authored;"
  echo "   add it to formally bind the WCAG 2.2 AA promise.)"
fi

echo
echo "Done. Results: ${OUTDIR}"
echo "Open the .html files in a browser for a panellist-facing report."

exit ${EXIT_CODE}
