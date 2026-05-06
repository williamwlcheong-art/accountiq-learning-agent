# Phase 2: Multi-User Data Isolation — Research

**Researched:** 2026-05-06
**Domain:** SQLite schema migration, FastAPI row-level security, IDOR prevention
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** All companies and documents are strictly private to the user who created them. No shared or demo company concept. DATA-01 as written in REQUIREMENTS.md is superseded by this decision.
- **D-02:** Existing rows in the DB (pre-auth, no user_id) become invisible after Phase 2. They are never returned by any API query. Implementation: all company/document queries include `WHERE user_id = ?` — NULL user_id rows simply drop out. No deletion required; rows remain in DB for safety.
- **D-03:** The `label_patterns` table stays global — pattern learning is cumulative across all users. No `user_id` column needed on `label_patterns`.
- **D-04:** Change `UNIQUE(name, exchange)` to `UNIQUE(name, exchange, user_id)`. Each user gets their own company namespace.
- **D-05:** The `/analytics` endpoints must filter to the authenticated user's own companies only.

### Claude's Discretion

- Migration mechanics: SQLite `ALTER TABLE ... ADD COLUMN user_id INTEGER` (nullable, no default) is the correct approach.
- Document access: both `companies` and `documents` get `user_id` columns; document `user_id` always equals the owning user's id and is set at upload time from `current_user["id"]`.
- `financial_rows` and `extraction_log` access is derived from document/company ownership — no `user_id` column needed on those tables.
- Route filtering: use `WHERE user_id = ?` with `current_user["id"]` for all direct company/document lookups. Return 404 (not 403) if not owner.

### Deferred Ideas (OUT OF SCOPE)

- None — discussion stayed within phase scope.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-07 | Each user's companies and documents are private (no cross-user data leakage) | Covered by: migration adding user_id to companies+documents, WHERE user_id filter on all routes, 404 for cross-user IDOR attempts |
| DATA-01 | Superseded by D-01/D-02: existing rows become invisible (NULL user_id drops out of all queries); no shared demo data | Covered by: NULL-safe WHERE user_id = ? filtering; no rows deleted |

</phase_requirements>

---

## Summary

Phase 2 adds a single nullable `user_id INTEGER` column to `companies` and `documents` tables, then updates every route that reads from those tables to include `WHERE user_id = ?` using `current_user["id"]`. Existing rows (NULL user_id) naturally drop out of all filtered queries — they become invisible without deletion. The UNIQUE constraint on companies must be rebuilt to include user_id, which requires a full table-rename migration in SQLite since ALTER TABLE cannot modify existing constraints.

The codebase already has `get_current_user` injected into all 15 routes from Phase 1 work. Phase 2 simply starts consuming `current_user["id"]` in the SQL layer. The pattern is uniform and low-risk: add one parameter to every SELECT/INSERT, update the UNIQUE constraint, and the isolation is complete.

The test infrastructure (pytest + pytest-asyncio + httpx AsyncClient) is already in place and working (15 passed, 1 skipped on the existing suite). The smoke test for cross-user isolation follows the exact same pattern as existing auth tests — two clients, two cookies, assert 404 on cross-user resource access.

