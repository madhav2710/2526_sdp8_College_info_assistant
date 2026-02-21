# AWS Deployment Plan: College Info Assistant

Date: 2026-02-18

## 1. Executive decision

Use **ECS (Fargate) for backend services** and **S3 + CloudFront for all 3 frontends**.

This is the best fit for your situation because:
- You currently run one large FastAPI app, but you already plan to split it into modules.
- You want near-term extraction of RAG into a separate service.
- ECS gives service boundaries, autoscaling, and cleaner future microservice rollout than EC2.
- Frontends are static Vite apps and are cheaper and simpler on S3 + CloudFront than EC2/ECS.

If you need the fastest possible first deployment with lowest learning curve, EC2 is viable, but it increases future migration work.

## 2. What I found in your current repo

### 2.1 Current architecture
- Backend: `FastAPI` monolith in `backend/main.py`.
- Three separate React/Vite frontends:
  - `frontend/User`
  - `frontend/Admin`
  - `frontend/Super admin`
- Data/auth/storage/vector: Supabase (single project) via `backend/app/core/database.py`.
- RAG logic is inside backend process in `backend/app/core/rag.py`.

### 2.2 Deployment-relevant risks and gaps
- CORS is fully open (`allow_origins=["*"]`) in `backend/main.py`.
- User frontend has hardcoded localhost dashboard links in `frontend/User/src/App.jsx`.
- "Scheduled processing" is stored in DB but there is no scheduler/worker loop that executes due jobs.
- No explicit backend dependency lock file (`requirements.txt` or `pyproject.toml`) in `backend/`.
- No Dockerfiles or infrastructure code currently present.

These do not block deployment, but should be addressed in Phase 1-2 below.

## 3. EC2 vs ECS comparison for your case

| Dimension | EC2 | ECS (Fargate) |
|---|---|---|
| Initial setup speed | Faster for one VM | Slightly slower at start |
| Operations overhead | High (patching, scaling, hardening) | Lower (managed control plane) |
| Scaling backend | Manual/ASG tuning | Service autoscaling built-in |
| Multi-service future | Harder (process manager + port sprawl) | Natural fit (one service per task) |
| Zero-downtime deploys | DIY | Standard rolling/blue-green |
| Security posture | More host management burden | Smaller host surface |
| Cost at very small size | Can be cheaper | Slight premium for managed runtime |
| Fit for future RAG split | Moderate | Strong |

**Recommendation**: ECS Fargate wins for your roadmap.

## 4. Target production architecture

## 4.1 Domain model
Use subdomains:
- `app.example.com` -> User frontend
- `admin.example.com` -> Admin frontend
- `superadmin.example.com` -> Super Admin frontend
- `api.example.com` -> Backend API

## 4.2 Frontend hosting
Deploy each frontend as static assets:
- Build with environment-specific `VITE_API_BASE_URL=https://api.example.com`.
- Host each build in its own S3 bucket.
- Put CloudFront in front of each bucket.
- Use ACM certificates (us-east-1 for CloudFront).

Reason: lower cost, better caching, simpler release rollback than container-hosted frontends.

## 4.3 Backend hosting
- Containerize FastAPI monolith.
- Push image to ECR.
- Run on ECS Fargate service (minimum 2 tasks across 2 AZs).
- Front with ALB (HTTPS only).
- Route53 `api.example.com` -> ALB.

## 4.4 External dependencies
- Supabase remains managed external data/auth/storage/vector.
- Gemini API remains external.
- Store keys in AWS Secrets Manager or SSM Parameter Store.

## 4.5 Observability and operations
- CloudWatch logs for ECS tasks.
- Metrics/alarms: 5xx rate, task restarts, ALB target health, latency.
- Add uptime synthetic checks for all 4 domains.

## 4.6 Security baseline
- Restrict CORS to real frontend domains (no wildcard in production).
- Store all secrets outside image.
- Enforce HTTPS with HTTP->HTTPS redirect.
- WAF on CloudFront/ALB for basic managed protections.
- Tight IAM task roles (least privilege).

## 5. Implementation phases

## Phase 1: Deploy current monolith safely (1-2 weeks)

### Goals
- Production deployment without architectural split yet.
- All 3 frontends live.

### Tasks
1. Backend packaging
- Create `backend/requirements.txt` (or `pyproject.toml`) and pin dependencies.
- Add backend Dockerfile.
- Add health endpoint (`/healthz`) that does not require auth.

2. Frontend production readiness
- Replace hardcoded localhost links in `frontend/User/src/App.jsx` with environment-driven URLs.
- Build each frontend per environment.

3. AWS infra
- Create ECR repo.
- Create ECS cluster/service/task definition for backend.
- Create ALB and target group health check on `/healthz`.
- Create 3 S3 buckets + 3 CloudFront distributions.
- Configure Route53 + ACM certs.

4. Release
- Deploy backend image.
- Upload frontend builds.
- Smoke test auth, chat, admin upload, super-admin approval.

### Exit criteria
- All 4 domains reachable via HTTPS.
- Upload -> approve -> process -> chat flow works end-to-end.
- Rollback procedure tested once.

## Phase 2: Production hardening and CI/CD (1-2 weeks)

### Tasks
1. CI/CD
- Backend: GitHub Actions -> ECR -> ECS rolling deploy.
- Frontends: build + deploy to S3 + CloudFront invalidation.
- Separate pipelines for `dev`, `staging`, `prod`.

2. Runtime hardening
- Tighten CORS and allowed origins.
- Add log correlation id per request.
- Add dashboard and alerts (CloudWatch + SNS).

3. Environment strategy
- Separate AWS accounts or at least isolated VPC stacks for staging/prod.
- Separate Supabase projects per environment if possible.

