# Phase 1: Security & Auth Foundation - Pattern Map

**Mapped:** 2026-05-05
**Files analyzed:** 8 new/modified files
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/auth.py` | service + route | request-response | `backend/main.py` (routes + `get_db`) | role-match |
| `backend/db.py` | model/schema | CRUD | `backend/db.py` itself (additive change) | exact |
| `backend/main.py` | config + route | request-response | `backend/main.py` itself (surgical edits) | exact |
| `frontend/index.html` | component | request-response | `frontend/index.html` itself (surgical edits) | exact |
| `backend/requirements.txt` | config | — | `backend/requirements.txt` itself | exact |
| `tests/conftest.py` | test | request-response | no existing test analog | no-analog |
| `tests/test_auth.py` | test | request-response | no existing test analog | no-analog |
| `tests/test_security.py` | test | request-response | no existing test analog | no-analog |

---

## Pattern Assignments

### `backend/auth.py` (service + route, request-response)

**Analog:** `backend/main.py`

This is a new module. All patterns below are extracted from the existing codebase analog and the locked research patterns.

**Imports pattern** — follow `backend/main.py` lines 1-22 import ordering (stdlib → third-party → local):

```python
"""
Auth routes and dependency for AccountIQ.
Register, login, logout, get_current_user.
"""
import os
from datetime import datetime, timedelta, UTC
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Response
import aiosqlite
import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from db import get_db, DB_PATH
```

**Section separator pattern** — `backend/main.py` lines 25-27:

```python
# ---------------------------------------------------------------------------
# Section name
# ---------------------------------------------------------------------------
```

**Logging pattern** — `backend/main.py` lines 58, 206:

```python
print("[AUTH] User registered: user@example.com")
print(f"[AUTH] Login failed for: {email}")
print(f"[ERROR] Auth error: {e}")
```

**`get_db` dependency pattern (exact model to extend)** — `backend/db.py` lines 102-108:

```python
async def get_db() -> aiosqlite.Connection:
    """Async dependency for FastAPI routes."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db
```

**`get_current_user` dependency** — mirrors `get_db` shape; follows research Pattern 2 exactly:

```python
SECRET_KEY = os.environ.get("SECRET_KEY", "")
ALGORITHM = "HS256"

async def get_current_user(
    accountiq_session: str | None = Cookie(default=None),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    if not accountiq_session:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(accountiq_session, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(401, "Invalid token")
    except InvalidTokenError:
        raise HTTPException(401, "Invalid or expired token")
    async with db.execute(
        "SELECT id, email, created_at FROM users WHERE id=?", (user_id,)
    ) as cur:
        user = await cur.fetchone()
    if not user:
        raise HTTPException(401, "User not found")
    return dict(user)
```

**Error handling pattern** — `backend/main.py` lines 104-107 (early validation → `raise HTTPException`):

```python
if not company:
    raise HTTPException(404, "Company not found")
if "UNIQUE constraint" in str(e):
    raise HTTPException(409, f"Company '{name}' on {exchange} already exists.")
raise HTTPException(500, str(e))
```

Apply the same pattern in auth routes:
- 400 for password too short / malformed input
- 401 for bad credentials / invalid token
- 409 for duplicate email on register

**Route handler pattern (POST with Form)** — `backend/main.py` lines 88-107 (`create_company` as model):

```python
@app.post("/companies")
async def create_company(
    name:     str = Form(...),
    ticker:   str = Form(None),
    db: aiosqlite.Connection = Depends(get_db),
):
    try:
        async with db.execute("""
            INSERT INTO companies (name, ticker, ...)
            VALUES (?, ?, ...)
        """, (name, ticker, ...)) as cur:
            company_id = cur.lastrowid
        await db.commit()
        return {"id": company_id, "name": name}
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(409, ...)
        raise HTTPException(500, str(e))
```

**Route handler pattern (GET with DB query)** — `backend/main.py` lines 74-84 (`list_companies` as model):

```python
@app.get("/companies")
async def list_companies(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT ...") as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]
```

**`/auth/me` response shape** — matches `get_company` pattern, `backend/main.py` lines 111-116:

```python
@app.get("/companies/{company_id}")
async def get_company(company_id: int, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM companies WHERE id=?", (company_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Company not found")
    return dict(row)
```

**`set_cookie` / `delete_cookie` pattern** — research Pattern 1 (no existing analog in codebase):

```python
# Login — set cookie
response.set_cookie(
    key="accountiq_session",
    value=token,
    httponly=True,
    samesite="lax",
    max_age=7 * 24 * 60 * 60,
    secure=False,  # HTTP localhost; flip to True in production
)

# Logout — delete cookie
response.delete_cookie(key="accountiq_session", httponly=True, samesite="lax")
```

**Background task DB connection pattern (for reference — `auth.py` does not use background tasks, but shows how the module opens its own connection)** — `backend/main.py` lines 195-207:

```python
async def _run_ingestion(document_id, company_id, filepath, ...):
    """Background task — opens its own DB connection."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        try:
            await ingest_document(...)
        except Exception as e:
            print(f"[ERROR] Ingestion failed for doc {document_id}: {e}")