**Primary recommendation:** Execute in three discrete steps — (1) schema migration via `_migrate_db`, (2) route updates, (3) integration tests. All three are independent sub-tasks but must be sequenced: migration first, then routes, then tests.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| User-id column addition | Database Layer (db.py) | — | Schema change belongs in `_migrate_db()` alongside existing v2 migration |
| UNIQUE constraint rebuild | Database Layer (db.py) | — | SQLite table-rename pattern; one-time migration at startup |
| Ownership filter on reads | API Layer (main.py routes) | — | Each route owns its own SQL; no ORM abstraction layer exists |
| Ownership assignment on writes | API Layer (main.py routes) | — | INSERT time, using `current_user["id"]` already in scope |
| Cross-user IDOR return code | API Layer (main.py routes) | — | 404 response hides existence; matches existing error handling style |
| Pattern library isolation | None | — | D-03: label_patterns is intentionally global, no change needed |
| Analytics user-scoping | API Layer (main.py /analytics/*) | Database Layer | COUNT queries must add JOIN+WHERE against companies.user_id |
| Integration smoke test | Test Layer (tests/) | — | pytest-asyncio + httpx AsyncClient; follows existing conftest pattern |

---

## Standard Stack

### Core (already installed — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiosqlite | existing | Async SQLite for all DB operations | Project standard; all routes already use it |
| FastAPI | existing | Route definitions + HTTPException | Project standard |
| pytest | 9.0.3 | Test runner | Already in project [VERIFIED: venv] |
| pytest-asyncio | 1.3.0 | Async test support | Already in project [VERIFIED: venv] |
| httpx | 0.28.1 | AsyncClient for test requests | Already in project [VERIFIED: venv] |

**No new packages are needed for this phase.** [VERIFIED: codebase inspection]

---

## Architecture Patterns

### System Architecture Diagram

```
HTTP Request (with accountiq_session cookie)
    │
    ▼
get_current_user(Depends)          ← already on all 15 routes
    │ returns {"id": int, "email": str, "created_at": str}
    │
    ▼
Route handler (main.py)
    │
    ├─── SELECT ... WHERE user_id = current_user["id"]  ← Phase 2 adds this
    │       └── NULL user_id rows never match → invisible
    │
    ├─── INSERT ... user_id = current_user["id"]        ← Phase 2 adds this
    │
    └─── 404 if row found but user_id != current_user["id"]  ← Phase 2 adds this
              (never 403 — do not leak existence)
```

### Recommended Project Structure

No new files or directories are needed. All changes are in:
```
backend/
├── db.py           # _migrate_db() — adds user_id columns + UNIQUE rebuild
└── main.py         # All route handlers — add WHERE user_id / INSERT user_id
tests/
└── test_isolation.py   # New: AUTH-07 smoke test (cross-user IDOR)
```

### Pattern 1: Adding user_id to SELECT queries

**What:** Add `WHERE c.user_id = ?` / `WHERE d.user_id = ?` to every SELECT that returns companies or documents.

**When to use:** GET /companies, GET /documents, GET /analytics/overview, GET /analytics/confidence

```python
# Source: [ASSUMED] — based on project's existing parameterized query pattern in main.py
# GET /companies — before Phase 2 (NO isolation):
async with db.execute("""
    SELECT c.*, COUNT(d.id) as doc_count
    FROM companies c
    LEFT JOIN documents d ON d.company_id = c.id
    GROUP BY c.id
    ORDER BY c.name
""") as cur:

# GET /companies — after Phase 2 (WITH isolation):
async with db.execute("""
    SELECT c.*, COUNT(d.id) as doc_count
    FROM companies c
    LEFT JOIN documents d ON d.company_id = c.id
    WHERE c.user_id = ?
    GROUP BY c.id
    ORDER BY c.name
""", (current_user["id"],)) as cur:
```

### Pattern 2: Adding user_id to INSERT queries

**What:** Include `user_id` column in every INSERT for companies and documents.

**When to use:** POST /companies, POST /documents/upload

```python
# Source: [ASSUMED] — follows project INSERT pattern from main.py lines 105-109
# POST /companies — after Phase 2:
async with db.execute("""
    INSERT INTO companies (name, ticker, exchange, sector, country, user_id)
    VALUES (?, ?, ?, ?, ?, ?)
""", (name, ticker, exchange, sector, country, current_user["id"])) as cur:
    company_id = cur.lastrowid
```

### Pattern 3: Single-row lookup with ownership check (IDOR prevention)

**What:** Combine `WHERE id = ? AND user_id = ?` — a row belonging to another user returns no row, which becomes a 404.

**When to use:** GET /companies/{id}, GET /documents/{id}/status, GET /documents/{id}/rows, POST /documents/{id}/retry

```python
# Source: [ASSUMED] — follows existing "if not row: raise HTTPException(404)" pattern in main.py
# GET /companies/{company_id} — after Phase 2:
async with db.execute(
    "SELECT * FROM companies WHERE id = ? AND user_id = ?",
    (company_id, current_user["id"])
) as cur:
    row = await cur.fetchone()
if not row:
    raise HTTPException(404, "Company not found")
```

**Key:** When `user_id` doesn't match, `fetchone()` returns `None`. The existing 404 error handler fires. The caller cannot distinguish "does not exist" from "exists but owned by someone else." This is the correct IDOR mitigation. [ASSUMED — standard OWASP IDOR mitigation pattern]

### Pattern 4: Derived access via JOIN (financial_rows, extraction_log)

**What:** `financial_rows` and `extraction_log` have no `user_id` column. They are accessed only through routes that already check document/company ownership. No change needed to those tables.

**When to use:** GET /financials/{company_id} — add `WHERE fr.company_id = ?` already exists; needs an additional company ownership check via JOIN.

```python
# Source: [ASSUMED] — derived from current main.py lines 276-292
# GET /financials/{company_id} — after Phase 2:
# First: verify company ownership (or add to the main query via JOIN)
query = """
    SELECT fr.statement, fr.row_key, fr.row_label, fr.period,
           AVG(fr.value) as value, fr.currency, fr.unit,
           AVG(fr.confidence) as confidence,
           COUNT(*) as source_count
    FROM financial_rows fr
    JOIN documents d ON d.id = fr.document_id
    JOIN companies c ON c.id = fr.company_id
    WHERE fr.company_id = ?
      AND d.extraction_status = 'done'
      AND c.user_id = ?
"""
params = [company_id, current_user["id"]]
```

### Pattern 5: Analytics aggregate filtering

**What:** COUNT queries in `/analytics/*` must be scoped to the current user's companies.

**When to use:** GET /analytics/overview, GET /analytics/confidence

```python
# Source: [ASSUMED] — derived from current main.py lines 345-367
# GET /analytics/overview — before (global counts):
async with db.execute("SELECT COUNT(*) as n FROM companies") as cur:

# After Phase 2 (user-scoped):
async with db.execute(
    "SELECT COUNT(*) as n FROM companies WHERE user_id = ?",
    (current_user["id"],)
) as cur:

# For documents (join through companies):
async with db.execute("""
    SELECT COUNT(*) as n FROM documents d
    JOIN companies c ON c.id = d.company_id
    WHERE c.user_id = ?
""", (current_user["id"],)) as cur:
```

### Anti-Patterns to Avoid

- **Checking company ownership separately before document access:** Don't do two round-trips (check company, then fetch document). Use `JOIN companies c ON c.id = d.company_id WHERE d.id = ? AND c.user_id = ?` in a single query for document routes.
- **Returning 403 Forbidden for cross-user resources:** Return 404 to avoid leaking that the resource exists for another user. The project already follows this pattern (see CONVENTIONS.md error handling style).
- **Adding `NOT NULL` constraint to user_id during migration:** Existing rows have no owner. The column must be nullable (`INTEGER` without `NOT NULL`).
- **Using `f"...{user_id}..."` in SQL strings:** All SQL must use `?` parameterization. Project convention forbids f-string interpolation into SQL (CONVENTIONS.md).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Row-level security | Custom middleware or permission service | `WHERE user_id = ?` in each query | SQLite has no RLS; parameterized WHERE is the correct pattern at this scale |
| UNIQUE constraint migration | Python code to detect/deduplicate conflicts | SQLite table-rename migration (see below) | SQLite ALTER TABLE cannot drop/modify constraints — table rebuild is the only correct path |
| Cross-user test isolation | Mock or stub user IDs | Two real AsyncClient sessions with separate cookies | Tests must exercise real auth flow; mocking `current_user` would not catch route-level filtering bugs |

**Key insight:** The "migration" is two lines of `ALTER TABLE ADD COLUMN` plus a table-rename procedure for the UNIQUE constraint. Do not over-engineer this into a migration framework — the project already uses try/except for safe `ALTER TABLE` migrations in `_migrate_db()`.

---

## SQLite Migration — Exact Steps

### Step A: Add user_id columns (safe, additive)

SQLite supports `ALTER TABLE ADD COLUMN` for nullable columns with no default or a constant default. [VERIFIED: SQLite documentation — ALTER TABLE section]

```python
# In backend/db.py _migrate_db() — append these two:
"ALTER TABLE companies ADD COLUMN user_id INTEGER",
"ALTER TABLE documents ADD COLUMN user_id INTEGER",
```

After this migration, all existing rows have `user_id = NULL`. The `WHERE user_id = ?` filter with any integer will exclude them (NULL != any integer in SQL). [VERIFIED: SQLite NULL comparison semantics]

### Step B: Rebuild companies UNIQUE constraint

SQLite does NOT support `ALTER TABLE DROP CONSTRAINT` or `ALTER TABLE ADD CONSTRAINT`. The only way to change a UNIQUE constraint is to recreate the table. [VERIFIED: SQLite documentation — ALTER TABLE limitations]

The standard SQLite table-rename pattern:

```sql
-- Step 1: Create new table with updated UNIQUE constraint
CREATE TABLE companies_new (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    ticker      TEXT,
    exchange    TEXT,
    sector      TEXT,
    country     TEXT    DEFAULT 'NZ',
    created_at  TEXT    DEFAULT (datetime('now')),
    user_id     INTEGER,
    UNIQUE(name, exchange, user_id)
);

-- Step 2: Copy all rows
INSERT INTO companies_new SELECT id, name, ticker, exchange, sector, country, created_at, NULL FROM companies;

-- Step 3: Drop old table
DROP TABLE companies;

-- Step 4: Rename new to old
ALTER TABLE companies_new RENAME TO companies;

-- Step 5: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_companies_user ON companies(user_id);
```

**Risk:** This operation is NOT atomic unless wrapped in a transaction. It must run inside `BEGIN; ... COMMIT;`. If the process crashes mid-migration, the DB could be in a broken state. Mitigation: run inside a transaction and test in the temp DB (test suite uses a fresh DB per run).

**UNIQUE(name, exchange, user_id) with NULLs:** In SQLite, NULL is not equal to NULL in UNIQUE constraints. Two rows with `user_id = NULL` and the same `(name, exchange)` will NOT conflict — each NULL is treated as distinct. [VERIFIED: SQLite documentation — UNIQUE constraint and NULL values] This means pre-existing rows (NULL user_id) coexist without constraint violations.

### Step C: Add user_id index on companies and documents

```sql
CREATE INDEX IF NOT EXISTS idx_companies_user ON companies(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_user  ON documents(user_id);
```

These are needed for query performance when filtering by user_id. [ASSUMED — standard index hygiene for foreign-key-like columns]

---

## Complete Route Audit

Every route that touches `companies` or `documents` tables, with exact change required:

| Route | Current SQL | Phase 2 Change Required | Category |
|-------|-------------|------------------------|----------|
| `GET /companies` | SELECT * FROM companies | Add `WHERE c.user_id = ?` | Filter reads |
| `POST /companies` | INSERT INTO companies (name, ticker, exchange, sector, country) | Add `user_id` to column list and VALUES | Assign on write |
| `GET /companies/{company_id}` | WHERE id=? | Change to `WHERE id=? AND user_id=?` | IDOR check |
| `GET /documents` | SELECT * FROM documents (+ optional company_id filter) | Add `WHERE d.user_id = ?` (always applied); keep optional company_id as AND clause | Filter reads |
| `POST /documents/upload` | INSERT INTO documents (...) — checks company exists with `WHERE id=?` | (1) Add `AND user_id=?` to company existence check; (2) Add `user_id` to documents INSERT | Assign on write + company ownership check |
| `GET /documents/{document_id}/status` | WHERE d.id=? | Change to `WHERE d.id=? AND d.user_id=?` | IDOR check |
| `GET /documents/{document_id}/rows` | WHERE document_id=? (financial_rows, no user_id) | Add JOIN to documents+companies, filter via `d.user_id=?` | Derived access |
| `GET /financials/{company_id}` | WHERE fr.company_id=? | Add JOIN companies, filter via `c.user_id=?` | Derived access |
| `GET /patterns` | SELECT * FROM label_patterns | NO CHANGE (D-03: global table) | Exempt |
| `GET /patterns/export` | get_pattern_library() | NO CHANGE (D-03: global table) | Exempt |
| `GET /analytics/overview` | Global COUNTs | All counts scoped via `WHERE user_id=?` or JOIN to companies.user_id | Filter reads |
| `GET /analytics/confidence` | Global AVG(confidence) FROM financial_rows | JOIN through documents→companies, filter `c.user_id=?` | Derived access |
| `POST /documents/{document_id}/retry` | WHERE d.id=? | Change to `WHERE d.id=? AND d.user_id=?` | IDOR check |
| `GET /settings` | No DB query for companies/documents | NO CHANGE | Exempt |
| `POST /settings` | No DB query for companies/documents | NO CHANGE | Exempt |

**Routes requiring no change:** `/health`, `/auth/*`, `/settings`, `/patterns`, `/patterns/export`

### Special case: `GET /documents` with optional company_id filter

Current code builds the WHERE clause conditionally. After Phase 2, user_id filter is always applied:

```python
# Source: [ASSUMED] — follows current conditional-query pattern in main.py lines 142-153
query = """
    SELECT d.*, c.name as company_name, c.exchange
    FROM documents d
    LEFT JOIN companies c ON c.id = d.company_id
    WHERE d.user_id = ?
"""
params = [current_user["id"]]
if company_id:
    query += " AND d.company_id = ?"
    params.append(company_id)
query += " ORDER BY d.created_at DESC"
```

### Special case: `POST /documents/upload` — double ownership check

The upload route currently verifies the company exists. After Phase 2, it must also verify the user owns that company (prevents a user uploading a document against someone else's company_id):

```python
# Source: [ASSUMED] — extends current main.py lines 173-176
async with db.execute(
    "SELECT id, exchange FROM companies WHERE id=? AND user_id=?",
    (company_id, current_user["id"])
) as cur:
    company = await cur.fetchone()
if not company:
    raise HTTPException(404, f"Company {company_id} not found.")
```

---

## Document Access Chain Analysis

The question: does checking `documents.user_id = current_user["id"]` give sufficient isolation, or do we also need to validate company ownership separately?

**Answer: Store user_id on BOTH tables and check independently.** [ASSUMED — based on defense-in-depth principle]

Rationale:
- A document's `user_id` is set at upload time from `current_user["id"]`. This is always correct if the upload route also validates company ownership.
- Checking `documents.user_id` is sufficient for document routes.
- Checking `companies.user_id` is sufficient for company routes.
- The `financial_rows` and `extraction_log` tables are only accessible via routes that go through a document/company ownership check — no direct route exposes them without the JOIN guard. [VERIFIED: main.py route enumeration]

**Access chain for financial_rows:**
```
GET /financials/{company_id}
  → filter: WHERE fr.company_id = ? AND c.user_id = ?
  → financial_rows only returned if their parent company is owned by the user
  → extraction_log is only accessed via GET /documents/{id}/status which gains user_id check
```

**No additional tables need user_id columns.** [ASSUMED — verified by examining every table and its access routes]

---

## IDOR Security Analysis

### What IDOR means in this context

Insecure Direct Object Reference: a user can access another user's resource by guessing or enumerating numeric IDs (e.g., `GET /companies/42` when company 42 belongs to user B). [ASSUMED — standard OWASP definition]

### Current IDOR exposure (before Phase 2)

All routes accept `company_id` or `document_id` as path parameters and query WITHOUT any ownership check. Any authenticated user can retrieve any company or document by guessing the ID. The IDs are sequential integers starting from 1, making enumeration trivial. [VERIFIED: main.py — no user_id WHERE clauses exist]

### Phase 2 IDOR mitigation

`WHERE id = ? AND user_id = ?` — the compound condition means:
- If the row exists and is owned by the user: row returned, 200 OK
- If the row exists but is owned by someone else: `fetchone()` returns None, 404 raised
- If the row does not exist: `fetchone()` returns None, 404 raised

The attacker cannot distinguish between "doesn't exist" and "exists but not yours." This is the correct mitigation. [ASSUMED — standard OWASP IDOR guidance]

### 404 vs 403 rationale

Returning 403 Forbidden when a resource exists but is owned by another user leaks the information that the resource exists. An attacker can enumerate valid IDs by noting which guesses get 403 vs 404. Returning 404 for all non-owned resources prevents this enumeration. [ASSUMED — standard OWASP recommendation; matches CONTEXT.md D-01 directive and existing project error handling style]

### Edge cases

1. **Sequential ID enumeration remains possible for existence detection** — even with 404, an attacker could in theory detect patterns in response timing (timing oracle). At this scale and use case (internal SaaS), this is acceptable. [ASSUMED]

2. **The `GET /documents` route with `company_id` filter** — a malicious user could pass another user's `company_id` to the filter. The Phase 2 fix addresses this: `WHERE d.user_id = ?` is always applied; the `company_id` filter is an AND condition, so cross-user company_id yields an empty result (not an error), which is correct behavior.

3. **The `/analytics` endpoints** — currently return global aggregates. After Phase 2, they return only the current user's data. A user with no companies sees zeros, not an error. This is correct.

---

## Common Pitfalls

### Pitfall 1: NULL comparison in SQL

**What goes wrong:** Writing `WHERE user_id = NULL` instead of `WHERE user_id IS NULL` (or expecting `NULL = NULL` to be true). In this phase, the filter is `WHERE user_id = current_user["id"]` where the ID is always an integer — this is correct. But if any code ever needs to find rows without an owner, it must use `IS NULL`.

**Why it happens:** SQL NULL semantics are unintuitive — `NULL = NULL` evaluates to NULL (unknown), not TRUE.

**How to avoid:** Never use `= NULL` in SQL. The Phase 2 filter `WHERE user_id = ?` with an integer parameter is safe. Existing rows with NULL user_id simply don't match any integer value. [VERIFIED: SQLite NULL comparison semantics]

### Pitfall 2: SQLite UNIQUE constraint and NULL values

**What goes wrong:** Assuming the new `UNIQUE(name, exchange, user_id)` will prevent two users from having the same company name on the same exchange. It does prevent this — but only between two users who both have non-NULL user_ids. Pre-existing rows with NULL user_id each count as "distinct null" and won't conflict with each other or with any user's company.

**Why it happens:** SQLite treats each NULL as unique in UNIQUE constraints, unlike some other databases where NULL = NULL for uniqueness purposes.

**How to avoid:** Understand this is correct behavior for this phase. Existing rows remain invisible and don't block new users from creating companies with matching names. [VERIFIED: SQLite documentation]

### Pitfall 3: Missing ownership check on document upload's company_id validation

**What goes wrong:** After adding user_id to documents INSERT, forgetting to also add `AND user_id = ?` to the "verify company exists" query in `POST /documents/upload`. This would allow User A to upload a document against User B's company_id.

**Why it happens:** There are two SQL queries in the upload route — the company existence check and the documents INSERT. Easy to update one and miss the other.

**How to avoid:** The company existence check and the documents INSERT must both include user_id. Treat the upload route as having two distinct ownership obligations.

### Pitfall 4: Transaction wrapping for UNIQUE constraint rebuild

**What goes wrong:** Running the table-rename migration without a transaction. If the process dies after `DROP TABLE companies` but before `ALTER TABLE companies_new RENAME TO companies`, the companies table is gone permanently.

**Why it happens:** SQLite DDL statements are not automatically transactional in the Python `sqlite3` module when using `executescript()`.

**How to avoid:** Wrap the table-rename sequence in explicit `BEGIN;` / `COMMIT;` or use a single `executescript()` call which implicitly commits at the end. Better: use `conn.execute()` for each DDL statement inside a try/except, and verify the final state before committing. [VERIFIED: Python sqlite3 documentation — executescript commits any pending transaction first]

### Pitfall 5: The fresh_db fixture only clears the users table

**What goes wrong:** The existing `fresh_db` fixture only deletes from `users`. A new `test_isolation.py` test that also creates companies and documents will leave those rows in the temp DB across tests if not cleaned up.

**Why it happens:** The fixture was designed for auth tests which only touch the users table.

**How to avoid:** The isolation test should either extend `fresh_db` to also DELETE from companies and documents, or create a separate `fresh_all_db` fixture, or rely on unique test data per test run.

---

## Runtime State Inventory

> This is not a rename/refactor phase — no string replacements or service renames are involved. However, the live database has existing rows that are directly affected by the migration.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `companies` table: 2 rows with `user_id = NULL` (pre-auth rows) [VERIFIED: sqlite3 query] | `ALTER TABLE ADD COLUMN` makes them invisible via query filter — no deletion |
| Stored data | `documents` table: 2 rows with `user_id = NULL` (pre-auth rows) [VERIFIED: sqlite3 query] | Same — invisible after migration, not deleted |
| Live service config | None — no external services | None |
| OS-registered state | None | None |
| Secrets/env vars | None relevant to this phase | None |
| Build artifacts | None | None |

**Summary:** 2 pre-existing company rows and 2 pre-existing document rows will become invisible to all users after Phase 2. They remain in the DB (D-02). The migration is safe to run on the live DB with no data loss.

---

## Code Examples

### Migration function (extend existing `_migrate_db`)

```python
# Source: [ASSUMED] — follows existing _migrate_db pattern in backend/db.py lines 120-129

def _migrate_db(conn: sqlite3.Connection):
    """Add columns introduced in v2/v3 — safe to run on an existing database."""
    # Existing Phase 1 migrations
    for sql in [
        "ALTER TABLE documents ADD COLUMN narrative TEXT",
        "ALTER TABLE documents ADD COLUMN reporting_standard TEXT DEFAULT 'UNKNOWN'",
        # Phase 2: user ownership columns
        "ALTER TABLE companies ADD COLUMN user_id INTEGER",
        "ALTER TABLE documents ADD COLUMN user_id INTEGER",
    ]:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists

    # Phase 2: rebuild companies UNIQUE constraint
    # Check if new UNIQUE already exists by checking index info
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='companies_new'"
    )
    if cur.fetchone():
        # Previous migration attempt left companies_new — clean up
        conn.execute("DROP TABLE companies_new")

    # Check if the constraint already has user_id (idempotency guard)
    cur = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='companies'"
    )
    schema = (cur.fetchone() or [""])[0]
    if "user_id" not in schema or "UNIQUE(name, exchange, user_id)" not in schema:
        conn.executescript("""
            BEGIN;
            CREATE TABLE companies_new (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                ticker      TEXT,
                exchange    TEXT,
                sector      TEXT,
                country     TEXT    DEFAULT 'NZ',
                created_at  TEXT    DEFAULT (datetime('now')),
                user_id     INTEGER,
                UNIQUE(name, exchange, user_id)
            );
            INSERT INTO companies_new
                SELECT id, name, ticker, exchange, sector, country, created_at, user_id
                FROM companies;
            DROP TABLE companies;
            ALTER TABLE companies_new RENAME TO companies;
            COMMIT;
        """)

    # Indexes for query performance
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_companies_user ON companies(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id)",
    ]:
        try:
            conn.execute(idx_sql)
        except sqlite3.OperationalError:
            pass

    conn.commit()
```

**Note:** `executescript()` in Python's sqlite3 module commits any pending transaction before running, then runs each statement. The `BEGIN; ... COMMIT;` inside the script is explicit. [VERIFIED: Python sqlite3 docs]

### Integration test pattern (cross-user IDOR smoke test)

```python
# Source: [ASSUMED] — follows existing conftest.py AsyncClient pattern

import pytest

async def _register_and_get_client(base_client, email, password="correcthorse"):
    """Register a user and return a new client with that user's cookie."""
    r = await base_client.post("/auth/register", data={"email": email, "password": password})
    assert r.status_code in (200, 201)
    # The AsyncClient automatically stores the set-cookie from the response
    return r.cookies  # return cookies to apply to a second client

async def test_cross_user_company_isolation(client, fresh_db):
    """AUTH-07: User A cannot see User B's companies."""
    # User A registers and creates a company
    r = await client.post("/auth/register", data={"email": "alice@test.com", "password": "correcthorse"})
    assert r.status_code in (200, 201)
    r = await client.post("/companies", data={"name": "Alice Corp", "exchange": "NZX"})
    assert r.status_code == 200
    alice_company_id = r.json()["id"]

    # User B registers in a separate client instance
    from httpx import AsyncClient, ASGITransport
    import main as _main_module
    async with AsyncClient(
        transport=ASGITransport(app=_main_module.app),
        base_url="http://test",
    ) as bob_client:
        r = await bob_client.post("/auth/register", data={"email": "bob@test.com", "password": "correcthorse"})
        assert r.status_code in (200, 201)

        # Bob tries to access Alice's company by ID — must get 404
        r = await bob_client.get(f"/companies/{alice_company_id}")
        assert r.status_code == 404, f"IDOR: Bob accessed Alice's company. Response: {r.text}"

        # Bob lists companies — Alice's company must NOT appear
        r = await bob_client.get("/companies")
        assert r.status_code == 200
        company_names = [c["name"] for c in r.json()]
        assert "Alice Corp" not in company_names, f"IDOR: Alice's company visible in Bob's list"
```

---

## Validation Architecture

> nyquist_validation is enabled (config.json key present and true).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `pytest.ini` (asyncio_mode = auto, testpaths = tests) |
| Quick run command | `cd /Users/William.Cheong/accountiq_learning && source venv/bin/activate && python -m pytest tests/test_isolation.py -x -q` |
| Full suite command | `cd /Users/William.Cheong/accountiq_learning && source venv/bin/activate && python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-07 (SC-1) | User A cannot retrieve User B's company by guessed ID | integration | `pytest tests/test_isolation.py::test_cross_user_company_isolation -x` | ❌ Wave 0 |
| AUTH-07 (SC-1) | User A cannot retrieve User B's document by guessed ID | integration | `pytest tests/test_isolation.py::test_cross_user_document_isolation -x` | ❌ Wave 0 |
| AUTH-07 (SC-3) | New user's uploaded document not visible to other users | integration | `pytest tests/test_isolation.py::test_new_user_document_isolation -x` | ❌ Wave 0 |
| AUTH-07 (SC-4) | All API routes returning companies/documents enforce user_id filter | integration | `pytest tests/test_isolation.py::test_list_endpoints_scoped -x` | ❌ Wave 0 |
| DATA-01 (SC-2) | Existing rows (NULL user_id) not visible to any user after migration | integration | `pytest tests/test_isolation.py::test_null_user_rows_invisible -x` | ❌ Wave 0 |

### Success Criteria Mapping

| Success Criterion | Test Approach |
|-------------------|--------------|
| SC-1: User A cannot retrieve User B's companies or documents via any API (even with valid JWT and guessed IDs) | Two separate AsyncClient sessions; User B attempts GET /companies/{alice_id}, GET /documents/{alice_doc_id} — expects 404 both times |
| SC-2: Existing NULL user_id rows NOT visible to any user | Create fresh registered user; GET /companies returns empty list; GET /documents returns empty list; existing 2 pre-auth rows not returned |
| SC-3: New user's documents not visible to any other user | Two users, each creates company + document; each user's GET /documents lists only own documents |
| SC-4: All API routes enforce user_id filter | Parametric test over all routes: GET /companies, GET /documents, GET /financials/{id}, GET /analytics/overview, GET /analytics/confidence, GET /documents/{id}/status |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_isolation.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_isolation.py` — covers AUTH-07 (all 4 SCs) and DATA-01 (SC-2)
- [ ] `tests/conftest.py` — extend `fresh_db` fixture to also DELETE from companies, documents, financial_rows (or add `fresh_all_db` fixture)

*(Existing test infrastructure is complete — only the new test file and fixture extension are needed)*

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | All backend code | ✓ | 3.13.6 | — |
| aiosqlite | All DB operations | ✓ | (in venv) | — |
| pytest | Test runner | ✓ | 9.0.3 | — |
| pytest-asyncio | Async tests | ✓ | 1.3.0 | — |
| httpx | AsyncClient tests | ✓ | 0.28.1 | — |
| SQLite | DB engine | ✓ | bundled with Python | — |
| Live DB (data/accountiq_learning.db) | Migration target | ✓ | 2 companies, 2 documents | — |

**No missing dependencies.** All required tools are available. [VERIFIED: pip show output, python --version, sqlite3 query]

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No (Phase 1 complete) | JWT + HTTP-only cookie (implemented) |
| V3 Session Management | No (Phase 1 complete) | 7-day expiry, SameSite=Lax (implemented) |
| V4 Access Control | **Yes** | WHERE user_id = ? parameterized filter on all resource queries |
| V5 Input Validation | Partial | company_id path param is int (FastAPI type validation); no new string inputs |
| V6 Cryptography | No | No new crypto operations |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR via sequential integer IDs | Information Disclosure | `WHERE id = ? AND user_id = ?` — 404 for non-owned resources |
| Forced browsing via /documents list | Information Disclosure | `WHERE d.user_id = ?` always applied — cannot see other users' document list |
| Cross-user analytics aggregation | Information Disclosure | Analytics COUNT queries scoped to current user's companies |
| Upload to another user's company | Tampering | Company existence check adds `AND user_id = ?` — 404 if not owned |
| NULL user_id bypass | Spoofing | SQL NULL != any integer; NULL rows never match authenticated user's ID |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Global data (no ownership) | Per-user data isolation via user_id column | Phase 2 | Breaking change for existing rows — they become invisible |
| `UNIQUE(name, exchange)` | `UNIQUE(name, exchange, user_id)` | Phase 2 | Each user gets independent company namespace |

**Deprecated/outdated:**
- DATA-01 as written (shared demo data): superseded by D-01. Do not implement shared demo data.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `UNIQUE(name, exchange, user_id)` with NULL user_id treats each NULL as distinct (no conflict between pre-existing rows) | Migration Steps | If wrong: constraint rebuild fails; pre-existing rows conflict with each other. Mitigation: test in temp DB before running on live DB. |
| A2 | `executescript()` with `BEGIN;...COMMIT;` inside is safe for the table-rename pattern | Migration Steps | If wrong: partial migration could corrupt companies table. Mitigation: wrap in try/except and verify final schema. |
| A3 | All financial_rows and extraction_log access is fully protected by the document/company ownership checks already on the route layer — no direct exposure path exists | Document Access Chain | If wrong: a route that exposes financial_rows without an ownership check could leak data. Mitigation: route audit (verified in full route enumeration above). |
| A4 | Two separate AsyncClient instances (for Alice and Bob) maintain independent cookie jars in the test | Integration test pattern | If wrong: tests may pass incorrectly because the same session is reused. Mitigation: verify with `client.cookies` assertions in test. |
| A5 | The `fresh_db` fixture deleting only from `users` is insufficient for isolation tests — companies/documents must also be cleared | Validation Architecture | If wrong: test state leaks between tests, causing false failures or false passes. Mitigation: extend fixture or use unique email/company names per test. |

---

## Open Questions

1. **conftest.py fresh_db fixture scope**
   - What we know: `fresh_db` only clears the `users` table
   - What's unclear: Should the planner extend `fresh_db` to clear all tables, or create a separate fixture?
   - Recommendation: Add a `fresh_all_db` fixture that also DELETEs from `companies`, `documents`, `financial_rows`, `extraction_log` — keep `fresh_db` for auth-only tests to avoid breaking them.

2. **Analytics route naming**
   - What we know: CONTEXT.md mentions `/analytics` endpoint; main.py has `/analytics/overview` and `/analytics/confidence` (not `/analytics`)
   - What's unclear: Are there additional analytics routes planned, or is the CONTEXT reference to the path prefix?
   - Recommendation: Update both `/analytics/overview` and `/analytics/confidence` to filter by user_id. No additional analytics routes exist in the current codebase.

---

## Sources

### Primary (HIGH confidence)

- `backend/main.py` — full route enumeration (all 15 routes inspected directly) [VERIFIED]
- `backend/db.py` — schema definition and existing `_migrate_db` pattern [VERIFIED]
- `backend/auth.py` — `get_current_user` return shape `{"id": int, "email": str, "created_at": str}` [VERIFIED]
- `tests/conftest.py` — AsyncClient + ASGITransport pattern for test isolation [VERIFIED]
- `tests/test_auth.py` — existing test patterns to follow [VERIFIED]
- `pytest.ini` — asyncio_mode=auto confirmed [VERIFIED]
- `data/accountiq_learning.db` — live schema and row counts confirmed via sqlite3 [VERIFIED]
- SQLite documentation — ALTER TABLE limitations, NULL in UNIQUE constraints [CITED: https://www.sqlite.org/lang_altertable.html]
- SQLite documentation — NULL comparison semantics [CITED: https://www.sqlite.org/nulls.html]

### Secondary (MEDIUM confidence)

- `.planning/codebase/CONVENTIONS.md` — error handling style, DB patterns [VERIFIED]
- `.planning/codebase/ARCHITECTURE.md` — data flow and table relationships [VERIFIED]
- `.planning/phases/02-multi-user-data-isolation/02-CONTEXT.md` — locked decisions [VERIFIED]

### Tertiary (LOW confidence — assumed)

- IDOR 404-vs-403 rationale: OWASP IDOR guidance applied to this codebase [ASSUMED — A3]
- Analytics join pattern for confidence stats route [ASSUMED — extrapolated from current route structure]

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all tools verified in venv, no new packages needed
- Migration approach: HIGH — SQLite ALTER TABLE ADD COLUMN and table-rename are documented SQLite behaviors
- Route audit: HIGH — inspected every line of main.py directly
- IDOR pattern: MEDIUM — standard OWASP guidance applied; not validated against a penetration test
- Test patterns: HIGH — existing conftest.py and test files directly inspected

**Research date:** 2026-05-06
**Valid until:** 2026-06-06 (stable — SQLite behavior and project stack do not change frequently)