### Exit criteria
- One-command or one-merge deployment process.
- Alerting for critical failures is active and verified.

## Phase 3: Modularize monolith on ECS (2-4 weeks)

### Service split (incremental)
Start from code boundaries in `backend/main.py` + `backend/app/core/*`:
- `api-gateway` (auth routing, request validation, shared middleware)
- `chat-service` (chat endpoints and conversation logic)
- `document-service` (upload/approval lifecycle)
- `notification-service` (notification CRUD/events)
- `rag-worker` (document processing and chunk/embedding pipeline)

Keep a shared contract package for auth/context models until fully independent.

### Key platform additions
- Introduce SQS queue for processing jobs.
- API service publishes job events; worker consumes queue.
- Move long-running `BackgroundTasks` work out of request lifecycle.

### Exit criteria
- API tasks remain stateless and short-lived.
- Job processing survives task restarts and deployments.

## Phase 4: Extract RAG as a dedicated service (2-3 weeks)

### Target RAG split
- New ECS service: `rag-service` (query-time retrieval/generation APIs).
- New ECS worker: `rag-indexer` (ingestion/indexing from queue).
- Queue(s):
  - `document-processing-queue`
  - optional `dead-letter-queue`

### Scheduling model
Current code stores `scheduled_at` but does not execute due work automatically.
Implement one of these:
- Preferred: EventBridge Scheduler to enqueue SQS message at requested time.
- Alternative: small scheduler service polling DB and enqueueing due docs.

### Exit criteria
- Monolith no longer owns RAG internals.
- RAG compute can scale independently from API traffic.

## 6. Recommended AWS service map

- Route53: DNS records for all subdomains
- ACM: TLS certificates
- CloudFront (x3): frontend delivery
- S3 (x3): frontend static hosting
- ECR: backend and future service images
- ECS Fargate: backend now, multi-services later
- ALB: API ingress
- Secrets Manager/SSM: env secrets
- CloudWatch + SNS: logs/metrics/alerts
- SQS (+ DLQ): async processing pipeline (Phase 3+)
- EventBridge Scheduler: scheduled document jobs (Phase 4)

## 7. Deployment topology details

## 7.1 Backend ECS task (initial)
- CPU/memory start point: `0.5 vCPU / 1-2 GB` per task
- Desired count: `2`
- Autoscaling:
  - scale out at CPU > 60% or ALB request/target threshold
  - scale in conservatively
- Health check path: `/healthz`

## 7.2 Frontend release pattern
For each app (`User`, `Admin`, `Super admin`):
1. `npm ci`
2. `npm run build`
3. Sync `dist/` to S3
4. Invalidate CloudFront cache

## 7.3 Secrets and config
Move these backend vars to Secrets Manager/SSM:
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `JWT_SECRET_KEY`
- `GEMINI_API_KEY`
- Any DB migration credentials (`DATABASE_URL` or `SUPABASE_DB_PASSWORD`)

## 8. Risks and mitigations

1. In-request background processing loss on task restart
- Mitigation: move to SQS worker pattern (Phase 3).

2. Scheduled jobs not executed automatically
- Mitigation: EventBridge Scheduler + SQS (Phase 4).

3. Cross-frontend auth/session confusion across subdomains
- Mitigation: define token storage and domain policy explicitly per frontend.

4. Open CORS in production
- Mitigation: explicit allowlist before go-live.

## 9. Suggested rollout order

1. Deploy staging first with full topology.
2. Run end-to-end validation:
- login/signup
- upload/approval/rejection
- immediate processing
- chat with and without RAG fallback
- notifications
3. Perform production cutover in low-traffic window.
4. Keep previous backend task definition/image for immediate rollback.

## 10. Concrete repo TODO checklist

- [ ] Add backend dependency file in `backend/`.
- [ ] Add backend Dockerfile in `backend/`.
- [ ] Add `/healthz` in `backend/main.py`.
- [ ] Replace localhost dashboard links in `frontend/User/src/App.jsx`.
- [ ] Restrict CORS in `backend/main.py`.
- [ ] Add infra code folder (Terraform or CloudFormation) for ECS + S3 + CloudFront.
- [ ] Add CI workflows for backend and each frontend.
- [ ] Introduce SQS-based worker for processing jobs.
- [ ] Implement scheduled-job execution path (EventBridge/Scheduler).

## 11. Final recommendation summary

For your current monolith plus near-term modularization and RAG extraction roadmap:
- Choose **ECS Fargate** for backend/services.
- Choose **S3 + CloudFront** for all three frontends.
- Use **SQS + worker services** before scaling traffic to avoid job-loss and scheduling gaps.

This gives lower long-term operational burden than EC2 and aligns directly with your planned architecture evolution.

## 12. AWS references used

- ECS capacity/launch options (includes Fargate vs EC2 operational model):
  - https://docs.aws.amazon.com/AmazonECS/latest/developerguide/launch_types.html
- ECS service autoscaling with target tracking:
  - https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-autoscaling-targettracking.html
  - https://docs.aws.amazon.com/AmazonECS/latest/developerguide/target-tracking-create-policy.html
- ECS sensitive config/secrets handling:
  - https://docs.aws.amazon.com/AmazonECS/latest/developerguide/specifying-sensitive-data.html
  - https://docs.aws.amazon.com/AmazonECS/latest/userguide/secrets-envvar-secrets-manager.html
- EventBridge Scheduler schedule types (including one-time scheduling) and SQS target setup:
  - https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html
  - https://docs.aws.amazon.com/scheduler/latest/UserGuide/setting-up.html
- CloudFront + S3 origin protection recommendations (OAC):
  - https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html
- HTTPS guidance for static sites behind CloudFront:
  - https://docs.aws.amazon.com/prescriptive-guidance/latest/aws-startup-security-baseline/wkld-13.html
