---
phase: 03-5-admin-gate-wizard-shell
reviewed: 2026-05-13T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - backend/auth.py
  - backend/db.py
  - backend/main.py
  - frontend/index.html
  - tests/test_admin_gate.py
  - tests/test_auth.py
  - tests/test_isolation.py
  - tests/test_profile.py
  - tests/test_upload_auto.py
findings:
  critical: 4
  warning: 5
  info: 3
  total: 12
status: issues_found
---

# Phase 03-5: Code Review Report

**Reviewed:** 2026-05-13
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 3.5 delivers admin gate (require_admin on all 25 routes), the OWNER_EMAIL self-promotion mechanism, and the /wizard/upload non-admin path. The auth chain and data-isolation WHERE clauses are sound. However, four blockers were found: the `is_admin` column is missing from the CREATE TABLE schema so a fresh-DB deploy skips migration and breaks auth; `create_access_token` issues tokens with an empty SECRET_KEY at register/login time (no matching guard in those paths); the frontend Dashboard "Label Patterns" stat is always `undefined` because the analytics/overview response never includes `label_patterns`; and `file.filename` can be `None` causing an unhandled TypeError crash in both upload routes. Five warnings cover information disclosure via `str(e)` in 500 responses, an `innerHTML` template-literal with numeric interpolation, test OWNER_EMAIL module-state mutation without using `fresh_all_db`, the `event.currentTarget` reliance in `wizardSubmitStep1`, and the deprecated `@app.on_event("startup")` decorator.

---

## Critical Issues

### CR-01: `is_admin` column absent from CREATE TABLE schema — fresh-DB deployments silently break admin gate

**File:** `backend/db.py:87-92`

**Issue:** The `users` table in `SCHEMA` (the `CREATE TABLE IF NOT EXISTS users` block executed at startup) has no `is_admin` column. The column is only added via `_migrate_db` through an `ALTER TABLE` statement. On an existing database this works fine — `ALTER TABLE` is idempotent. On a fresh database, however, `executescript(SCHEMA)` creates the `users` table, then `_migrate_db` fires and the `ALTER TABLE users ADD COLUMN is_admin` succeeds (adding the column after the fact). This path works in the current codebase only because `init_db` calls both `executescript` and `_migrate_db` in sequence.

The real breakage vector: any code that creates the `users` table outside `init_db` (e.g. the test suite `conftest.py` which calls `init_db()` once at module load and then wipes rows but not structure, or a future migration tool) will end up with a `users` table missing `is_admin`. The `SELECT id, email, is_admin, created_at FROM users WHERE id=?` in `get_current_user` will then raise an `OperationalError: no such column: is_admin`, causing every authenticated request to 500.

**Fix:** Add `is_admin INTEGER NOT NULL DEFAULT 0` directly into the `CREATE TABLE IF NOT EXISTS users` DDL so the schema and the migration are consistent. Keep the `ALTER TABLE` as the idempotency guard for existing DBs.

```python
# db.py — SCHEMA constant, users table
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT    NOT NULL UNIQUE,
    hashed_pw   TEXT    NOT NULL,
    is_admin    INTEGER NOT NULL DEFAULT 0,   # ADD THIS LINE
    created_at  TEXT    DEFAULT (datetime('now'))
);
```

---

### CR-02: `create_access_token` issues tokens with empty `SECRET_KEY` — login and register bypass the misconfiguration guard

**File:** `backend/auth.py:52-55`, `auth.py:81-83`

**Issue:** `get_current_user` (line 81) checks `if not SECRET_KEY` and raises HTTP 500, correctly preventing token _validation_ with an empty secret. However `create_access_token` (line 55) calls `jwt.encode(..., SECRET_KEY, ...)` with no equivalent guard. If `SECRET_KEY` is not set (empty string), a JWT is issued signed with `""` at lines 146 (register) and 167 (login). Once issued these tokens cannot be validated by `get_current_user` (which 500s), effectively locking users out immediately after they register or log in — but the tokens themselves are technically valid JWTs signed with `""` and could be decoded by an attacker who knows the secret is empty.

**Fix:** Add a guard at the top of `create_access_token`:

```python
def create_access_token(data: dict) -> str:
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY is not configured — cannot issue tokens")
    to_encode = dict(data)
    to_encode["exp"] = datetime.now(UTC) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```

The `register` and `login` routes will then propagate an unhandled 500 (which is appropriate and consistent with the decode-side guard), rather than silently issuing a broken token.

