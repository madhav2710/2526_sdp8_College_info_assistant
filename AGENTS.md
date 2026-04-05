# AGENTS.md - Project Guide for AI Coding Agents

> This document provides essential context for AI coding agents working on the CollegeInfo-Agent project.
> Read this file before making any changes to understand project structure, conventions, and constraints.

## Project Overview

**CollegeInfo-Agent** is a multi-college academic assistant platform built with:
- **Backend**: FastAPI (Python 3.10+) with modular architecture
- **Frontend**: Three separate React 18 + Vite 5 applications:
  - User app (student/guest chat interface)
  - Admin app (college admin portal)
  - Super Admin app (platform management console)
- **Database/Auth/Storage**: Supabase (PostgreSQL + pgvector + Auth + Storage)
- **AI**: Google Gemini API (text-embedding-004, gemini-2.0-flash-exp)
- **Deployment**: Docker with Caddy reverse proxy, AWS ECS via Copilot

### Core Purpose
The platform ingests college documents (PDF/DOCX/TXT), processes them into vector embeddings (768-dim), and answers student questions through a RAG (Retrieval-Augmented Generation) pipeline with college-scoped retrieval.

---

## Architecture Principles

### 1. Single Supabase Project (Enforced)
- The application uses **one unified Supabase project** for auth, relational data, storage, and vector data
- DO NOT configure separate `RAG_SUPABASE_*`, `SUPABASE_RAG_*`, or `VECTOR_SUPABASE_*` variables
- The system validates at startup that all Supabase operations use the same project
- Vector storage uses `pgvector` extension with `public.document_chunks.embedding VECTOR(768)`

### 2. Modular Backend (Recent Refactor)
- Backend was refactored from a 3,594-line `main.py` monolith to domain-coupled modules
- **Principle**: Keep strongly coupled logic together. Group functions that change together into the same service module.
- Route handlers are thin; domain logic lives in services
- Avoid creating tiny single-function files

### 3. Domain-Coupled Module Organization
- `chat_service.py` - Rate limiting + chat orchestration helpers
- `document_service.py` - File validation/hash + document processing orchestration
- `governance_service.py` - Superadmin/admin/college management query helpers

### 4. Graceful Degradation
- RAG failures fall back to basic responses via `generate_basic_response()`
- Circuit breaker pattern in health manager for service resilience
- Application continues to function even when AI services are unavailable

---

## Project Structure

```
backend/
├── main.py                    # FastAPI entry point + middleware + router registration
├── requirements.txt           # Python dependencies (frozen)
├── run_migration.py           # Database migration runner
├── seed_default_data.py       # Default data seeder
├── .env / .env.example        # Environment configuration
├── app/
│   ├── core/                  # Core business logic
│   │   ├── auth.py            # Authentication & authorization
│   │   ├── basic_chat.py      # Fallback chat responses
│   │   ├── config.py          # Configuration management (dataclasses + validation)
│   │   ├── database.py        # Supabase client initialization
│   │   ├── notifications.py   # Notification system
│   │   ├── rag.py             # RAG pipeline & vector search (KEEP INTACT)
│   │   └── workflow.py        # Document workflow state machine
│   ├── routers/               # API route handlers (thin orchestration)
│   │   ├── admin.py           # College admin endpoints
│   │   ├── auth.py            # Auth endpoints
│   │   ├── chat.py            # Chat endpoints
│   │   ├── notifications.py   # Notification endpoints
│   │   ├── superadmin.py      # Super admin endpoints
│   │   ├── system.py          # System health & config endpoints
│   │   └── user.py            # User profile endpoints
│   ├── schemas/               # Pydantic request/response schemas
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── chat.py
│   │   ├── college.py
│   │   └── document.py
│   ├── services/              # Business logic services (domain-coupled)
│   │   ├── chat_service.py
│   │   ├── document_service.py
│   │   ├── governance_service.py
│   │   └── __init__.py
│   ├── models/                # Database models/ORM
│   │   ├── notification.py
│   │   └── __init__.py
│   └── legacy_main.py         # Legacy code reference (do not use)
├── migrations/                # SQL migration scripts
│   ├── 000_unified_single_project_schema.sql
│   ├── 000_unified_single_project_schema_check.sql
│   ├── 001_repair_auth_foreign_keys.sql
│   └── 008_fix_notify_document_status_change_case.sql
└── tests/                     # Pytest test suite
    ├── test_admin.py
    ├── test_app_init.py
    ├── test_auth.py
    ├── test_chat.py
    └── test_rag.py

frontend/
├── User/                      # Student/guest chat interface
│   ├── package.json           # React 18 + Vite 5 + Tailwind CSS 3
│   ├── vite.config.js
│   ├── .env.example           # VITE_API_BASE_URL
│   └── src/
├── Admin/                     # College admin portal
│   ├── package.json           # React 18 + Vite 6 + Vitest
│   ├── vite.config.js
│   ├── .env.example
│   └── src/
└── Super admin/               # Super admin console (note: space in path)
    ├── package.json           # React 18 + Vite 5
    ├── vite.config.js
    ├── .env.example
    └── src/

copilot/                       # AWS Copilot deployment configs
├── api/manifest.yml
├── user-frontend/manifest.yml
└── environments/

scripts/
└── manual_docker_check.sh     # Docker deployment verification

# Root configuration files
Dockerfile                     # Multi-stage build (Node.js + Python + Caddy)
docker-compose.yml             # Local deployment
Caddyfile                      # Reverse proxy configuration
supervisord.conf               # Process management (Caddy + Uvicorn)
```

