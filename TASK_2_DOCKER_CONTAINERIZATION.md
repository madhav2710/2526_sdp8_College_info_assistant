# Task 2: Docker Containerization

## Overview

The project has **no Docker setup** — no Dockerfile, no docker-compose, no gateway config, no `.dockerignore`. The goal is to create a single Docker image that, when run, serves the entire application:

- **1 FastAPI backend** (Python/Uvicorn on port 8000 internally)
- **3 React frontends** (pre-built static files served by Caddy)
- **Caddy** as the unified entry point (port 80) — serves static files and reverse-proxies `/api` to the backend

The database (Supabase) is external/hosted, so nothing to containerize there.

### Current State

| Component | Tech | Dev Port | Build Tool |
|-----------|------|----------|------------|
| Backend | FastAPI + Python 3.12 | 8000 | uvicorn |
| Frontend - User | React + Vite | 5173 (default) | `npm run build` → `dist/` |
| Frontend - Admin | React + Vite | 5174 | `npm run build` → `dist/` |
| Frontend - Super Admin | React + Vite | 5173 (default) | `npm run build` → `dist/` |
| Database | Supabase (hosted) | — | External |

All 3 frontends use `VITE_API_BASE_URL=http://localhost:8000` in dev. In Docker, this changes to `/api` (relative path through Caddy).

### Target Architecture

```
┌──────────────────────────────────────────────────┐
│                Docker Container                   │
│                                                   │
│   ┌───────────────────────────────────────────┐   │
│   │              Caddy (:80)                  │   │
│   │                                           │   │
│   │  /          → User frontend (static)      │   │
│   │  /admin     → Admin frontend (static)     │   │
│   │  /super     → Super Admin frontend (static│   │
│   │  /api/*     → proxy_pass :8000            │   │
│   └───────────────────────────────────────────┘   │
│                      │                            │
│                      ▼                            │
│   ┌───────────────────────────────────────────┐   │
│   │         Uvicorn / FastAPI (:8000)         │   │
│   └───────────────────────────────────────────┘   │
│                                                   │
│   ┌───────────────────────────────────────────┐   │
│   │     supervisord (process manager)         │   │
│   └───────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
                       │
                       ▼ (external network)
              Supabase Cloud (DB + Auth + Storage)
```

---

## Subtasks

### Subtask 2.1 — Create `.dockerignore`

**What:** Prevent unnecessary files from being sent to the Docker build context, keeping the image small and builds fast.

**File:** `.dockerignore` (project root)

**Entries to exclude:**
```
.git
.gitignore
*.md
overleaf/
Learning/
backend/.venv/
backend/__pycache__/
backend/.pytest_cache/
backend/app/__pycache__/
backend/app/core/__pycache__/
backend/app/models/__pycache__/
backend/.env
backend/_env
backend/_env1
frontend/Admin/node_modules/
frontend/Admin/dist/
frontend/User/node_modules/
frontend/User/dist/
frontend/Super admin/node_modules/
frontend/Super admin/dist/
.pytest_cache/
DEV_NOTES.ipynb
*.pyc
```

**Risk:** None — purely build optimization.

---

### Subtask 2.2 — Create `requirements.txt` (if not done in Task 1)

**What:** Ensure `backend/requirements.txt` exists with all Python dependencies frozen from the current venv.

**Note:** This may already be completed as Subtask 1.1 of Task 1. If so, skip this.

**Risk:** None.

---

### Subtask 2.3 — Create Caddy Configuration

**What:** Write a `Caddyfile` that serves the 3 frontends as static files and proxies API requests to the backend.

**File:** `Caddyfile` (project root)

**Routing rules:**

| Path | Destination | Notes |
|------|-------------|-------|
| `/` | User frontend `dist/` | SPA — fallback to `index.html` for client-side routing |
| `/admin` | Admin frontend `dist/` | SPA — fallback to `index.html` |
| `/super` | Super Admin frontend `dist/` | SPA — fallback to `index.html` |
| `/api/(.*)` | `http://127.0.0.1:8000/$1` | Strip `/api` prefix, proxy to uvicorn |

**Key considerations:**
- SPA fallback for client-side routing on all 3 apps
- `handle_path /api/*` (or equivalent) to strip `/api` before proxying to uvicorn
- Compression for static assets
- Cache headers for JS/CSS bundles (hashed filenames from Vite)

**Risk:** Low — standard Caddy SPA + reverse proxy pattern.

---

### Subtask 2.4 — Create `supervisord.conf`

**What:** Since we're running 2 processes (Caddy + Uvicorn) in a single container, we need a process manager.

**File:** `supervisord.conf` (project root)

**Processes:**
1. **caddy** — runs in foreground (`caddy run --config /etc/caddy/Caddyfile --adapter caddyfile`)
2. **uvicorn** — runs the FastAPI app (`uvicorn main:app --host 0.0.0.0 --port 8000`)

**Key considerations:**
- `nodaemon=true` so supervisord stays in foreground (Docker requirement)
- Proper stdout/stderr logging to `/dev/stdout` and `/dev/stderr` so `docker logs` works
- Auto-restart on crash for both processes

**Risk:** None — standard pattern for multi-process containers.

---