---

### CR-03: Dashboard "Label Patterns" stat is always `undefined` — analytics/overview omits `label_patterns` key

**File:** `backend/main.py:800-806`, `frontend/index.html:562`

**Issue:** The frontend `loadDashboard()` reads `ov.label_patterns` at line 562 and assigns it to the stat card. The `/analytics/overview` route (lines 800–806) returns a dict that contains `companies`, `documents`, `docs_done`, `financial_rows`, and `by_exchange` — but no `label_patterns` key. The stat card therefore always displays `undefined` (JavaScript silently reads a missing property as `undefined`, and `textContent = undefined` renders the string `"undefined"` in the browser).

The comment at line 798–799 explains the deliberate omission for data-isolation reasons, but the frontend still reads the key, making the stat card permanently broken.

**Fix (option A — preferred):** Return the global pattern count from the route, since it is explicitly non-user-scoped ML data and is already exposed via `GET /patterns`:

```python
async with db.execute("SELECT COUNT(*) as n FROM label_patterns") as cur:
    patterns = (await cur.fetchone())["n"]
# then add to the return dict:
"label_patterns": patterns,
```

**Fix (option B):** Remove the stat card from the HTML, or hide it, rather than leaving it permanently broken.

---

### CR-04: `file.filename` can be `None` — unhandled `TypeError` crash in both upload routes

**File:** `backend/main.py:532`, `backend/main.py:929`

**Issue:** FastAPI's `UploadFile.filename` is typed as `Optional[str]` and is `None` when the client sends a part without a filename header. Both `upload_document` (line 532: `Path(file.filename).suffix.lower()`) and `wizard_upload` (line 929: same pattern) will raise `TypeError: argument should be str or an os.PathLike object, not 'NoneType'` which propagates as an unhandled 500 rather than a meaningful 400.

**Fix:** Add an explicit check before using `file.filename` in both routes:

```python
if not file.filename:
    raise HTTPException(400, "Uploaded file must have a filename.")
```

---

## Warnings

### WR-01: Internal exception detail leaked to client via `str(e)` in HTTP 500 responses

**File:** `backend/auth.py:139`, `backend/main.py:123`

**Issue:** Both `register` (auth.py:139) and `create_company` (main.py:123) catch a broad `Exception` and re-raise as `HTTPException(500, str(e))`. This exposes raw Python exception messages (which can include DB file paths, schema details, or library internals) to API clients. Even when SQLite raises `UNIQUE constraint failed`, that is caught by the earlier branch — whatever reaches the bare `raise HTTPException(500, str(e))` is an unexpected error that should not be disclosed.

**Fix:**
```python
except Exception as e:
    if "UNIQUE constraint" in str(e):
        raise HTTPException(409, "Email already registered")
    # Log internally; return opaque message to client
    print(f"[ERROR] register failed: {e}")
    raise HTTPException(500, "Internal server error")
```

---

### WR-02: `innerHTML` template literal interpolates server-derived numeric count — fragile if value is ever non-integer

**File:** `frontend/index.html:1740`, `1745`

**Issue:**
```javascript
wrap.innerHTML = `<div class="empty">Extraction in progress for ${processing.length} document(s)…</div>`;
wrap.innerHTML = `<div class="empty">Extraction failed for ${failed.length} document(s)…</div>`;
```

`processing.length` and `failed.length` are JavaScript array lengths (always integers from client-side filter operations), so there is no XSS vector from these specific values today. However, using `innerHTML` with template literals that contain any variable is contrary to the project's explicit convention ("Always use `.textContent` or `.createTextNode()` for user-influenced text — never `.innerHTML`"). Future maintainers may copy this pattern and substitute a server-controlled string. The CLAUDE.md rule does not restrict itself to "user-influenced text" in production — the convention is `.textContent` everywhere to eliminate the class of bug.

**Fix:** Use `textContent` with DOM construction:
```javascript
const div = document.createElement('div');
div.className = 'empty';
div.textContent = `Extraction in progress for ${processing.length} document(s) — check back in a moment.`;
wrap.appendChild(div);
```

---

### WR-03: `test_protected_route_with_auth` in `test_auth.py` mutates `OWNER_EMAIL` module state without `fresh_all_db` fixture — potential test-ordering pollution

**File:** `tests/test_auth.py:133-141`