---

## Key Configuration Files

### Backend: `.env` (Required Variables)

```bash
# Required
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_KEY=YOUR_SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SUPABASE_SERVICE_ROLE_KEY
JWT_SECRET_KEY=REPLACE_WITH_LONG_RANDOM_SECRET_MIN_32_CHARS

# Required for full RAG functionality
GEMINI_API_KEY=YOUR_GEMINI_API_KEY

# Optional (have defaults)
RAG_CHUNK_SIZE=1500
RAG_CHUNK_OVERLAP=300
RAG_SIMILARITY_THRESHOLD=0.7
RAG_MAX_CHUNKS_PER_QUERY=5
MAX_FILE_SIZE_MB=50
ALLOWED_FILE_EXTENSIONS=.pdf,.doc,.docx,.txt
DEFAULT_RATE_LIMIT_PER_MINUTE=60
APP_NAME=College Platform API
APP_VERSION=1.0.0
DEBUG=false
LOG_LEVEL=INFO
```

### Frontend: `.env` Files

Each frontend requires `VITE_API_BASE_URL`:
```bash
# User app
VITE_API_BASE_URL=http://localhost:8000

# Admin app
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_BASE=/admin/

# Super Admin app
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_BASE=/super/
```

---

## Build and Run Commands

### Backend Development

```bash
cd backend/

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python run_migration.py --plan current-all

# Optional: Seed default data
python seed_default_data.py

# Start development server
uvicorn main:app --reload --port 8000
```

### Frontend Development

```bash
# User app
cd frontend/User
npm install
npm run dev          # Runs on default Vite port (5173)

# Admin app
cd frontend/Admin
npm install
npm run dev          # Configured for port 5174

# Super Admin app
cd "frontend/Super admin"
npm install
npm run dev -- --port 5175
```

### Docker (Production-like)

```bash
# From project root
docker compose build
docker compose up -d

# Verify
curl http://localhost/api/
curl http://localhost/api/public/colleges

# Access points:
# - http://localhost/          (User)
# - http://localhost/admin/    (Admin)
# - http://localhost/super/    (Super Admin)

# View logs
docker compose logs -f app

# Shutdown
docker compose down
```

### Testing

```bash
cd backend/
pytest

# With coverage (if configured)
pytest --cov=app
```

---

## Code Style Guidelines

### Python (Backend)

1. **Imports**: Group in this order:
   - Standard library imports
   - Third-party imports (FastAPI, Pydantic, etc.)
   - Local app imports (absolute from `app.module`)

