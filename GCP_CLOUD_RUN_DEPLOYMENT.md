# GCP Cloud Run Deployment Guide

This guide deploys the existing single-container runtime (Caddy + FastAPI + User/Admin/Super Admin frontends) to Google Cloud Run.

## Target Topology

- One Cloud Run service: `college-info-agent`
- Region: `us-central1`
- Container serves:
  - User app at `/`
  - Admin app at `/admin/`
  - Super Admin app at `/super/`
  - API at `/api/*`

## Prerequisites

- `gcloud` CLI installed and authenticated.
- A GCP project with billing enabled.
- Access to Supabase and Gemini credentials.
- Dockerfile builds successfully in this repository root.

## 1) Preflight Checks

Run local deployment lint checks before building:

```bash
./scripts/gcp/preflight_cloud_run.sh backend/.env
```

What this validates:

- No leftover merge markers (`<<<<<<<`, `>>>>>>>`) in key code paths.
- `DEBUG` is not true.
- `JWT_SECRET_KEY` is not missing/placeholder/too short.
- `SUPABASE_*` values are present.
- Warns if `GEMINI_API_KEY` is missing (degraded RAG mode).
- Warns if `MAX_FILE_SIZE_MB > 32` (Cloud Run request-size constraint risk).

## 2) One-Time GCP Bootstrap

Set core variables:

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export AR_REPO="college-info-agent"
export SERVICE_NAME="college-info-agent"
```

Optional: export runtime secrets in your shell first if you want script-based secret version upload:

```bash
export SUPABASE_URL="https://<project-ref>.supabase.co"
export SUPABASE_KEY="<anon-key>"
export SUPABASE_SERVICE_ROLE_KEY="<service-role-key>"
export GEMINI_API_KEY="<gemini-key>"
export JWT_SECRET_KEY="<32+ char random secret>"
```

Run bootstrap:

```bash
PROJECT_ID="$PROJECT_ID" REGION="$REGION" AR_REPO="$AR_REPO" SERVICE_NAME="$SERVICE_NAME" \
./scripts/gcp/setup_cloud_run.sh
```

This script:

- Enables required APIs.
- Creates Artifact Registry repo (if missing).
- Creates runtime service account (if missing).
- Grants runtime secret access.
- Creates required Secret Manager secrets (if missing).
- Creates optional `GEMINI_API_KEY` secret (if missing).
- Adds secret versions from current shell env values when provided.

If your deployer needs IAM grants from script, run with:

```bash
GRANT_DEPLOYER_ROLES=true DEPLOYER_MEMBER="user:you@example.com" ./scripts/gcp/setup_cloud_run.sh
```

## 3) Run Production Migrations

Run database migrations against production Supabase before routing traffic:

```bash
cd backend
python run_migration.py --plan current-all
cd ..
```

Use production DB credentials (`DATABASE_URL` or `SUPABASE_DB_*`) for this step.

## 4) Deploy to Cloud Run

```bash
PROJECT_ID="$PROJECT_ID" REGION="$REGION" AR_REPO="$AR_REPO" SERVICE_NAME="$SERVICE_NAME" \
./scripts/gcp/deploy_cloud_run.sh
```

What it does:

- Runs preflight checks (default).
- Builds and pushes image via Cloud Build.
- Deploys to Cloud Run with:
  - `--allow-unauthenticated`
  - `--port 80`
  - `--cpu 1 --memory 2Gi --timeout 300 --concurrency 40`
  - min/max instances: `0/10`
  - non-secret env vars (`DEBUG=false`, rate limit + upload settings)
- secret env bindings from Secret Manager
  - `GEMINI_API_KEY` is auto-included only when a secret version exists

Optional overrides:

```bash
RUN_PREFLIGHT=false IMAGE_TAG="manual-$(date +%Y%m%d)" MAX_INSTANCES=20 ./scripts/gcp/deploy_cloud_run.sh
```

## 5) Smoke Test After Deploy

```bash
PROJECT_ID="$PROJECT_ID" REGION="$REGION" SERVICE_NAME="$SERVICE_NAME" \
./scripts/gcp/smoke_test_cloud_run.sh
```

Or pass a URL directly:

```bash
./scripts/gcp/smoke_test_cloud_run.sh "https://your-service-xyz-uc.a.run.app"
```

Checks include:

- API root and public colleges.
- Frontend routes and SPA deep links.
- `/admin` and `/super` redirect behavior.
- Protected health endpoint returning one of `200/401/403`.

## 6) Rollback

List revisions:

```bash
gcloud run revisions list --service "$SERVICE_NAME" --region "$REGION" --project "$PROJECT_ID"
```

Shift all traffic to a previous revision:

```bash
gcloud run services update-traffic "$SERVICE_NAME" \
  --to-revisions "<previous-revision>=100" \
  --region "$REGION" \
  --project "$PROJECT_ID"
```

## 7) Known Limitation (Current Release)

- Application-level upload limit is `MAX_FILE_SIZE_MB=50`.
- Cloud Run can reject larger HTTP requests before app validation.
- For now, this release keeps current upload flow and accepts this limitation.
- Recommended follow-up: direct-to-storage uploads (signed URL flow) for larger documents.
