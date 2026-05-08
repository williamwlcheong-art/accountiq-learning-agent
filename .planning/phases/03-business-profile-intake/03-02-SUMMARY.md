---
phase: 03-business-profile-intake
plan: "02"
subsystem: backend-routes
tags:
  - fastapi
  - crud
  - tdd-green
  - profile-api
dependency_graph:
  requires:
    - 03-01  # schema: management_team, ebitda_adjustments, description column
  provides:
    - POST /companies/{id}/profile
    - GET /companies/{id}/profile-status
    - GET/POST/PUT/DELETE /companies/{id}/management-team[/{member_id}]
    - GET/POST/PUT/DELETE /companies/{id}/ebitda-adjustments[/{adj_id}]
    - enriched GET /companies with description + sections_complete
  affects:
    - 03-03-PLAN.md  # frontend consumes all 11 new routes
    - Phase 5 report generation gate (can_generate key from profile-status)
tech_stack:
  added: []
  patterns:
    - ownership-verify-then-child-query (SELECT id FROM companies WHERE id=? AND user_id=?)
    - conditional UPDATE for optional form fields
    - correlated subqueries in SELECT for sections_complete badge
    - EBITDA bridge: depreciation_amortisation preferred, depreciation as fallback
key_files:
  created: []
  modified:
    - backend/main.py
    - backend/db.py
    - tests/conftest.py
    - tests/test_profile.py
decisions:
  - Companies table rename block in _migrate_db must include description column to survive idempotent re-runs
  - profile-status uses separate COUNT queries (not JOIN) to avoid cross-join cardinality issues
  - EBITDA bridge fetches max(period) first, then all row_keys in that period, to handle sparse financial_rows
  - All child-table routes perform company ownership check BEFORE touching the child table (defence in depth)
metrics:
  duration: "12 minutes"
  completed_date: "2026-05-08"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 4
---

# Phase 3 Plan 2: Backend Profile CRUD Routes Summary

**One-liner:** Full CRUD API surface for business profile intake — profile patch, management-team and ebitda-adjustments CRUD (11 new routes + 1 enriched), with profile-status gate returning 9-key dict including EBITDA bridge and can_generate flag.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace list_companies SQL and add update_company_profile + profile_status routes | fcb4621 | backend/main.py, backend/db.py, tests/conftest.py, tests/test_profile.py |
| 2 | Add management-team CRUD and ebitda-adjustments CRUD routes | d7fecc7 | backend/main.py |

## Changes Made

### Routes Added (11 new, 1 modified)

| Method | Path | Handler | Status |
|--------|------|---------|--------|
| GET | `/companies` | `list_companies` (modified) | 200 — now includes `description` and `sections_complete` |
| POST | `/companies/{id}/profile` | `update_company_profile` | 200 — patches sector and/or description |
| GET | `/companies/{id}/profile-status` | `profile_status` | 200 — 9-key dict |
| GET | `/companies/{id}/management-team` | `list_management_team` | 200 |
| POST | `/companies/{id}/management-team` | `add_management_team_member` | 201 |
| PUT | `/companies/{id}/management-team/{member_id}` | `update_management_team_member` | 200 |
| DELETE | `/companies/{id}/management-team/{member_id}` | `delete_management_team_member` | 204 No Content |
| GET | `/companies/{id}/ebitda-adjustments` | `list_ebitda_adjustments` | 200 |
| POST | `/companies/{id}/ebitda-adjustments` | `add_ebitda_adjustment` | 201 |
| PUT | `/companies/{id}/ebitda-adjustments/{adj_id}` | `update_ebitda_adjustment` | 200 |
| DELETE | `/companies/{id}/ebitda-adjustments/{adj_id}` | `delete_ebitda_adjustment` | 204 No Content |

### profile-status Response Shape (9 keys)

```json
{
  "sections_complete": 2,
  "total": 4,
  "sector_complete": true,
  "description_complete": false,
  "management_complete": false,
  "ebitda_complete": true,
  "can_generate": true,
  "reported_ebitda": 250000.0,
  "has_financials": true
}
```

- `sections_complete`: integer 0..4 (sum of four boolean section flags)
- `can_generate`: `sector_complete AND ebitda_complete` (Phase 5 gate)
- `reported_ebitda`: `net_profit + depreciation_amortisation` from MAX(period) financial_rows; `null` if no financial rows exist
- `has_financials`: `true` if at least one matching financial_row exists for this company

### EBITDA Bridge Fallback Logic

The bridge query fetches `row_key IN ('net_profit', 'depreciation_amortisation', 'depreciation')` for the most recent period. The code then:

