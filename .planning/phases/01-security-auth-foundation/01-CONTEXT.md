# Phase 1: Security & Auth Foundation - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Harden the existing FastAPI app against three known high-severity vulnerabilities (wildcard CORS, filename path traversal, innerHTML XSS), then add JWT-based user authentication — register, login, logout, session management, and account/purchase history page. All existing API routes become protected. The app is not usable by external users until this phase is complete.

</domain>

<decisions>
## Implementation Decisions

### Login UI
- **D-01:** Auth wall — when unauthenticated, the entire app is hidden and only the login/register form is visible. No nav tabs, no content leakage.
- **D-02:** Login and register are on the same page, toggled by a "Create account" / "Back to login" link that swaps the form in place. No separate routes.
- **D-03:** After successful login/register, user lands on the Dashboard tab (not Companies or last-visited).
- **D-04:** Logout is a button in the top-right corner of the header alongside the user's email address. Always visible when authenticated.

### Security Fixes (not discussed — clear-cut from CONCERNS.md)
- **D-05:** CORS: Replace `allow_origins=["*"]` with localhost origins only for development. Production origin to be added when deployment is configured.
- **D-06:** Filename: Replace `file.filename` with `Path(file.filename).name` at `main.py:166` — basename only, no path components.
- **D-07:** XSS: Replace all `element.innerHTML = serverData` patterns in `frontend/index.html` with `element.textContent = serverData` or `document.createTextNode()`. Claude narrative text and extraction log entries are the primary vectors.

### Auth Implementation (Claude's Discretion)
- Token storage: HTTP-only cookies (better XSS posture — JS cannot read the token even if an XSS bug survives the innerHTML fix). Cookie name: `accountiq_session`.
- JWT expiry: 7 days. No refresh token in v1 — expired session redirects to the auth wall with a "Session expired — please log in again" message.
- Password requirements: minimum 8 characters. No complexity rules in v1.
- Auth middleware: FastAPI `Depends()` pattern, consistent with existing `get_db` dependency. A `get_current_user` dependency raises HTTP 401 if token is absent or invalid.
- `/health` remains public (no auth required). All other routes (`/companies`, `/documents`, `/financials`, `/patterns`, `/analytics`, `/settings`) require auth.
- The `/settings` endpoint (writes API key to disk) is protected by the same user auth as all other routes. No additional admin-only gate in v1 — single-user/owner context assumed.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Security vulnerabilities to fix
- `.planning/codebase/CONCERNS.md` — Full list of security issues; §Security/High Priority contains the three issues this phase must fix (CORS, filename, innerHTML XSS)
- `backend/main.py:35-40` — CORS middleware configuration to replace
- `backend/main.py:166` — Unsanitised `file.filename` line to fix

### Existing code patterns to follow
- `.planning/codebase/CONVENTIONS.md` — Code style, naming, async pattern, DB patterns, frontend patterns
- `.planning/codebase/ARCHITECTURE.md` — System architecture; FastAPI + SQLite + static frontend structure
- `backend/main.py` — Route definitions and `Depends(get_db)` pattern to extend for auth
- `frontend/index.html` — Tab navigation structure (`apiFetch`/`apiPost` helpers, `.nav-tab`/`.page.active` pattern) that auth wall sits on top of

### Requirements
- `.planning/REQUIREMENTS.md` — AUTH-01 through AUTH-08 are Phase 1 requirements
- `.planning/ROADMAP.md` — Phase 1 success criteria

### Project context
- `.planning/PROJECT.md` — Why this matters: external users, pay-per-report, must be secure before launch

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apiFetch(path)` and `apiPost(path, formData)` in `frontend/index.html` — both need a single patch to attach the auth cookie (cookies are sent automatically with `credentials: 'include'`) or Authorization header. Centralised helpers mean auth is added in one place.
- `Depends(get_db)` pattern in `backend/main.py` — the new `get_current_user` auth dependency follows this exact pattern; each route adds it alongside `get_db`.

### Established Patterns
- **Route error handling:** `raise HTTPException(status_code, detail_str)` — use `401` for missing/invalid token, `403` for forbidden (wrong user).
- **DB connections:** `async with aiosqlite.connect(DB_PATH) as db` with `PRAGMA foreign_keys=ON` on every connection — new `users` table queries follow this.
- **Section separators:** `# ---... Section name ...---` in backend files — new auth module should follow this structure.
- **Print logging:** `print("[AUTH] ...")` for log messages (no logging framework in use).
- **Frontend tab pattern:** `.nav-tab` buttons set `.page.active` — the auth wall is a separate `#auth-page` div that is shown/hidden; the main app container is hidden until authenticated.

### Integration Points
- **All existing API routes** (`/companies`, `/documents`, `/financials`, `/patterns`, `/analytics`, `/settings`) need `current_user: dict = Depends(get_current_user)` added to their signatures.
- **Frontend `apiFetch`/`apiPost`** need `credentials: 'include'` added to the `fetch()` call options so HTTP-only cookies are sent.
- **On page load:** JS checks for an existing valid session (e.g., `GET /auth/me`) — if 401, show auth wall; if 200, show main app and load initial data.
- **CORS:** With HTTP-only cookies and same-origin static mount, CORS only matters if the frontend is ever served from a separate origin. Lock down to `localhost:8765` for dev; add production origin when known.

</code_context>

<specifics>
## Specific Ideas

- Auth wall is the user's own phrasing — implement it literally: the entire app is hidden behind a clean login/register screen. Nothing leaks through.
- "Create account" / "Back to login" toggle in place (no page navigation) — user confirmed this is the preferred flow.
- User email displayed in top-right header once logged in, next to logout button.

</specifics>

<deferred>
## Deferred Ideas

- Auto-refresh tokens before expiry — deferred; 7-day expiry with redirect on expiry is sufficient for v1
- Admin-only gate on `/settings` — deferred; single-user context assumed for v1
- Email verification on registration — deferred to v2; adds SMTP/email dependency before payment phase
- "Remember me" / persistent sessions beyond 7 days — deferred to v2
- Two-factor authentication — out of scope

</deferred>

---

*Phase: 1-Security & Auth Foundation*
*Context gathered: 2026-05-04*
