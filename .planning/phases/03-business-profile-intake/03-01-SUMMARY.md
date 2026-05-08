---
phase: 03-business-profile-intake
plan: "01"
subsystem: database-schema + test-scaffolding
tags:
  - schema-migration
  - sqlite
  - tdd-red
  - test-fixtures
dependency_graph:
  requires:
    - 02-multi-user-data-isolation  # companies table with user_id already migrated
  provides:
    - management_team table
    - ebitda_adjustments table
    - description column on companies
    - fresh_all_db fixture covering new tables
    - 9 RED test stubs in tests/test_profile.py
  affects:
    - 03-02-PLAN.md  # backend routes must turn the 9 RED tests GREEN
tech_stack:
  added: []
  patterns:
    - try/except ALTER TABLE idempotent migration in _migrate_db()
    - CREATE TABLE IF NOT EXISTS for new child tables in _migrate_db()
    - FK-ordered table deletion in fresh_all_db fixture
key_files:
  created:
    - tests/test_profile.py
  modified:
    - backend/db.py
    - tests/conftest.py
decisions:
  - D-01: description TEXT added via ALTER TABLE in existing try/except migration for-loop
  - D-02: management_team uses company_id FK (no user_id column); ownership verified at route layer
  - D-03: ebitda_adjustments uses company_id FK (no user_id column); same ownership model as D-02
  - TDD: test_profile_ownership_403 passes in RED phase because non-existent route returns 404 (expected)
metrics:
  duration: "4 minutes"
  completed_date: "2026-05-08"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 3
---

# Phase 3 Plan 1: Schema Migrations + RED Test Stubs Summary

**One-liner:** SQLite schema extended with description column, management_team and ebitda_adjustments child tables via idempotent _migrate_db(), with 9 RED pytest stubs covering PROF-01..PROF-04, D-05, D-06.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend _migrate_db with description column and two new child tables | cd95015 | backend/db.py |
| 2 | Extend fresh_all_db fixture to include new child tables | 9b47886 | tests/conftest.py |
| 3 | Create tests/test_profile.py with 9 RED stubs for PROF-01..PROF-04, D-05, D-06 | d05ce68 | tests/test_profile.py |

## Changes Made

### Task 1: backend/db.py — _migrate_db() extended

Three changes made to `_migrate_db(conn)`:

1. **description column ALTER** — appended to existing Phase 2 for-loop:
   ```python
   "ALTER TABLE companies ADD COLUMN description TEXT",
   ```

2. **management_team table** — inserted after Phase 2 index loop, before final `conn.commit()`:
   ```sql
   CREATE TABLE IF NOT EXISTS management_team (
       id          INTEGER PRIMARY KEY AUTOINCREMENT,
       company_id  INTEGER REFERENCES companies(id) ON DELETE CASCADE,
       name        TEXT NOT NULL,
       title       TEXT,
       bio         TEXT,
       created_at  TEXT DEFAULT (datetime('now'))
   )
   ```

3. **ebitda_adjustments table** — same location:
   ```sql
   CREATE TABLE IF NOT EXISTS ebitda_adjustments (
       id          INTEGER PRIMARY KEY AUTOINCREMENT,
       company_id  INTEGER REFERENCES companies(id) ON DELETE CASCADE,
       label       TEXT NOT NULL,
       amount      REAL NOT NULL,
       rationale   TEXT,
       created_at  TEXT DEFAULT (datetime('now'))
   )
   ```

4. **Two indexes**: `idx_mgmt_team_company ON management_team(company_id)` and `idx_ebitda_adj_company ON ebitda_adjustments(company_id)` — wrapped in try/except for idempotency.

Migration is idempotent: verified twice with `db.init_db()` — no errors on second run.

### Task 2: tests/conftest.py — fresh_all_db fixture extended

One-line edit to the FK-ordered table deletion list (line 81):

Before:
```python
for table in ["financial_rows", "extraction_log", "documents", "companies", "users"]:
```

After:
```python
for table in ["financial_rows", "extraction_log", "management_team", "ebitda_adjustments", "documents", "companies", "users"]:
```

`management_team` and `ebitda_adjustments` placed before `documents` and `companies` to respect FK constraints (children deleted before parents).

### Task 3: tests/test_profile.py — 9 RED test stubs

| Test Name | Requirement | Status |
|-----------|-------------|--------|
| test_save_industry | PROF-01 | RED (404 on non-existent route) |
| test_profile_ownership_403 | PROF-01 | Passes in RED phase (404 from non-existent route matches assertion) |
| test_save_description | PROF-02 | RED (404 on non-existent route) |
| test_management_team_crud | PROF-03 | RED (404 on non-existent route) |
| test_management_team_delete | PROF-03 | RED (404 on non-existent route) |
| test_ebitda_adjustments_crud | PROF-04 | RED (404 on non-existent route) |
| test_profile_status_gate | PROF-04, D-06 | RED (404 on non-existent route) |
| test_profile_status_blocked | PROF-04, D-06 | RED (404 on non-existent route) |
| test_ebitda_bridge_calculation | PROF-04, D-05 | RED (404 on non-existent route) |

**Note on test_profile_ownership_403:** This test asserts `r.status_code == 404` for an unowned company. In the RED phase, the route doesn't exist and FastAPI returns 404 for unknown routes. This test will remain GREEN after Plan 02 implements the route because an unowned company correctly returns 404. This is not a problem — it represents a valid Wave 0 state.

All 9 tests use the `fresh_all_db` fixture (now including the new child tables) and register a unique user per test to avoid cross-test pollution.

Plan 02 must implement the backend routes to turn all 9 tests GREEN.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — this plan creates schema and test scaffolding only. No production code stubs.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundary changes in this plan. Schema migrations and test fixtures only.

## Self-Check: PASSED

- [x] `backend/db.py` modified — commit cd95015 verified
- [x] `tests/conftest.py` modified — commit 9b47886 verified
- [x] `tests/test_profile.py` created — commit d05ce68 verified
- [x] Migration idempotent — verified twice with `db.init_db()`
- [x] management_team table has columns: id, company_id, name, title, bio, created_at
- [x] ebitda_adjustments table has columns: id, company_id, label, amount, rationale, created_at
- [x] fresh_all_db includes management_team and ebitda_adjustments before companies
- [x] 9 test stubs collected by pytest
- [x] 21 existing tests still pass (test_isolation.py, test_auth.py, test_security.py)