2. **Type Hints**: Use type hints for function signatures and return types

3. **Error Handling**:
   - Use custom exceptions from `app.core.config`: `ConfigurationError`, `ConfigValidationError`
   - RAG errors: `RAGError`, `EmbeddingServiceError`, `VectorStoreError`
   - Log errors with `logger = logging.getLogger(__name__)`
   - Use `logger.exception()` for stack traces in exception handlers

4. **Configuration Access**:
   ```python
   from app.core.config import get_system_config
   config = get_system_config()
   rag_config = config.rag
   ```

5. **Database Client**:
   ```python
   from app.core.database import supabase, get_service_client
   # For user operations: supabase (uses anon key)
   # For admin operations: get_service_client() (uses service role key)
   ```

6. **Router Registration** (in `main.py`):
   ```python
   from app.routers import auth, user, chat, admin, superadmin, notifications, system
   app.include_router(auth.router, prefix="/auth", tags=["auth"])
   ```

### JavaScript/React (Frontend)

1. **All frontends use**: React 18, Vite 5+, Tailwind CSS 3, Lucide React icons
2. **Styling**: Tailwind utility classes (no CSS modules)
3. **Icons**: Use `lucide-react` for all icons
4. **Environment**: Access via `import.meta.env.VITE_*`
5. **Build outputs**: Each frontend builds to `dist/` directory

---

## Testing Strategy

### Backend Tests (`backend/tests/`)

- **Framework**: pytest + pytest-asyncio
- **Client**: FastAPI TestClient
- **Mocking**: Use `unittest.mock.patch` for Supabase operations
- **Coverage**:
  - Authentication flows (signup, login, token validation)
  - Chat endpoints (authenticated & guest)
  - RAG pipeline (document processing, vector search, fallback)
  - Admin workflows (upload, document management)
  - Application initialization

### Running Tests

```bash
cd backend/
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest tests/test_auth.py # Specific test file
pytest -k "test_login"    # Tests matching pattern
```

### Frontend Tests

- **Admin app** has Vitest configured: `npm test`
- User and Super Admin apps currently have no test setup

---

## Database Schema (Key Tables)

### Core Tables

| Table | Purpose |
|-------|---------|
| `public.colleges` | College information (name, code, domain, etc.) |
| `public.profiles` | User profiles linked to auth.users (role, college_id) |
| `public.users` | Compatibility table for legacy code paths |
| `public.admins` | Compatibility table for admin relationships |

### Document Workflow Tables

| Table | Purpose |
|-------|---------|
| `public.documents` | Document metadata with status workflow |
| `public.document_chunks` | Vector chunks (768-dim) for RAG |
| `public.document_approvals` | Approval/rejection audit trail |
| `public.document_status_history` | Status change history |

### Chat Tables

| Table | Purpose |
|-------|---------|
| `public.conversations` | Chat conversation headers |
| `public.messages` | Individual messages with sources metadata |

### Notification System

| Table | Purpose |
|-------|---------|
| `public.notifications` | User notifications for document events |

### Document Status Workflow

```
uploaded → pending_approval → approved → processing → completed
                              ↘ rejected
                              ↘ failed
```

Processing modes after approval: `immediate`, `scheduled`, `manual`

---

## Security Considerations

### Authentication
- JWT tokens with configurable expiration (default 30 minutes)
- Supabase Auth for user management with email confirmation
- Role-based access: `student`, `college_admin`, `super_admin`

### Authorization
- `get_current_user` dependency validates JWT and returns user dict
- College-scoped queries: All document/chat queries filter by `college_id`
- Super admin endpoints check for `super_admin` role

### File Upload Security
- Size limits (default 50MB)
- MIME type validation (PDF, DOCX, TXT)
- Duplicate detection via SHA256 file hash
- PDF corruption checks using pypdf

### CORS
- Currently open for development (`allow_origins=["*"]`)
- Configure restricted origins for production

