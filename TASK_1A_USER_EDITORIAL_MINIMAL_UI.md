# Task 1A: User UI/UX Refactor - Editorial Minimal

## Scope

Implement the user-facing UI redesign based on:
- `frontend/USER_EDITORIAL_MINIMAL_DESIGN.md`

Primary code surface:
- `frontend/User/src/index.css`
- `frontend/User/src/App.jsx`
- `frontend/User/src/components/ChatInterface.jsx`
- `frontend/User/src/components/ChatHistorySidebar.jsx`
- `frontend/User/src/components/Login.jsx`
- `frontend/User/src/components/ProfileCard.jsx`
- `frontend/User/src/components/MarkdownRenderer.jsx`

## Execution Steps

### 1A.1 Typography + Token Foundation

- Add Google Font loading (`Newsreader`, `Manrope`, `IBM Plex Mono`) with `display=swap`.
- Add preconnect hints for `fonts.googleapis.com` and `fonts.gstatic.com`.
- Define Editorial Minimal CSS token block in `frontend/User/src/index.css`.
- Establish shared typography utility classes:
  - display, h1, h2, h3, body-lg, body, small, meta.

### 1A.2 Global Surfaces + Motion Rules

- Replace gradient-heavy globals with paper-like layer system:
  - canvas, surface, subtle.
- Apply shadow policy from design spec.
- Normalize radii:
  - surfaces 16px, controls 12px, chips full-pill.
- Restrict animations to allowed set and durations.

### 1A.3 App Shell Refactor

- Refactor header to low-height restrained branding.
- Remove loud hero gradients and decorative glow patterns.
- Preserve current behavior for auth gating and role redirects.

### 1A.4 Chat Layout Refactor

- Constrain main assistant content readability width (65-75 chars equivalent).
- Ensure vertical rhythm:
  - message gap 20px
  - section gap 24px
- Keep input dock anchored and editorial in tone.
- Restyle user/assistant bubbles per spec.

### 1A.5 Sidebar Refactor

- Keep sidebar darker than content but not pure black.
- Add subtle active marker and restrained contrast.
- Preserve current collapse/open behavior.

### 1A.6 Markdown Rendering System

- Centralize markdown visual hierarchy in `MarkdownRenderer.jsx`.
- Apply spec for:
  - headings
  - paragraphs
  - list spacing/indents
  - blockquotes
  - inline code + fenced code
  - links
- Ensure markdown remains robust for mixed plain text + markdown responses.

### 1A.7 Empty State + Supporting Components

- Replace generic suggestion chips with 2-3 high quality prompt starters.
- Keep empty state quiet: one icon, one heading, one paragraph.
- Refactor login/profile panels into same editorial language.

### 1A.8 Accessibility + Responsiveness

- Validate at 360px / 768px / 1440px.
- Ensure focus states are visible and keyboard navigation remains intact.
- Verify touch targets >= 40px.
- Verify contrast requirements for text and headings.

### 1A.9 Functional Regression Checks

- Guest flow:
  - college selection -> guest chat
- Authenticated flow:
  - login -> chat -> history -> conversation restore
- Error states:
  - backend unavailable
  - rate limit messages

## Definition of Done

- Editorial Minimal visual language is consistently applied.
- No gradient-heavy AI-template visuals remain.
- Assistant messages read as publication-quality text blocks.
- Existing chat behavior remains unchanged.