**Issue:** This test directly mutates `_auth_module.OWNER_EMAIL` in a `try/finally` block (correctly restoring it), but it uses the `fresh_db` fixture which only clears the `users` table. If a previous test left companies or documents behind in the shared temp DB, this test's registered admin user at `prot@example.com` could interact with stale rows. More importantly, `GET /companies` returning 200 proves authentication and admin gate work, but the response content is not validated — stale company rows from another user's test could appear in the response without causing the assertion to fail, masking a data-isolation regression.

Additionally, if an exception occurs between `_auth_module.OWNER_EMAIL = "prot@example.com"` (line 135) and the `try` block entry (line 136) — which cannot happen here since there is no code between them — the restore would be skipped. The safer pattern is the one used in `test_admin_gate.py`'s `_register_admin` helper, which wraps the mutation inside the `try` block. This test does it right, but the discrepancy with the other tests' `_register_admin` helper is worth flagging for consistency.

**Fix:** Either use `fresh_all_db` (which is the right fixture for tests involving cross-cutting state), or assert `r.json() == []` to confirm no leaked rows:
```python
async def test_protected_route_with_auth(client, fresh_all_db):
    ...
```

---

### WR-04: `wizardSubmitStep1` reads `event.currentTarget` from the global `event` object — unreliable in modern browsers

**File:** `frontend/index.html:2181`

```javascript
const btn = event.currentTarget || document.querySelector('[onclick="wizardSubmitStep1()"]');
```

`event` here is the implicit global `window.event`, which is deprecated and not available in strict-mode ES modules or Firefox (which never supported `window.event`). The fallback `document.querySelector('[onclick="wizardSubmitStep1()"]')` will work in practice for the current HTML, but it is fragile: it does a live DOM query by attribute string, which breaks if the button's `onclick` attribute is ever changed or if the function is called programmatically. The correct approach is to pass `event` explicitly.

**Fix:** Change the HTML button to pass `this`:
```html
<button ... onclick="wizardSubmitStep1(this)">Continue &#x2192;</button>
```
And the function signature:
```javascript
async function wizardSubmitStep1(btn) {
  // btn is now the element directly — no event.currentTarget needed
```

---

### WR-05: `@app.on_event("startup")` is deprecated — will be removed in a future FastAPI version

**File:** `backend/main.py:60-63`

**Issue:** FastAPI deprecated `@app.on_event("startup")` in favour of lifespan context managers. The decorator still works in current FastAPI versions but generates a deprecation warning and will eventually be removed.

**Fix:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("[STARTUP] AccountIQ Learning Agent ready.")
    yield

app = FastAPI(..., lifespan=lifespan)
```

---

## Info

### IN-01: `_register_admin` helper duplicated across four test files — should be in `conftest.py`

**File:** `tests/test_admin_gate.py:17-29`, `tests/test_auth.py:133-141` (inline), `tests/test_isolation.py:22-32`, `tests/test_profile.py:24-34`, `tests/test_upload_auto.py:16-26`

The `_register_admin` helper that patches `OWNER_EMAIL` is copy-pasted across four test modules (slight variations between `test_auth.py` inline usage and the three files with the full helper). A single version in `conftest.py` would eliminate the drift. The inline version in `test_auth.py` does not restore to `original` but hardcodes `""`, which is a subtle divergence.

**Fix:** Move one canonical `_register_admin` to `conftest.py` and import or reference it from each test module.

---

### IN-02: `test_upload_auto.py` redundantly marks tests with `@pytest.mark.asyncio` — `asyncio_mode = auto` in `pytest.ini` makes these no-ops

**File:** `tests/test_upload_auto.py:47,61,83,104,121,145,166`

`pytest.ini` sets `asyncio_mode = auto`, so all async test functions are automatically collected as async tests. The explicit `@pytest.mark.asyncio` decorators in `test_upload_auto.py` are redundant noise that can mislead readers into thinking other test files are missing them when they are not.

**Fix:** Remove the `@pytest.mark.asyncio` decorators from `test_upload_auto.py`.

---

### IN-03: `print()` used for structured logging throughout the backend

**File:** `backend/auth.py:148,165,169`, `backend/main.py:63,629`

The backend uses bare `print()` for log output. In a production ASGI deployment (gunicorn/uvicorn workers) this bypasses log routing, loses timestamps, and has no log levels. No immediate bug risk, but noted for the "first-draft quality bar" standard.

**Fix:** Replace with Python's `logging` module:
```python
import logging
logger = logging.getLogger(__name__)
logger.info("[AUTH] User registered: %s", email)
```

---

_Reviewed: 2026-05-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
