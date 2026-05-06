# Phase 2: Multi-User Data Isolation — Pattern Map

**Mapped:** 2026-05-06
**Files analyzed:** 3 modified + 1 created
**Analogs found:** 3 / 3 (all modified files are self-referencing analogs; new test file has a direct analog)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/db.py` | migration / config | batch (startup) | `backend/db.py` lines 120–130 (`_migrate_db`) | exact — extend in-place |
| `backend/main.py` | controller | CRUD + request-response | `backend/main.py` (all routes) | exact — modify in-place |
| `tests/conftest.py` | test config | — | `tests/conftest.py` lines 56–67 (`fresh_db` fixture) | exact — extend in-place |
| `tests/test_isolation.py` | test | request-response | `tests/test_auth.py` (full file) | role-match — new file, same structure |

---

## Pattern Assignments

### `backend/db.py` — `_migrate_db` extension + SCHEMA update

**Analog:** `backend/db.py` lines 120–130 (existing `_migrate_db`) and lines 12–26 (SCHEMA `companies` table).

**Existing migration pattern** (lines 120–130) — copy this try/except loop structure and extend it:
```python
def _migrate_db(conn: sqlite3.Connection):
    """Add columns introduced in v2 — safe to run on an existing database."""
    for sql in [
        "ALTER TABLE documents ADD COLUMN narrative TEXT",
        "ALTER TABLE documents ADD COLUMN reporting_standard TEXT DEFAULT 'UNKNOWN'",
    ]:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
```

**Phase 2 change — append two ALTER TABLE statements to the existing list:**
```python
        # Phase 2: user ownership columns
        "ALTER TABLE companies ADD COLUMN user_id INTEGER",
        "ALTER TABLE documents ADD COLUMN user_id INTEGER",
```
The `try/except sqlite3.OperationalError: pass` wrapper is already the idempotency guard — the same pattern covers the new columns.

**Phase 2 addition — UNIQUE constraint rebuild block (after the ALTER TABLE loop, before `conn.commit()`):**

The `companies` table SCHEMA (lines 17–26) currently declares `UNIQUE(name, exchange)`. SQLite cannot modify that with ALTER TABLE, so a table-rename migration is required. The rebuild must be:
1. Guarded by an idempotency check (inspect `sqlite_master` for existing `user_id` in the schema string)
2. Wrapped in an atomic `executescript()` block with explicit `BEGIN; ... COMMIT;`
3. Followed by index creation using the same `try/except` guard already used in the function

**Existing SCHEMA `companies` table** (lines 17–26) — reference for the `companies_new` DDL:
```python
CREATE TABLE IF NOT EXISTS companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    ticker      TEXT,
    exchange    TEXT,
    sector      TEXT,
    country     TEXT    DEFAULT 'NZ',
    created_at  TEXT    DEFAULT (datetime('now')),
    UNIQUE(name, exchange)
);
```
The new table replaces `UNIQUE(name, exchange)` with `UNIQUE(name, exchange, user_id)` and adds `user_id INTEGER` as a column.

**Index creation pattern** — use the same `try/except` loop already in the function, adding:
```python
"CREATE INDEX IF NOT EXISTS idx_companies_user ON companies(user_id)",
"CREATE INDEX IF NOT EXISTS idx_documents_user  ON documents(user_id)",
```

---

### `backend/main.py` — Route updates (all company/document queries)

**Analog:** `backend/main.py` — all 15 routes. Every route already has `current_user: dict = Depends(get_current_user)` injected (lines 81, 102, 120, 138, 165, 229, 253, 271, 302, 323, 342, 371, 390, 406, 434). Phase 2 simply starts using `current_user["id"]` in the SQL.

#### Pattern A — Filter list reads (`WHERE user_id = ?`)

**Source pattern:** `GET /companies` (lines 78–91). Current:
```python
async with db.execute("""
    SELECT c.*, COUNT(d.id) as doc_count
    FROM companies c
    LEFT JOIN documents d ON d.company_id = c.id
    GROUP BY c.id
    ORDER BY c.name
""") as cur:
    rows = await cur.fetchall()
