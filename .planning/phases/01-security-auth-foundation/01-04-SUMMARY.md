---
phase: "01"
plan: "04"
subsystem: frontend-auth
status: human_verification_pending
tags: [authentication, frontend, auth-wall, account-page, javascript, cookies]
dependency_graph:
  requires: [01-02, 01-03]
  provides: [auth-wall-ui, account-page, credentialed-api-calls, initApp-lifecycle]
  affects: [frontend/index.html]
tech_stack:
  added: []
  patterns: [auth-wall-overlay, credential-cookie-fetch, in-place-form-toggle, button-disable-in-flight]
key_files:
  created: []
  modified:
    - frontend/index.html
decisions:
  - "initApp overrides showAuthWall(true) with showAuthWall(false) on cold-load — cosmetic flicker accepted over refactoring apiFetch (per RESEARCH pitfall note)"
  - "doLogout always shows auth wall even if network request fails — safety over cookie precision"
  - "Field-level password errors render in per-field divs (#reg-password-error, #reg-confirm-error); banner errors in #auth-alert"
  - "loadAccount uses apiFetch which auto-routes 401 to showAuthWall — no separate 401 guard needed"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-05"
  tasks: 3
  files_created: 0
  files_modified: 1
---

# Phase 1 Plan 4: Frontend Auth Wall Summary

Frontend auth wall with login/register toggle, header logout button, Account page, and credentialed API calls on all four fetch sites — gating the entire app UI behind /auth/me on page load.

## Status: HUMAN VERIFICATION PENDING

Tasks 1–3 (automated) are complete and committed. Task 4 is a `checkpoint:human-verify` requiring manual browser testing of the full auth interaction flow. The orchestrator will present the 8 verification scenarios to the user.

## What Was Built

### Task 1: Auth wall HTML, #main-app wrapper, Account page, nav (commit 7f4db69)

**CSS additions** (14 new rules):
- `.auth-page` — fixed full-screen overlay, z-index 200, flex-centered
- `.auth-card` — 400px card with card/border/radius styles
- `.auth-toggle`, `.auth-field-error`, `.btn-ghost-light`
- `#user-header`, `#user-email` — nav right-side user info area

**HTML additions:**
- `#auth-page` — full-screen auth wall with login form (default) and register form (hidden by default)
- Login form: email, password inputs, "Sign in" button, toggle link
- Register form: email, password, confirm-password, field-level error divs, "Create account" button, toggle link
- `#main-app` wrapper div (hidden by default) wrapping all nav + page divs
- `#user-header` in nav: `#user-email` span + "Sign out" button
- Account nav tab (before Settings)
- `#page-account`: Account Details card (email, member since) + Report Purchase History card (empty state)

**JS changes:**
- PAGES array extended: `'account'` added before `'settings'`
- `showPage()` dispatches to `loadAccount()` when `name === 'account'`

### Task 2: Credentials and 401 handling on all fetch sites (commit 0f4e1aa)

Four fetch sites updated with `credentials: 'include'` and `if (res.status === 401) { showAuthWall(true); return null; }`:
- `apiFetch(path)` — all GET API calls
- `apiPost(path, formData)` — all POST API calls via the helper
- `retryDoc(docId)` — bare fetch for document retry
- `saveSettings()` — bare fetch for settings save

### Task 3: Auth JS functions + initApp entrypoint (commit b2694d7)

Eight functions added:
- `showAuthWall(expired)` — hides #main-app, shows auth-page, clears password fields, optional session-expired alert
- `showMainApp(user)` — hides auth-page, shows #main-app, sets email textContent, calls showPage('dashboard') + checkApiKey()
- `toggleAuthForm()` — swaps login/register forms, clears alerts and field errors
- `_setAuthAlert(msg, type)` — XSS-safe alert helper (uses textContent)
- `submitLogin()` — FormData POST /auth/login, in-flight button disable, handles 200/401/error
- `submitRegister()` — client-side validation (pw length >= 8, pw match), POST /auth/register, handles 409 duplicate
- `doLogout()` — POST /auth/logout, always calls showAuthWall(false) regardless of network result
- `loadAccount()` — fetches /auth/me, populates #acct-email and #acct-created (formatted as "Month Year")
- `initApp()` — page-load entrypoint: calls apiFetch('/auth/me'), routes 200->showMainApp, 401->showAuthWall(false)

Old bare `loadDashboard(); checkApiKey();` entrypoint replaced with `initApp();`.

## Test Results

Backend tests: **15 passed, 1 skipped** — no regressions from frontend-only changes.

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

## Commits

| Commit | Task | Description |
|--------|------|-------------|
| 7f4db69 | Task 1 | feat(01-04): add auth wall HTML, #main-app wrapper, Account page, nav modifications |
| 0f4e1aa | Task 2 | feat(01-04): add credentials:'include' and 401->showAuthWall to all four fetch sites |
| b2694d7 | Task 3 | feat(01-04): add 8 auth JS functions and replace loadDashboard init with initApp |

## Manual Verification Pending (Task 4)

Task 4 is a `checkpoint:human-verify` with 8 browser scenarios. Results will be captured after human review:

| # | Scenario | Status |
|---|----------|--------|
| 1 | Cold-load auth wall (D-01) | PENDING |
| 2 | Toggle login <-> register (D-02) | PENDING |
| 3 | Register new user (AUTH-04) | PENDING |
| 4 | Register validation errors | PENDING |
| 5 | Login after logout (AUTH-05, AUTH-06) | PENDING |
| 6 | Account tab (AUTH-08) | PENDING |
| 7 | Logout flow (AUTH-06) | PENDING |
| 8 | XSS smoke (AUTH-03 manual gate) | PENDING |

## Deviations from Plan

None — plan executed exactly as written. All edits applied per the plan's Edit A-F spec and all function implementations match the plan's action section verbatim.

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| Report Purchase History empty state | frontend/index.html | Intentional: no reports exist in Phase 1; future Phase 6 will wire real purchase data per AUTH-08 spec |

The `#acct-created` default value of "—" is not a stub — it is immediately populated by `loadAccount()` when the Account tab is viewed.

## Threat Flags

No new threat surface introduced beyond what is in the plan's threat_model. All mitigations implemented:

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-04-01 | HttpOnly cookie (Plan 03) + viewNarrative XSS-safe | DONE (prior plans) |
| T-04-02 | #main-app starts hidden; initApp gates reveal | DONE (Tasks 1+3) |
| T-04-03 | SameSite=Lax (Plan 03) + CORS allowlist (Plan 02) | DONE (prior plans) |
| T-04-04 | showAuthWall clears password field values | DONE (Task 3) |
| T-04-05 | Submit buttons disabled in-flight | DONE (Task 3) |
| T-04-06 | Same-origin deployment accepted | ACCEPTED |
| T-04-07 | initApp cold-load flicker accepted | ACCEPTED |

## Self-Check: PASSED

- frontend/index.html: FOUND
- commit 7f4db69: FOUND (Task 1)
- commit 0f4e1aa: FOUND (Task 2)
- commit b2694d7: FOUND (Task 3)
- 15 backend tests passing: CONFIRMED
- id="auth-page": FOUND (count=1)
- id="main-app": FOUND (count=1)
- credentials:'include': FOUND (4 sites)
- async function initApp: FOUND (count=1)
- Task 4 manual verification: PENDING (human checkpoint)
