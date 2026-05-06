---
phase: 02-multi-user-data-isolation
reviewed: 2026-05-07T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - backend/db.py
  - backend/main.py
  - tests/conftest.py
  - tests/test_isolation.py
findings:
  critical: 0
  warning: 0
  info: 2
  total: 10
status: fixed
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-07
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

The Phase 2 implementation adds `user_id` columns to `companies` and `documents`, applies `WHERE user_id=?` filters on all read paths, and verifies company ownership before document uploads. The overall shape is correct and the most critical IDOR vectors (direct GET by ID, list endpoints, upload to another user's company) are guarded.

However, three blockers exist: (1) a TOCTOU race in the retry endpoint allows a concurrent request to clear another user's financial data under the right timing, due to write operations using only `document_id` after the ownership check; (2) the `analytics/overview` endpoint leaks the global count of `label_patterns` rows to every authenticated user regardless of ownership; (3) the migration's `executescript` call silently commits any open ALTER TABLE transaction before running, meaning a crash between the first ALTER and the executescript results in a partially-migrated database with no rollback — the schema guard then finds the columns already present and skips re-adding them, but the UNIQUE constraint rebuild never ran.

Five warnings cover: the documents count in analytics using `c.user_id` instead of `d.user_id` (creates a blind spot for orphaned documents), missing test coverage for `/documents/{id}/rows` isolation, the shared `patterns_export.json` file being world-readable via `FileResponse`, the `fresh_all_db` fixture not enabling `PRAGMA foreign_keys=ON` before deleting, and the regex used in `normalise_label` importing inside a hot function.

---

## Critical Issues

### CR-01: Retry endpoint write operations do not re-validate ownership (TOCTOU / IDOR)

**File:** `backend/main.py:479-484`

**Issue:** The `retry_document` handler checks ownership at line 472 (`WHERE d.id=? AND d.user_id=?`), then issues three write statements that use only `document_id` without the user filter:

```python
await db.execute(
    "UPDATE documents SET extraction_status='pending' ... WHERE id=?",
    (document_id,)
)
await db.execute("DELETE FROM financial_rows WHERE document_id=?", (document_id,))
await db.execute("DELETE FROM extraction_log WHERE document_id=?", (document_id,))
```

Because `document_id` values are sequential integers, a race between a legitimate owner's retry and a concurrent request is not needed for this to be a logic defect — the pattern itself is wrong. If, for any reason (bug elsewhere, future code change), a caller reaches lines 479-484 holding a `document_id` that belongs to another user, it will silently wipe that user's ingestion data. The ownership proof obtained at line 473 is not carried into the write operations.

**Fix:** Add `AND user_id=?` to each write statement, or verify that the update touched exactly one row:

```python
await db.execute(
    "UPDATE documents SET extraction_status='pending', updated_at=datetime('now') WHERE id=? AND user_id=?",
    (document_id, current_user["id"])
)
await db.execute(
    "DELETE FROM financial_rows WHERE document_id=? AND document_id IN (SELECT id FROM documents WHERE user_id=?)",
    (document_id, current_user["id"])
)
await db.execute(
    "DELETE FROM extraction_log WHERE document_id=? AND document_id IN (SELECT id FROM documents WHERE user_id=?)",
    (document_id, current_user["id"])
)
```

---

### CR-02: `analytics/overview` leaks global `label_patterns` count to all users

**File:** `backend/main.py:380`

**Issue:** Every other query in `analytics_overview` is scoped to `current_user["id"]`, but the `label_patterns` query has no user filter:

```python
async with db.execute("SELECT COUNT(*) as n FROM label_patterns") as cur:
    patterns = (await cur.fetchone())["n"]
```

The `label_patterns` table is populated from all users' documents. Any authenticated user can learn the total number of patterns in the system — effectively revealing information about other users' data volume and activity. As the platform grows this becomes an information disclosure vulnerability.

Note also that `label_patterns` has no `user_id` column. If patterns are intentionally shared across users (as a global ML library), that design decision should be made explicit and documented. If it is unintentional, a `user_id` column and per-user filter are needed.

**Fix (if patterns are meant to be global/shared — just document it):**
Remove `label_patterns` from the overview response or label it clearly as a global system count in the API contract.

**Fix (if patterns should be per-user):**
Add `user_id INTEGER` to `label_patterns`, filter all reads by `user_id=?`, and filter this query accordingly.

---

### CR-03: Migration `_migrate_db` partial-commit risk — ALTER TABLE changes can be committed without the UNIQUE constraint rebuild

**File:** `backend/db.py:122-182`

**Issue:** `_migrate_db` executes several `ALTER TABLE` statements using `conn.execute()` inside try/except blocks (lines 122-132). Python's `sqlite3` module operates in implicit-transaction mode by default (`isolation_level = ''`). These DDL statements open an implicit transaction.

When `conn.executescript(...)` is called at line 151, the [Python docs](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.executescript) state: _"If there is a pending transaction, an implicit COMMIT statement is executed first."_ This means the ALTER TABLE changes are committed to disk **before** the `companies_new` table rename script runs. If the process crashes or the script fails between these two phases, the database is left with the `user_id` columns added but the old `UNIQUE(name, exchange)` constraint still in place — and the idempotency guard on line 143 will correctly detect this partial state on the next run (the `user_id` column exists but the UNIQUE constraint does not match), so it will re-run. That part is okay.

The more dangerous path: if `companies_new` already exists from a previous failed attempt, the guard at lines 145-149 drops it. However `DROP TABLE companies_new` is itself a DDL statement that could fail silently if FK constraints block it, and there is no error handling around that drop. If it fails silently (the `except` only wraps the `ALTER TABLE` loops, not this `DROP`), `executescript` will fail on `CREATE TABLE companies_new` and raise, leaving the function having already committed the ALTER TABLE changes without the UNIQUE rebuild.

**Fix:** Wrap the entire migration in a single explicit transaction and use explicit error handling:

```python
conn.execute("BEGIN")
try:
    # all migration steps
    conn.execute("COMMIT")
except Exception:
    conn.execute("ROLLBACK")
    raise
```

Alternatively, make each migration step fully idempotent and independently safe rather than relying on a single `executescript` with an embedded `BEGIN/COMMIT`.

---

## Warnings

### WR-01: `analytics/overview` documents count uses `c.user_id` — orphaned documents with direct `user_id` bypass the join

**File:** `backend/main.py:362-367`

**Issue:** The documents count query joins `documents` to `companies` and filters by `c.user_id`:

```sql
SELECT COUNT(*) as n FROM documents d
JOIN companies c ON c.id = d.company_id
WHERE c.user_id=?
```

Documents also have their own `d.user_id` column (added in Phase 2). A document uploaded via the upload endpoint has both `d.user_id` and `d.company_id` set correctly, so the join is sound. However, the upload endpoint verifies `company_id` ownership and then uses `company_id` from the request, not from the document's `user_id`. If a document somehow ends up with `d.company_id = NULL` (FK is not `NOT NULL` in schema — line 32 of `db.py`), the JOIN would drop it from the count. The more consistent pattern is to filter by `d.user_id = ?` directly, which is what `list_documents` already does (line 149). This inconsistency will become a bug if any code path sets `d.user_id` without setting `d.company_id`.

**Fix:** Apply the same direct filter used in `list_documents`:

```sql
SELECT COUNT(*) as n FROM documents d
WHERE d.user_id=?
```

---

### WR-02: `GET /documents/{document_id}/status` fetches `extraction_log` without user gate

**File:** `backend/main.py:248-252`

**Issue:** The outer document fetch at lines 238-244 correctly enforces `d.user_id=?` and returns 404 if not owned. If that guard passes, the log fetch on line 249 queries `extraction_log` by `document_id` alone:

```python
async with db.execute("""
    SELECT level, message, created_at FROM extraction_log
    WHERE document_id=? ORDER BY id DESC LIMIT 30
""", (document_id,)) as cur:
```

This is not a direct IDOR because the outer guard already validated ownership. However it is a latent risk: if the outer query is ever refactored to not 404 early, or if the `extraction_log` endpoint is duplicated elsewhere without the guard, logs from another user's document would leak. The fix also makes the code more obviously correct on its own.

**Fix:** Enforce ownership in the log query by subquery or join:

```sql
SELECT el.level, el.message, el.created_at
FROM extraction_log el
JOIN documents d ON d.id = el.document_id
WHERE el.document_id=? AND d.user_id=?
ORDER BY el.id DESC LIMIT 30
```

---

### WR-03: `GET /patterns/export` writes a shared file overwritten by concurrent users

**File:** `backend/main.py:340-345`

**Issue:** The export endpoint writes to a fixed path:

```python
export_path = EXPORT_DIR / "patterns_export.json"
with open(export_path, "w") as f:
    json.dump(lib, f, indent=2)
return FileResponse(str(export_path), ...)
```

All users share a single `patterns_export.json` file. Two concurrent requests will race on the file write. More importantly, the file is written synchronously in an async route handler, blocking the event loop for the duration of the JSON write. This violates the project's convention (CLAUDE.md) that synchronous I/O in async routes must be wrapped in `run_in_executor`.

**Fix:** Use a unique per-request temp file (or stream the response in-memory) and wrap the write in `run_in_executor`:

```python
import tempfile, asyncio
loop = asyncio.get_running_loop()
buf = await loop.run_in_executor(None, lambda: json.dumps(lib, indent=2))
return Response(content=buf, media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=accountiq_patterns.json"})
```

---

### WR-04: `fresh_all_db` fixture does not enable `PRAGMA foreign_keys=ON` before deleting

**File:** `tests/conftest.py:79-89`

**Issue:** The `fresh_all_db` fixture opens a direct `aiosqlite` connection and deletes rows from each table sequentially. It does not issue `PRAGMA foreign_keys=ON`. Without FK enforcement, the deletion order (children before parents) still works in practice, but if the order is accidentally changed in a future edit, silent data corruption could occur without any FK violation being raised. Additionally, if a future schema adds a `RESTRICT` FK that crosses a table boundary not in this list, the fixture would not catch it.

**Fix:** Enable FK enforcement at the start of the fixture connection:

```python
async with aiosqlite.connect(_TMP_DB_PATH) as conn:
    await conn.execute("PRAGMA foreign_keys=ON")
    for table in ["financial_rows", "extraction_log", "documents", "companies", "users"]:
        ...
```

---

### WR-05: Isolation tests do not cover `GET /documents/{id}/rows` or `GET /financials/{company_id}`

**File:** `tests/test_isolation.py`

**Issue:** The success criterion SC-1 states "User A cannot retrieve User B's companies or documents via **any** API endpoint." The test file covers:
- `GET /companies` list and `GET /companies/{id}` (direct)
- `GET /documents` list and `GET /documents/{id}/status`
- `POST /documents/upload` to another user's company
- `GET /analytics/overview`

Not covered:
- `GET /documents/{id}/rows` — cross-user financial row access by document ID
- `GET /financials/{company_id}` — cross-user financial rows by company ID

Both routes exist in `main.py` (lines 257-270 and 277-304) with correct `user_id` guards, but they are untested. A future regression that drops the guard would not be caught.

**Fix:** Add tests:

```python
async def test_cross_user_financial_rows_isolation(client, fresh_all_db):
    """User B cannot access User A's financial rows via document or company endpoints."""
    await _register(client, "alice5@test.com")
    alice_co = await _create_company(client, "Alice Fin Corp", "NZX")
    # ... upload a doc, get doc id ...
    async with _make_bob_client() as bob:
        await _register(bob, "bob5@test.com")
        r = await bob.get(f"/documents/{alice_doc_id}/rows")
        assert r.status_code == 404
        r = await bob.get(f"/financials/{alice_co}")
        assert r.json() == []
```

---

## Info

### IN-01: `normalise_label` imports `re` inside the function body on every call

**File:** `backend/db.py:203-208`

**Issue:** The `import re` statement is inside `normalise_label`, which is called for every row during pattern learning. While Python caches module imports, the attribute lookup on `sys.modules` occurs on every call.

**Fix:** Move the import to the module top-level alongside the other imports.

---

### IN-02: `get_db` re-issues `PRAGMA` statements on every request connection

**File:** `backend/db.py:111-117`

**Issue:** `get_db` issues `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` on every request. `journal_mode=WAL` is a persistent database-level setting that only needs to be set once (on database creation). Issuing it on every connection is harmless but wasteful.

**Fix:** Remove `PRAGMA journal_mode=WAL` from `get_db` (keep `PRAGMA foreign_keys=ON` since that must be set per-connection). The WAL pragma is already applied in `SCHEMA` via `init_db`.

---

_Reviewed: 2026-05-07_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
