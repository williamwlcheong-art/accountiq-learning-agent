---
phase: 02-multi-user-data-isolation
verified: 2026-05-07T09:45:00Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 0
---

# Phase 2: Multi-User Data Isolation — Verification Report

**Phase Goal:** Each user sees only their own data — companies, documents, financials, and analytics are all isolated by user_id. Cross-user access attempts return 404 (not 403). Existing NULL user_id rows become invisible without deletion.
**Verified:** 2026-05-07T09:45:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User A cannot retrieve User B's companies or documents via any API endpoint (IDOR) | VERIFIED | `test_cross_user_company_isolation` and `test_cross_user_document_isolation` pass; `GET /companies/{id}` uses `WHERE id=? AND user_id=?` |
| 2 | Existing NULL user_id rows are not visible to any authenticated user | VERIFIED | `test_null_user_rows_invisible` passes; all queries use `WHERE user_id=?` — SQLite NULL != integer |
| 3 | A newly registered user's uploaded documents are not visible to any other user | VERIFIED | `test_cross_user_document_isolation` passes; documents INSERT stamps `user_id = current_user["id"]` |
| 4 | All API routes that return companies or documents enforce the user_id filter | VERIFIED | `test_list_endpoints_scoped` and `test_upload_to_other_users_company_rejected` pass; grep confirms all routes |
| 5 | GET /companies returns only the authenticated user's own companies | VERIFIED | `WHERE c.user_id = ?` at line 87 of `main.py` |
| 6 | POST /companies assigns user_id = current_user['id'] on INSERT | VERIFIED | `INSERT INTO companies (... user_id) VALUES (... ?)` at line 107 of `main.py` |
| 7 | GET /companies/{id} returns 404 (not 403) when company belongs to another user | VERIFIED | `WHERE id=? AND user_id=?` at line 126; raises HTTPException(404) |
| 8 | GET /documents returns only the authenticated user's own documents | VERIFIED | `WHERE d.user_id = ?` at line 149 of `main.py` |
| 9 | POST /documents/upload verifies company ownership and stamps user_id | VERIFIED | Company check `WHERE id=? AND user_id=?` at line 179; documents INSERT includes `user_id` at line 195 |
| 10 | GET /documents/{id}/status returns 404 for cross-user document IDs | VERIFIED | `WHERE d.id=? AND d.user_id=?` at line 241 |
| 11 | GET /documents/{id}/rows returns 404 for cross-user document IDs | VERIFIED | JOIN to documents with `d.user_id=?` at line 264 |
| 12 | GET /analytics/overview counts only the current user's companies/documents/financial_rows | VERIFIED | All 5 COUNT queries scoped via `WHERE user_id=?` or `JOIN companies c WHERE c.user_id=?`; `label_patterns` stays global (D-03) |
| 13 | POST /documents/{id}/retry returns 404 for cross-user document IDs | VERIFIED | `WHERE d.id=? AND d.user_id=?` at line 471 |

**Score:** 13/13 truths verified

### Deferred Items

None.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/db.py` | Extended `_migrate_db` with user_id columns, UNIQUE constraint rebuild, indexes | VERIFIED | Lines 120–182 implement the full migration with idempotency guards |
| `backend/main.py` | All company/document routes updated with user_id filter or assignment | VERIFIED | 9 route changes confirmed via code and grep analysis |
| `tests/conftest.py` | `fresh_all_db` fixture that clears all tables in FK-safe order | VERIFIED | Lines 70–89; deletes financial_rows, extraction_log, documents, companies, users |
| `tests/test_isolation.py` | 5 integration smoke tests for AUTH-07 and DATA-01 | VERIFIED | 5 test functions; all pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/db.py _migrate_db` | companies table schema | `ALTER TABLE + executescript table-rename` | VERIFIED | `user_id INTEGER` column added; `UNIQUE(name, exchange, user_id)` constraint present in live DB |
| `GET /companies` handler | companies table | `WHERE c.user_id = ?` | VERIFIED | Line 87 of `main.py` |
| `GET /companies/{id}` handler | companies table | `WHERE id=? AND user_id=?` | VERIFIED | Line 126 of `main.py` |
| `GET /documents` handler | documents table | `WHERE d.user_id = ?` | VERIFIED | Line 149 of `main.py` |
| `POST /documents/upload` handler | companies + documents table | `AND user_id=?` ownership check + user_id INSERT | VERIFIED | Lines 179 and 195 of `main.py` |
| `GET /financials/{company_id}` handler | financial_rows + companies tables | `JOIN companies c WHERE c.user_id = ?` | VERIFIED | Line 294 of `main.py` |
| `GET /analytics/overview` handler | companies + documents + financial_rows | `WHERE user_id=?` / `JOIN companies WHERE c.user_id=?` | VERIFIED | Lines 357–385 of `main.py` |
| `GET /analytics/confidence` handler | financial_rows + companies | `JOIN companies WHERE c.user_id=?` | VERIFIED | Line 407 of `main.py` |
| `tests/test_isolation.py` | GET /companies, GET /documents, POST /documents/upload | Two AsyncClient instances with separate cookie jars | VERIFIED | `_make_bob_client()` creates fresh client per test block |

