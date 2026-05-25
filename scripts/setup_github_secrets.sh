#!/usr/bin/env bash
#
# Interactive setup of LandGuard's GitHub Actions secrets.
#
# Mirrors the secret set proven in mpairwe7/OptiscanAI:
#
#   Repository-level (visible to any workflow on this repo):
#     DOCKERHUB_USERNAME, DOCKERHUB_TOKEN
#
#   production environment (deploy-cranecloud.yml only):
#     CRANE_CLOUD_EMAIL, CRANE_CLOUD_PASSWORD
#     CRANE_CLOUD_BACKEND_APP_ID, CRANE_CLOUD_FRONTEND_APP_ID
#     CRANE_CLOUD_BACKEND_URL, CRANE_CLOUD_FRONTEND_URL
#
# Each prompt uses `gh secret set NAME --body -` reading the value via
# `read -s` (no echo). The value is piped to gh via stdin so it never
# appears in process argv, never lands in shell history, and never
# enters this script's stdout. GitHub stores it encrypted-at-rest from
# then on (write-only after that).
#
# Usage:
#   bash scripts/setup_github_secrets.sh           # skip secrets that are already set
#   bash scripts/setup_github_secrets.sh --rotate  # overwrite even when already set

set -euo pipefail

REPO="mpairwe7/LandGuardUganda"
ENV_NAME="production"
ROTATE="${1:-}"

# Known non-secret defaults sourced from mpairwe7/MLOPS_V1/docs/22-crane-cloud-deployment.md
# §"Docker Hub Credentials" and §"Crane Cloud Platform Reference". The user
# can press Enter to accept them rather than retype.
DEFAULT_DOCKERHUB_USERNAME="landwind"
DEFAULT_CRANE_CLOUD_EMAIL="mpairwelauben75@gmail.com"

# Auto-source non-secret values from the bootstrap script's output file
# (scripts/bootstrap_cranecloud.sh writes UUIDs + URLs there). Then the
# user only needs to type the actual secrets (passwords/tokens).
BOOTSTRAP_SUMMARY="${LANDGUARD_BOOTSTRAP_SUMMARY:-/tmp/landguard-cranecloud-bootstrap.env}"
if [ -f "$BOOTSTRAP_SUMMARY" ]; then
  echo "→ Found bootstrap summary at $BOOTSTRAP_SUMMARY — sourcing non-secret values."
  # shellcheck disable=SC1090
  source "$BOOTSTRAP_SUMMARY"
fi

GH_BIN="$(command -v gh 2>/dev/null || echo /home/developer/bin/gh)"
if ! "$GH_BIN" --version >/dev/null 2>&1; then
  echo "✗ GitHub CLI not found. Install: https://cli.github.com/manual/installation"
  exit 1
fi

if ! "$GH_BIN" auth status -h github.com 2>&1 | grep -q "Logged in to github.com"; then
  echo "✗ gh CLI is not authenticated. Run: gh auth login"
  exit 1
fi

prompt_and_set() {
  local name="$1"
  local hint="$2"
  local scope="$3"          # "repo" or "env"
  local default="${4:-}"    # optional default value (non-secret values only)
  local secret="${5:-true}" # "true" → no echo; "false" → echoed (usernames, UUIDs)
  local existing
  local cmd

  if [ "$scope" = "env" ]; then
    cmd=("$GH_BIN" secret set "$name" --repo "$REPO" --env "$ENV_NAME")
    existing=$("$GH_BIN" secret list --repo "$REPO" --env "$ENV_NAME" 2>/dev/null | awk -v n="$name" '$1 == n {print $1; exit}')
  else
    cmd=("$GH_BIN" secret set "$name" --repo "$REPO")
    existing=$("$GH_BIN" secret list --repo "$REPO" 2>/dev/null | awk -v n="$name" '$1 == n {print $1; exit}')
  fi

  if [ -n "$existing" ] && [ "$ROTATE" != "--rotate" ]; then
    echo "  ✓ $name (already set; pass --rotate to overwrite)"
    return 0
  fi

  echo
  echo "→ $name"
  echo "  ($hint)"
  if [ "$secret" = "true" ]; then
    if [ -n "$default" ]; then
      echo -n "  Value [Enter for default] (no echo): "
    else
      echo -n "  Value (no echo): "
    fi
    IFS= read -rs value
    echo
  else
    if [ -n "$default" ]; then
      echo -n "  Value [Enter for default: $default]: "
    else
      echo -n "  Value: "
    fi
    IFS= read -r value
  fi
  if [ -z "${value:-}" ]; then
    if [ -n "$default" ]; then
      value="$default"
      echo "  · using default"
    else
      echo "  · skipped (no value entered)"
      return 0
    fi
  fi
  printf '%s' "$value" | "${cmd[@]}" --body -
  unset value
}

