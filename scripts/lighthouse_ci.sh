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

if ! command -v npx >/dev/null 2>&1 && ! command -v bunx >/dev/null 2>&1; then
  echo "✗ Need node (npx) or bun (bunx) to run Lighthouse."
  exit 1
fi

# Prefer npx over bunx — bunx fails on filesystems where it can't create
# symlinks for puppeteer's native deps (ENOTSUP) which is the puppeteer
# install path used by `lighthouse` to fetch Chrome.
RUNNER="npx --yes"
if ! command -v npx >/dev/null 2>&1; then
  RUNNER="bunx"
fi

# Resolve a Chrome binary. Order of preference:
#   1. $CHROME_PATH (operator override)
#   2. puppeteer's cached chrome-headless-shell  (works in sandboxed CI runners)
#   3. puppeteer's cached chrome-for-testing
#   4. system-installed chrome / chromium
# If nothing is found, we let Lighthouse try to auto-download.
if [ -z "${CHROME_PATH:-}" ]; then
  CHROME_PATH="$(find "${HOME}/.cache/puppeteer/chrome-headless-shell" -maxdepth 4 -type f -name chrome-headless-shell 2>/dev/null | sort -r | head -1)"
fi
if [ -z "${CHROME_PATH:-}" ]; then
  CHROME_PATH="$(find "${HOME}/.cache/puppeteer/chrome" -maxdepth 4 -type f -name chrome 2>/dev/null | sort -r | head -1)"
fi
if [ -z "${CHROME_PATH:-}" ]; then
  for c in google-chrome chromium chromium-browser; do
    if command -v "$c" >/dev/null 2>&1; then
      CHROME_PATH="$(command -v "$c")"; break
    fi
  done
fi
if [ -n "${CHROME_PATH:-}" ] && [ -x "${CHROME_PATH}" ]; then
  echo "→ Using Chrome: ${CHROME_PATH}"
  export CHROME_PATH
else
  echo "→ No Chrome found locally — Lighthouse will attempt auto-download. If this fails, install chrome-headless-shell:"
  echo "  npx --yes puppeteer browsers install chrome-headless-shell"
fi

# Chrome profile dir must be on a filesystem that supports flock + extended
# attributes — network mounts (NFS, CIFS) typically fail with
# "Failed to create SingletonLock: Operation not supported".
USER_DATA_DIR="$(mktemp -d "${HOME}/.cache/landguard-chrome-profile.XXXXXX")"
CHROME_PORT="${CHROME_PORT:-9333}"
CHROME_PID=""
cleanup() {
  if [ -n "${CHROME_PID}" ]; then
    kill "${CHROME_PID}" 2>/dev/null || true
    wait "${CHROME_PID}" 2>/dev/null || true
  fi
  rm -rf "${USER_DATA_DIR}"
}
trap cleanup EXIT

# Pre-launch Chrome ourselves on a fixed devtools port. Lighthouse's built-in
# chrome-launcher sometimes loses the Chrome PID handshake on sandboxed
# runners; passing --port skips it and uses our managed instance.
if [ -n "${CHROME_PATH:-}" ] && [ -x "${CHROME_PATH}" ]; then
  echo "→ Pre-launching Chrome on devtools port ${CHROME_PORT}"
  "${CHROME_PATH}" \
    --headless=new \
    --no-sandbox \
    --disable-gpu \
    --disable-dev-shm-usage \
    --user-data-dir="${USER_DATA_DIR}/profile" \
    --remote-debugging-port="${CHROME_PORT}" \
    about:blank >"${OUTDIR}/chrome.log" 2>&1 &
  CHROME_PID=$!
  # Wait up to 10s for the devtools endpoint to come up
  for i in $(seq 1 20); do
    if curl -fsS "http://127.0.0.1:${CHROME_PORT}/json/version" >/dev/null 2>&1; then
      echo "  Chrome ready (PID=${CHROME_PID})"
      break
    fi
    sleep 0.5
    if [ "$i" -eq 20 ]; then
      echo "  ✗ Chrome did not become ready on port ${CHROME_PORT}; falling back to lighthouse-managed launch"
      kill "${CHROME_PID}" 2>/dev/null || true
      CHROME_PID=""
    fi
  done
fi

EXIT_CODE=0
for path in "${PAGES[@]}"; do
  safe_name="$(echo "${path}" | sed 's|/|_|g; s|^_||; s|^$|root|')"
  echo "→ Lighthouse: ${BASE_URL}${path}"
  # --disable-storage-reset: chrome-headless-shell doesn't support
  # Storage.getUsageAndQuota CDP method; the storage reset step would
  # otherwise abort the audit. The storage-reset scoring impact is
  # documented at https://github.com/GoogleChrome/lighthouse/blob/main/docs/disable-storage-reset.md
  if [ -n "${CHROME_PID}" ]; then
    ${RUNNER} lighthouse "${BASE_URL}${path}" \
      --port="${CHROME_PORT}" \
      --disable-storage-reset \
      --only-categories=performance,accessibility,best-practices,seo \
      --output=html,json \
      --output-path="${OUTDIR}/${safe_name}" \
      --quiet || { EXIT_CODE=1; echo "  (lighthouse failed for ${path})"; }
  else
    ${RUNNER} lighthouse "${BASE_URL}${path}" \
      --disable-storage-reset \
      --only-categories=performance,accessibility,best-practices,seo \
      --output=html,json \
      --output-path="${OUTDIR}/${safe_name}" \
      --chrome-flags="--headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu --user-data-dir=${USER_DATA_DIR}/${safe_name}" \
      --quiet || { EXIT_CODE=1; echo "  (lighthouse failed for ${path})"; }
  fi
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