1. Prefers `depreciation_amortisation` if present
2. Falls back to `depreciation` alone if `depreciation_amortisation` is NULL
3. Returns `null` for `reported_ebitda` if no matching financial_rows exist at all

### GET /companies Enrichment

The `list_companies` query now uses `COUNT(DISTINCT d.id)` (was `COUNT(d.id)`) and adds a `sections_complete` correlated subquery:

```sql
(CASE WHEN c.sector IS NOT NULL AND c.sector != '' THEN 1 ELSE 0 END
 + CASE WHEN c.description IS NOT NULL AND LENGTH(TRIM(c.description)) >= 50 THEN 1 ELSE 0 END
 + CASE WHEN (SELECT COUNT(*) FROM management_team mt WHERE mt.company_id = c.id) > 0 THEN 1 ELSE 0 END
 + CASE WHEN (SELECT COUNT(*) FROM ebitda_adjustments ea WHERE ea.company_id = c.id) > 0 THEN 1 ELSE 0 END
) as sections_complete
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed description column lost during companies table rebuild**

- **Found during:** Task 1 (test_save_industry failed with `sqlite3.OperationalError: no such column: description`)
- **Issue:** `_migrate_db` adds `description` via ALTER TABLE, but the Phase 2 UNIQUE constraint rebuild creates `companies_new` without `description` and replaces the old table. On a fresh DB, the ALTER runs first then the rename drops the column.
- **Fix:** Added `description TEXT` to the `companies_new` CREATE TABLE in `db.py`, and updated the INSERT to include the `description` column in the SELECT.
- **Files modified:** `backend/db.py` (lines 165-183)
- **Commit:** fcb4621

**2. [Rule 1 - Bug] Fixed `import conftest` causing second temp DB in test_ebitda_bridge_calculation**

- **Found during:** Task 1 verification (`test_ebitda_bridge_calculation` failed with `KeyError: 'has_financials'`)
- **Issue:** `test_profile.py` did `import conftest; db_path = conftest._TMP_DB_PATH` to get the test DB path. When Python imports `conftest` as a regular module (separate from pytest's plugin mechanism), it re-executes conftest's module-level code, creating a second temp DB file and calling `init_db()` again. The test then inserted financial rows into the second DB, while the HTTP client was connected to the first.
- **Fix 1:** Changed the test to use `import db as _db_module; db_path = _db_module.DB_PATH` — this reads the already-patched DB_PATH set by conftest at test session startup.
- **Fix 2:** Added `tests/` to `sys.path` in conftest to support `import conftest` patterns in other tests that may rely on this.
- **Files modified:** `tests/test_profile.py`, `tests/conftest.py`
- **Commit:** fcb4621

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| tests/test_profile.py | 9 | 9 passed |
| tests/test_isolation.py | 14 | 14 passed |
| tests/test_auth.py | 4 | 4 passed |
| tests/test_security.py | 3 | 3 passed, 1 skipped |
| **Total** | **30** | **30 passed, 1 skipped** |

All 9 Phase 3 backend tests GREEN. No regression in existing suites.

## Known Stubs

None. All routes are fully implemented and wired to the database.

## Threat Surface Scan

All new routes are protected by `Depends(get_current_user)` (T-03-03: auth bypass mitigated). All routes verify company ownership via `WHERE id=? AND user_id=?` before touching child tables (T-03-01: IDOR mitigated). All SQL uses `?` parameterized placeholders (T-03-02: SQL injection mitigated). All not-found/not-owned responses return 404 with generic messages (T-03-04: information disclosure mitigated).

No new network endpoints beyond those in the plan's threat model. No new trust boundary crossings.

## Self-Check: PASSED

- [x] `backend/main.py` modified — commits fcb4621 and d7fecc7 verified
- [x] `backend/db.py` modified — commit fcb4621 verified (description column in companies_new)
- [x] `tests/conftest.py` modified — commit fcb4621 verified (tests/ on sys.path)
- [x] `tests/test_profile.py` modified — commit fcb4621 verified (db.DB_PATH instead of conftest._TMP_DB_PATH)
- [x] All 11 new routes present in backend/main.py
- [x] list_companies enriched with sections_complete correlated subquery
- [x] profile_status returns 9-key dict with EBITDA bridge and fallback logic
- [x] DELETE routes return Response(status_code=204)
- [x] No f-string SQL interpolation in any new routes
- [x] 9 tests in test_profile.py: 9 passed
- [x] 21 existing tests (test_isolation.py, test_auth.py, test_security.py): all pass
