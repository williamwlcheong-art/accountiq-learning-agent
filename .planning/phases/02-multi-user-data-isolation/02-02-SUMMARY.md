---
phase: 02-multi-user-data-isolation
plan: 02
subsystem: api-routes
tags: [fastapi, user-isolation, idor, sql-filtering, data-isolation]

# Dependency graph
requires:
  - phase: 02-multi-user-data-isolation
    plan: 01
    provides: user_id columns on companies and documents tables with indexes
provides:
  - All company/document routes enforce WHERE user_id=? filters
  - Analytics routes scoped to current user's data
  - IDOR protection on single-row lookups (returns 404 not 403)
  - Documents INSERT stamps user_id on creation
affects: [02-03-integration-tests, all future phases using company/document routes]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Compound WHERE clause pattern: WHERE id=? AND user_id=? for single-row IDOR prevention"
    - "Base WHERE then AND pattern: WHERE d.user_id=? as unconditional base; optional filters become AND clauses"
    - "JOIN-based ownership: financial_rows filtered via JOIN companies WHERE c.user_id=?"
    - "D-03 exception: label_patterns COUNT stays global — no user_id filter for ML pattern learning"

key-files:
  created: []
  modified:
    - backend/main.py

key-decisions:
  - "Returns 404 (not 403) on cross-user resource access to prevent IDOR by hiding resource existence"
  - "label_patterns routes left global per D-03 decision — pattern learning is intentionally cross-user shared ML data"
  - "financial_rows filtered via JOIN companies rather than direct user_id column since financial_rows table has no user_id — ownership traced through company"
  - "Analytics overview label_patterns COUNT kept global while all other 5 queries scoped to current user"

requirements-completed:
  - AUTH-07
  - DATA-01

# Metrics
duration: 2min
completed: 2026-05-07
---

# Phase 2 Plan 02: Route-Level User Isolation Summary

**All 11 API route handlers updated with WHERE user_id=? SQL filters, closing the gap between schema columns (Plan 01) and enforcement — authenticated users can now only read and write their own data**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-06T21:21:16Z
- **Completed:** 2026-05-06T21:24:08Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Applied 3 company route changes (GET /companies, POST /companies, GET /companies/{id}) — Task 1
- Applied 9 document/analytics route changes across 6 routes — Task 2:
  - GET /documents: unconditional `WHERE d.user_id = ?` base; company_id filter demoted to AND clause
  - POST /documents/upload: company existence check adds `AND user_id=?`; documents INSERT includes `user_id` column
  - GET /documents/{id}/status: `WHERE d.id=? AND d.user_id=?` (IDOR protection, 404 on mismatch)
  - GET /documents/{id}/rows: JOIN to documents table verifies `d.user_id=?` (IDOR protection)
  - GET /financials/{company_id}: JOIN companies adds `AND c.user_id=?` filter
  - GET /analytics/overview: all 5 COUNT queries scoped to current user via WHERE/JOIN; label_patterns COUNT stays global (D-03)
  - GET /analytics/confidence: JOIN companies adds `WHERE c.user_id=?`
  - POST /documents/{id}/retry: `WHERE d.id=? AND d.user_id=?` (IDOR protection)
- All 13 existing auth tests continue to pass with 0 failures
- App imports cleanly with no syntax errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Company route user_id filters** — `cad2b39` (feat)
2. **Task 2: Document and analytics route user_id filters** — `63035ad` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend/main.py` — All 12 route changes applied (3 company + 9 document/analytics): WHERE user_id filters, IDOR-preventing compound conditions, and user_id stamping on INSERT operations

## Decisions Made

- 404 returned (not 403) on cross-user resource lookups to prevent IDOR by hiding whether a resource exists
- label_patterns routes remain global per D-03 decision — aggregate ML pattern data, no PII, no user-identifying data
- financial_rows owned-by traced through companies JOIN since financial_rows has no direct user_id column
- Analytics overview preserves label_patterns global count while scoping all other 5 COUNT queries to authenticated user

## Deviations from Plan

None - plan executed exactly as written. All 9 changes in Task 2 were applied as specified, including the exact SQL patterns from the plan's `<interfaces>` section.

## Known Stubs

None — this plan modifies SQL filtering only. No UI rendering or data display paths involved.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. This plan closes the following threat register items from T-2-02 through T-2-05:

| Threat | Mitigation Applied |
|--------|-------------------|
| T-2-02 (IDOR via single-row lookups) | `WHERE id=? AND user_id=?` compound condition on /companies/{id}, /documents/{id}/status, /documents/{id}/rows, /documents/{id}/retry |
| T-2-03 (list endpoint disclosure) | `WHERE user_id=?` applied unconditionally to /companies and /documents list queries |
| T-2-04 (upload against another user's company) | Company existence check adds `AND user_id=?` |
| T-2-05 (analytics aggregate leakage) | All COUNT/AVG queries in /analytics/overview and /analytics/confidence scoped to current_user["id"] |
| T-2-06 (label_patterns) | Accepted — intentionally global per D-03 |
| T-2-07 (NULL user_id bypass) | Accepted — SQLite NULL != integer; no bypass via NULL injection through typed int params |

## Self-Check

- [x] `backend/main.py` modified — confirmed at `/Users/William.Cheong/accountiq_learning/.claude/worktrees/agent-af90b1d65d0ef4c9f/backend/main.py`
- [x] Task 1 commit `cad2b39` exists in git log
- [x] Task 2 commit `63035ad` exists in git log
- [x] 13 tests pass, 0 failures
- [x] App imports cleanly: `python -c "import main; print('OK')"` outputs OK
- [x] All grep acceptance criteria satisfied (WHERE c.user_id, WHERE d.user_id, AND d.user_id=?, AND user_id=?, user_id) column count)
- [x] No unscoped COUNT queries remain (except label_patterns which is D-03 exempt)

## Self-Check: PASSED

## Next Phase Readiness

- Route-level isolation is fully enforced — Plan 03 (integration tests) can now verify cross-user isolation end-to-end
- NULL user_id rows (pre-auth/legacy data) are invisible to all authenticated users
- No blockers
---
*Phase: 02-multi-user-data-isolation*
*Completed: 2026-05-07*
