---
phase: "03-5"
plan: "03"
subsystem: auth-wizard
tags: [wizard, non-admin-ux, frontend, upload-route, tdd]
dependency_graph:
  requires: [03-5-01, 03-5-02]
  provides: [POST /wizard/upload, wizard-frontend, is_admin-branching]
  affects: [backend/main.py, frontend/index.html, tests/test_admin_gate.py]
tech_stack:
  added: []
  patterns: [TDD-RED-GREEN, FormData-fetch, module-scope-wizard-state, DOM-createElement-XSS-safe]
key_files:
  created: []
  modified:
    - backend/main.py
    - frontend/index.html
    - tests/test_admin_gate.py
decisions:
  - "Wizard upload uses get_current_user (not require_admin) — non-admin users are the designated callers (D-05)"
  - "submitLogin/submitRegister re-fetch /auth/me after login to get is_admin — login/register responses only return {id, email}"
  - "wizardSubmitStep1 uses direct fetch instead of apiPost to show alerts in wizard-alert container not upload-alert"
  - "Report type names use textContent not innerHTML — XSS compliance enforced at DOM build time"
metrics:
  duration: "8 minutes"
  completed_date: "2026-05-13"
  tasks_completed: 2
  files_changed: 3
---

# Phase 3.5 Plan 03: Wizard Upload Route + 3-Step Wizard Frontend Summary

POST /wizard/upload backend route plus a 3-step wizard frontend: non-admin users see upload-then-select-report-type flow after login; admin users see the full existing UI unchanged.

## What Was Built

### Task 1: POST /wizard/upload backend route (TDD)

**TDD RED phase:** Removed `@pytest.mark.xfail` markers from 3 wizard tests — tests fail as expected since route not yet present.

**TDD GREEN phase:** Added `POST /wizard/upload` to `backend/main.py` after the retry route (line 909+):

- Uses `Depends(get_current_user)` — NOT `require_admin`; accessible to both regular and admin users (D-05)
- Validates `business_name` not empty (400) and file suffix in `{.pdf, .xlsx, .xls, .xlsm}` (400)
- Uses `_resolve_or_create_company(db, name, current_user["id"])` — idempotent company creation (D-06)
- Saves file using `Path(file.filename).name` — path traversal prevention (T-03-5-08)
- Inserts document record with `report_type='compilation'`, `entity_type='sme'`, `fiscal_year_end=''`
- Kicks off `_run_ingestion` as background task (same pipeline as admin upload)
- Returns `{company_id, document_id, status: "processing"}` with HTTP 201

All 3 wizard tests moved from XFAIL to GREEN. Full suite: 49 passed, 1 skipped.

### Task 2: Wizard HTML + JS frontend + initApp branching

**HTML:** Added `#wizard-page` div (initially hidden) after `#main-app` closing tag, before `<script>`:
- Nav header with wizard step indicator and user email (`.textContent`)
- Step 1: business name input + file input + "Continue" button
- Step 2: `#wizard-report-cards` container + Back/Continue buttons (`wiz-step2-continue` starts disabled)
- Step 3: success alert + email confirmation (`#wiz-confirm-email` uses `.textContent`)

**JS (before Auth section):**
- Module-scope state: `_wizardStep`, `_wizardUploadResult`, `_wizardReportType`, `_wizardUser`
- `WIZARD_REPORT_TYPES` array with 5 locked report types (D-10)
- `showWizard(user)` — hides auth-page + main-app, shows wizard-page, sets user email via `.textContent`
- `renderWizardStep(step)` — shows correct step panel, updates step indicator, sets confirm email in step 3
- `_renderReportTypeCards()` — builds card elements using `createElement` + `.textContent` (no `.innerHTML`)
- `_selectReportType(key)` — highlights selected card (blue border + `#e3f2fd` bg), enables Continue button
- `wizardSubmitStep1()` — validates inputs, calls `POST /wizard/upload` via direct `fetch`, advances to step 2
- `wizardConfirm()` — validates report type selected, advances to step 3
- `wizardReset()` — clears state + form inputs, returns to step 1

**initApp() updated:** Now branches on `user.is_admin` from `/auth/me` response:
- `true` → `showMainApp(user)` (existing full UI)
- `false` → `showWizard(user)`

**submitLogin() and submitRegister() updated:** After successful auth, re-fetch `/auth/me` to get `is_admin` (login/register responses only have `{id, email}`), then branch.

## Test Results

```
tests/test_admin_gate.py::test_wizard_upload_creates_company_and_document  PASSED
tests/test_admin_gate.py::test_wizard_upload_requires_auth                 PASSED
tests/test_admin_gate.py::test_wizard_upload_not_admin_gated               PASSED

Full suite: 49 passed, 1 skipped, 0 failed
```

## Commits

| Hash | Message |
|------|---------|
| c5f111c | test(03-5-03): remove xfail markers — RED phase for wizard upload tests |
| c7fb3d2 | feat(03-5-03): add POST /wizard/upload route to main.py |
| 0e40c88 | feat(03-5-03): add 3-step wizard frontend + initApp is_admin branching |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] submitLogin/submitRegister re-fetch /auth/me instead of passing through login response**

- **Found during:** Task 2 implementation
- **Issue:** Plan specified `showMainApp(user)` pattern patched with `user.is_admin` check, but login/register responses only return `{id, email}` without `is_admin`. Using the raw response would always route to `showWizard` (no `is_admin` field = falsy).
- **Fix:** After successful login/register, consume the response body then call `apiFetch('/auth/me')` to get the full user object including `is_admin`. Branch on the `/auth/me` result. Plan noted this approach in the action block's note section.
- **Files modified:** frontend/index.html
- **Commit:** 0e40c88

## Known Stubs

Step 3 confirmation is intentionally static — "we'll email you" is copy only. No email is actually sent (Phase 5 concern). The `_wizardReportType` value is captured in JS state but not yet persisted to the backend (no report order table yet — Phase 5). This is documented in the plan as intentional (D-10).

## Checkpoint Status

**Task 3 (checkpoint:human-verify) reached — awaiting human verification.**

The server must be started manually before verification. Admin user should see full tab UI; regular user should see the 3-step wizard.

## Threat Model Compliance

- T-03-5-08 (path traversal): `Path(file.filename).name` applied in `wizard_upload` before file save — VERIFIED
- T-03-5-09 (XSS in wizard): All dynamic values use `.textContent` or `createTextNode()` — grep confirms 0 `.innerHTML` for user data — VERIFIED
- T-03-5-10 (privilege escalation): Backend `require_admin` gate from Plan 02 still applies to all 25 admin routes; frontend gating is UX-only — VERIFIED
- T-03-5-11 (spoofing): Accepted — backend always enforces; frontend is cosmetic — ACCEPTED per threat register

## Threat Flags

No new threat surface introduced beyond the plan's threat model.

## Self-Check: PASSED

- `POST /wizard/upload` in backend/main.py: FOUND (line 916)
- `Depends(get_current_user)` occurs exactly 1 time in main.py: CONFIRMED
- `#wizard-page` div in frontend/index.html: FOUND (2 occurrences)
- `showWizard` function defined and called: FOUND (4 occurrences)
- `user.is_admin` branch: FOUND (3 occurrences)
- No `.innerHTML` for user-controlled wizard data: CONFIRMED (grep = 0)
- Commit c5f111c (RED phase): FOUND
- Commit c7fb3d2 (GREEN phase route): FOUND
- Commit 0e40c88 (frontend): FOUND
- Full suite 49 passed, 0 failed: CONFIRMED
