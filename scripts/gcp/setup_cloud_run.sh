#!/usr/bin/env bash

set -euo pipefail

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '[ERROR] Required command not found: %s\n' "$1"
    exit 2
  fi
}

require_cmd gcloud

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-us-central1}"
AR_REPO="${AR_REPO:-college-info-agent}"
SERVICE_NAME="${SERVICE_NAME:-college-info-agent}"
RUNTIME_SA_NAME="${RUNTIME_SA_NAME:-cloud-run-college-info}"
GRANT_DEPLOYER_ROLES="${GRANT_DEPLOYER_ROLES:-false}"
DEPLOYER_MEMBER="${DEPLOYER_MEMBER:-}"

if [[ -z "${PROJECT_ID}" ]]; then
  printf '[ERROR] PROJECT_ID is required. Export PROJECT_ID or run `gcloud config set project <id>` first.\n'
  exit 1
fi

if [[ -z "${DEPLOYER_MEMBER}" ]]; then
  active_account="$(gcloud config get-value account 2>/dev/null || true)"
  if [[ -n "${active_account}" ]]; then
    DEPLOYER_MEMBER="user:${active_account}"
  fi
fi

RUNTIME_SA_EMAIL="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

printf '== Cloud Run Bootstrap ==\n'
printf 'Project: %s\n' "${PROJECT_ID}"
printf 'Region: %s\n' "${REGION}"
printf 'Artifact Registry Repo: %s\n' "${AR_REPO}"
printf 'Service Name: %s\n' "${SERVICE_NAME}"
printf 'Runtime Service Account: %s\n\n' "${RUNTIME_SA_EMAIL}"

printf 'Enabling required APIs...\n'
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  --project "${PROJECT_ID}"

printf 'Ensuring Artifact Registry repository exists...\n'
if gcloud artifacts repositories describe "${AR_REPO}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  printf '[OK] Artifact Registry repository already exists: %s\n' "${AR_REPO}"
else
  gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Container images for ${SERVICE_NAME}" \
    --project "${PROJECT_ID}"
  printf '[OK] Created Artifact Registry repository: %s\n' "${AR_REPO}"
fi

printf 'Ensuring runtime service account exists...\n'
if gcloud iam service-accounts describe "${RUNTIME_SA_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  printf '[OK] Service account already exists: %s\n' "${RUNTIME_SA_EMAIL}"
else
  gcloud iam service-accounts create "${RUNTIME_SA_NAME}" \
    --display-name="Cloud Run runtime for ${SERVICE_NAME}" \
    --project "${PROJECT_ID}"
  printf '[OK] Created service account: %s\n' "${RUNTIME_SA_EMAIL}"
fi

printf 'Granting runtime access to Secret Manager...\n'
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet >/dev/null
printf '[OK] Runtime service account can read secrets\n'

if [[ "${GRANT_DEPLOYER_ROLES}" == "true" ]]; then
  if [[ -z "${DEPLOYER_MEMBER}" ]]; then
    printf '[ERROR] Could not infer DEPLOYER_MEMBER. Set DEPLOYER_MEMBER and rerun.\n'
    exit 1
  fi

  printf 'Granting deployer IAM roles to %s...\n' "${DEPLOYER_MEMBER}"
  deployer_roles=(
    roles/run.admin
    roles/iam.serviceAccountUser
    roles/artifactregistry.writer
    roles/cloudbuild.builds.editor
  )
  for role in "${deployer_roles[@]}"; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="${DEPLOYER_MEMBER}" \
      --role="${role}" \
      --quiet >/dev/null
    printf '[OK] Granted %s\n' "${role}"
  done
fi

required_secrets=(
  SUPABASE_URL
  SUPABASE_KEY
  SUPABASE_SERVICE_ROLE_KEY
  JWT_SECRET_KEY
)
optional_secrets=(
  GEMINI_API_KEY
)

printf 'Ensuring required secrets exist...\n'
for secret_name in "${required_secrets[@]}"; do
  if gcloud secrets describe "${secret_name}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    printf '[OK] Secret exists: %s\n' "${secret_name}"
  else
    gcloud secrets create "${secret_name}" \
      --replication-policy="automatic" \
      --project "${PROJECT_ID}" >/dev/null
    printf '[OK] Created secret: %s\n' "${secret_name}"
  fi

  secret_value="${!secret_name:-}"
  if [[ -n "${secret_value}" ]]; then
    printf '%s' "${secret_value}" | gcloud secrets versions add "${secret_name}" \
      --data-file=- \
      --project "${PROJECT_ID}" >/dev/null
    printf '[OK] Added new secret version from current shell env: %s\n' "${secret_name}"
  else
    printf '[WARN] %s is not set in current shell; no new secret version added\n' "${secret_name}"
  fi
done

printf 'Ensuring optional secrets exist...\n'
for secret_name in "${optional_secrets[@]}"; do
  if gcloud secrets describe "${secret_name}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    printf '[OK] Optional secret exists: %s\n' "${secret_name}"
  else
    gcloud secrets create "${secret_name}" \
      --replication-policy="automatic" \
      --project "${PROJECT_ID}" >/dev/null
    printf '[OK] Created optional secret: %s\n' "${secret_name}"
  fi

  secret_value="${!secret_name:-}"
  if [[ -n "${secret_value}" ]]; then
    printf '%s' "${secret_value}" | gcloud secrets versions add "${secret_name}" \
      --data-file=- \
      --project "${PROJECT_ID}" >/dev/null
    printf '[OK] Added new optional secret version from current shell env: %s\n' "${secret_name}"
  else
    printf '[WARN] %s is not set in current shell; app will run in degraded RAG mode\n' "${secret_name}"
  fi
done

cat <<EOF

Bootstrap complete.

Next steps:
1. If any secret versions were not added, set them manually:
   printf '%s' "<value>" | gcloud secrets versions add <SECRET_NAME> --data-file=- --project ${PROJECT_ID}
2. Run deployment:
   PROJECT_ID=${PROJECT_ID} REGION=${REGION} AR_REPO=${AR_REPO} SERVICE_NAME=${SERVICE_NAME} ./scripts/gcp/deploy_cloud_run.sh
3. Run smoke tests after deploy:
   PROJECT_ID=${PROJECT_ID} REGION=${REGION} SERVICE_NAME=${SERVICE_NAME} ./scripts/gcp/smoke_test_cloud_run.sh
EOF
