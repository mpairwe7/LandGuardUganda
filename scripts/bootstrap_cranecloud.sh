#!/usr/bin/env bash
#
# One-shot bootstrap of LandGuard's Crane Cloud deployment.
#
# Adapted from mpairwe7/MLOPS_V1/docs/22-crane-cloud-deployment.md
# "Option B: Crane Cloud API" — direct curl to api.cranecloud.io with no
# CLI dependency. Same authenticated user, same RENU cluster.
#
# What it does:
#   1. Prompts for Crane Cloud password (read -s, no echo).
#   2. POST /users/login → JWT access_token + user_id.
#   3. GET /projects → finds existing "LandGuard" project or POSTs a new
#      one on the RENU cluster.
#   4. GET /projects/{id}/apps → for each of backend / frontend, finds the
#      existing app by name or POSTs a new one with the LandGuard env vars.
#   5. Prints APP_IDs and URLs (non-secret UUIDs / URLs).
#
# Output is piped via tee into setup_github_secrets.sh-friendly env-var
# exports the operator can copy into the script's prompts.
#
# Why API not CLI: the cranecloud Python CLI requires a keyring backend
# (D-Bus SecretService) that's absent on headless boxes. Direct curl
# works anywhere with bash + curl + python3.
#
# Usage:
#   bash scripts/bootstrap_cranecloud.sh
#
# After completion, copy the printed app IDs and URLs into your password
# manager or paste into the prompts when running scripts/setup_github_secrets.sh.

set -euo pipefail

CRANE_API="${CRANE_CLOUD_API:-https://api.cranecloud.io}"
# Per MLOPS_V1 docs §"Crane Cloud Platform Reference": prefer RENU over
# AHUMAIN until AHUMAIN's pod-scheduling issue resolves.
RENU_CLUSTER_ID="${RENU_CLUSTER_ID:-9e81a70e-8460-4e5d-b0a8-17abcac30f68}"
PROJECT_NAME="${LANDGUARD_PROJECT_NAME:-LandGuardUganda}"
BACKEND_APP_NAME="${BACKEND_APP_NAME:-landguard-backend}"
FRONTEND_APP_NAME="${FRONTEND_APP_NAME:-landguard-frontend}"
# Default Docker Hub namespace — mpairwe7's pattern across MLOPs projects.
DOCKERHUB_USERNAME="${DOCKERHUB_USERNAME:-landwind}"
# Default email from MLOPS_V1 docs §"Crane Cloud Platform Reference"
# ("must be lowercase").
DEFAULT_EMAIL="${CRANE_CLOUD_EMAIL:-mpairwelauben75@gmail.com}"

if ! command -v curl >/dev/null 2>&1; then
  echo "✗ curl is required" >&2; exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "✗ python3 is required for JSON parsing" >&2; exit 1
fi

# JSON-safe extractor — never echoes the input to stderr.
jget() {
  # $1 = json blob (string), $2 = dotted path like "data.access_token"
  python3 -c "
import json, sys
d = json.loads(sys.argv[1])
for p in sys.argv[2].split('.'):
    if isinstance(d, list):
        d = d[int(p)] if p.isdigit() else next((x for x in d if x.get('name')==p), None)
    else:
        d = d.get(p) if isinstance(d, dict) else None
    if d is None:
        sys.exit(1)
print(d if isinstance(d, str) else json.dumps(d))
" "$1" "$2" 2>/dev/null
}

echo "=== LandGuard Crane Cloud bootstrap ==="
echo "  API:        $CRANE_API"
echo "  Project:    $PROJECT_NAME (on RENU cluster)"
echo "  Apps:       $BACKEND_APP_NAME, $FRONTEND_APP_NAME"
echo "  Docker Hub: $DOCKERHUB_USERNAME/landguard-uganda-{backend,frontend}"
echo

# ── 1. Credentials ───────────────────────────────────────────────────────
echo -n "Crane Cloud email [$DEFAULT_EMAIL]: "
read CRANE_EMAIL
CRANE_EMAIL="${CRANE_EMAIL:-$DEFAULT_EMAIL}"
# Per MLOPS_V1 docs: email is case-sensitive — must be lowercase for login.
CRANE_EMAIL="$(echo "$CRANE_EMAIL" | tr '[:upper:]' '[:lower:]')"

echo -n "Crane Cloud password (no echo): "
IFS= read -rs CRANE_PASSWORD
echo
if [ -z "${CRANE_PASSWORD:-}" ]; then
  echo "✗ Password is empty — aborting." >&2; exit 1
fi

