#!/usr/bin/env bash

set -u -o pipefail

BASE_URL="${1:-http://localhost}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

pass_count=0
fail_count=0
warn_count=0

print_section() {
  printf '\n== %s ==\n' "$1"
}

pass() {
  pass_count=$((pass_count + 1))
  printf '[PASS] %s\n' "$1"
}

fail() {
  fail_count=$((fail_count + 1))
  printf '[FAIL] %s\n' "$1"
}

warn() {
  warn_count=$((warn_count + 1))
  printf '[WARN] %s\n' "$1"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '[ERROR] Required command not found: %s\n' "$1"
    exit 2
  fi
}

check_http() {
  local path="$1"
  local expected_code="$2"
  local body_pattern="${3:-}"
  local note="${4:-$path}"
  local url="${BASE_URL}${path}"
  local body_file header_file status

  body_file="$(mktemp)"
  header_file="$(mktemp)"

  status="$(curl -sS -o "${body_file}" -D "${header_file}" -w "%{http_code}" "${url}" 2>/dev/null || true)"

  if [[ "${status}" != "${expected_code}" ]]; then
    fail "${note}: expected ${expected_code}, got ${status}"
    rm -f "${body_file}" "${header_file}"
    return
  fi

  if [[ -n "${body_pattern}" ]]; then
    if ! grep -qi "${body_pattern}" "${body_file}"; then
      fail "${note}: body did not match pattern '${body_pattern}'"
      rm -f "${body_file}" "${header_file}"
      return
    fi
  fi

  pass "${note}: ${expected_code}"
  rm -f "${body_file}" "${header_file}"
}

check_redirect() {
  local path="$1"
  local expected_location="$2"
  local url="${BASE_URL}${path}"
  local body_file header_file status location

  body_file="$(mktemp)"
  header_file="$(mktemp)"

  status="$(curl -sS -o "${body_file}" -D "${header_file}" -w "%{http_code}" "${url}" 2>/dev/null || true)"
  location="$(awk 'tolower($1)=="location:" {print $2}' "${header_file}" | tr -d '\r')"

  if [[ "${status}" != "301" ]]; then
    fail "${path}: expected 301 redirect, got ${status}"
    rm -f "${body_file}" "${header_file}"
    return
  fi

  if [[ "${location}" != "${expected_location}" ]]; then
    fail "${path}: expected Location '${expected_location}', got '${location}'"
    rm -f "${body_file}" "${header_file}"
    return
  fi

  pass "${path}: 301 -> ${expected_location}"
  rm -f "${body_file}" "${header_file}"
}

check_asset_cache_header() {
  local page_path="$1"
  local html asset_path headers cache_control status

  html="$(curl -sS "${BASE_URL}${page_path}" 2>/dev/null || true)"
  asset_path="$(printf '%s\n' "${html}" | grep -Eo 'src="[^"]+assets/[^"]+\.js"' | head -n1 | cut -d'"' -f2)"

  if [[ -z "${asset_path}" ]]; then
    warn "${page_path}: could not extract JS asset path from HTML"
    return
  fi

  headers="$(curl -sSI "${BASE_URL}${asset_path}" 2>/dev/null || true)"
  status="$(printf '%s\n' "${headers}" | awk 'toupper($1) ~ /^HTTP\// {print $2; exit}')"
  cache_control="$(printf '%s\n' "${headers}" | awk -F': ' 'tolower($1)=="cache-control" {print tolower($2)}' | tr -d '\r')"

  if [[ "${status}" != "200" ]]; then
    fail "${asset_path}: expected 200, got ${status:-none}"
    return
  fi

  if [[ "${cache_control}" == *immutable* ]]; then
    pass "${asset_path}: Cache-Control contains immutable"
  else
    fail "${asset_path}: Cache-Control missing immutable"
  fi
}

print_section "Prerequisites"
require_cmd docker
require_cmd curl
require_cmd grep
require_cmd awk

if ! docker compose version >/dev/null 2>&1; then
  printf '[ERROR] docker compose is not available.\n'
  exit 2
fi
pass "docker compose available"

if ! docker compose ps >/dev/null 2>&1; then
  printf '[ERROR] Cannot access Docker daemon from this shell.\n'
  printf 'Hint: re-login or run `newgrp docker`, then rerun this script.\n'
  exit 2
fi
pass "docker daemon access confirmed"

print_section "Container Status"
if docker compose ps --format json 2>/dev/null | grep -q '"State":"running"'; then
  pass "at least one compose service is running"
else
  warn "no running compose service detected; run 'docker compose up -d' first"
fi

print_section "API and Routing Checks"
check_http "/api/" "200" "welcome to our application" "GET /api/"
check_http "/api/public/colleges" "200" "colleges" "GET /api/public/colleges"
check_http "/" "200" "<!doctype html" "GET /"
check_redirect "/admin" "/admin/"
check_redirect "/super" "/super/"
check_http "/admin/" "200" "<!doctype html" "GET /admin/"
check_http "/super/" "200" "<!doctype html" "GET /super/"
check_http "/admin/dashboard" "200" "<!doctype html" "GET /admin/dashboard"
check_http "/super/colleges" "200" "<!doctype html" "GET /super/colleges"

print_section "Static Asset Header Checks"
check_asset_cache_header "/"
check_asset_cache_header "/admin/"
check_asset_cache_header "/super/"

print_section "Summary"
printf 'Pass: %d | Fail: %d | Warn: %d\n' "${pass_count}" "${fail_count}" "${warn_count}"

if [[ "${fail_count}" -gt 0 ]]; then
  printf 'Automated checks reported failures.\n'
else
  printf 'Automated checks passed.\n'
fi

cat <<EOF

Manual browser checklist (${BASE_URL})
1. Open ${BASE_URL}/ and verify User app renders with no console errors.
2. From User app, verify role links navigate to ${BASE_URL}/admin/ and ${BASE_URL}/super/.
3. Open ${BASE_URL}/admin/ and verify dashboard layout, tables, and action buttons render correctly.
4. Open ${BASE_URL}/super/ and verify admin/college management sections render correctly.
5. Verify deep-link refresh works:
   - ${BASE_URL}/admin/dashboard
   - ${BASE_URL}/super/colleges
6. In browser Network tab, confirm frontend API calls target /api/* (not localhost:8000 hardcoded URLs).
7. Run one real workflow per role (user chat, admin doc upload, super-admin approval/reject) and confirm no crashes.
EOF

if [[ "${fail_count}" -gt 0 ]]; then
  exit 1
fi

exit 0