return [dict(r) for r in rows]
```
Phase 2 change: add `WHERE c.user_id = ?` before `GROUP BY` and pass `(current_user["id"],)` as params.

**Source pattern:** `GET /documents` (lines 135–154). Current conditional query build:
```python
query = """
    SELECT d.*, c.name as company_name, c.exchange
    FROM documents d
    LEFT JOIN companies c ON c.id = d.company_id
"""
params = []
if company_id:
    query += " WHERE d.company_id = ?"
    params.append(company_id)
query += " ORDER BY d.created_at DESC"

async with db.execute(query, params) as cur:
```
Phase 2 change: `d.user_id = ?` becomes the mandatory base filter; `company_id` becomes an AND clause:
```python
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

#### Pattern B — Single-row IDOR check (`WHERE id = ? AND user_id = ?`)

**Source pattern:** `GET /companies/{company_id}` (lines 118–128). Current:
```python
async with db.execute("SELECT * FROM companies WHERE id=?", (company_id,)) as cur:
    row = await cur.fetchone()
if not row:
    raise HTTPException(404, "Company not found")
return dict(row)
```
Phase 2 change: add `AND user_id=?` and pass both params:
```python
async with db.execute(
    "SELECT * FROM companies WHERE id=? AND user_id=?",
    (company_id, current_user["id"])
) as cur:
    row = await cur.fetchone()
if not row:
    raise HTTPException(404, "Company not found")
```
The same `if not row: raise HTTPException(404, ...)` pattern is reused unchanged — it now handles both "not found" and "belongs to another user" without distinguishing them (correct IDOR mitigation).

Apply the same `AND user_id=?` addition to:
- `GET /documents/{document_id}/status` (lines 224–246): `WHERE d.id=?` → `WHERE d.id=? AND d.user_id=?`
- `POST /documents/{document_id}/retry` (lines 430–462): `WHERE d.id=?` → `WHERE d.id=? AND d.user_id=?`

#### Pattern C — Assign ownership on INSERT

**Source pattern:** `POST /companies` (lines 94–115). Current INSERT:
```python
async with db.execute("""
    INSERT INTO companies (name, ticker, exchange, sector, country)
    VALUES (?, ?, ?, ?, ?)
""", (name, ticker, exchange, sector, country)) as cur:
    company_id = cur.lastrowid
await db.commit()
```
Phase 2 change: add `user_id` to column list and `current_user["id"]` to params:
```python
async with db.execute("""
    INSERT INTO companies (name, ticker, exchange, sector, country, user_id)
    VALUES (?, ?, ?, ?, ?, ?)
""", (name, ticker, exchange, sector, country, current_user["id"])) as cur:
    company_id = cur.lastrowid
await db.commit()
```

**Source pattern:** `POST /documents/upload` (lines 157–207). Two changes required:

(1) Company ownership check (lines 173–176) — existing:
```python
async with db.execute("SELECT id, exchange FROM companies WHERE id=?", (company_id,)) as cur:
    company = await cur.fetchone()
if not company:
    raise HTTPException(404, f"Company {company_id} not found.")
```
Phase 2 change:
```python
async with db.execute(
    "SELECT id, exchange FROM companies WHERE id=? AND user_id=?",
    (company_id, current_user["id"])
) as cur:
    company = await cur.fetchone()
if not company:
    raise HTTPException(404, f"Company {company_id} not found.")
```

(2) Documents INSERT (lines 187–193) — existing:
```python
async with db.execute("""
    INSERT INTO documents
        (company_id, filename, filepath, report_type, entity_type, fiscal_year_end)
    VALUES (?, ?, ?, ?, ?, ?)
""", (company_id, safe_name, str(dest),
      report_type, entity_type, fiscal_year_end)) as cur:
    document_id = cur.lastrowid
```
Phase 2 change: add `user_id` to column list and `current_user["id"]` to params.

#### Pattern D — Derived access via JOIN (financial_rows, extraction_log)

