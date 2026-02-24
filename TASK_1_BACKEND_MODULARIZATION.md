# Task 1: Backend Modularization + UI/UX Refactor (Phased)

## Overview

The project currently has two structural problems:

1. Backend logic is concentrated in a **3,594-line `backend/main.py`** monolith.
2. Frontend visual systems are inconsistent and heavily utility-class driven, with no shared design-token architecture.

This task now covers both:

- **Phase A**: Backend modularization with zero API contract changes.
- **Phase B**: User app UI/UX refactor to Editorial Minimal.
- **Phase C**: Admin + Super Admin UI/UX unification to Swiss Console.

The backend refactor must follow a strict principle: **keep strongly coupled logic together**. Do not split into tiny single-function files.

---

## Architectural Principle (Updated)

### Service extraction strategy

Use **domain-coupled modules**, not one-file-per-helper:

- Group functions that change together into the same service module.
- Keep route orchestration thin; move domain logic into services.
- Keep `app/core/rag.py` intact in this phase (no micro-splitting yet).
- Avoid creating a file for each tiny utility function.

### What this means in practice

Prefer this:
- `chat_service.py` (rate limiting + chat orchestration helpers)
- `document_service.py` (file validation/hash + document processing orchestration)
- `governance_service.py` (superadmin/admin/college management query helpers)

Avoid this:
- `rate_limit_service.py`, `hash_service.py`, `validation_service.py`, etc. as separate micro files.

---

## Current State Snapshot

| Area | Current State |
|------|---------------|
| Backend entrypoint | `backend/main.py` (3,594 lines) |
| Backend routes | 40 endpoints defined in one file |
| Pydantic models in `main.py` | 15 models |
| Existing core modules | `app/core/*` already contains auth, config, database, rag, notifications, workflow |
| User frontend | Gradient-heavy chat-first UI with mixed typography system |
| Admin frontend | Standalone style language, no shared token system |
| Super admin frontend | Separate style language from admin |

---

## Target State

```text
backend/
├── app/
│   ├── core/                    # Keep existing modules intact
│   ├── routers/
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── chat.py
│   │   ├── admin.py
│   │   ├── superadmin.py
│   │   ├── notifications.py
│   │   └── system.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── chat.py
│   │   ├── admin.py
│   │   ├── document.py
│   │   └── college.py
│   ├── services/
│   │   ├── chat_service.py
│   │   ├── document_service.py
│   │   ├── governance_service.py
│   │   └── __init__.py
│   └── models/
├── main.py                      # app init + middleware + router registration
└── requirements.txt

frontend/
├── USER_EDITORIAL_MINIMAL_DESIGN.md
├── ADMIN_SUPERADMIN_SWISS_CONSOLE_DESIGN.md
└── (UI updates applied to User/Admin/Super admin apps)
```

---

## Subtasks

### Subtask 1.1 - Generate `backend/requirements.txt`

**What:** Freeze the current backend venv dependencies for reproducibility.

**Actions:**
- Run `backend/.venv/bin/pip freeze > backend/requirements.txt`
- Verify package list is complete (current environment is ~123 packages)

**Risk:** None (additive).

---

### Subtask 1.2 - Extract Pydantic Schemas into `app/schemas/`

**What:** Move all `BaseModel` definitions from `main.py` into domain schema modules.

**Important:** Current code contains **15** models in `main.py`; include all models still referenced by handlers.

**Suggested files:**
- `app/schemas/auth.py`
- `app/schemas/chat.py`
- `app/schemas/admin.py`
- `app/schemas/document.py`
- `app/schemas/college.py`
- `app/schemas/__init__.py`

**Risk:** Low (move + import updates).

---

### Subtask 1.3 - Extract Services by Domain Coupling (Updated)

**What:** Move route-adjacent business logic out of route handlers into **domain-coupled services**.

**Service grouping:**
- `app/services/chat_service.py`
  - Chat rate limiting state and helpers
  - Chat response assembly/shared chat utility logic
- `app/services/document_service.py`
  - `get_file_config()`, `validate_file()`, `calculate_file_hash()`
  - `_trigger_rag_processing_with_status_tracking()` and document workflow helpers
- `app/services/governance_service.py`
  - Shared college/admin/superadmin management query helpers

**Explicit non-goal for this task:**
- Do not split `app/core/rag.py` into many files yet.

**Risk:** Low-medium (import correctness + keeping behavior identical).

---

### Subtask 1.4 - Create Route Modules in `app/routers/`

**What:** Move endpoints into APIRouter modules by domain.

**Router mapping:**
- `auth.py`: `/auth/*`
- `user.py`: `/user/*`
- `chat.py`: `/chat/*`, `/guest-chat`
- `admin.py`: `/admin/*`
- `superadmin.py`: `/super-admin/*`, `/superadmin/*`
- `notifications.py`: `/notifications/*`
- `system.py`: `/config/*`, `/system/*`, `/public/*`, `/`, `/student/{id}`

