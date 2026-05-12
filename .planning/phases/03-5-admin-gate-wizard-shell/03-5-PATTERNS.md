# Phase 3.5: Admin Gate + User Wizard Shell - Pattern Map

**Mapped:** 2026-05-12
**Files analyzed:** 6 (4 modified, 1 new route inlined, 1 new test file)
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/db.py` | migration | batch | `backend/db.py` lines 122-134 (same file, same pattern) | exact |
| `backend/auth.py` | middleware/dependency | request-response | `backend/auth.py` `get_current_user` (same file, extend) | exact |
| `backend/main.py` | controller | request-response | `backend/main.py` `/documents/upload` lines 520-615 | exact |
| `frontend/index.html` | component/UI | event-driven | `frontend/index.html` `showMainApp` / `initApp` lines 1999-2154 | exact |
| `tests/test_admin_gate.py` | test | request-response | `tests/test_auth.py` + `tests/test_profile.py` | exact |
| `tests/conftest.py` | test config | — | `tests/conftest.py` `fresh_db` + `_register` pattern | exact |

---

## Pattern Assignments

### `backend/db.py` — `_migrate_db` extension (migration, batch)

**Analog:** `backend/db.py` lines 122-134 (same file)

**Migration loop pattern** (lines 122-134):
```python
def _migrate_db(conn: sqlite3.Connection):
    """Add columns introduced in v2/v3 — safe to run on an existing database."""
    for sql in [
        "ALTER TABLE documents ADD COLUMN narrative TEXT",
        "ALTER TABLE documents ADD COLUMN reporting_standard TEXT DEFAULT 'UNKNOWN'",
        # Phase 2: user ownership columns
        "ALTER TABLE companies ADD COLUMN user_id INTEGER",
        "ALTER TABLE documents ADD COLUMN user_id INTEGER",
        # Phase 3: business profile description
        "ALTER TABLE companies ADD COLUMN description TEXT",
    ]:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
```

**What to add for Phase 3.5** — insert at the end of the `for sql in [...]` list:
```python
        # Phase 3.5: admin role
        "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0",
```

Note: `NOT NULL DEFAULT 0` is valid for `ALTER TABLE ADD COLUMN` in SQLite when a default is supplied. All existing users receive `is_admin = 0` automatically. No table-rename pattern needed (unlike the Phase 2 UNIQUE constraint migration at lines 136-188).

---

### `backend/auth.py` — extend `get_current_user`, add `require_admin`, extend `register`, add `OWNER_EMAIL` (middleware, request-response)

**Analog:** `backend/auth.py` (same file — extend existing patterns)

**Imports / module-scope config pattern** (lines 8-33):
```python
import os
# ... existing imports ...
SECRET_KEY = os.environ.get("SECRET_KEY", "")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
```
Copy this env-var loading pattern for OWNER_EMAIL:
```python
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "").strip().lower()
```

**`get_current_user` — current SELECT** (lines 90-96):
```python
async with db.execute(
    "SELECT id, email, created_at FROM users WHERE id=?", (user_id,)
) as cur:
    user = await cur.fetchone()
if not user:
    raise HTTPException(401, "User not found")
return dict(user)
```
Extend to:
```python
async with db.execute(
    "SELECT id, email, is_admin, created_at FROM users WHERE id=?", (user_id,)
) as cur:
    user = await cur.fetchone()
if not user:
    raise HTTPException(401, "User not found")
return dict(user)
```
`dict(user)` on an `aiosqlite.Row` picks up all selected columns automatically, so `is_admin` appears in the returned dict with no further change.

**`register` route — current INSERT block** (lines 119-134):
```python
try:
    async with db.execute(
        "INSERT INTO users (email, hashed_pw) VALUES (?, ?)",
        (email, hashed),
    ) as cur:
        user_id = cur.lastrowid
    await db.commit()
except Exception as e:
    if "UNIQUE constraint" in str(e):
        raise HTTPException(409, "Email already registered")
    raise HTTPException(500, str(e))

token = create_access_token({"sub": str(user_id), "email": email})
_set_session_cookie(response, token)
print(f"[AUTH] User registered: {email}")
return {"id": user_id, "email": email}
```
Add OWNER_EMAIL check after `await db.commit()` and before token creation:
```python
    await db.commit()
# Promote to admin if OWNER_EMAIL matches (case-insensitive — both lowercased at load/input time)
if OWNER_EMAIL and email == OWNER_EMAIL:
    await db.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user_id,))
    await db.commit()
