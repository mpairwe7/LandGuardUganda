#!/usr/bin/env bash
#
# Generate CycloneDX SBOMs for the backend, frontend, and smart contracts.
#
# Output: evidence/sbom/<component>-cyclonedx.json + matching .sha256
#
# Backend  → cyclonedx-py reads the uv-locked pyproject
# Frontend → @cyclonedx/cyclonedx-bom reads package.json + bun.lock
# Contracts→ records git-pinned submodule SHAs (OpenZeppelin + forge-std)
#
# This script is INTENTIONALLY idempotent — re-running it overwrites
# evidence/sbom/* so the panel sees the freshest dep graph.
#
# Standards: CycloneDX 1.5 JSON, signed via the project lead's GitHub
# commit signature (no external key infrastructure required at the
# prototype stage).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTDIR="${ROOT}/evidence/sbom"
mkdir -p "${OUTDIR}"

echo "→ Backend SBOM (CycloneDX 1.5)…"
if command -v uvx >/dev/null 2>&1; then
  uvx --from cyclonedx-bom cyclonedx-py environment "${ROOT}/backend/.venv" \
    --output-format json \
    --output-file "${OUTDIR}/backend-cyclonedx.json"
elif command -v pipx >/dev/null 2>&1; then
  pipx run --spec cyclonedx-bom cyclonedx-py requirements "${ROOT}/backend/pyproject.toml" \
    --output-format json \
    --output-file "${OUTDIR}/backend-cyclonedx.json"
else
  echo "  (skipped — install uv or pipx to enable cyclonedx-py)"
fi

echo "→ Frontend SBOM (CycloneDX 1.5)…"
# We use a two-strategy approach because the frontend uses bun.lock and
# React 19 — npm's strict peer-dep checker can refuse to enumerate the
# graph even when the project builds cleanly.
#
# Strategy A: @cyclonedx/cyclonedx-npm with --ignore-npm-errors flag.
# Strategy B (fallback): pure-Python generator that reads package.json
#            + bun.lock directly. Always works.
FRONTEND_SBOM="${OUTDIR}/frontend-cyclonedx.json"
FRONTEND_OK=0
if [ -d "${ROOT}/frontend/node_modules" ] && command -v npx >/dev/null 2>&1; then
  if ( cd "${ROOT}/frontend" && \
       npx --yes @cyclonedx/cyclonedx-npm \
         --output-format JSON \
         --output-file "${FRONTEND_SBOM}" \
         --spec-version 1.5 \
         --ignore-npm-errors 2>&1 | tail -3 ) && [ -f "${FRONTEND_SBOM}" ]; then
    FRONTEND_OK=1
  fi
fi
if [ "${FRONTEND_OK}" -ne 1 ]; then
  echo "  (cyclonedx-npm not available or failed; using built-in generator)"
  python3 "${ROOT}/scripts/_sbom_frontend_fallback.py" \
    --package-json "${ROOT}/frontend/package.json" \
    --lockfile "${ROOT}/frontend/bun.lock" \
    --out "${FRONTEND_SBOM}"
fi

echo "→ Contracts SBOM (git submodule digest)…"
{
  echo "{"
  echo "  \"bomFormat\": \"CycloneDX\","
  echo "  \"specVersion\": \"1.5\","
  echo "  \"version\": 1,"
  echo "  \"metadata\": {"
  echo "    \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\","
  echo "    \"component\": {"
  echo "      \"type\": \"application\","
  echo "      \"name\": \"landguard-contracts\","
  echo "      \"version\": \"0.1.0\""
  echo "    }"
  echo "  },"
  echo "  \"components\": ["
  ( cd "${ROOT}" && git submodule status --recursive | \
    awk '{print "    {\"type\":\"library\",\"name\":\""$2"\",\"version\":\""$1"\"}"}' | \
    paste -sd "," - )
  echo "  ]"
  echo "}"
} > "${OUTDIR}/contracts-cyclonedx.json"

echo "→ Content-addressing every SBOM…"
for f in "${OUTDIR}"/*.json; do
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${f}" > "${f}.sha256"
  else
    shasum -a 256 "${f}" > "${f}.sha256"
  fi
done

cat <<EOF

SBOMs generated:
  $(ls -1 "${OUTDIR}/" | sed 's|^|  |')

The submission-day SBOM bundle ships in evidence/sbom/ alongside the
SHA-256 of each file. Panellists can independently verify the dep
tree by running this script on a clean checkout.
EOF
