---
phase: "01"
plan: "03"
subsystem: auth
tags: [authentication, jwt, cookies, fastapi, security]
dependency_graph:
  requires: [01-01, 01-02]
  provides: [jwt-auth, session-cookies, protected-routes]
  affects: [all-data-endpoints]
tech_stack:
  added: [PyJWT, pwdlib, python-jose]
  patterns: [http-only-cookie-session, dependency-injection-auth, route-protection]
key_files:
  created:
    - backend/auth.py
  modified:
    - backend/main.py
    - backend/db.py
    - tests/conftest.py
decisions:
  - "HTTP-only cookies chosen over Authorization header for session management (CSRF-safe with SameSite=Lax)"
  - "JWT HS256 with 7-day expiry — refresh not needed for MVP (single-device use case)"
  - "Empty SECRET_KEY raises HTTP 500 — fail-safe over fail-open"
  - "conftest.py .env search extended to 4th-level parent to support git worktree paths"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-05"
  tasks: 3
  files_created: 1
  files_modified: 3
---

# Phase 1 Plan 3: Auth Implementation Summary

JWT-based authentication with HTTP-only cookies, Argon2 password hashing, and protected route enforcement across all 15 data endpoints using FastAPI dependency injection.

## What Was Built

### backend/auth.py (new)

Full authentication module implementing:
- **Register** (`POST /auth/register`): email + password validation, Argon2 hashing, JWT token issued as HTTP-only cookie on success
- **Login** (`POST /auth/login`): credential verification, JWT cookie issued
- **Logout** (`POST /auth/logout`): cookie cleared with Max-Age=0
- **Me** (`GET /auth/me`): returns authenticated user dict (id, email, created_at)
- **`get_current_user` dependency**: validates JWT cookie, looks up user in DB, raises 401 on failure or 500 if SECRET_KEY unconfigured

Cookie configuration:
- Name: `accountiq_session`
- HttpOnly: true
- SameSite: lax
- Max-Age: 604800 (7 days)
- Secure: configurable via `COOKIE_SECURE` env var (false in dev)

### backend/main.py (modified)

- Imported `auth_router` and `get_current_user` from `auth`
- Mounted `auth_router` via `app.include_router(auth_router)`
- Added `current_user: dict = Depends(get_current_user)` to all 15 data routes

### tests/conftest.py (modified)

Extended `.env` file search to include 4th-level parent directory, enabling tests to find the project `.env` when running from inside a git worktree (where the project root is 4 levels above `tests/`).

## Protected Routes (15)

| Route | Method | Endpoint |
|-------|--------|----------|
| list_companies | GET | /companies |
| create_company | POST | /companies |
| get_company | GET | /companies/{company_id} |
| list_documents | GET | /documents |
| upload_document | POST | /documents/upload |
| document_status | GET | /documents/{document_id}/status |
| document_rows | GET | /documents/{document_id}/rows |
| retry_document | POST | /documents/{document_id}/retry |
| company_financials | GET | /financials/{company_id} |
| list_patterns | GET | /patterns |
| export_patterns | GET | /patterns/export |
| analytics_overview | GET | /analytics/overview |
| confidence_stats | GET | /analytics/confidence |
| get_settings | GET | /settings |
| update_settings | POST | /settings |

## Public Routes (kept open)

| Route | Method | Reason |
|-------|--------|--------|
| root | GET | / — API discovery |
| health | GET | /health — monitoring/ops |
| register | POST | /auth/register — must be pre-auth |
| login | POST | /auth/login — must be pre-auth |
| logout | POST | /auth/logout — graceful even without valid token |
| me | GET | /auth/me — protected internally via get_current_user |

## Test Results

```
tests/test_auth.py::test_register_success          PASSED
tests/test_auth.py::test_register_short_password   PASSED
tests/test_auth.py::test_register_duplicate        PASSED
tests/test_auth.py::test_login_sets_cookie         PASSED
tests/test_auth.py::test_cookie_attributes         PASSED
tests/test_auth.py::test_me_authenticated          PASSED
tests/test_auth.py::test_me_unauthenticated        PASSED
tests/test_auth.py::test_logout                    PASSED
tests/test_auth.py::test_protected_after_logout    PASSED
tests/test_auth.py::test_me_returns_user_fields    PASSED
tests/test_auth.py::test_protected_route_no_auth   PASSED
tests/test_auth.py::test_protected_route_with_auth PASSED
tests/test_auth.py::test_health_remains_public     PASSED
tests/test_security.py::test_cors_restricted_unknown_origin  PASSED
tests/test_security.py::test_cors_allowed_origin_localhost   PASSED
tests/test_security.py::test_filename_traversal_basename_only SKIPPED

Result: 15 passed, 1 skipped
```

The skipped test (`test_filename_traversal_basename_only`) was skipped in plan 01-02 — it requires a live upload endpoint with multipart form support that is not wired in the test harness. Pre-existing skip, not a regression.

## Commits

| Commit | Description |
|--------|-------------|
| cebe286 | feat(01-03): add users table and email index to db.py SCHEMA |
| df1d5d8 | feat(01-03): create backend/auth.py with JWT auth, register/login/logout/me |
| 1487a0e | feat(01-03): wire auth router + protect 15 routes in main.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] conftest.py .env path not found in git worktree**
- **Found during:** Task 3 verification (3 tests failing with "Server auth not configured")
- **Issue:** conftest.py searched only 3 levels up from tests/ directory, but the project `.env` is 4 levels up when running inside a git worktree at `.claude/worktrees/agent-*/`
- **Fix:** Added 4th candidate path `_HERE.parent.parent.parent.parent / ".env"` to conftest.py search list
- **Files modified:** tests/conftest.py
- **Commit:** 1487a0e (included with Task 3 commit)

## Known Stubs

None — all routes return real data from the database.

## Threat Flags

No new threat surface introduced beyond what is in scope. Auth endpoints follow secure defaults (HttpOnly cookies, SameSite=Lax, Argon2 hashing, JWT with server-side secret).

## Self-Check: PASSED

- backend/auth.py: FOUND
- backend/main.py: FOUND (modified)
- tests/conftest.py: FOUND (modified)
- commit cebe286: FOUND
- commit df1d5d8: FOUND
- commit 1487a0e: FOUND
- 15 tests passing: CONFIRMED
