#!/usr/bin/env bash
#
# Pack F — production hardening probe.
#
# Asserts the security-headers contract on the deployed LandGuard
# backend. Returns 0 if every header is present with the expected
# value; returns 1 (and prints the diff) otherwise.
#
# USAGE
#   bash scripts/probe_security_headers.sh
#   BACKEND=https://landguard-backend-x.cranecloud.io bash scripts/probe_security_headers.sh

set -uo pipefail

BACKEND="${BACKEND:-https://landguard-backend-d1e66f33.renu-01.cranecloud.io}"
PROBE_PATHS=(
  "/healthz"
  "/readyz"
  "/api/v1/verify/sample-qr-payload"
)

# (header, expected substring). For headers with multi-token values we
# match a substring instead of pinning the whole string.
declare -A EXPECT=(
  ["Strict-Transport-Security"]="max-age=31536000"
  ["X-Content-Type-Options"]="nosniff"
  ["X-Frame-Options"]="DENY"
  ["Referrer-Policy"]="strict-origin-when-cross-origin"
  ["Cross-Origin-Opener-Policy"]="same-origin"
  ["Permissions-Policy"]="camera=(self)"
)
FORBIDDEN_SERVER="uvicorn"
EXPECT_SERVER="landguard"

FAIL=0
PASS=0

probe_path() {
  local path="$1"
  local resp_headers
  resp_headers=$(curl -sI --max-time 15 "${BACKEND}${path}" | tr -d '\r')
  echo "→ ${BACKEND}${path}"
  for header in "${!EXPECT[@]}"; do
    expected="${EXPECT[$header]}"
    actual=$(printf '%s\n' "$resp_headers" | grep -i "^${header}:" | head -1 | sed "s/^[^:]*: *//")
    if printf '%s' "$actual" | grep -q -F "$expected"; then
      printf "  %s %-40s ok\n" PASS "$header"
      PASS=$((PASS+1))
    else
      printf "  %s %-40s expected~%q  got=%q\n" FAIL "$header" "$expected" "$actual"
      FAIL=$((FAIL+1))
    fi
  done
  # Server header — must be "landguard", must NOT be "uvicorn".
  srv=$(printf '%s\n' "$resp_headers" | grep -i '^server:' | head -1 | sed 's/^[^:]*: *//')
  if [ "$srv" = "$EXPECT_SERVER" ]; then
    printf "  %s %-40s ok\n" PASS "Server=$EXPECT_SERVER"; PASS=$((PASS+1))
  else
    printf "  %s %-40s expected=%q  got=%q\n" FAIL "Server" "$EXPECT_SERVER" "$srv"; FAIL=$((FAIL+1))
  fi
  if printf '%s' "$srv" | grep -qi "$FORBIDDEN_SERVER"; then
    printf "  %s %-40s leaked %q\n" FAIL "Server (no-leak)" "$FORBIDDEN_SERVER"; FAIL=$((FAIL+1))
  fi
  echo
}

for path in "${PROBE_PATHS[@]}"; do
  probe_path "$path"
done

# /readyz enrichment — confirm new fraud_model + audit_chain fields exist.
echo "→ ${BACKEND}/readyz body shape"
body=$(curl -s --max-time 15 "${BACKEND}/readyz")
for field in '"fraud_model"' '"audit_chain"'; do
  if printf '%s' "$body" | grep -q "$field"; then
    printf "  %s readyz contains %s\n" PASS "$field"; PASS=$((PASS+1))
  else
    printf "  %s readyz missing %s\n" FAIL "$field"; FAIL=$((FAIL+1))
  fi
done
echo

echo "============================================"
echo "PASS: ${PASS}    FAIL: ${FAIL}"
echo "============================================"
exit $FAIL