**Source pattern:** `GET /financials/{company_id}` (lines 267–292). Current query:
```python
query = """
    SELECT fr.statement, fr.row_key, fr.row_label, fr.period,
           AVG(fr.value) as value, fr.currency, fr.unit,
           AVG(fr.confidence) as confidence,
           COUNT(*) as source_count
    FROM financial_rows fr
    JOIN documents d ON d.id = fr.document_id
    WHERE fr.company_id = ? AND d.extraction_status = 'done'
"""
params = [company_id]
```
Phase 2 change: add `JOIN companies c` and `AND c.user_id = ?`:
```python
query = """
    SELECT fr.statement, fr.row_key, fr.row_label, fr.period,
           AVG(fr.value) as value, fr.currency, fr.unit,
           AVG(fr.confidence) as confidence,
           COUNT(*) as source_count
    FROM financial_rows fr
    JOIN documents d ON d.id = fr.document_id
    JOIN companies c ON c.id = fr.company_id
    WHERE fr.company_id = ? AND d.extraction_status = 'done'
      AND c.user_id = ?
"""
params = [company_id, current_user["id"]]
```

**Source pattern:** `GET /documents/{document_id}/rows` (lines 249–260). Current:
```python
async with db.execute("""
    SELECT * FROM financial_rows WHERE document_id=?
    ORDER BY statement, row_key, period
""", (document_id,)) as cur:
```
Phase 2 change: add JOIN to documents filtered by `d.user_id = ?`:
```python
async with db.execute("""
    SELECT fr.* FROM financial_rows fr
    JOIN documents d ON d.id = fr.document_id
    WHERE fr.document_id=? AND d.user_id=?
    ORDER BY fr.statement, fr.row_key, fr.period
""", (document_id, current_user["id"])) as cur:
```

#### Pattern E — Analytics aggregate filtering

**Source pattern:** `GET /analytics/overview` (lines 340–367). Current global counts:
```python
async with db.execute("SELECT COUNT(*) as n FROM companies") as cur:
    companies = (await cur.fetchone())["n"]
async with db.execute("SELECT COUNT(*) as n FROM documents") as cur:
    documents = (await cur.fetchone())["n"]
async with db.execute("SELECT COUNT(*) as n FROM documents WHERE extraction_status='done'") as cur:
    done = (await cur.fetchone())["n"]
async with db.execute("SELECT COUNT(*) as n FROM financial_rows") as cur:
    fin_rows = (await cur.fetchone())["n"]
async with db.execute("""
    SELECT exchange, COUNT(*) as n FROM companies GROUP BY exchange
""") as cur:
    by_exchange = [dict(r) for r in await cur.fetchall()]
```
Phase 2 change: scope all counts to `current_user["id"]`. Companies and their derived counts filter directly; documents and financial_rows filter via JOIN to companies:
```python
async with db.execute(
    "SELECT COUNT(*) as n FROM companies WHERE user_id=?",
    (current_user["id"],)
) as cur:
    companies = (await cur.fetchone())["n"]
async with db.execute("""
    SELECT COUNT(*) as n FROM documents d
    JOIN companies c ON c.id = d.company_id
    WHERE c.user_id=?
""", (current_user["id"],)) as cur:
    documents = (await cur.fetchone())["n"]
async with db.execute("""
    SELECT COUNT(*) as n FROM documents d
    JOIN companies c ON c.id = d.company_id
    WHERE d.extraction_status='done' AND c.user_id=?
""", (current_user["id"],)) as cur:
    done = (await cur.fetchone())["n"]
async with db.execute("""
    SELECT COUNT(*) as n FROM financial_rows fr
    JOIN companies c ON c.id = fr.company_id
    WHERE c.user_id=?
""", (current_user["id"],)) as cur:
    fin_rows = (await cur.fetchone())["n"]
async with db.execute("""
    SELECT exchange, COUNT(*) as n FROM companies
    WHERE user_id=? GROUP BY exchange
""", (current_user["id"],)) as cur:
    by_exchange = [dict(r) for r in await cur.fetchall()]
```
Note: `label_patterns` count stays global (D-03) — no change to that line.

