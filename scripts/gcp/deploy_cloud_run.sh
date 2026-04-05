#!/usr/bin/env bash

set -euo pipefail

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '[ERROR] Required command not found: %s\n' "$1"
    exit 2
  fi
}

require_cmd gcloud
require_cmd git

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${ROOT_DIR}"

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-us-central1}"
AR_REPO="${AR_REPO:-college-info-agent}"
SERVICE_NAME="${SERVICE_NAME:-college-info-agent}"
RUNTIME_SA_NAME="${RUNTIME_SA_NAME:-cloud-run-college-info}"
RUNTIME_SA_EMAIL="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

RUN_PREFLIGHT="${RUN_PREFLIGHT:-true}"
ENV_FILE="${ENV_FILE:-backend/.env}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)-$(date +%Y%m%d%H%M%S)}"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE_NAME}:${IMAGE_TAG}"

MAX_INSTANCES="${MAX_INSTANCES:-10}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"
CPU="${CPU:-1}"
MEMORY="${MEMORY:-2Gi}"
TIMEOUT="${TIMEOUT:-300}"
CONCURRENCY="${CONCURRENCY:-40}"

NON_SECRET_ENV_VARS="${NON_SECRET_ENV_VARS:-DEBUG=false,LOG_LEVEL=INFO,RATE_LIMIT_ENABLED=true,DEFAULT_RATE_LIMIT_PER_MINUTE=60,MAX_FILE_SIZE_MB=50,ALLOWED_FILE_EXTENSIONS=.pdf,.doc,.docx,.txt}"
SECRET_MAPPINGS="${SECRET_MAPPINGS:-}"

if [[ -z "${PROJECT_ID}" ]]; then
  printf '[ERROR] PROJECT_ID is required. Export PROJECT_ID or run `gcloud config set project <id>` first.\n'
  exit 1
fi

secret_has_enabled_version() {
  local secret_name="$1"
  local count
  count="$(gcloud secrets versions list "${secret_name}" \
    --project "${PROJECT_ID}" \
    --filter='state=enabled' \
    --limit=1 \
    --format='value(name)' 2>/dev/null || true)"
  [[ -n "${count}" ]]
}

if [[ -z "${SECRET_MAPPINGS}" ]]; then
  required_secrets=(
    SUPABASE_URL
    SUPABASE_KEY
    SUPABASE_SERVICE_ROLE_KEY
    JWT_SECRET_KEY
  )

  for required_secret in "${required_secrets[@]}"; do
    if ! secret_has_enabled_version "${required_secret}"; then
      printf '[ERROR] Secret %s has no enabled version in project %s.\n' "${required_secret}" "${PROJECT_ID}"
      printf '        Add one with: printf %%s "<value>" | gcloud secrets versions add %s --data-file=- --project %s\n' "${required_secret}" "${PROJECT_ID}"
      exit 1
    fi
  done

  secret_mappings_parts=(
    "SUPABASE_URL=SUPABASE_URL:latest"
    "SUPABASE_KEY=SUPABASE_KEY:latest"
    "SUPABASE_SERVICE_ROLE_KEY=SUPABASE_SERVICE_ROLE_KEY:latest"
    "JWT_SECRET_KEY=JWT_SECRET_KEY:latest"
  )

  if secret_has_enabled_version "GEMINI_API_KEY"; then
    secret_mappings_parts+=("GEMINI_API_KEY=GEMINI_API_KEY:latest")
  else
    printf '[WARN] GEMINI_API_KEY has no enabled version; deploying without Gemini (RAG fallback mode).\n'
  fi

  SECRET_MAPPINGS="$(IFS=,; printf '%s' "${secret_mappings_parts[*]}")"
fi

printf '== Cloud Run Deploy ==\n'
printf 'Project: %s\n' "${PROJECT_ID}"
printf 'Region: %s\n' "${REGION}"
printf 'Service: %s\n' "${SERVICE_NAME}"
printf 'Image: %s\n' "${IMAGE_URI}"
printf 'Runtime SA: %s\n\n' "${RUNTIME_SA_EMAIL}"

if [[ "${RUN_PREFLIGHT}" == "true" ]]; then
  printf 'Running preflight checks...\n'
  "${SCRIPT_DIR}/preflight_cloud_run.sh" "${ENV_FILE}"
fi

printf 'Authenticating Docker client with Artifact Registry...\n'
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet >/dev/null

printf 'Building and pushing image via Cloud Build...\n'
gcloud builds submit --tag "${IMAGE_URI}" --project "${PROJECT_ID}" .

printf 'Deploying revision to Cloud Run...\n'
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_URI}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --service-account "${RUNTIME_SA_EMAIL}" \
  --port 80 \
  --cpu "${CPU}" \
  --memory "${MEMORY}" \
  --timeout "${TIMEOUT}" \
  --concurrency "${CONCURRENCY}" \
  --min-instances "${MIN_INSTANCES}" \
  --max-instances "${MAX_INSTANCES}" \
  --set-env-vars "${NON_SECRET_ENV_VARS}" \
  --set-secrets "${SECRET_MAPPINGS}"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.url)')"
LATEST_REVISION="$(gcloud run services describe "${SERVICE_NAME}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.latestReadyRevisionName)')"

cat <<EOF

Deploy complete.
Service URL: ${SERVICE_URL}
Latest ready revision: ${LATEST_REVISION}

Next:
1. Run smoke tests:
   PROJECT_ID=${PROJECT_ID} REGION=${REGION} SERVICE_NAME=${SERVICE_NAME} ./scripts/gcp/smoke_test_cloud_run.sh
2. If needed, roll back traffic:
   gcloud run services update-traffic ${SERVICE_NAME} --to-revisions <previous_revision>=100 --region ${REGION} --project ${PROJECT_ID}
EOF
