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
  local scope="$3"   # "repo" or "env"
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
  echo -n "  Value (will not be echoed): "
  IFS= read -rs value
  echo
  if [ -z "${value:-}" ]; then
    echo "  · skipped (no value entered)"
    return 0
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
  "your Docker Hub username — e.g. 'landwind'" \
  repo
prompt_and_set DOCKERHUB_TOKEN \
  "Docker Hub PAT with Read/Write/Delete scope — generate at hub.docker.com → Account Settings → Personal access tokens" \
  repo

echo
echo "─── production environment secrets (used by deploy-cranecloud.yml) ───"
prompt_and_set CRANE_CLOUD_EMAIL \
  "Crane Cloud account email" \
  env
prompt_and_set CRANE_CLOUD_PASSWORD \
  "Crane Cloud account password — POSTed in JSON body to api.cranecloud.io/users/login" \
  env
prompt_and_set CRANE_CLOUD_BACKEND_APP_ID \
  "UUID of the Crane Cloud app for the FastAPI backend (cranecloud apps list)" \
  env
prompt_and_set CRANE_CLOUD_FRONTEND_APP_ID \
  "UUID of the Crane Cloud app for the Next.js frontend (cranecloud apps list)" \
  env
prompt_and_set CRANE_CLOUD_BACKEND_URL \
  "Public URL of the backend app (e.g. https://landguard-backend.cranecloud.ug) — used for /healthz polling. Optional." \
  env
prompt_and_set CRANE_CLOUD_FRONTEND_URL \
  "Public URL of the frontend app (e.g. https://landguard.cranecloud.ug) — used for /api/health polling. Optional." \
  env

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