```

---

### `backend/db.py` — additive change: `users` table

**Analog:** `backend/db.py` itself (lines 12-91)

**Existing SCHEMA string pattern** (lines 12-91) — new `users` table is appended inside `SCHEMA`:

```python
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Companies master table
CREATE TABLE IF NOT EXISTS companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    ...
    created_at  TEXT    DEFAULT (datetime('now')),
    UNIQUE(name, exchange)
);
...
"""
```

Add the `users` table in the same style — `TEXT DEFAULT (datetime('now'))` for timestamps, `UNIQUE` constraint for email:

```sql
-- Authenticated users
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT    NOT NULL UNIQUE,
    hashed_pw   TEXT    NOT NULL,
    created_at  TEXT    DEFAULT (datetime('now'))
);
```

**`_migrate_db` pattern** (lines 111-121) — if `users` table cannot be created via SCHEMA on existing DB, use the safe try/except ALTER TABLE pattern:

```python
def _migrate_db(conn: sqlite3.Connection):
    """Add columns introduced in v2 — safe to run on an existing database."""
    for sql in [
        "ALTER TABLE documents ADD COLUMN narrative TEXT",
        ...
    ]:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
```

Note: Since `users` is a whole new table (not a column), `CREATE TABLE IF NOT EXISTS` in `SCHEMA` is sufficient. No ALTER TABLE needed.

---

### `backend/main.py` — three surgical fixes + route protection

**Analog:** `backend/main.py` itself

**Fix 1: CORS middleware** — lines 35-40 (current broken pattern → fixed pattern):

```python
# CURRENT (broken — wildcard + no credentials flag):
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# FIXED:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8765"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Fix 2: Filename sanitisation** — line 167 (current broken pattern → fixed pattern):

```python
# CURRENT (line 167 — raw filename, path traversal risk):
dest = company_dir / file.filename

# FIXED (one-line change):
dest = company_dir / Path(file.filename).name
```

Also fix line 176 where `file.filename` is stored in DB — use `Path(file.filename).name` there too.

**Fix 3: Add auth to all routes** — existing pattern `backend/main.py` lines 74-75, extended:

```python
# BEFORE (existing pattern for all routes):
@app.get("/companies")
async def list_companies(db: aiosqlite.Connection = Depends(get_db)):

# AFTER — add current_user alongside get_db (same Depends() pattern):
@app.get("/companies")
async def list_companies(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
```

**Routes that need `Depends(get_current_user)` added** (enumerate all — no global catch-all):
- `GET /companies` (line 75)
- `POST /companies` (line 88)
- `GET /companies/{company_id}` (line 111)
- `GET /documents` (line 124)
- `POST /documents/upload` (line 145)
- `GET /documents/{document_id}/status` (line 210)
- `GET /documents/{document_id}/rows` (line 231)
- `POST /documents/{document_id}/retry` (line 396)
- `GET /financials/{company_id}` (line 245)
- `GET /patterns` (line 276)
- `GET /patterns/export` (line 297)
- `GET /analytics/overview` (line 313)
- `GET /analytics/confidence` (line 340)
- `GET /settings` (line 356)
- `POST /settings` (line 369)

Routes that remain public: `GET /health` (line 65), all `/auth/*` routes.

**Import of auth router** — follows existing local module import pattern (line 22-23):

```python
# Existing local imports:
from db import init_db, get_db, get_pattern_library, DB_PATH
from ingestion import ingest_document, ALL_ROWS

# Add:
from auth import auth_router, get_current_user
app.include_router(auth_router)
```

---

### `frontend/index.html` — four categories of changes

**Analog:** `frontend/index.html` itself

**Change 1: `apiFetch` and `apiPost` helpers** — lines 698-713 (current → fixed):

```javascript
// CURRENT apiFetch (line 698-704):
async function apiFetch(path) {
  try {
    const res = await fetch(API + path);
    if (!res.ok) { console.error(await res.text()); return null; }
    return res.json();
  } catch(e) { console.error(e); return null; }
}

// FIXED — add credentials: 'include' AND handle 401 → show auth wall:
async function apiFetch(path) {
  try {
    const res = await fetch(API + path, { credentials: 'include' });
    if (res.status === 401) { showAuthWall(); return null; }
    if (!res.ok) { console.error(await res.text()); return null; }
    return res.json();
  } catch(e) { console.error(e); return null; }
}

// CURRENT apiPost (line 706-713):
async function apiPost(path, formData) {
  try {
    const res = await fetch(API + path, { method: 'POST', body: formData });
    const json = await res.json();
    if (!res.ok) { showAlert('upload-alert', json.detail || 'Error', 'error'); return null; }
    return json;
  } catch(e) { showAlert('upload-alert', e.message, 'error'); return null; }
}

// FIXED — add credentials: 'include' AND handle 401:
async function apiPost(path, formData) {
  try {
    const res = await fetch(API + path, { method: 'POST', body: formData, credentials: 'include' });
    if (res.status === 401) { showAuthWall(); return null; }
    const json = await res.json();
    if (!res.ok) { showAlert('upload-alert', json.detail || 'Error', 'error'); return null; }
    return json;
  } catch(e) { showAlert('upload-alert', e.message, 'error'); return null; }
}
```

**Change 2: Auth wall HTML** — insert before `<nav>` (line 115). New `#auth-page` div following existing card/form-group/btn patterns (lines 28-48):

```html
<!-- Auth wall — shown when unauthenticated; hides entire main app -->
<div id="auth-page" style="display:none;position:fixed;inset:0;background:var(--bg);
     z-index:200;display:flex;align-items:center;justify-content:center">
  <div class="card" style="width:380px;max-width:95vw">
    <h2 id="auth-heading">Sign in to AccountIQ</h2>
    <div id="auth-alert"></div>
    <!-- Login form (shown by default) -->
    <div id="login-form">
      <div class="form-group"><label>Email</label>
        <input id="auth-email" type="email" placeholder="you@example.com"/>
      </div>
      <div class="form-group"><label>Password</label>
        <input id="auth-password" type="password" placeholder="••••••••"/>
      </div>
      <button class="btn btn-primary" style="width:100%;margin-top:1rem" onclick="doLogin()">Sign in</button>
      <p class="text-muted" style="text-align:center;margin-top:1rem;font-size:.85rem">
        No account? <a href="#" onclick="toggleAuthMode()">Create account</a>
      </p>
    </div>
    <!-- Register form (hidden by default) -->
    <div id="register-form" style="display:none">
      <div class="form-group"><label>Email</label>
        <input id="reg-email" type="email" placeholder="you@example.com"/>
      </div>
      <div class="form-group"><label>Password (min 8 characters)</label>
        <input id="reg-password" type="password" placeholder="••••••••"/>
      </div>
      <button class="btn btn-primary" style="width:100%;margin-top:1rem" onclick="doRegister()">Create account</button>
      <p class="text-muted" style="text-align:center;margin-top:1rem;font-size:.85rem">
        Have an account? <a href="#" onclick="toggleAuthMode()">Back to login</a>
      </p>
    </div>
  </div>
</div>
```

**Change 3: Header logout button** — insert into `<nav>` (after line 129), following existing nav pattern (lines 115-129):

```html
<!-- Add to nav, after .nav-tabs div -->
<div id="user-header" style="display:none;margin-left:1rem;display:flex;align-items:center;gap:.75rem">
  <span id="user-email" style="font-size:.8rem;opacity:.8"></span>
  <button class="btn btn-sm" style="background:rgba(255,255,255,.15);color:#fff" onclick="doLogout()">Logout</button>
</div>
```

**Change 4: `showAlert` fix** — line 715-720 (current uses `innerHTML`; fix uses `textContent` for the message):

```javascript
// CURRENT (line 715-720 — innerHTML XSS risk if msg contains server data):
function showAlert(containerId, msg, type) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = `<div class="alert alert-${type}">${msg}</div>`;
  if (type !== 'error') setTimeout(() => { el.innerHTML = ''; }, 5000);
}

// FIXED — build div via DOM; only type (trusted local string) goes into className:
function showAlert(containerId, msg, type) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const div = document.createElement('div');
  div.className = `alert alert-${type}`;
  div.textContent = msg;
  el.innerHTML = '';
  el.appendChild(div);
  if (type !== 'error') setTimeout(() => { el.innerHTML = ''; }, 5000);
}
```

**Change 5: `viewNarrative` fix** — lines 742-750 (current uses `innerHTML` on AI-generated text — critical XSS):

```javascript
// CURRENT (line 744-748 — critical: AI text injected as HTML):
const text = decodeURIComponent(encodedText);
document.getElementById('narrative-body').innerHTML = text
  .split(/\n\n+/)
  .map(p => `<p>${p.replace(/\n/g,'<br/>')}</p>`)
  .join('');

// FIXED — create <p> elements, set .textContent on each:
function viewNarrative(docId, title, encodedText) {
  document.getElementById('narrative-title').textContent = title || 'Executive Summary';
  const text = decodeURIComponent(encodedText);
  const container = document.getElementById('narrative-body');
  container.innerHTML = '';
  text.split(/\n\n+/).forEach(para => {
    if (!para.trim()) return;
    const p = document.createElement('p');
    p.textContent = para;
    container.appendChild(p);
  });
  document.getElementById('narrative-modal').classList.add('open');
}
```

**Change 6: Page init — `loadDashboard()` on line 760 → `initApp()`**:

```javascript
// CURRENT (line 759-761 — loads dashboard without auth check):
// Init
loadDashboard();
checkApiKey();

// FIXED — auth check first, show wall or app:
async function initApp() {
  const user = await apiFetch('/auth/me');
  if (!user) {
    showAuthWall();
    return;
  }
  showApp(user);
}

function showAuthWall() {
  document.getElementById('auth-page').style.display = 'flex';
  document.getElementById('main-app').style.display = 'none';
}

function showApp(user) {
  document.getElementById('auth-page').style.display = 'none';
  document.getElementById('main-app').style.display = 'block';
  document.getElementById('user-email').textContent = user.email;
  document.getElementById('user-header').style.display = 'flex';
  showPage('dashboard');
  checkApiKey();
}

// Replace last two lines of <script>:
initApp();
```

Note: The existing `<nav>` and all page `<div>`s must be wrapped in a `<div id="main-app">` that starts hidden, so the auth wall can gate everything.

**Change 7: XSS fixes in `loadDashboard`** — lines 375 and 384 (server data in `innerHTML`):

```javascript
// CURRENT (line 375) — e.exchange is server data, interpolated into innerHTML:
document.getElementById('exchange-list').innerHTML = ov.by_exchange.map(e =>
  `<div ...><span>${e.exchange || 'Private'}</span>...`
).join('') || '<span>No data yet.</span>';

// FIXED — build DOM nodes; only static structural strings use innerHTML:
const list = document.getElementById('exchange-list');
list.innerHTML = '';
if (!ov.by_exchange.length) {
  list.textContent = 'No data yet.';
} else {
  ov.by_exchange.forEach(e => {
    const row = document.createElement('div');
    row.className = 'flex';
    row.style.cssText = 'padding:.4rem 0;border-bottom:1px solid var(--border)';
    const label = document.createElement('span');
    label.textContent = e.exchange || 'Private';
    const count = document.createElement('span');
    count.className = 'ml-auto';
    count.style.fontWeight = '700';
    count.textContent = e.n;
    row.appendChild(label);
    row.appendChild(count);
    list.appendChild(row);
  });
}
```

**Change 8: XSS fix in `loadCompanies`** — lines 404-412 (company fields in `innerHTML`):

```javascript
// CURRENT (line 404) — c.name, c.ticker, c.sector, etc. interpolated into innerHTML:
tbody.innerHTML = data.map(c => `<tr>
  <td><strong>${c.name}</strong></td>
  ...
</tr>`).join('');

// FIXED — build rows via DOM for all server-sourced leaf text nodes:
tbody.innerHTML = '';
data.forEach(c => {
  const tr = document.createElement('tr');
  // name cell
  const tdName = document.createElement('td');
  const strong = document.createElement('strong');
  strong.textContent = c.name;
  tdName.appendChild(strong);
  tr.appendChild(tdName);
  // ticker, exchange, sector, country, doc_count cells use textContent
  ['ticker','exchange','sector','country'].forEach(field => {
    const td = document.createElement('td');
    td.textContent = c[field] || '—';
    tr.appendChild(td);
  });
  // doc_count
  const tdCount = document.createElement('td');
  tdCount.textContent = c.doc_count;
  tr.appendChild(tdCount);
  // action button (static trusted HTML — onclick uses numeric id, not string from server)
  const tdBtn = document.createElement('td');
  const btn = document.createElement('button');
  btn.className = 'btn btn-sm btn-primary';
  btn.textContent = 'Upload PDF';
  btn.onclick = () => { showPage('upload'); setUploadCompany(c.id); };
  tdBtn.appendChild(btn);
  tr.appendChild(tdBtn);
  tbody.appendChild(tr);
});
```

**Change 9: XSS fix in `populateCompanySelects`** — lines 454-458 (c.name in `innerHTML`):

```javascript
// CURRENT (line 454) — c.name interpolated into option innerHTML:
const opts = companies.map(c => `<option value="${c.id}">${c.name} ...`).join('');

// FIXED — createElement('option') + textContent:
const selects = ['up-company', 'fin-company'];
selects.forEach(id => {
  const sel = document.getElementById(id);
  sel.innerHTML = '<option value="">Select company…</option>';
  companies.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = `${c.name} ${c.exchange ? `(${c.exchange})` : '(Private)'}`;
    sel.appendChild(opt);
  });
});
```

**Change 10: XSS fix in `loadSettings`** — lines 655-660 (`api_key_preview` in `innerHTML`):

```javascript
// CURRENT (line 655-659) — api_key_preview in innerHTML:
el.innerHTML = `<span ...>✓ API key configured</span> — <code>${s.api_key_preview}</code>`;

// FIXED — build DOM nodes; api_key_preview goes into textContent:
el.innerHTML = '';
const check = document.createElement('span');
check.style.color = 'var(--green)';
check.textContent = '✓ API key configured';
el.appendChild(check);
el.appendChild(document.createTextNode(' — '));
const code = document.createElement('code');
code.style.fontSize = '.8rem';
code.textContent = s.api_key_preview;
el.appendChild(code);
```

---

### `backend/requirements.txt` — additive change

**Analog:** `backend/requirements.txt` itself (lines 1-13)

Existing pinning style uses `>=` version specifiers. New libraries use exact pins as required by research:

```
# Add these lines (exact versions — verified on PyPI 2026-05-05):
pyjwt==2.12.1
pwdlib[argon2]==0.3.0
pytest==9.0.3
pytest-asyncio==1.3.0
httpx==0.28.1
```

---

### `tests/conftest.py` (test fixture, no existing analog)

No existing test files in the project. Use standard pytest-asyncio pattern from research:

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from db import init_db

@pytest_asyncio.fixture
async def client():
    """In-memory test app — does NOT use the real data/accountiq_learning.db."""
    # Override DB_PATH to in-memory SQLite for tests
    ...
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
```

---

### `tests/test_auth.py` and `tests/test_security.py` (test files, no existing analog)

No existing test analog. Structure should follow the requirement-to-test map from RESEARCH.md Validation Architecture section (lines 556-574). Each test function name maps directly to a requirement ID.

---

### `pytest.ini` (config, no existing analog)

```ini
[pytest]
asyncio_mode = auto
```

---

## Shared Patterns

### DB Query Pattern
**Source:** `backend/main.py` — used on every route handler
**Apply to:** All auth route handlers in `backend/auth.py`

```python
async with db.execute("SELECT ... WHERE id=?", (user_id,)) as cur:
    row = await cur.fetchone()
if not row:
    raise HTTPException(404, "Not found")
return dict(row)
```

### HTTPException Error Handling
**Source:** `backend/main.py` lines 104-107, 115-116
**Apply to:** All auth route handlers

```python
# Early guard — raise immediately, no nested try needed for simple cases:
if not user:
    raise HTTPException(401, "Invalid email or password")

# Exception wrapping for DB operations:
try:
    async with db.execute("INSERT INTO users ...") as cur:
        user_id = cur.lastrowid
    await db.commit()
except Exception as e:
    if "UNIQUE constraint" in str(e):
        raise HTTPException(409, "Email already registered")
    raise HTTPException(500, str(e))
```

### Parameterised SQL (never f-string)
**Source:** `backend/db.py` lines 160-167, `backend/main.py` lines 97-100
**Apply to:** All DB operations in `backend/auth.py`

```python
# ALWAYS use ? placeholders:
await db.execute("INSERT INTO users (email, hashed_pw) VALUES (?, ?)", (email, hashed))
# NEVER:
await db.execute(f"INSERT INTO users (email) VALUES ('{email}')")  # SQL injection
```

### aiosqlite Row-to-Dict Conversion
**Source:** `backend/main.py` lines 83-84, 116
**Apply to:** All auth DB query returns

```python
# Single row:
return dict(row)

# Multiple rows:
return [dict(r) for r in rows]
```

### `await db.commit()` After Writes
**Source:** `backend/main.py` lines 101, 179
**Apply to:** All INSERT/UPDATE in auth routes

```python
async with db.execute("INSERT INTO users ...") as cur:
    user_id = cur.lastrowid
await db.commit()  # always commit after write
```

### Frontend DOM Pattern (textContent, not innerHTML, for server data)
**Source:** `frontend/index.html` lines 370-374 (correct usages already in codebase)
**Apply to:** All new auth wall JS and all XSS fixes

```javascript
// CORRECT — for any value that originates from the server or AI:
document.getElementById('stat-companies').textContent = ov.companies;

// CORRECT — for new elements:
const span = document.createElement('span');
span.textContent = serverValue;
container.appendChild(span);

// NEVER for server data:
element.innerHTML = serverValue;
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/conftest.py` | test fixture | request-response | No tests exist in the project yet |
| `tests/test_auth.py` | test | request-response | No tests exist in the project yet |
| `tests/test_security.py` | test | request-response | No tests exist in the project yet |
| `pytest.ini` | config | — | No test infrastructure exists yet |

For these files, the planner should use the patterns from RESEARCH.md Validation Architecture section (lines 546-590) and standard pytest-asyncio + httpx `AsyncClient` patterns.

---

## Metadata

**Analog search scope:** `backend/`, `frontend/`
**Files read:** `backend/main.py` (436 lines), `backend/db.py` (189 lines), `frontend/index.html` (765 lines — targeted sections), `.planning/codebase/CONVENTIONS.md`, `backend/requirements.txt`
**Pattern extraction date:** 2026-05-05
