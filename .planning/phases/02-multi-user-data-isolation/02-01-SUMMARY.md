---
phase: 02-multi-user-data-isolation
plan: 01
subsystem: database
tags: [sqlite, migration, schema, user-isolation, indexes]

# Dependency graph
requires:
  - phase: 01-security-auth-foundation
    provides: users table with id, email, hashed_pw — user_id FK target
provides:
  - user_id INTEGER column on companies table (nullable, no existing rows affected)
  - user_id INTEGER column on documents table (nullable, no existing rows affected)
  - UNIQUE(name, exchange, user_id) constraint on companies (replaces UNIQUE(name, exchange))
  - idx_companies_user index for per-user company queries
  - idx_documents_user index for per-user document queries
  - Idempotent _migrate_db() that is safe to call on any existing DB state
affects: [02-02-route-filtering, 02-03-integration-tests, all future phases using companies/documents tables]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SQLite table-rename pattern for UNIQUE constraint rebuild (no ALTER CONSTRAINT in SQLite)"
    - "Idempotency guard via sqlite_master schema string check before table-rename"
    - "companies_new leftover cleanup guard for interrupted migration recovery"
    - "try/except sqlite3.OperationalError: pass for idempotent ALTER TABLE ADD COLUMN"

key-files:
  created: []
  modified:
    - backend/db.py

key-decisions:
  - "user_id columns are nullable (INTEGER, no NOT NULL) — existing rows retain NULL and remain invisible to authenticated users without deletion"
  - "Table-rename pattern chosen over virtual migration table to atomically swap the UNIQUE constraint in SQLite"
  - "Idempotency guard reads sqlite_master DDL string rather than PRAGMA table_info — catches full constraint shape, not just column presence"

patterns-established:
  - "Phase migration pattern: extend _migrate_db for each phase's schema changes, guarded by try/except or sqlite_master check"
  - "NULL user_id as implicit 'pre-auth' / legacy-demo sentinel — never deleted, never surfaced to authenticated users"

requirements-completed:
  - AUTH-07
  - DATA-01

# Metrics
duration: 10min
completed: 2026-05-07
---

# Phase 2 Plan 01: DB Schema — user_id Columns + UNIQUE Constraint Rebuild Summary

**SQLite migration adds user_id INTEGER to companies and documents, rebuilds UNIQUE(name, exchange, user_id) via table-rename, and creates query-performance indexes — idempotent and safe on live DB**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-07T00:00:00Z
- **Completed:** 2026-05-07T00:10:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Extended `_migrate_db()` with two new user_id ALTER TABLE statements (companies, documents) using existing idempotent try/except pattern
- Rebuilt companies UNIQUE constraint from `UNIQUE(name, exchange)` to `UNIQUE(name, exchange, user_id)` using SQLite table-rename pattern with full idempotency guard
- Added `idx_companies_user` and `idx_documents_user` indexes for efficient per-user WHERE clauses in Plan 02 route filtering
- All migration steps verified idempotent — calling `init_db()` twice raises no exceptions

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend _migrate_db with user_id columns, UNIQUE constraint rebuild, and indexes** - `1204106` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `backend/db.py` - Extended `_migrate_db()` with Phase 2 schema migration: user_id columns on companies and documents, table-rename UNIQUE constraint rebuild, and user query indexes

## Decisions Made
- user_id is nullable (no NOT NULL constraint) so existing rows without owners are preserved as NULL — they become invisible to authenticated users via `WHERE user_id = ?` without any data deletion
- Idempotency guard checks `sqlite_master` DDL string for `"UNIQUE(name, exchange, user_id)"` rather than just column presence, ensuring the full constraint shape is verified before skipping the table-rename
- companies_new cleanup guard added to handle interrupted previous migration attempts

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - this plan only modifies DB schema via migration code. No UI rendering or data flow paths involved.

## Threat Flags

No new network endpoints, auth paths, or file access patterns introduced. Migration code runs at startup with no user input surface (T-2-01 through T-2-03 mitigations confirmed implemented as planned).

## Issues Encountered

The plan's verification script used `cd /Users/William.Cheong/accountiq_learning` before importing `db`, which caused it to load the original repo's `backend/db.py` (unchanged) instead of the worktree's modified file. Verification was re-run directly from the worktree directory, where the updated `db.py` was imported correctly and all assertions passed.

## Self-Check

- [x] `backend/db.py` modified — confirmed at `/Users/William.Cheong/accountiq_learning/.claude/worktrees/agent-a707afaf1dbcdade1/backend/db.py`
- [x] Task commit `1204106` exists in git log
- [x] ALL CHECKS PASSED (user_id columns, UNIQUE constraint, both indexes)
- [x] IDEMPOTENCY CHECK PASSED (init_db() called twice with no error)

## Self-Check: PASSED

## Next Phase Readiness
- DB schema foundation is in place — Plan 02 can now add `WHERE user_id = ?` filters to all company and document route handlers
- NULL user_id rows (existing pre-auth data) will be invisible to all authenticated users without deletion
- No blockers

---
*Phase: 02-multi-user-data-isolation*
*Completed: 2026-05-07*
