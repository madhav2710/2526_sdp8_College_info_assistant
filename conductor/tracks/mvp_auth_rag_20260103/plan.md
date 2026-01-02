# Track Plan: End-to-End MVP

## Phase 1: Infrastructure & Database Setup [checkpoint: 1b8aab2]

- [x] Task: Database Schema Setup
    - [ ] Subtask: Write SQL migration for Users (with roles), Colleges, Documents, and Chat Messages tables.
    - [ ] Subtask: Apply migration to Supabase.
- [x] Task: Backend Project Initialization
    - [ ] Subtask: Write Tests: Verify FastAPI app initialization and DB connection.
    - [ ] Subtask: Implement Feature: Set up basic FastAPI app structure with Supabase client.
- [x] Task: Conductor - User Manual Verification 'Infrastructure & Database Setup' (Protocol in workflow.md)

## Phase 2: Authentication & Authorization [checkpoint: 8f9b489]

- [x] Task: Auth Endpoints
    - [ ] Subtask: Write Tests: Test login endpoint and token generation.
    - [ ] Subtask: Implement Feature: Create /auth/login and dependency for current user/role.
- [x] Task: Frontend Auth
    - [ ] Subtask: Write Tests: Test Login component rendering and submission.
    - [ ] Subtask: Implement Feature: Create Login page and Auth context provider.
- [x] Task: Conductor - User Manual Verification 'Authentication & Authorization' (Protocol in workflow.md)

## Phase 3: Student Chat Features [checkpoint: 5aad23a]

- [x] Task: Chat Backend
    - [ ] Subtask: Write Tests: Test POST /chat (storage) and GET /chat/history.
    - [ ] Subtask: Implement Feature: Create endpoints to store user messages and return mock response.
- [x] Task: Chat Frontend
    - [ ] Subtask: Write Tests: Test Chat interface rendering and message sending.
    - [ ] Subtask: Implement Feature: Build Chat UI with history view.
- [x] Task: Conductor - User Manual Verification 'Student Chat Features' (Protocol in workflow.md)

## Phase 4: Admin Document Pipeline

- [x] Task: Document Upload Backend
    - [x] Subtask: Write Tests: Test file upload endpoint and permission check.
    - [x] Subtask: Implement Feature: Create POST /admin/upload to save file metadata and trigger background task.
- [x] Task: RAG Processing (Async)
    - [x] Subtask: Write Tests: Test text extraction and embedding generation (mocked).
    - [x] Subtask: Implement Feature: Implement background task for text extraction and Supabase vector storage.
- [x] Task: Admin Dashboard Frontend
    - [x] Subtask: Write Tests: Test Dashboard render and file upload interaction.
    - [x] Subtask: Implement Feature: Build Admin Dashboard for file upload and status viewing.
- [~] Task: Conductor - User Manual Verification 'Admin Document Pipeline' (Protocol in workflow.md)      
## Phase 5: Super Admin & Polish

- [ ] Task: Super Admin Backend
    - [ ] Subtask: Write Tests: Test GET /superadmin/colleges.
    - [ ] Subtask: Implement Feature: Create endpoints for managing colleges/admins.
- [ ] Task: Super Admin Frontend
    - [ ] Subtask: Write Tests: Test Super Admin view.
    - [ ] Subtask: Implement Feature: Build Super Admin Dashboard.
- [ ] Task: Rate Limiting
    - [ ] Subtask: Write Tests: Test rate limit triggers.
    - [ ] Subtask: Implement Feature: Add rate limiting middleware to FastAPI.
- [ ] Task: Conductor - User Manual Verification 'Super Admin & Polish' (Protocol in workflow.md)

