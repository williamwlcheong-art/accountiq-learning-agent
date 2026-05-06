---
phase: 02-multi-user-data-isolation
plan: 03
subsystem: testing
tags: [pytest, httpx, asyncclient, integration-tests, idor, user-isolation, data-isolation]

# Dependency graph
requires:
  - phase: 02-multi-user-data-isolation
    plan: 01
    provides: user_id columns on companies and documents tables — isolation schema foundation
  - phase: 02-multi-user-data-isolation
    plan: 02
    provides: WHERE user_id=? route filters and IDOR 404 protection on all company/document routes
provides:
  - fresh_all_db fixture in tests/conftest.py — clears all tables in FK-safe order between isolation tests
  - tests/test_isolation.py — 5 integration smoke tests proving AUTH-07 and DATA-01 end-to-end
  - Definitive proof that Phase 2 schema (Plan 01) and route filters (Plan 02) enforce isolation correctly
affects: [all-future-phases, phase-03-business-profile-intake, phase-04-extraction-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-client isolation pattern: _make_bob_client() returns a fresh AsyncClient with separate cookie jar per test block"
    - "fresh_all_db fixture: DELETE all tables in FK-safe order (financial_rows, extraction_log, documents, companies, users) before each isolation test"
    - "Contextual assertion messages: all cross-user assertions include actual response body in f-string for immediate debugging"

key-files:
  created:
    - tests/test_isolation.py
  modified:
    - tests/conftest.py

key-decisions:
  - "fresh_all_db deletes in FK-safe reverse order — children before parents — matching SQLite FK constraint enforcement with foreign keys ON"
  - "_make_bob_client() creates AsyncClient inside the test function (not as a fixture) to guarantee a fresh empty cookie jar per cross-user block"
  - "Fake PDF bytes (%PDF-1.4 fake...) are sufficient to reach company ownership check — test is not about extraction correctness"
  - "Each test uses unique email suffixes (alice@, alice2@, alice3@, alice4@) to avoid conflicts across tests that may share DB state before fresh_all_db truncation"

patterns-established:
  - "Integration test pattern for multi-user isolation: register two users with separate clients, perform cross-user action, assert 404 or empty list"
  - "Test helper _register() asserts status in (200, 201) and surfaces response body — prevents silent registration failures masking cross-user test logic"

requirements-completed:
  - AUTH-07
  - DATA-01

# Metrics
duration: 8min
completed: 2026-05-07
---

# Phase 2 Plan 03: Integration Tests for Multi-User Data Isolation Summary

**5 pytest integration tests using dual AsyncClient sessions prove IDOR prevention (404), per-user list filtering, and NULL user_id invisibility — definitive end-to-end proof of AUTH-07 and DATA-01**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-07T00:00:00Z
- **Completed:** 2026-05-07T00:08:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Extended `tests/conftest.py` with `fresh_all_db` fixture — deletes all tables in FK-safe order (financial_rows, extraction_log, documents, companies, users) before each isolation test
- Created `tests/test_isolation.py` with 5 test functions covering all Phase 2 success criteria
- Full test suite: 20 passed, 1 skipped, 0 failures (13 auth + 5 isolation + 2 security tests)
- Proved that Plans 01 and 02 work correctly together: schema + route filters enforce real isolation

## Task Commits

Each task was committed atomically:

1. **Task 1: Add fresh_all_db fixture to conftest.py** - `9bb4349` (feat)
2. **Task 2: Create tests/test_isolation.py with 5 cross-user isolation tests** - `22cdf15` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `tests/conftest.py` — Extended with `fresh_all_db` fixture appended after existing `fresh_db`; existing `fresh_db` unchanged
- `tests/test_isolation.py` — New file with 5 integration test functions covering AUTH-07 (IDOR) and DATA-01 (NULL row invisibility)

## Decisions Made

- `fresh_all_db` uses FK-safe deletion order (children before parents): financial_rows, extraction_log, documents, companies, users — required because SQLite has foreign keys ON
- `_make_bob_client()` returns `AsyncClient(...)` directly (not an `async with` block) so each call in a test creates a completely fresh client with an empty cookies dict
- Fake PDF content `b"%PDF-1.4 fake..."` is sufficient — the upload route checks company ownership before processing the file, so actual PDF content is irrelevant for these tests
- Used unique email suffixes per test (`alice@test.com`, `alice2@test.com`, etc.) so that if the DB is not perfectly cleared between tests, there is no email uniqueness collision

## Deviations from Plan

None - plan executed exactly as written. Both fixtures and all 5 test functions match the plan specification exactly.

## Known Stubs

None — this plan adds test code only. No UI, data rendering, or data flow paths introduced.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All three threats from the plan's threat_model were mitigated:

| Threat | Mitigation Applied |
|--------|-------------------|
| T-2-08 (shared cookie jars giving false positives) | Each `async with _make_bob_client() as bob:` creates a new AsyncClient with empty cookies |
| T-2-09 (DB state leakage between tests) | `fresh_all_db` fixture clears all tables in FK-safe order before each test |
| T-2-10 (missing detail in assertion messages) | All cross-user assertions include actual response data via f-string |

## Issues Encountered

None - all 5 tests passed on first run. No debugging required.

## Self-Check

- [x] `tests/conftest.py` modified — `fresh_all_db` appended after `fresh_db`
- [x] `tests/test_isolation.py` created — 5 test functions present
- [x] Task 1 commit `9bb4349` exists in git log
- [x] Task 2 commit `22cdf15` exists in git log
- [x] `python -m pytest tests/test_isolation.py -v` — 5 passed, 0 failed
- [x] `python -m pytest tests/ -v` — 20 passed, 1 skipped, 0 failures

## Self-Check: PASSED

## Next Phase Readiness

- Phase 2 is complete: schema (Plan 01) + route filters (Plan 02) + integration tests (Plan 03) all committed
- All 5 Phase 2 success criteria verified: IDOR 404, list filtering per-user, NULL row invisibility, analytics scoping, upload ownership check
- No blockers

---
*Phase: 02-multi-user-data-isolation*
*Completed: 2026-05-07*
