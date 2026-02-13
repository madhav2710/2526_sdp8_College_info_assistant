# CollegeInfo-Agent

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/API-FastAPI-teal)
![React](https://img.shields.io/badge/Frontend-React-%2361DAFB)
![Supabase](https://img.shields.io/badge/Backend-Supabase-3ECF8E)
![pgvector](https://img.shields.io/badge/VectorDB-pgvector-blueviolet)

## Overview

CollegeInfo-Agent is a multi-college academic assistant built with a FastAPI backend and React frontends (User, College Admin, Super Admin).

It ingests college documents (PDF/DOCX/TXT), processes them into embeddings, and answers questions through RAG.

## Current Architecture (Important Update)

- The project no longer uses ChromaDB.
- Vector storage is now in Supabase Postgres using `pgvector` (`public.document_chunks.embedding VECTOR(768)`).
- The previous split Supabase setup has been merged into a single unified Supabase project.
- One Supabase project now handles:
  - Auth (`auth.users`)
  - Relational data (`public.*` tables)
  - Storage bucket (`documents`)
  - Vector data + similarity search (`pgvector`)

This is enforced in code (`backend/app/core/database.py`) and migrations (`backend/migrations/000_unified_single_project_schema.sql`).

## Key Features

- RAG-based Q&A with source snippets.
- College-scoped retrieval (queries filtered by `college_id`).
- Native vector retrieval via Supabase RPC `match_documents(...)` with Python fallback similarity search.
- College admin document upload and query-history view.
- Super admin approval workflow for documents.
- Document lifecycle states:
  - `uploaded -> pending_approval -> approved/rejected -> processing -> completed/failed`
- Optional processing modes after approval:
  - `immediate`, `scheduled`, `manual`
- Notification system for document events:
  - uploaded, approved, rejected, processed, failed
- Guest chat endpoint (`/guest-chat`) with graceful fallback when RAG is unavailable.

## Tech Stack

- Backend: FastAPI
- Database/Auth/Storage: Supabase
- Vector DB: pgvector on Supabase Postgres
- AI models: Google Gemini (embeddings + generation)
- PDF extraction: `pypdf`
- Frontend: React + Vite + Tailwind (three separate apps)

## Repository Layout

```text
backend/
  main.py
  app/core/
  migrations/
  run_migration.py
  tests/

frontend/
  User/
  Admin/
  Super admin/
```

## Database Schema (Unified Supabase Project)

Primary tables created in `backend/migrations/000_unified_single_project_schema.sql`:

- `public.colleges`
- `public.profiles`
- `public.users` (compatibility table)
- `public.admins` (compatibility table)
- `public.documents`
- `public.document_chunks` (with `VECTOR(768)`)
- `public.conversations`
- `public.messages`
- `public.notifications`
- `public.document_approvals`
- `public.document_status_history`

Also includes:

- `CREATE EXTENSION IF NOT EXISTS vector`
- HNSW/auxiliary indexes for vector search
- RPC functions such as `public.match_documents(...)`
- RLS policies for multi-tenant access control

## Local Setup

### 1) Backend configuration

```bash
cp backend/.env.example backend/.env
```

Fill required values in `backend/.env`:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `JWT_SECRET_KEY`
- `GEMINI_API_KEY` (required for full RAG responses)

Single-project note:

- Do not point any `RAG_SUPABASE_*`, `SUPABASE_RAG_*`, or `VECTOR_SUPABASE_*` vars to a different project.

### 2) Run DB migrations

From `backend/`:

```bash
python run_migration.py --plan current-all
```

### 3) Start backend

From `backend/`:

```bash
uvicorn main:app --reload --port 8000
```

### 4) Start frontends

Each frontend reads `VITE_API_BASE_URL` (see each `.env.example`).

User app:

```bash
cd frontend/User
npm install
npm run dev
```

Admin app (configured for port `5174`):

```bash
cd frontend/Admin
npm install
npm run dev
```

Super Admin app (default Vite port; use a different port if needed):

```bash
cd "frontend/Super admin"
npm install
npm run dev -- --port 5175
```

## API Surface (High Level)

- Auth: `/auth/signup`, `/auth/login`
- User chat/history: `/chat/`, `/chat/history/`, `/chat/conversation/{id}/messages`
- Guest chat: `/guest-chat`
- College admin: `/admin/upload`, `/admin/documents`, `/admin/query-history`, `/admin/trigger-rag-processing`
- Super admin approvals/workflow:
  - `/super-admin/pending-documents`
  - `/super-admin/approve-document`
  - `/super-admin/reject-document`
  - `/super-admin/schedule-document-processing`
  - `/super-admin/trigger-processing`
- Super admin management:
  - `/superadmin/stats`
  - `/superadmin/colleges*`
  - `/superadmin/admins*`
  - `/superadmin/documents`
- Notifications:
  - `/notifications`
  - `/notifications/{notification_id}/read`
  - `/notifications/{notification_id}`
  - `/notifications/unread-count`

## Tests

From `backend/`:

```bash
pytest
```