echo "=== LandGuard GitHub secrets setup ==="
echo "  repo:        $REPO"
echo "  environment: $ENV_NAME"
echo "  rotate:      $([ "$ROTATE" = "--rotate" ] && echo "yes — overwriting" || echo "no — skipping already-set")"
echo
echo "Press Enter at any prompt to skip that secret. Values are read"
echo "without echo and piped directly to gh secret set via stdin —"
echo "they never enter argv, history, or stdout."

echo
echo "─── Repository-level secrets (visible to all workflows) ───"
prompt_and_set DOCKERHUB_USERNAME \
  "Docker Hub username (mpairwe7 uses 'landwind' across MLOps projects per MLOPS_V1 docs)" \
  repo "${DOCKERHUB_USERNAME:-$DEFAULT_DOCKERHUB_USERNAME}" false
prompt_and_set DOCKERHUB_TOKEN \
  "Docker Hub PAT (Read/Write/Delete) — hub.docker.com → Account Settings → Personal access tokens" \
  repo

echo
echo "─── production environment secrets (used by deploy-cranecloud.yml) ───"
prompt_and_set CRANE_CLOUD_EMAIL \
  "Crane Cloud account email — MUST be lowercase per api.cranecloud.io behaviour" \
  env "${CRANE_CLOUD_EMAIL:-$DEFAULT_CRANE_CLOUD_EMAIL}" false
prompt_and_set CRANE_CLOUD_PASSWORD \
  "Crane Cloud password — POSTed in JSON body to api.cranecloud.io/users/login" \
  env
prompt_and_set CRANE_CLOUD_BACKEND_APP_ID \
  "Crane Cloud app UUID for FastAPI backend (auto-filled if you ran scripts/bootstrap_cranecloud.sh)" \
  env "${CRANE_CLOUD_BACKEND_APP_ID:-}" false
prompt_and_set CRANE_CLOUD_FRONTEND_APP_ID \
  "Crane Cloud app UUID for Next.js frontend" \
  env "${CRANE_CLOUD_FRONTEND_APP_ID:-}" false
prompt_and_set CRANE_CLOUD_BACKEND_URL \
  "Backend public URL (e.g. https://landguard-backend-<id>.renu-01.cranecloud.io) for /healthz polling" \
  env "${CRANE_CLOUD_BACKEND_URL:-}" false
prompt_and_set CRANE_CLOUD_FRONTEND_URL \
  "Frontend public URL for /api/health polling" \
  env "${CRANE_CLOUD_FRONTEND_URL:-}" false

echo
echo "─── Verify ───"
echo "Repository secrets:"
"$GH_BIN" secret list --repo "$REPO" | sed 's/^/  /'
echo
echo "production environment secrets:"
"$GH_BIN" secret list --repo "$REPO" --env "$ENV_NAME" | sed 's/^/  /'

echo
echo "✓ Setup complete. Next:"
echo "    git tag v0.1.0-showcase"
echo "    git push origin main v0.1.0-showcase"
echo "  build-push.yml → deploy-cranecloud.yml will run automatically."