```

**`require_admin` dependency — new function after `get_current_user`:**
```python
async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Return user if admin, else 403. Unauthenticated callers still get 401 (from get_current_user)."""
    if not current_user.get("is_admin"):
        raise HTTPException(403, "Admin access required")
    return current_user
```
This chains off `get_current_user` exactly as FastAPI's dependency caching requires — no JWT re-decode. The error response follows the established `HTTPException(status_code, detail_string)` convention used throughout `auth.py` and `main.py`.

**`/auth/me` route** (lines 173-175):
```python
@auth_router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user
```
No change needed: once `get_current_user` includes `is_admin` in its SELECT, `/auth/me` returns it automatically.

---

### `backend/main.py` — apply `require_admin` to existing routes + add `POST /wizard/upload` (controller, request-response)

**Analog:** `backend/main.py` existing route signatures

**Import extension** (line 25 — current):
```python
from auth import auth_router, get_current_user
```
Extend to:
```python
from auth import auth_router, get_current_user, require_admin
```

**Per-route dependency swap pattern** (lines 79-83 — `list_companies` as representative):
```python
# Before:
@app.get("/companies")
async def list_companies(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):

# After:
@app.get("/companies")
async def list_companies(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),   # replaces get_current_user
):
```
Apply this one-line swap to all 15 routes under `/companies/*`, `/documents/*`, `/financials/*`, `/patterns/*`, `/analytics/*`, `/settings/*`. Do NOT apply to `/health`, `/auth/*`, or the new `/wizard/upload`.

**`POST /wizard/upload` — copy structure from `/documents/upload`** (lines 520-615):

The `/documents/upload` route provides the exact pattern to copy:
- `UploadFile`, `Form`, `BackgroundTasks`, `Depends(get_db)`, `Depends(get_current_user)` signature
- `Path(file.filename).suffix.lower()` + allowed set for file type validation
- `Path(file.filename).name` for safe filename (project security convention)
- `_resolve_or_create_company(db, name, user_id)` for idempotent company creation (lines 502-517)
- `company_dir = PDF_DIR / str(company_id); company_dir.mkdir(exist_ok=True)` for directory creation
- `shutil.copyfileobj(file.file, f)` for streaming file write
- `INSERT INTO documents ... user_id=current_user["id"]` with `cur.lastrowid`
- `background_tasks.add_task(_run_ingestion, document_id, company_id, str(dest), entity_type, exchange, fiscal_year_end)`

**Key simplification vs `/documents/upload`:** wizard upload always uses `entity_type="sme"`, `exchange="Private"`, `fiscal_year_end=""` — no conditional branches needed. Always uses `_resolve_or_create_company` (no explicit `company_id` path).

**Return shape** (matches D-06):
```python
return {"company_id": company_id, "document_id": document_id, "status": "processing"}
```

**Circular import note:** Define the wizard route directly in `main.py` (below existing routes) to avoid `wizard.py` ↔ `main.py` circular import. `_run_ingestion` and `PDF_DIR` are defined in `main.py` and cannot be imported from it by a module that `main.py` also imports.

---

### `frontend/index.html` — extend `initApp()` and add wizard HTML/JS (component, event-driven)

**Analog:** `frontend/index.html` `showMainApp` (lines 1999-2011) and `initApp` (lines 2145-2154)

**`showAuthWall` display-toggle pattern** (lines 1973-1997):
```javascript
function showAuthWall(expired) {
  document.getElementById('main-app').style.display = 'none';
  document.getElementById('user-header').style.display = 'none';
  const authPage = document.getElementById('auth-page');
  authPage.style.display = 'flex';
  // ...field clearing and alert logic
}
```
Copy this hide/show element pattern for `showWizard(user)`:
```javascript
function showWizard(user) {
  document.getElementById('auth-page').style.display = 'none';
  document.getElementById('main-app').style.display = 'none';
  document.getElementById('wizard-page').style.display = 'block';
  document.getElementById('wizard-user-email').textContent = user.email; // .textContent, not .innerHTML
  document.getElementById('user-header').style.display = 'flex';
  document.getElementById('user-email').textContent = user.email;
  renderWizardStep(1);
}
```

**`showMainApp` user email pattern** (lines 1999-2011):
```javascript
function showMainApp(user) {
  document.getElementById('auth-page').style.display = 'none';
  document.getElementById('main-app').style.display = 'block';
  document.getElementById('user-email').textContent = user.email;   // .textContent — XSS rule
  document.getElementById('user-header').style.display = 'flex';
  // ...
}
```

**`initApp` — current** (lines 2145-2154):
```javascript
async function initApp() {
  const user = await apiFetch('/auth/me');
  if (!user) {
    showAuthWall(false);
    return;
  }
  showMainApp(user);
}
```
Extend to:
```javascript
async function initApp() {
  const user = await apiFetch('/auth/me');
  if (!user) {
    showAuthWall(false);
    return;
  }
  if (user.is_admin) {
    showMainApp(user);
  } else {
    showWizard(user);
  }
}
```

**`apiFetch` / `apiPost` helpers** (lines 1875-1892) — wizard calls use these directly:
```javascript
async function apiFetch(path) {
  try {
    const res = await fetch(API + path, { credentials: 'include' });
    if (res.status === 401) { showAuthWall(true); return null; }
    if (!res.ok) { console.error(await res.text()); return null; }
    return res.json();
  } catch(e) { console.error(e); return null; }
}

async function apiPost(path, formData) {
  try {
    const res = await fetch(API + path, { method: 'POST', body: formData, credentials: 'include' });
    if (res.status === 401) { showAuthWall(true); return null; }
    const json = await res.json();
    if (!res.ok) { showAlert('upload-alert', json.detail || 'Error', 'error'); return null; }
    return json;
  } catch(e) { showAlert('upload-alert', e.message, 'error'); return null; }
}
```
Wizard step 1 submit calls `apiPost('/wizard/upload', fd)`. Wizard alert uses `showAlert('wizard-alert', msg, type)` — follow same `showAlert` signature (line 1894-1903).

**`showAlert` pattern** (lines 1894-1903):
```javascript
function showAlert(containerId, msg, type) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '';
  const div = document.createElement('div');
  div.className = `alert alert-${type}`;
  div.textContent = msg;    // .textContent — XSS rule
  el.appendChild(div);
  if (type !== 'error') setTimeout(() => { el.innerHTML = ''; }, 5000);
}
```

**Wizard state machine pattern** — copy module-scope variable style from existing globals in `index.html`:
```javascript
// Module-scope wizard state (no framework — matches existing pattern)
let wizardStep = 1;
let wizardUploadResult = null;   // {company_id, document_id, status}
let wizardReportType = null;     // string key

function renderWizardStep(step) {
  wizardStep = step;
  document.querySelectorAll('.wizard-step').forEach(el => {
    el.style.display = el.dataset.step == step ? 'block' : 'none';
  });
  const ind = document.getElementById('wizard-step-indicator');
  if (ind) ind.textContent = `Step ${step} of 3`;
}
```

**XSS rule:** All user-supplied values (email, business name) must use `.textContent` or `createTextNode()`. Never `.innerHTML` for dynamic content. This applies to the wizard confirmation card where `user.email` is interpolated.

**CSS reuse:** Use existing tokens and classes only — `--navy`, `--blue`, `--card`, `--border`, `.card`, `.form-group`, `.btn`, `.btn-primary`, `.alert`, `.alert-error`, `.alert-success`. No new CSS variables. Selected report type card style: `border: 2px solid var(--blue); background: #e3f2fd`.

---

### `tests/test_admin_gate.py` — new test file (test, request-response)

**Analog 1:** `tests/test_auth.py` — helper function pattern and fixture usage
**Analog 2:** `tests/test_profile.py` — `fresh_all_db` fixture, multi-user `_make_other_client` pattern

**File structure pattern** (copy from `tests/test_auth.py` lines 1-18):
```python
"""Tests for Phase 3.5: Admin Gate + User Wizard Shell (AUTH-09, UX-01)."""
import pytest
import os

# Helpers
async def _register(client, email="alice@example.com", password="correcthorse"):
    return await client.post(
        "/auth/register",
        data={"email": email, "password": password},
    )
```

**`_register_admin` helper pattern** — extend `_register` convention to set OWNER_EMAIL env var:
```python
async def _register_admin(client, email="admin@example.com", password="correcthorse"):
    """Register a user as admin by setting OWNER_EMAIL env var before registration."""
    import auth as _auth_module
    original = _auth_module.OWNER_EMAIL
    _auth_module.OWNER_EMAIL = email.lower()
    try:
        r = await client.post(
            "/auth/register",
            data={"email": email, "password": password},
        )
    finally:
        _auth_module.OWNER_EMAIL = original
    return r
```
This follows the DB-patching pattern from `conftest.py` (lines 39-46: `_db_module.DB_PATH = ...`) — directly mutate the module-level variable, restore in `finally`.

**403 gate test pattern** (copy structure from `tests/test_auth.py` lines 126-130):
```python
async def test_regular_user_companies_403(client, fresh_all_db):
    """AUTH-09: non-admin GET /companies returns 403 (not 401 or 404)."""
    await _register(client, "user@example.com")
    r = await client.get("/companies")
    assert r.status_code == 403, r.text
```

**Admin passes gate pattern:**
```python
async def test_admin_user_companies_200(client, fresh_all_db):
    """AUTH-09: admin user GET /companies returns 200."""
    await _register_admin(client, "admin@example.com")
    r = await client.get("/companies")
    assert r.status_code == 200, r.text
```

**Unauthenticated still 401 pattern** (not 403 — dependency chain test):
```python
async def test_unauthenticated_returns_401_not_403(client, fresh_all_db):
    """AUTH-09: no cookie on admin-gated route must return 401, not 403."""
    client.cookies.clear()
    r = await client.get("/companies")
    assert r.status_code == 401, r.text
```

**Wizard upload test pattern** — use `io.BytesIO` for file upload, copy from `tests/test_profile.py` `_create_company` for FormData pattern:
```python
async def test_wizard_upload_creates_company_and_document(client, fresh_all_db):
    """UX-01: POST /wizard/upload creates company + document for non-admin user."""
    await _register(client, "user@example.com")
    import io
    fd = {
        "business_name": (None, "My Test Business"),
        "file": ("financials.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"),
    }
    r = await client.post("/wizard/upload", files=fd)
    assert r.status_code == 201, r.text
    body = r.json()
    assert "company_id" in body
    assert "document_id" in body
    assert body["status"] == "processing"
```

**Fixture usage pattern:** Use `fresh_all_db` (not `fresh_db`) for admin gate tests — these tests register multiple users and create companies/documents that must be isolated. `fresh_all_db` truncates all tables in FK-safe order (see `conftest.py` lines 77-96).

---

### `tests/conftest.py` — add `_register_admin` helper (test config)

**Analog:** `tests/conftest.py` `fresh_db` fixture (lines 62-73) and `fresh_all_db` fixture (lines 76-96)

The `_register_admin` helper is more naturally a standalone async function in `test_admin_gate.py` (as shown above) than a pytest fixture, because it needs the `client` argument. The `conftest.py` only needs updating if other test files also need admin registration. For Phase 3.5, define `_register_admin` locally in `test_admin_gate.py`.

If added to `conftest.py` as a fixture for reuse, follow the `fresh_db` fixture pattern:
```python
@pytest_asyncio.fixture
async def admin_client(client, fresh_all_db):
    """AsyncClient pre-authenticated as admin user."""
    import auth as _auth_module
    _auth_module.OWNER_EMAIL = "admin@example.com"
    await client.post("/auth/register", data={"email": "admin@example.com", "password": "adminpass"})
    _auth_module.OWNER_EMAIL = ""
    yield client
```

---

## Shared Patterns

### Authentication — `get_current_user` dependency chain
**Source:** `backend/auth.py` lines 73-96
**Apply to:** `require_admin` implementation; all routes that replace `get_current_user` with `require_admin`
```python
async def get_current_user(
    accountiq_session: str | None = Cookie(default=None),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    """Return the authenticated user dict, or raise 401."""
    if not accountiq_session:
        raise HTTPException(401, "Not authenticated")
    # ... JWT decode ...
    return dict(user)
```
`require_admin` must call `Depends(get_current_user)` — never replicate JWT decode logic. FastAPI caches the dependency result within a single request so there is no double DB query.

### Error handling — `HTTPException` with string detail
**Source:** `backend/auth.py` throughout; `backend/main.py` throughout
**Apply to:** `require_admin`, `/wizard/upload` validation
```python
raise HTTPException(403, "Admin access required")   # status code first, detail string second
raise HTTPException(400, "Business name is required")
raise HTTPException(400, f"Only PDF and Excel files are accepted. Got: {suffix}")
```
Convention: `detail` is always a plain string, never a dict.

### File safety — `Path(file.filename).name`
**Source:** `backend/main.py` line 582
**Apply to:** `/wizard/upload` file save
```python
safe_name = Path(file.filename).name   # strips directory traversal — project security rule
dest = company_dir / safe_name
```

### Async DB pattern
**Source:** `backend/main.py` lines 113-123 (create_company), 594-601 (document insert)
**Apply to:** `/wizard/upload` company and document inserts
```python
async with db.execute("INSERT INTO ... VALUES (?)", (val,)) as cur:
    row_id = cur.lastrowid
await db.commit()
```

### Frontend XSS rule
**Source:** `frontend/index.html` lines 2002, 1900
**Apply to:** All wizard HTML rendering of user-supplied values (email, business_name, step indicator)
```javascript
document.getElementById('wizard-user-email').textContent = user.email;  // never .innerHTML
div.textContent = msg;   // in showAlert
```

### Environment variable loading
**Source:** `backend/auth.py` lines 23-28
**Apply to:** `OWNER_EMAIL` module-scope constant in `auth.py`
```python
SECRET_KEY = os.environ.get("SECRET_KEY", "")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
# Pattern: os.environ.get("VAR", "").strip().lower() for string comparisons
```

---

## No Analog Found

None — all Phase 3.5 files have direct analogs in the existing codebase.

---

## Metadata

**Analog search scope:** `backend/`, `frontend/`, `tests/`
**Files scanned:** `backend/auth.py`, `backend/db.py`, `backend/main.py` (lines 1-680), `frontend/index.html` (lines 1870-2158), `tests/conftest.py`, `tests/test_auth.py`, `tests/test_profile.py`
**Pattern extraction date:** 2026-05-12
