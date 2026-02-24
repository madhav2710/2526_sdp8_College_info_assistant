# Task 1B: Admin + Super Admin UI/UX Refactor - Swiss Console

## Scope

Implement a shared operations-console UI language for both admin apps based on:
- `frontend/ADMIN_SUPERADMIN_SWISS_CONSOLE_DESIGN.md`

Primary code surface:
- `frontend/Admin/src/index.css`
- `frontend/Admin/src/App.jsx`
- `frontend/Super admin/src/index.css`
- `frontend/Super admin/src/App.jsx`

## Execution Steps

### 1B.1 Shared Token System

- Add Swiss Console CSS variables to both app stylesheets.
- Apply common font system:
  - IBM Plex Sans (UI)
  - IBM Plex Mono (numeric/metadata)
- Define shared utility classes for labels, metadata, badges, table density.

### 1B.2 Page Shell + Layout Rhythm

- Standardize page shell with consistent spacing scale.
- Ensure strict left-aligned structure and consistent column rhythm.
- Replace rounded-marketing cards with lower-radius operational panels.

### 1B.3 Sidebar + Header Language

- Implement dark console sidebar with:
  - quiet text
  - active row marker (accent bar)
- Keep top header concise:
  - title
  - subtitle
  - compact identity block

### 1B.4 Status + Action Standardization

- Normalize status badge components and semantic color usage.
- Ensure mandatory statuses have uniform shape and icon usage.
- Normalize button hierarchy:
  - primary / secondary / destructive
- Ensure icon-only actions include tooltip/title + accessible labels.

### 1B.5 Data-Dense Views

- Prioritize table-first layouts for operational datasets.
- Ensure compact but accessible row heights.
- Implement truncation strategy for long filename/email values.
- Keep key controls near tables (search/filter/primary action).

### 1B.6 Modal & Form Structure

- Use flat structured modal forms.
- Keep footer actions consistent:
  - Cancel left
  - Submit right
- Reduce heavy backdrop blur.
- Show inline validation near form controls.

### 1B.7 App-Specific Emphasis

#### Admin app (`frontend/Admin`)

- Keep document queue and upload lifecycle visually dominant.
- Keep query history metrics readable and operational.

#### Super admin app (`frontend/Super admin`)

- Keep pending approvals and governance actions dominant.
- Ensure admin/college management actions remain one-click accessible.

### 1B.8 Responsive + Accessibility

- Validate desktop-first behavior and tablet fallback.
- On <1024px:
  - sidebar collapses gracefully
  - key controls remain above datasets
- Validate keyboard focus flow and visible focus rings.
- Validate contrast for table text and status elements.

### 1B.9 Functional Regression Checks

- Admin:
  - login, upload, documents, query history, notifications
- Super admin:
  - login, pending approvals, colleges CRUD, admins CRUD, stats/documents views

## Definition of Done

- Both admin apps read as one shared Swiss Console control surface.
- Status + actions are scannable in under 2 seconds.
- Decorative excess and inconsistent visual language are removed.
- Existing workflows and backend integrations remain unchanged.
