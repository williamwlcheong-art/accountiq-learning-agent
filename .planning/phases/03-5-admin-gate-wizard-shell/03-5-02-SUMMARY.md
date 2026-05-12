---
phase: "03-5"
plan: "02"
subsystem: auth
tags: [auth, admin-gate, require_admin, route-hardening, test-updates]
dependency_graph:
  requires: [03-5-01]
  provides: [admin-gated-routes, require_admin-on-all-25-routes]
  affects: [backend/main.py, tests/test_auth.py, tests/test_isolation.py, tests/test_profile.py, tests/test_upload_auto.py]
tech_stack:
  added: []
  patterns: [FastAPI-Depends-chaining, require_admin-per-route]
key_files:
  created: []
  modified:
    - backend/main.py
    - tests/test_auth.py
    - tests/test_isolation.py
    - tests/test_profile.py
    - tests/test_upload_auto.py
decisions:
  - "Applied require_admin to all 25 admin-facing routes via replace_all edit — single atomic swap, no missed routes"
  - "Updated test helpers in 4 test files to use _register_admin (OWNER_EMAIL patching) so pre-existing route tests continue to pass with admin gate active"
metrics:
  duration: "3 minutes"
  completed_date: "2026-05-12"
  tasks_completed: 1
  files_changed: 5
---

# Phase 3.5 Plan 02: Apply require_admin to All 25 Admin Routes Summary

All 25 existing admin-facing routes in main.py now use `Depends(require_admin)` instead of `Depends(get_current_user)`. Non-admin callers receive 403; unauthenticated callers receive 401; admin users receive 200. Full test suite green (46 passed, 1 skipped, 3 xfailed).

## What Was Built

### Task 1: Swap Depends(get_current_user) → Depends(require_admin) on all 25 admin routes

- `backend/main.py`: All 25 route-level `Depends(get_current_user)` occurrences replaced with `Depends(require_admin)`. The import line (`from auth import auth_router, get_current_user, require_admin`) was left intact. Routes affected span all admin namespaces: `/companies/*` (13 routes), `/documents/*` (5 routes), `/financials/*` (1 route), `/patterns/*` (2 routes), `/analytics/*` (2 routes), `/settings/*` (2 routes).
- `/health` and `/auth/*` routes have no `current_user` parameter and were not touched.

## Test Results

```
tests/test_admin_gate.py — 9 passed, 3 xfailed
tests/test_auth.py — passed (all)
tests/test_isolation.py — passed (all)
tests/test_profile.py — passed (all)
tests/test_upload_auto.py — passed (all)

Full suite: 46 passed, 1 skipped, 3 xfailed, 0 failed
```

Specific gate tests now GREEN (were RED in Plan 01):
```
tests/test_admin_gate.py::test_regular_user_companies_403     PASSED
tests/test_admin_gate.py::test_regular_user_financials_403    PASSED
tests/test_admin_gate.py::test_regular_user_patterns_403      PASSED
tests/test_admin_gate.py::test_regular_user_settings_403      PASSED
tests/test_admin_gate.py::test_admin_user_companies_200       PASSED
tests/test_admin_gate.py::test_unauthenticated_returns_401_not_403  PASSED
```

3 wizard xfail tests remain XFAIL (Plan 03 implements `/wizard/upload`).

## Commits

| Hash | Message |
|------|---------|
| 70c8af7 | feat(03-5-02): apply require_admin to all 25 admin routes in main.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing test helpers to use admin registration**
- **Found during:** Task 1 verification — after the route swap, `pytest tests/ -q` showed 23 failures across test_isolation.py, test_profile.py, test_upload_auto.py, and test_auth.py
- **Issue:** These test files registered non-admin users and called routes that are now admin-gated (403 instead of expected 200). Tests were correct before Plan 02 applied require_admin.
- **Fix:** Added `_register_admin` helper (OWNER_EMAIL module-level patching, identical pattern to test_admin_gate.py) to each affected test file; replaced all `_register(` calls with `_register_admin(`. Cross-user data isolation is still tested by the `user_id WHERE` clauses — both Alice and Bob can be admins while still seeing only their own data.
- **Files modified:** tests/test_auth.py, tests/test_isolation.py, tests/test_profile.py, tests/test_upload_auto.py
- **Commit:** 70c8af7 (included in the same task commit)

## Threat Model Compliance

All T-03-5-05, T-03-5-06, T-03-5-07 mitigations implemented:
- T-03-5-05: `Depends(require_admin)` on all 25 routes; 403 for non-admin; 401 for unauthenticated — VERIFIED
- T-03-5-06: `grep -c "Depends(require_admin)" backend/main.py` = 25 — VERIFIED
- T-03-5-07: `/health` and `/auth/*` unchanged; no current_user param on those routes — VERIFIED

## Known Stubs

None — this plan adds no UI or data display components. Route hardening only.

## Threat Flags

No new threat surface introduced. This plan reduces attack surface by removing non-admin access from 25 routes.

## Self-Check: PASSED

- `backend/main.py` contains 25 `Depends(require_admin)`: FOUND
- `backend/main.py` contains 0 route-level `Depends(get_current_user)`: CONFIRMED
- Import line still includes `get_current_user`: FOUND
- Commit 70c8af7 exists: FOUND
- All 6 admin gate tests GREEN: CONFIRMED
- Full suite 46 passed, 0 failed: CONFIRMED
