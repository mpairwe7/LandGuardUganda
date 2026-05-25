#!/usr/bin/env bash
#
# Reproducible scalability benchmark for the LandGuard backend.
#
# Default profile:
#   - 60-second sustained burst against the public verifier
#   - 250 requests/second target
#   - Targets evidence the docs/SLA_TARGETS.md §2 envelope
#
# This script intentionally uses **no third-party SaaS** — it spawns an
# async httpx client in the backend's own venv so the benchmark is
# reproducible on any contributor's machine without sign-up.
#
# Output: evidence/load/<timestamp>/summary.json + raw.csv

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${BASE_URL:-http://localhost:8000}"
DURATION="${DURATION:-60}"      # seconds
TARGET_RPS="${TARGET_RPS:-250}"
TITLE_NO="${TITLE_NO:-UG-MIT-T00007/2026}"
TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
OUTDIR="${ROOT}/evidence/load/${TIMESTAMP}"
mkdir -p "${OUTDIR}"

# Liveness check
if ! curl -fsS "${BASE_URL}/healthz" >/dev/null; then
  echo "✗ Backend at ${BASE_URL} is not reachable. Bring it up first:"
  echo "    docker compose --profile default up -d --build"
  exit 1
fi

cd "${ROOT}/backend"
exec uv run python scripts/load_test.py \
  --base-url "${BASE_URL}" \
  --duration "${DURATION}" \
  --target-rps "${TARGET_RPS}" \
  --title-no "${TITLE_NO}" \
  --out-summary "${OUTDIR}/summary.json" \
  --out-csv "${OUTDIR}/raw.csv"