**Source pattern:** `GET /analytics/confidence` (lines 370–382). Current:
```python
async with db.execute("""
    SELECT row_key, AVG(confidence) as avg_conf, COUNT(*) as n
    FROM financial_rows
    GROUP BY row_key
    ORDER BY avg_conf ASC
""") as cur:
```
Phase 2 change: filter via JOIN to companies:
```python
async with db.execute("""
    SELECT fr.row_key, AVG(fr.confidence) as avg_conf, COUNT(*) as n
    FROM financial_rows fr
    JOIN companies c ON c.id = fr.company_id
    WHERE c.user_id=?
    GROUP BY fr.row_key
    ORDER BY avg_conf ASC
""", (current_user["id"],)) as cur:
```

#### Routes requiring NO change (confirmed)

- `GET /patterns` (lines 299–318) — `label_patterns` is global (D-03)
- `GET /patterns/export` (lines 321–333) — same, calls `get_pattern_library(db)` on global table
- `GET /settings`, `POST /settings` (lines 389–427) — no company/document queries
- `GET /health` (lines 69–71) — public endpoint
- All `/auth/*` routes — owned by `auth_router`, not affected

---

### `tests/conftest.py` — Extend `fresh_db` fixture

**Analog:** `tests/conftest.py` lines 56–67 (existing `fresh_db` fixture):
```python
@pytest_asyncio.fixture
async def fresh_db():
    """Truncate users table between tests that need a clean slate."""
    import aiosqlite
    async with aiosqlite.connect(_TMP_DB_PATH) as conn:
        # Best-effort: only DELETE if table exists (auth plan creates it)
        try:
            await conn.execute("DELETE FROM users")
            await conn.commit()
        except Exception:
            pass
    yield
```

Phase 2 change: add a second fixture `fresh_all_db` (do NOT modify `fresh_db` — auth tests depend on it). The new fixture extends the same `aiosqlite.connect` + `try/except` pattern:
```python
@pytest_asyncio.fixture
async def fresh_all_db():
    """Truncate users, companies, documents, financial_rows, extraction_log between tests."""
    import aiosqlite
    async with aiosqlite.connect(_TMP_DB_PATH) as conn:
        for table in ["financial_rows", "extraction_log", "documents", "companies", "users"]:
            try:
                await conn.execute(f"DELETE FROM {table}")
            except Exception:
                pass
        try:
            await conn.commit()
        except Exception:
            pass
    yield
```
Order matters: child rows (`financial_rows`, `extraction_log`) must be deleted before their parent (`documents`), then `companies`, then `users` (foreign key constraints are ON in this DB).

---

### `tests/test_isolation.py` — New integration test file

**Analog:** `tests/test_auth.py` (full file, 144 lines) — exact structural model.

**Imports pattern** (test_auth.py lines 1–2 and conftest.py lines 1–12):
```python
"""Tests for AUTH-07 (cross-user data isolation) and DATA-01 (NULL user_id rows invisible)."""
import pytest
```
No additional imports needed — `client` and `fresh_all_db` fixtures are injected via conftest.py. A second client for "Bob" is created inline using `AsyncClient(transport=ASGITransport(app=_main_module.app), base_url="http://test")` — the same pattern used in `conftest.py` lines 47–53.

**Helper function pattern** (test_auth.py lines 6–17):
```python
async def _register(client, email="alice@example.com", password="correcthorse"):
    return await client.post(
        "/auth/register",
        data={"email": email, "password": password},
    )
```
Follow the same `async def _helper(client, ...)` pattern. Isolation tests need helpers for register, create company, upload document.

**Test function pattern** (test_auth.py lines 24–29):
```python
async def test_register_success(client, fresh_db):
    r = await _register(client)
    assert r.status_code in (200, 201), r.text
```
Follow the same `async def test_*(client, fresh_all_db):` signature. Use `fresh_all_db` (not `fresh_db`) so companies and documents are cleared between tests.