# ── 2. Login ─────────────────────────────────────────────────────────────
echo "→ Logging in…"
LOGIN_RESP=$(curl -sf -X POST "$CRANE_API/users/login" \
  -H "Content-Type: application/json" \
  --data-binary @<(python3 -c "
import json, sys
print(json.dumps({'email': sys.argv[1], 'password': sys.argv[2]}))
" "$CRANE_EMAIL" "$CRANE_PASSWORD")) || { echo "✗ Login failed (HTTP error)." >&2; exit 1; }
unset CRANE_PASSWORD                 # immediately discard

TOKEN=$(jget "$LOGIN_RESP" "data.access_token") || { echo "✗ Login returned no access_token." >&2; exit 1; }
USER_ID=$(jget "$LOGIN_RESP" "data.id") || { echo "✗ Login returned no user id." >&2; exit 1; }
echo "  ✓ authenticated as user $USER_ID"

# ── 3. Find or create project on RENU ────────────────────────────────────
echo "→ Looking for existing project '$PROJECT_NAME'…"
PROJECTS_RESP=$(curl -sf -H "Authorization: Bearer $TOKEN" "$CRANE_API/projects")
PROJECT_ID=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
target = sys.argv[1]
projects = data.get('data', {}).get('pagination', {}).get('projects', []) \
        or data.get('data', {}).get('projects', []) \
        or data.get('data', []) if isinstance(data.get('data'), list) else []
for p in projects:
    if p.get('name') == target:
        print(p['id']); sys.exit(0)
" "$PROJECT_NAME" <<<"$PROJECTS_RESP") || true

if [ -z "${PROJECT_ID:-}" ]; then
  echo "  Project not found — creating on RENU cluster $RENU_CLUSTER_ID"
  CREATE_PROJECT_RESP=$(curl -sf -X POST "$CRANE_API/projects" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    --data-binary @<(python3 -c "
import json, sys
print(json.dumps({'name': sys.argv[1], 'cluster_id': sys.argv[2], 'owner_id': sys.argv[3], 'description': 'LandGuard Uganda — blockchain-enhanced land administration. Bootstrap script: scripts/bootstrap_cranecloud.sh'}))
" "$PROJECT_NAME" "$RENU_CLUSTER_ID" "$USER_ID"))
  PROJECT_ID=$(jget "$CREATE_PROJECT_RESP" "data.project.id") \
    || PROJECT_ID=$(jget "$CREATE_PROJECT_RESP" "data.id")
  if [ -z "${PROJECT_ID:-}" ]; then
    echo "✗ Project creation returned no id." >&2
    echo "  Response: $CREATE_PROJECT_RESP" >&2
    exit 1
  fi
  echo "  ✓ project created: $PROJECT_ID"
else
  echo "  ✓ project exists: $PROJECT_ID"
fi

# ── 4. Find or create the two apps ───────────────────────────────────────
existing_apps_resp=$(curl -sf -H "Authorization: Bearer $TOKEN" \
  "$CRANE_API/projects/$PROJECT_ID/apps")

create_or_find_app() {
  local app_name="$1"
  local image="$2"
  local port="$3"
  local env_json="$4"

  echo "→ Looking for app '$app_name'…"
  local existing_id
  existing_id=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
target = sys.argv[1]
apps = data.get('data', {}).get('apps', []) \
    or data.get('data', {}).get('pagination', {}).get('apps', []) \
    or (data.get('data') if isinstance(data.get('data'), list) else [])
for a in apps:
    if a.get('name') == target:
        print(a.get('id', ''), a.get('url', ''))
        break
" "$app_name" <<<"$existing_apps_resp") || true

  if [ -n "${existing_id:-}" ]; then
    echo "  ✓ already exists: $existing_id"
    echo "$existing_id"
    return 0
  fi

  echo "  Creating app $app_name on RENU…"
  local body
  body=$(python3 -c "
import json, sys
print(json.dumps({
    'name': sys.argv[1],
    'image': sys.argv[2],
    'port': int(sys.argv[3]),
    'replicas': 1,
    'env_vars': json.loads(sys.argv[4]),
    'project_id': sys.argv[5],
    'private_image': False,
}))
" "$app_name" "$image" "$port" "$env_json" "$PROJECT_ID")

  local resp
  resp=$(curl -sf -X POST "$CRANE_API/projects/$PROJECT_ID/apps" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    --data-binary "$body") || {
      echo "✗ App creation failed for $app_name" >&2; return 1; }
  local new_id new_url
  new_id=$(jget "$resp" "data.app.id") || new_id=$(jget "$resp" "data.id")
  new_url=$(jget "$resp" "data.app.url") || new_url=$(jget "$resp" "data.url")
  echo "  ✓ created: $new_id"
  echo "    URL: $new_url"
  echo "$new_id $new_url"
}

# Backend env vars (LandGuard-specific). All scalars; no spaces in keys/values
# per MLOPS_V1 docs §Troubleshooting "Environment variable keys have spaces".
# Production-grade values: APP_ENV=production, DEMO_MODE=false (Settings.assert_prod_safety
# will refuse to start otherwise — see backend/app/config.py).
BACKEND_ENV=$(python3 -c "
import json
print(json.dumps({
    'APP_ENV': 'production',
    'APP_NAME': 'landguard-backend',
    'LOG_LEVEL': 'INFO',
    'DEMO_MODE': 'false',
    'DB_BACKEND': 'sqlite',
    'SQLITE_PATH': '/app/data_store/landguard.db',
    'REDIS_URL': 'memory://',
    'AUTH_MODE': 'dev',
    'JWT_HS256_SECRET': 'rotate-via-crane-cloud-dashboard-immediately-32chars',
    'JWT_ISSUER': 'landguard.ug',
    'JWT_AUDIENCE': 'landguard-backend',
    'BLOCKCHAIN_PROVIDER': 'mock',
    'NIRA_PROVIDER': 'mock',
    'PII_ENCRYPTION_KEY': 'cm90YXRlLXZpYS1jcmFuZS1jbG91ZC1kYXNoLTMyYnl0ZXMtbm93PT0=',
    'PROMETHEUS_METRICS_ENABLED': 'true',
})
")

FRONTEND_ENV=$(python3 -c "
import json
print(json.dumps({
    'NEXT_PUBLIC_APP_NAME': 'LandGuard Uganda',
    'NEXT_PUBLIC_DEMO_MODE': 'false',
    'NEXT_PUBLIC_DEFAULT_DISTRICT_ID': '3',
})
")

echo
BACKEND_INFO=$(create_or_find_app "$BACKEND_APP_NAME" \
  "$DOCKERHUB_USERNAME/landguard-uganda-backend:latest" 8000 "$BACKEND_ENV")
BACKEND_APP_ID=$(echo "$BACKEND_INFO" | awk 'END{print $1}')
BACKEND_URL=$(echo "$BACKEND_INFO" | awk 'END{print $2}')

echo
FRONTEND_INFO=$(create_or_find_app "$FRONTEND_APP_NAME" \
  "$DOCKERHUB_USERNAME/landguard-uganda-frontend:latest" 3000 "$FRONTEND_ENV")
FRONTEND_APP_ID=$(echo "$FRONTEND_INFO" | awk 'END{print $1}')
FRONTEND_URL=$(echo "$FRONTEND_INFO" | awk 'END{print $2}')

# ── 5. Output (non-secret UUIDs + URLs) ───────────────────────────────────
echo
echo "============================================================"
echo "  LandGuard Crane Cloud bootstrap complete"
echo "============================================================"
echo
echo "  PROJECT_ID              = $PROJECT_ID"
echo "  CRANE_CLOUD_BACKEND_APP_ID  = $BACKEND_APP_ID"
echo "  CRANE_CLOUD_FRONTEND_APP_ID = $FRONTEND_APP_ID"
echo "  CRANE_CLOUD_BACKEND_URL     = $BACKEND_URL"
echo "  CRANE_CLOUD_FRONTEND_URL    = $FRONTEND_URL"
echo
echo "  Next:"
echo "    1. Rotate JWT_HS256_SECRET and PII_ENCRYPTION_KEY via the"
echo "       Crane Cloud dashboard — the bootstrap defaults are"
echo "       intentionally weak so production-safety assertion catches them."
echo "    2. Run: bash scripts/setup_github_secrets.sh"
echo "       (it will pre-populate the values above; you only need to"
echo "       enter DOCKERHUB_TOKEN, CRANE_CLOUD_EMAIL, CRANE_CLOUD_PASSWORD)."
echo "    3. Tag and push:"
echo "         git tag v0.1.0-showcase"
echo "         git push origin main v0.1.0-showcase"
echo

# Persist a non-secret summary to a local file the next script can read.
SUMMARY_FILE="${LANDGUARD_BOOTSTRAP_SUMMARY:-/tmp/landguard-cranecloud-bootstrap.env}"
{
  echo "# Auto-generated by scripts/bootstrap_cranecloud.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# Non-secret values only. Source from setup_github_secrets.sh or paste into prompts."
  echo "DOCKERHUB_USERNAME=$DOCKERHUB_USERNAME"
  echo "CRANE_CLOUD_EMAIL=$CRANE_EMAIL"
  echo "CRANE_CLOUD_BACKEND_APP_ID=$BACKEND_APP_ID"
  echo "CRANE_CLOUD_FRONTEND_APP_ID=$FRONTEND_APP_ID"
  echo "CRANE_CLOUD_BACKEND_URL=$BACKEND_URL"
  echo "CRANE_CLOUD_FRONTEND_URL=$FRONTEND_URL"
  echo "# These are NOT in this file — set them via setup_github_secrets.sh:"
  echo "#   DOCKERHUB_TOKEN (hub.docker.com PAT)"
  echo "#   CRANE_CLOUD_PASSWORD"
} > "$SUMMARY_FILE"
chmod 600 "$SUMMARY_FILE"
echo "  Non-secret summary written to: $SUMMARY_FILE"
