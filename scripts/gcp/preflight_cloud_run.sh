#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${ROOT_DIR}"

ENV_FILE="${1:-backend/.env}"

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

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '[ERROR] Required command not found: %s\n' "$1"
    exit 2
  fi
}

read_env_file_value() {
  local key="$1"
  local value

  if [[ ! -f "${ENV_FILE}" ]]; then
    return 0
  fi

  value="$(grep -E "^[[:space:]]*${key}=" "${ENV_FILE}" | tail -n1 | sed -E "s/^[[:space:]]*${key}=//; s/[[:space:]]+$//; s/^\"(.*)\"$/\\1/; s/^'(.*)'$/\\1/" || true)"
  printf '%s' "${value}"
}

printf '== Cloud Run Preflight ==\n'
printf 'Repo: %s\n' "${ROOT_DIR}"
printf 'Env file: %s\n\n' "${ENV_FILE}"

require_cmd rg
require_cmd grep
require_cmd sed

if rg -n '^(<<<<<<< |>>>>>>> )' backend frontend scripts Dockerfile Caddyfile >/tmp/cloudrun_conflicts.$$ 2>/dev/null; then
  fail "merge conflict markers found in tracked code paths"
  cat /tmp/cloudrun_conflicts.$$
else
  pass "no merge conflict markers detected"
fi
rm -f /tmp/cloudrun_conflicts.$$

if [[ ! -f "${ENV_FILE}" ]]; then
  warn "env file not found; skipped env lint checks"
else
  pass "env file found at ${ENV_FILE}"

  debug_value="$(read_env_file_value DEBUG)"
  jwt_secret="$(read_env_file_value JWT_SECRET_KEY)"
  supabase_url="$(read_env_file_value SUPABASE_URL)"
  supabase_key="$(read_env_file_value SUPABASE_KEY)"
  supabase_service_key="$(read_env_file_value SUPABASE_SERVICE_ROLE_KEY)"
  gemini_key="$(read_env_file_value GEMINI_API_KEY)"
  max_file_size_mb="$(read_env_file_value MAX_FILE_SIZE_MB)"

  if [[ "${debug_value,,}" == "true" ]]; then
    fail "DEBUG=true is not allowed for production"
  else
    pass "DEBUG is disabled for production"
  fi

  if [[ -z "${jwt_secret}" ]]; then
    fail "JWT_SECRET_KEY is missing"
  elif [[ "${#jwt_secret}" -lt 32 ]]; then
    fail "JWT_SECRET_KEY is too short (must be at least 32 chars)"
  elif [[ "${jwt_secret,,}" == *"change-this-in-production"* || "${jwt_secret,,}" == *"replace_with"* || "${jwt_secret,,}" == *"your-super-secret"* ]]; then
    fail "JWT_SECRET_KEY still looks like a placeholder value"
  else
    pass "JWT_SECRET_KEY looks production-ready"
  fi

  if [[ -z "${supabase_url}" || "${supabase_url}" == *"YOUR_PROJECT_REF"* ]]; then
    fail "SUPABASE_URL is missing or placeholder"
  else
    pass "SUPABASE_URL configured"
  fi

  if [[ -z "${supabase_key}" || "${supabase_key}" == *"YOUR_SUPABASE_ANON_KEY"* ]]; then
    fail "SUPABASE_KEY is missing or placeholder"
  else
    pass "SUPABASE_KEY configured"
  fi

  if [[ -z "${supabase_service_key}" || "${supabase_service_key}" == *"YOUR_SUPABASE_SERVICE_ROLE_KEY"* ]]; then
    fail "SUPABASE_SERVICE_ROLE_KEY is missing or placeholder"
  else
    pass "SUPABASE_SERVICE_ROLE_KEY configured"
  fi

  if [[ -z "${gemini_key}" || "${gemini_key}" == *"YOUR_GEMINI_API_KEY"* ]]; then
    warn "GEMINI_API_KEY not set; app will run with degraded RAG responses"
  else
    pass "GEMINI_API_KEY configured"
  fi

  if [[ -n "${max_file_size_mb}" ]] && [[ "${max_file_size_mb}" =~ ^[0-9]+$ ]] && (( max_file_size_mb > 32 )); then
    warn "MAX_FILE_SIZE_MB=${max_file_size_mb}; Cloud Run HTTP request limit can reject large uploads before app validation"
  fi
fi

printf '\n== Summary ==\n'
printf 'Pass: %d | Fail: %d | Warn: %d\n' "${pass_count}" "${fail_count}" "${warn_count}"

if (( fail_count > 0 )); then
  exit 1
fi

exit 0