**Two-client IDOR test pattern** — inline AsyncClient creation (per RESEARCH.md pattern, mirrors conftest.py lines 47–53):
```python
from httpx import AsyncClient, ASGITransport
import main as _main_module

async def test_cross_user_company_isolation(client, fresh_all_db):
    """AUTH-07: User A cannot see User B's companies."""
    # Alice registers and creates a company using the shared `client` fixture
    r = await client.post("/auth/register", data={"email": "alice@test.com", "password": "correcthorse"})
    assert r.status_code in (200, 201)
    r = await client.post("/companies", data={"name": "Alice Corp", "exchange": "NZX"})
    assert r.status_code == 200
    alice_company_id = r.json()["id"]

    # Bob gets a fresh client — separate cookie jar
    async with AsyncClient(
        transport=ASGITransport(app=_main_module.app),
        base_url="http://test",
    ) as bob_client:
        r = await bob_client.post("/auth/register", data={"email": "bob@test.com", "password": "correcthorse"})
        assert r.status_code in (200, 201)
        # Bob cannot access Alice's company by ID — must get 404 (IDOR prevention)
        r = await bob_client.get(f"/companies/{alice_company_id}")
        assert r.status_code == 404, f"IDOR: Bob accessed Alice's company. Response: {r.text}"
        # Bob's company list must not include Alice's company
        r = await bob_client.get("/companies")
        assert r.status_code == 200
        assert "Alice Corp" not in [c["name"] for c in r.json()]
```

**Assertion style** — matches test_auth.py throughout:
- `assert r.status_code == X, r.text` (include response body on failure)
- `assert "field" in body` for presence checks
- `assert value not in collection, f"message: {detail}"` for absence checks

---

## Shared Patterns

### Authentication dependency (already in place — no change)
**Source:** `backend/auth.py` lines 73–96
**Apply to:** All route handlers (already applied in Phase 1)
```python
async def get_current_user(
    accountiq_session: str | None = Cookie(default=None),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    """Return the authenticated user dict, or raise 401."""
    ...
    return dict(user)  # {"id": int, "email": str, "created_at": str}
```
Phase 2 consumes `current_user["id"]` from this return value in every modified SQL statement. No change to the function itself.

### Parameterized query pattern (project-wide rule)
**Source:** All routes in `backend/main.py` — every SQL call uses `?` placeholders
**Apply to:** All new SQL in Phase 2
```python
# CORRECT — always use ? placeholders
await db.execute("SELECT * FROM companies WHERE id=? AND user_id=?", (company_id, current_user["id"]))

# FORBIDDEN — never interpolate user data into SQL strings
# f"SELECT * FROM companies WHERE id={company_id}"  # SQL injection risk
```

### Error handling pattern (404 for missing/unauthorized resources)
**Source:** `backend/main.py` lines 125–127
**Apply to:** All single-row lookups with ownership check
```python
if not row:
    raise HTTPException(404, "Company not found")
```
Use 404 (not 403) for all cross-user IDOR scenarios. This matches the existing convention and prevents existence-leaking.

### Async DB context manager pattern
**Source:** `backend/main.py` throughout — consistent `async with db.execute(...) as cur:`
**Apply to:** All modified SQL statements in Phase 2
```python
async with db.execute(query, params) as cur:
    rows = await cur.fetchall()
return [dict(r) for r in rows]
```

### Migration idempotency pattern
**Source:** `backend/db.py` lines 122–129
**Apply to:** All new `_migrate_db` additions
```python
try:
    conn.execute(sql)
except sqlite3.OperationalError:
    pass  # column already exists — safe to ignore
```
Every ALTER TABLE in `_migrate_db` is wrapped in this guard so repeated startup calls are safe.

---

## No Analog Found

No files in this phase lack an analog. All changes are either extensions of existing files or direct structural copies of `test_auth.py`.

---

## Metadata

**Analog search scope:** `backend/`, `tests/`
**Files scanned:** `backend/db.py` (198 lines), `backend/main.py` (471 lines), `backend/auth.py` (176 lines), `tests/conftest.py` (68 lines), `tests/test_auth.py` (144 lines)
**Pattern extraction date:** 2026-05-06