### Subtask 2.5 — Update Frontend API Base URLs

**What:** The frontends currently hardcode `VITE_API_BASE_URL=http://localhost:8000`. In Docker, API calls go through Caddy at `/api`, so the base URL must change.

**Approach:** Set `VITE_API_BASE_URL=/api` as a build-time argument in the Dockerfile. Vite bakes environment variables into the bundle at build time, so this must be set during `npm run build`.

**Files affected:**
- Build-time env for all three apps:
  - `VITE_API_BASE_URL=/api`
- Verify frontend build path strategy for subpath hosting:
  - Admin bundle must work under `/admin`
  - Super Admin bundle must work under `/super`
- If needed, set Vite `base` per app build target (or equivalent build-time override) so static assets do not conflict under shared Caddy host.
- Update cross-app links that still point to dev ports (if present) to production paths (`/admin`, `/super`) for container runtime.

**Risk:** Medium — API base URL is straightforward, but subpath asset routing must be validated for all 3 bundles.

---

### Subtask 2.6 — Create the Dockerfile (Multi-Stage)

**What:** Write a multi-stage Dockerfile that builds everything into a single image.

**File:** `Dockerfile` (project root)

**Stages:**

#### Stage 1: Frontend Builder (`node:20-alpine`)
```
- WORKDIR /build
- Copy frontend/User, install deps, build with VITE_API_BASE_URL=/api
- Copy frontend/Admin, install deps, build with VITE_API_BASE_URL=/api
- Copy frontend/Super admin, install deps, build with VITE_API_BASE_URL=/api
- Output: 3 dist/ directories ready to copy
```

#### Stage 2: Runtime (`python:3.12-slim`)
```
- Install caddy, supervisor
- Copy requirements.txt, pip install
- Copy backend source code
- Copy built frontend dist files from Stage 1:
    - User dist → /var/www/user/
    - Admin dist → /var/www/admin/
    - Super Admin dist → /var/www/super/
- Copy Caddyfile → /etc/caddy/Caddyfile
- Copy supervisord.conf → /etc/supervisor/conf.d/
- EXPOSE 80
- CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
```

**Key considerations:**
- Build for `linux/amd64` (standard deployment target)
- Use `--no-cache-dir` for pip to keep image small
- Set `PYTHONUNBUFFERED=1` for proper log output
- Working directory for uvicorn must be the backend folder

**Risk:** Medium — multi-stage builds can be tricky with path references. Need to verify all 3 frontends build cleanly in the Node stage.

---

### Subtask 2.7 — Create `docker-compose.yml`

**What:** Provide a convenient way to build and run the container with all required environment variables.

**File:** `docker-compose.yml` (project root)

**Structure:**
```yaml
services:
  app:
    build: .
    ports:
      - "80:80"
    env_file:
      - ./backend/.env
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
```

**Environment variables passed at runtime:**
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SERVICE_ROLE_KEY` (alias)
- `GEMINI_API_KEY`

**Risk:** None — straightforward compose file.

---

### Subtask 2.8 — Build & Test

**What:** Build the Docker image and verify everything works end-to-end.

**Actions:**

1. **Build the image:**
   ```bash
   docker compose build
   ```

2. **Run the container:**
   ```bash
   docker compose up
   ```

3. **Verify backend:**
   - `curl http://localhost/api/` → should return `{"message": "Welcome to Our Application!"}`
   - `curl http://localhost/api/public/colleges` → should return college list

4. **Verify frontends:**
   - `http://localhost/` → User frontend loads
   - `http://localhost/admin` → Admin frontend loads
   - `http://localhost/super` → Super Admin frontend loads

5. **Verify SPA routing:**
   - `http://localhost/admin/dashboard` → should still load Admin frontend (not 404)
   - `http://localhost/super/colleges` → should still load Super Admin frontend (not 404)

6. **Check logs:**
   ```bash
   docker compose logs -f
   ```
   - Caddy access logs visible
   - Uvicorn startup logs visible
   - No import errors or crashes

**Risk:** This is where integration issues surface — wrong paths, missing env vars, build failures.

---

## Constraints & Rules

1. **Single image, single container** — everything runs in one container (Caddy + Uvicorn via supervisord)
2. **External database only** — Supabase is hosted, not containerized
3. **Build-time vs runtime separation** — frontend env vars are build-time (baked into JS bundles), backend env vars are runtime (passed via docker-compose)
4. **No source code changes to backend** — only the Dockerfile and infra configs are new
5. **Frontend deployment-path changes only** — frontend source/build config changes must be limited to deployment routing needs (API base URL, subpath asset base, cross-app route links)
6. **Port 80 exposed** — single entry point for everything
7. **amd64 architecture** — build for standard Linux servers

## Dependencies

- **Task 1 Phase A (Backend Modularization, especially 1.1-1.6)** should be completed first so backend structure and `requirements.txt` are stable.
- **Task 1 UI phases (1.7-1.13)** can run in parallel, but final URL behavior must align with Docker routes (`/`, `/admin`, `/super`, `/api`).
- Docker and Docker Compose must be installed on the build machine
- Node.js 20+ and npm available in the build stage (handled by the Docker image)
- Python 3.12 available in the runtime stage (handled by the Docker image)