**Risk:** Medium (must preserve exact paths/methods).

---

### Subtask 1.5 - Slim `main.py` + Preserve Test Compatibility

**What:** Reduce `main.py` to startup/config/middleware/router registration.

**Additional requirement:** existing tests currently patch `main.*` symbols. Preserve compatibility by either:
- Updating tests to patch new module paths, or
- Re-exporting required symbols in `main.py` temporarily during migration.

**Risk:** Medium (test coupling to `main` namespace).

---

### Subtask 1.6 - Backend Validation & Regression

**Checks:**
- `python -c "from main import app"`
- Run backend tests (`backend/tests/`)
- Verify all endpoint URLs/methods unchanged
- Verify auth dependency behavior unchanged

**Risk:** Medium (catches integration mistakes).

---

### Subtask 1.7 - User App Design Token Foundation (Editorial Minimal)

**Source of truth:** `frontend/USER_EDITORIAL_MINIMAL_DESIGN.md`

**What:** Introduce typography, color tokens, spacing rhythm, and motion constraints in:
- `frontend/User/src/index.css`

**Includes:**
- Newsreader + Manrope + IBM Plex Mono integration
- CSS variable token block from design doc
- Global type scale and focus-state primitives

**Risk:** Low.

---

### Subtask 1.8 - User App UI Refactor (Editorial Minimal)

**Source of truth:** `frontend/USER_EDITORIAL_MINIMAL_DESIGN.md`

**Primary files:**
- `frontend/User/src/App.jsx`
- `frontend/User/src/components/ChatInterface.jsx`
- `frontend/User/src/components/ChatHistorySidebar.jsx`
- `frontend/User/src/components/Login.jsx`
- `frontend/User/src/components/ProfileCard.jsx`

**Goals:**
- Remove gradient-heavy visual style
- Establish calm text-first hierarchy
- Keep chat readable with constrained line length and editorial pacing
- Update empty states, message bubbles, source cards, and input dock behavior

**Risk:** Medium (large visual diff, must keep behavior intact).

---

### Subtask 1.9 - User Markdown Styling Consolidation

**Primary file:**
- `frontend/User/src/components/MarkdownRenderer.jsx`

**What:** Match heading, paragraph, list, blockquote, link, inline code, and code-block styles to Editorial Minimal spec.

**Risk:** Low-medium (readability + rendering edge cases).

---

### Subtask 1.10 - Admin + Super Admin Token Unification (Swiss Console)

**Source of truth:** `frontend/ADMIN_SUPERADMIN_SWISS_CONSOLE_DESIGN.md`

**Primary files:**
- `frontend/Admin/src/index.css`
- `frontend/Super admin/src/index.css`

**What:** Add shared token system and typography primitives for both apps.

**Risk:** Low.

---

### Subtask 1.11 - Admin + Super Admin Visual System Refactor

**Source of truth:** `frontend/ADMIN_SUPERADMIN_SWISS_CONSOLE_DESIGN.md`

**Primary files:**
- `frontend/Admin/src/App.jsx`
- `frontend/Super admin/src/App.jsx`

**Goals:**
- Convert to consistent operations-console language
- Remove decorative/marketing-style surfaces
- Standardize status badges, action button hierarchy, modal structure, table density
- Ensure both apps feel like one shared control surface

**Risk:** Medium-high (large UI surface area).

---

### Subtask 1.12 - Cross-App Responsive + Accessibility Pass

**What:** Validate all updated UIs at:
- `360px`, `768px`, `1440px`

**Checks:**
- Keyboard navigation
- Focus ring visibility
- Minimum touch targets
- Text contrast and readability

**Risk:** Medium.

---

### Subtask 1.13 - Final Verification (Backend + UI)

**What:** Validate functionally and visually with no API/behavior regressions.

**Checks:**
- Backend import/tests
- Frontend builds for all 3 apps
- Manual smoke flows:
  - User chat + history
  - Admin upload/documents/history
  - Super admin approvals/admin/college management

**Risk:** Medium.

---

## Companion Task Docs (Detailed UI Execution)

For implementation-level UI details, use:
- `TASK_1A_USER_EDITORIAL_MINIMAL_UI.md`
- `TASK_1B_ADMIN_SUPERADMIN_SWISS_CONSOLE_UI.md`

These expand subtasks 1.7-1.12 into concrete checklists.

---

## Constraints & Rules

1. **Backend API contracts unchanged** (URL, method, request/response shape).
2. **Backend behavior unchanged** (structural refactor only).
3. **Service extraction is domain-coupled** (no micro-file fragmentation).
4. **No RAG micro-split in this pass**; keep `app/core/rag.py` intact.
5. **UI changes are visual/UX only**; no backend API rewrites required.
6. **Admin + Super Admin must share one design language** after refactor.
7. **Complete in phased order**: backend core first, then UI tracks, then full validation.