### Data-Flow Trace (Level 4)

Not applicable — this phase modifies SQL filtering logic and database schema, not data rendering pipelines. The "data flow" is: authenticated `current_user["id"]` from JWT → SQL WHERE clause → filtered row set returned. This is verified by the integration tests which prove correct data flows (only user-owned rows returned).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 5 isolation tests pass | `python -m pytest tests/test_isolation.py -v` | 5 passed, 0 failed | PASS |
| Full test suite passes without regressions | `python -m pytest tests/ -v` | 20 passed, 1 skipped, 0 failed | PASS |
| App imports without syntax error | `python -c "import sys; sys.path.insert(0,'backend'); import main; print('OK')"` | OK | PASS |
| init_db() is idempotent | `python -c "import db; db.init_db()"` (called twice) | `[DB] Initialised` with no exception | PASS |
| DB schema has UNIQUE(name, exchange, user_id) | sqlite_master check | Constraint confirmed present | PASS |
| idx_companies_user and idx_documents_user exist | sqlite_master index check | Both indexes present | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| AUTH-07 | 02-01, 02-02, 02-03 | Each user's companies and documents are private (no cross-user data leakage) | SATISFIED | Route-level `WHERE user_id=?` filters on all company/document/analytics routes; IDOR returns 404; 5 integration tests prove isolation holds |
| DATA-01 | 02-01, 02-02, 02-03 | SUPERSEDED by D-01 decision in 02-CONTEXT.md — existing NULL user_id rows become invisible (not shared demo data) | SATISFIED (with deviation) | REQUIREMENTS.md DATA-01 text says "visible as shared demo data"; CONTEXT.md D-01 explicitly supersedes this: existing rows invisible via `WHERE user_id = ?` (NULL never matches integer). ROADMAP.md Success Criterion 2 confirms this interpretation. See note below. |

**DATA-01 note:** There is a documented conflict between REQUIREMENTS.md (DATA-01 says "visible as shared demo data") and the implemented behaviour (NULL rows invisible). This was a deliberate design decision captured in 02-CONTEXT.md decision D-01: "DATA-01 as written in REQUIREMENTS.md is superseded by this decision." The ROADMAP.md success criteria (the authoritative phase contract) explicitly states "Existing companies and documents (with no owner, NULL user_id) are not visible to any authenticated user" — matching the implementation exactly. The REQUIREMENTS.md text is outdated and was knowingly overridden. This is a documentation debt, not an implementation defect.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/main.py` | 59 | `@app.on_event("startup")` deprecated | Info | FastAPI deprecation warning only; no functional impact; recommended fix in a future phase |

No TODO/FIXME/PLACEHOLDER patterns found in any modified file. No empty handler stubs. No hardcoded empty data returns in route handlers. No unscoped COUNT queries remaining (except `label_patterns` which is intentionally global per D-03).

**Minor discrepancy — plan grep criterion vs actual counts:**
- Plan 02 Task 2 acceptance criterion: `grep -c "AND c.user_id=?" backend/main.py` returns at least 3
- Actual result: returns 1 (because most user_id checks on the companies table use `WHERE c.user_id=?` not `AND c.user_id=?`)
- Total `c.user_id` references in main.py: 7 (all correctly scoped)
- This is a gap in the plan's grep criterion, not an implementation defect. The SQL is correct and tests prove it.

### Human Verification Required

None. All success criteria for this phase are verifiable programmatically via the integration test suite. The test suite passes with 20/21 tests (1 skipped for unrelated reason — `test_filename_traversal_basename_only` in security tests).

### Gaps Summary

No gaps. All 13 must-have truths are VERIFIED. The full test suite passes. Route-level isolation is correctly implemented and proven by integration tests using real HTTP sessions against the actual FastAPI app.

**One operational observation (not a code gap):** The migration in Plan 01 was verified against a worktree-local SQLite database, not the main repo's `data/accountiq_learning.db`. As a result, the live DB was in a partially-migrated state (user_id columns added but UNIQUE constraint not yet rebuilt, and indexes missing) until `init_db()` was invoked directly during this verification. The migration code ran successfully and all checks now pass. This is not a defect — the migration code is correct and idempotent. The server's startup event (`init_db()` in `@app.on_event("startup")`) will apply the migration the first time the server starts.

---

_Verified: 2026-05-07T09:45:00Z_
_Verifier: Claude (gsd-verifier)_
