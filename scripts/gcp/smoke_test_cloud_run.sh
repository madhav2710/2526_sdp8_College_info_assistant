#!/usr/bin/env bash

set -euo pipefail

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '[ERROR] Required command not found: %s\n' "$1"
    exit 2
  fi
}

pass_count=0
fail_count=0
warn_count=0

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

check_http() {
  local path="$1"
  local expected_codes_csv="$2"
  local body_pattern="${3:-}"
  local note="${4:-$path}"
  local url="${BASE_URL}${path}"
  local status body_file

  body_file="$(mktemp)"
  status="$(curl -sS -o "${body_file}" -w "%{http_code}" "${url}" || true)"

  if [[ ",${expected_codes_csv}," != *",${status},"* ]]; then
    fail "${note}: expected ${expected_codes_csv}, got ${status}"
    rm -f "${body_file}"
    return
  fi

  if [[ -n "${body_pattern}" ]]; then
    if ! grep -qi "${body_pattern}" "${body_file}"; then
      fail "${note}: body did not match pattern '${body_pattern}'"
      rm -f "${body_file}"
      return
    fi
  fi

  pass "${note}: ${status}"
  rm -f "${body_file}"
}

check_redirect() {
  local path="$1"
  local expected_location="$2"
  local status location header_file body_file

  header_file="$(mktemp)"
  body_file="$(mktemp)"
  status="$(curl -sS -o "${body_file}" -D "${header_file}" -w "%{http_code}" "${BASE_URL}${path}" || true)"
  location="$(awk 'tolower($1)=="location:" {print $2}' "${header_file}" | tr -d '\r')"

  if [[ "${status}" != "301" ]]; then
    fail "${path}: expected 301 redirect, got ${status}"
    rm -f "${header_file}" "${body_file}"
    return
  fi

  if [[ "${location}" != "${expected_location}" ]]; then
    fail "${path}: expected Location '${expected_location}', got '${location}'"
    rm -f "${header_file}" "${body_file}"
    return
  fi

  pass "${path}: 301 -> ${expected_location}"
  rm -f "${header_file}" "${body_file}"
}

require_cmd curl
require_cmd grep
require_cmd awk
require_cmd gcloud

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-college-info-agent}"

BASE_URL="${1:-}"
if [[ -z "${BASE_URL}" ]]; then
  if [[ -z "${PROJECT_ID}" ]]; then
    printf '[ERROR] PROJECT_ID is required if BASE_URL is not provided.\n'
    exit 1
  fi
  BASE_URL="$(gcloud run services describe "${SERVICE_NAME}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.url)')"
fi

printf '== Cloud Run Smoke Test ==\n'
printf 'Base URL: %s\n\n' "${BASE_URL}"

check_http "/api/" "200" "welcome to our application" "GET /api/"
check_http "/api/public/colleges" "200" "colleges" "GET /api/public/colleges"
check_http "/api/system/health" "200,401,403" "" "GET /api/system/health (protected endpoint)"
check_http "/" "200" "<!doctype html" "GET /"
check_redirect "/admin" "/admin/"
check_redirect "/super" "/super/"
check_http "/admin/" "200" "<!doctype html" "GET /admin/"
check_http "/super/" "200" "<!doctype html" "GET /super/"
check_http "/admin/dashboard" "200" "<!doctype html" "GET /admin/dashboard"
check_http "/super/colleges" "200" "<!doctype html" "GET /super/colleges"

printf '\n== Summary ==\n'
printf 'Pass: %d | Fail: %d | Warn: %d\n' "${pass_count}" "${fail_count}" "${warn_count}"

if (( fail_count > 0 )); then
  exit 1
fi

exit 0