### Secrets Management
- All secrets via environment variables
- Service role key only used server-side
- JWT secret minimum 32 characters

---

## Common Development Tasks

### Adding a New API Endpoint

1. Determine domain (auth, chat, admin, etc.)
2. Add Pydantic schema to `app/schemas/{domain}.py`
3. Add business logic to `app/services/{domain}_service.py` if complex
4. Add route to `app/routers/{domain}.py`
5. Import and include router in `main.py` (if new router)
6. Add tests to `backend/tests/test_{domain}.py`

### Running Database Migrations

```bash
cd backend/
python run_migration.py --plan current-all
```

Migration plans:
- `current`: Basic schema + checks
- `current-all`: All current migrations
- `schema`: Just schema bootstrap
- `check`: Just validation checks

### Adding Environment Variables

1. Add to `backend/.env.example`
2. Add to `app/core/config.py` in appropriate dataclass
3. Add validation in dataclass's `validate()` method
4. Load from environment in `ConfigurationManager.load_from_environment()`

### Document Processing Pipeline

To manually trigger RAG processing for testing:

```bash
curl -X POST http://localhost:8000/admin/trigger-rag-processing \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"document_id": "uuid-here"}'
```

---

## Troubleshooting

### Backend won't start
- Check `.env` file has all required variables
- Verify Supabase credentials are correct
- Run migrations: `python run_migration.py --plan current-all`
- Check for configuration validation errors in logs

### RAG not working / Always getting fallback responses
- Verify `GEMINI_API_KEY` is set and valid
- Check document status is `completed` (not `pending_approval` or `processing`)
- Verify documents have chunks: query `public.document_chunks` table
- Check system health: `GET /system/health`
- Reset circuit breaker: `POST /system/health/reset`

### Upload fails
- Check file size is under limit (default 50MB)
- Verify file type is allowed (PDF, DOCX, TXT)
- For PDFs, ensure file is not corrupted
- Check Supabase storage bucket `documents` exists

### Frontend can't connect to backend
- Verify `VITE_API_BASE_URL` in frontend `.env` files
- Check CORS settings in `backend/main.py`
- Ensure backend is running on expected port

---

## Deployment

### Docker (Local/Single Server)
- Multi-stage Dockerfile builds all frontends + backend
- Caddy serves static files and reverse proxies `/api` to Uvicorn
- Supervisor manages both Caddy and Uvicorn processes
- See `docker-compose.yml` for configuration

### AWS ECS (Production)
- AWS Copilot CLI for infrastructure management
- See `AWS_ECS_DEPLOYMENT_GUIDE.md` for detailed instructions
- Fargate for container orchestration
- ECR for container registry
- Application Load Balancer for traffic distribution

---

## Important Notes for AI Agents

1. **Do NOT split RAG module** (`app/core/rag.py`) into micro-files. Keep it intact.

2. **Do NOT create single-function service files**. Group related functionality.

3. **Always validate configuration** when adding new env vars. Add to `app/core/config.py`.

4. **Use existing patterns**:
   - Copy existing router structure for new endpoints
   - Follow existing error handling patterns
   - Use existing Pydantic schema patterns

5. **Test your changes**:
   - Run `pytest` in backend directory
   - Test both success and error cases
   - Mock external services (Supabase, Gemini)

6. **Document changes**:
   - Update relevant `.md` files if architecture changes
   - Add docstrings to new functions
   - Update `.env.example` for new environment variables

7. **Frontend consistency**:
   - All three frontends use Tailwind CSS
   - Use Lucide React for icons
   - Follow existing component patterns

8. **Database migrations**:
   - New migrations should be idempotent (`IF NOT EXISTS`)
   - Update `run_migration.py` MIGRATION_PLANS if adding new migration files

9. **Security**:
   - Never commit `.env` files
   - Never log sensitive data (use `***REDACTED***` pattern from config.py)
   - Always use parameterized queries (Supabase client handles this)

10. **Error handling**:
    - Use appropriate HTTP status codes
    - Return meaningful error messages
    - Log errors for debugging
