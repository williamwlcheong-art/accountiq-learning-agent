# Phase 3: Business Profile Intake - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 3 (backend/db.py, backend/main.py, frontend/index.html) — all modifications, no new files
**Analogs found:** 3 / 3

---

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------|------|-----------|----------------|---------------|
| `backend/db.py` | migration | batch (schema init) | `backend/db.py` `_migrate_db()` lines 120–197 | exact (self-analog — extend the same function) |
| `backend/main.py` | controller | CRUD request-response | `backend/main.py` documents upload + company GET patterns | exact |
| `frontend/index.html` | component + utility | request-response (DOM) | `frontend/index.html` `loadCompanies()`, `addCompany()`, `apiPost`, `apiFetch`, `showAlert` | exact |
| `tests/test_profile.py` | test | request-response | `tests/test_isolation.py` | role-match |
| `tests/conftest.py` | config | batch | `tests/conftest.py` `fresh_all_db` fixture | exact (self-analog — extend existing fixture) |

---

## Pattern Assignments

---

### `backend/db.py` — Phase 3 Migration Block

**Analog:** `backend/db.py` `_migrate_db()` lines 120–197

**Existing migration try/except pattern** (lines 122–132):
```python
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
```

**What to add for Phase 3** — append to the same `for sql in [...]` list:
```python
    "ALTER TABLE companies ADD COLUMN description TEXT",
```

**New-table creation pattern** (after the for-loop, before `conn.commit()`) — use `CREATE TABLE IF NOT EXISTS` directly on `conn` (not executescript, which issues an implicit COMMIT):
```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS management_team (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id  INTEGER REFERENCES companies(id) ON DELETE CASCADE,
        name        TEXT NOT NULL,
        title       TEXT,
        bio         TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    )
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS ebitda_adjustments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id  INTEGER REFERENCES companies(id) ON DELETE CASCADE,
        label       TEXT NOT NULL,
        amount      REAL NOT NULL,
        rationale   TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    )
""")
conn.commit()   # already present at end of _migrate_db — do not add a second call
```

**Existing `conn.commit()` at end of `_migrate_db`** (line 197):
```python
conn.commit()
```
The new `CREATE TABLE IF NOT EXISTS` blocks must be inserted **before** this final commit.

---

### `backend/main.py` — Profile CRUD Routes

**Primary analog:** `backend/main.py` — documents upload route (ownership verification), `list_companies` (SELECT pattern), `update_settings` (optional Form fields).

---

#### Route 1: `GET /companies` — add `description` + `sections_complete` to list query

**Analog** (lines 79–93 — existing `list_companies`):
```python
@app.get("/companies")
async def list_companies(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute("""
        SELECT c.*, COUNT(d.id) as doc_count
        FROM companies c
        LEFT JOIN documents d ON d.company_id = c.id
        WHERE c.user_id = ?
        GROUP BY c.id
        ORDER BY c.name
    """, (current_user["id"],)) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]
```

**Replace the SELECT string with** (adds `sections_complete` subquery — `description` appears automatically once the column migration runs because `c.*` is already there):
```sql
SELECT c.*,
       COUNT(DISTINCT d.id) as doc_count,
       (CASE WHEN c.sector IS NOT NULL AND c.sector != '' THEN 1 ELSE 0 END
        + CASE WHEN c.description IS NOT NULL AND LENGTH(TRIM(c.description)) >= 50 THEN 1 ELSE 0 END
        + CASE WHEN (SELECT COUNT(*) FROM management_team mt WHERE mt.company_id = c.id) > 0 THEN 1 ELSE 0 END
        + CASE WHEN (SELECT COUNT(*) FROM ebitda_adjustments ea WHERE ea.company_id = c.id) > 0 THEN 1 ELSE 0 END
       ) as sections_complete
FROM companies c
LEFT JOIN documents d ON d.company_id = c.id
WHERE c.user_id = ?
GROUP BY c.id
ORDER BY c.name
```

---

#### Route 2: `POST /companies/{company_id}/profile` — patch sector + description

**Analog:** `POST /settings` (lines 444–469) — optional Form fields, mutate only provided ones; and ownership verification from upload route (lines 178–185).

**Imports pattern** (already at top of `main.py` lines 1–25 — no new imports needed):
```python
from typing import Optional
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends, BackgroundTasks
import aiosqlite
from auth import auth_router, get_current_user
```

**Full route pattern** (copy ownership-verify then conditional UPDATE):
```python
@app.post("/companies/{company_id}/profile")
async def update_company_profile(
    company_id: int,
    sector: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")
    if sector is not None:
        await db.execute(
            "UPDATE companies SET sector=? WHERE id=?",
            (sector, company_id)
        )
    if description is not None:
        await db.execute(
            "UPDATE companies SET description=? WHERE id=?",
            (description, company_id)
        )
    await db.commit()
    async with db.execute(
        "SELECT sector, description FROM companies WHERE id=?",
        (company_id,)
    ) as cur:
        row = await cur.fetchone()
    return dict(row)
```

---

#### Routes 3–5: `GET/POST/DELETE /companies/{company_id}/management-team` — child-table CRUD

**Analog:** `GET /documents/{document_id}/rows` (lines 262–282) for ownership-then-child-query pattern; `POST /companies` (lines 96–117) for INSERT + lastrowid + `await db.commit()`.

**Ownership verification pattern** (lines 268–274 — copy this for ALL management-team and ebitda-adjustments routes):
```python
async with db.execute(
    "SELECT id FROM companies WHERE id=? AND user_id=?",
    (company_id, current_user["id"])
) as cur:
    if not await cur.fetchone():
        raise HTTPException(404, "Company not found")
```

**List route pattern** (after ownership check):
```python
@app.get("/companies/{company_id}/management-team")
async def list_management_team(
    company_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # ownership check here (see above)
    async with db.execute(
        "SELECT id, name, title, bio FROM management_team WHERE company_id=? ORDER BY id ASC",
        (company_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]
```

**Create route pattern** (mirrors `create_company` lines 96–117):
```python
@app.post("/companies/{company_id}/management-team", status_code=201)
async def add_management_team_member(
    company_id: int,
    name: str = Form(...),
    title: str = Form(None),
    bio: str = Form(None),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # ownership check here (see above)
    async with db.execute(
        "INSERT INTO management_team (company_id, name, title, bio) VALUES (?, ?, ?, ?)",
        (company_id, name, title, bio)
    ) as cur:
        member_id = cur.lastrowid
    await db.commit()
    return {"id": member_id, "name": name, "title": title, "bio": bio}
```

**Delete route pattern** (return 204, no body):
```python
@app.delete("/companies/{company_id}/management-team/{member_id}", status_code=204)
async def delete_management_team_member(
    company_id: int,
    member_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # ownership check here (see above)
    await db.execute(
        "DELETE FROM management_team WHERE id=? AND company_id=?",
        (member_id, company_id)
    )
    await db.commit()
    return Response(status_code=204)
```

**Same three routes apply identically to `ebitda_adjustments`**, replacing `management_team` with `ebitda_adjustments` and `(name, title, bio)` with `(label, amount, rationale)`. Amount uses `float = Form(...)` (required, accepts negative).

---

#### Route 6: `GET /companies/{company_id}/profile-status`

**Analog:** `GET /analytics/overview` (lines 367–407) — multiple sequential `async with db.execute(...)` blocks aggregating into a single returned dict.

**Error handling pattern** (from `get_company` lines 120–133):
```python
async with db.execute(
    "SELECT * FROM companies WHERE id=? AND user_id=?",
    (company_id, current_user["id"])
) as cur:
    row = await cur.fetchone()
if not row:
    raise HTTPException(404, "Company not found")
```

**COUNT subquery pattern** (from `analytics_overview` lines 372–376):
```python
async with db.execute(
    "SELECT COUNT(*) as n FROM companies WHERE user_id=?",
    (current_user["id"],)
) as cur:
    companies = (await cur.fetchone())["n"]
```

**Full profile-status route** — combine ownership check + four COUNT subqueries + EBITDA bridge query into a single response dict. The dict keys are: `sections_complete`, `total`, `sector_complete`, `description_complete`, `management_complete`, `ebitda_complete`, `can_generate`, `reported_ebitda`, `has_financials`. (Full implementation is in RESEARCH.md Pattern 5 — use it verbatim.)

---

### `frontend/index.html` — Accordion UI + Profile JS Functions

**Primary analogs:** `loadCompanies()` (lines 527–579), `addCompany()` (lines 586–601), `apiFetch` (lines 1037–1044), `apiPost` (lines 1046–1054), `showAlert` (lines 1056–1065), `numCell` (lines 916–930), badge CSS classes (lines 54–60).

---

#### CSS additions (append to `<style>` block, after line 115)

**Accordion panel pattern** — extend modal-overlay/modal approach (lines 90–95) for inline row expansion:
```css
/* Profile accordion */
.profile-panel-row { display: none; }
.profile-panel-row.open { display: table-row; }
.profile-panel-td { padding: 0; border-bottom: 2px solid var(--border); }
.profile-panel-inner { padding: 1.5rem 1rem; background: var(--card); }
.profile-section { margin-bottom: 1.5rem; }
.profile-section-title {
  font-size: .8rem; font-weight: 600; color: var(--muted);
  text-transform: uppercase; letter-spacing: .04em; margin-bottom: .75rem;
}
/* Completion badge variants */
.badge-profile-complete { background: #e8f5e9; color: var(--green); }
.badge-profile-partial  { background: #fff8e1; color: var(--amber); }
.badge-profile-empty    { background: #f5f5f5; color: var(--muted); }
/* EBITDA bridge table */
.ebitda-bridge { width: 100%; border-collapse: collapse; font-size: .85rem; margin-top: .75rem; }
.ebitda-bridge td { padding: 4px 8px; border-bottom: 1px solid var(--border); }
.ebitda-bridge .bridge-total td { font-weight: 700; color: var(--blue); border-top: 2px solid var(--border); }
```

---

#### `loadCompanies()` modification

**Analog:** existing `loadCompanies()` lines 527–579 — DOM-builder pattern using `document.createElement` + `.textContent`.

**Pattern to follow for completion badge** (reuse existing badge creation lines 546–555):
```javascript
// Existing pattern — copy for completion badge
const exBadge = document.createElement('span');
exBadge.className = 'badge badge-listed';
exBadge.textContent = c.exchange;
tdEx.appendChild(exBadge);
```

**New completion badge** — add after sector td, before actions td:
```javascript
const tdProfile = document.createElement('td');
const profileBadge = document.createElement('span');
const sc = c.sections_complete || 0;
profileBadge.className = sc === 4 ? 'badge badge-profile-complete'
                        : sc > 0  ? 'badge badge-profile-partial'
                        :           'badge badge-profile-empty';
profileBadge.textContent = `${sc}/4 complete`;
tdProfile.appendChild(profileBadge);
tr.appendChild(tdProfile);
```

**Edit Profile button** — add alongside existing "Upload PDF" button in `tdAct`:
```javascript
const editBtn = document.createElement('button');
editBtn.className = 'btn btn-sm btn-primary';
editBtn.textContent = 'Edit Profile';
editBtn.onclick = () => toggleProfilePanel(c.id);
tdAct.appendChild(editBtn);
```

**Accordion row injection** — append after `tbody.appendChild(tr)`:
```javascript
const panelRow = document.createElement('tr');
panelRow.id = `profile-panel-${c.id}`;
panelRow.className = 'profile-panel-row';
panelRow.dataset.companyId = c.id;
const panelTd = document.createElement('td');
panelTd.colSpan = 8;   // adjust colspan to match total column count after badge column added
panelTd.className = 'profile-panel-td';
panelTd.id = `profile-panel-td-${c.id}`;
panelRow.appendChild(panelTd);
tbody.appendChild(panelRow);
```

---

#### New JS function: `toggleProfilePanel(companyId)`

**Analog:** `toggleAddCompany()` (lines 581–584) — toggle display of a hidden element.

```javascript
function toggleProfilePanel(companyId) {
  // Close all other panels first
  document.querySelectorAll('.profile-panel-row').forEach(p => {
    if (parseInt(p.dataset.companyId) !== companyId) {
      p.classList.remove('open');
    }
  });
  const row = document.getElementById(`profile-panel-${companyId}`);
  const isOpen = row.classList.toggle('open');
  if (isOpen) loadProfilePanel(companyId);
}
```

---

#### New JS function: `loadProfilePanel(companyId)`

**Analog:** `loadCompanies()` pattern — `apiFetch` call, null-guard, then DOM build via createElement + textContent.

```javascript
async function loadProfilePanel(companyId) {
  const td = document.getElementById(`profile-panel-td-${companyId}`);
  // Fetch child data in parallel
  const [members, adjs, status] = await Promise.all([
    apiFetch(`/companies/${companyId}/management-team`),
    apiFetch(`/companies/${companyId}/ebitda-adjustments`),
    apiFetch(`/companies/${companyId}/profile-status`),
  ]);
  if (!members || !adjs || !status) return;
  // Build panel HTML via DOM (never innerHTML for user data)
  // ... see section renders below
}
```

---

#### Save functions: `saveProfile(companyId)`, `addMember(companyId)`, `removeMember(companyId, memberId)`, `addAdjustment(companyId)`, `removeAdjustment(companyId, adjId)`

**Analog for POST calls:** `addCompany()` lines 586–601 — build FormData, call `apiPost`, check result, show alert, reload.

```javascript
async function saveProfile(companyId) {
  const fd = new FormData();
  fd.append('sector', document.getElementById(`sector-${companyId}`).value);
  fd.append('description', document.getElementById(`desc-${companyId}`).value);
  const res = await apiPost(`/companies/${companyId}/profile`, fd);
  if (res) {
    showAlert(`profile-alert-${companyId}`, 'Profile saved.', 'success');
    loadCompanies();  // refresh badge count on company row
  }
}
```

**Analog for DELETE calls:** `apiPost` must NOT be used for DELETE (returns 204 No Content — `.json()` would throw). Use a dedicated `apiDelete` helper following the `apiFetch` credential pattern:

```javascript
async function apiDelete(path) {
  try {
    const res = await fetch(API + path, { method: 'DELETE', credentials: 'include' });
    if (res.status === 401) { showAuthWall(true); return false; }
    return res.ok;
  } catch(e) { console.error(e); return false; }
}
```

**Remove member call** (after `apiDelete`, reload the panel section):
```javascript
async function removeMember(companyId, memberId) {
  const ok = await apiDelete(`/companies/${companyId}/management-team/${memberId}`);
  if (ok) loadProfilePanel(companyId);  // re-render the full panel
}
```

---

#### Number formatting in EBITDA bridge

**Analog:** `numCell` helper (lines 916–930) — inline cell builder with red parens for negatives:
```javascript
const numCell = v => {
  const td = document.createElement('td');
  td.style.textAlign = 'right';
  if (v == null) {
    td.textContent = '—';
  } else if (v < 0) {
    const span = document.createElement('span');
    span.style.color = 'var(--red)';
    span.textContent = `(${Math.abs(v).toLocaleString()})`;
    td.appendChild(span);
  } else {
    td.textContent = v.toLocaleString();
  }
  return td;
};
```

Use this exact helper (or a local copy in the bridge render function) for Reported EBITDA, adjustment amounts, and Normalised EBITDA values in the bridge table.

---

#### Alert pattern for per-section feedback

**Analog:** `showAlert` (lines 1056–1065) — takes a container ID, message, and type:
```javascript
function showAlert(containerId, msg, type) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '';
  const div = document.createElement('div');
  div.className = `alert alert-${type}`;
  div.textContent = msg;
  el.appendChild(div);
  if (type !== 'error') setTimeout(() => { el.innerHTML = ''; }, 5000);
}
```

Each profile section needs its own alert container div with a unique ID (`profile-alert-{companyId}`, `mgmt-alert-{companyId}`, `ebitda-alert-{companyId}`) so alerts don't overwrite each other.

---

### `tests/test_profile.py` — New Test File

**Analog:** `tests/test_isolation.py` (lines 1–100+) — pytest-asyncio, `AsyncClient`, helper functions for register + create resources, then assert on status codes and response bodies.

**Imports pattern** (from `test_isolation.py` lines 1–12):
```python
"""Tests for Phase 3: Business Profile Intake (PROF-01 through PROF-04, D-05, D-06)."""
import pytest
from httpx import AsyncClient, ASGITransport
```

**Helper pattern** (from `test_isolation.py` lines 18–27):
```python
async def _register(client, email, password="correcthorse"):
    r = await client.post("/auth/register", data={"email": email, "password": password})
    assert r.status_code in (200, 201), f"Register failed for {email!r}: {r.text}"
    return r

async def _create_company(client, name, exchange="Private"):
    r = await client.post("/companies", data={"name": name, "exchange": exchange})
    assert r.status_code == 200, f"Create company failed: {r.text}"
    return r.json()["id"]
```

**Test function structure** (from `test_isolation.py` lines 44–65):
```python
async def test_save_industry(client, fresh_all_db):
    """PROF-01: sector saved to company via POST /companies/{id}/profile."""
    await _register(client, "alice@test.com")
    cid = await _create_company(client, "Test Co")
    r = await client.post(f"/companies/{cid}/profile", data={"sector": "Technology & Software"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sector"] == "Technology & Software"
```

**Ownership 404 pattern**:
```python
async def test_profile_ownership_403(client, fresh_all_db):
    """PROF-01: unowned company returns 404 (not 403) on profile save."""
    await _register(client, "owner@test.com")
    cid = await _create_company(client, "Owner Co")
    import main as _main_module
    async with AsyncClient(
        transport=ASGITransport(app=_main_module.app), base_url="http://test"
    ) as other:
        await other.post("/auth/register", data={"email": "other@test.com", "password": "correcthorse"})
        r = await other.post(f"/companies/{cid}/profile", data={"sector": "Retail"})
        assert r.status_code == 404, r.text
```

---

### `tests/conftest.py` — Update `fresh_all_db` Fixture

**Analog:** `tests/conftest.py` `fresh_all_db` fixture (lines 70–90) — extend the deletion list to include new child tables before `companies`.

**Current list** (line 81):
```python
for table in ["financial_rows", "extraction_log", "documents", "companies", "users"]:
```

**Replace with** (management_team and ebitda_adjustments before companies — FK ordering):
```python
for table in ["financial_rows", "extraction_log", "management_team", "ebitda_adjustments", "documents", "companies", "users"]:
```

---

## Shared Patterns

### Authentication (apply to ALL new routes in main.py)

**Source:** `backend/auth.py` lines 73–96; used in every route via `Depends(get_current_user)`

```python
current_user: dict = Depends(get_current_user)
# Returns: {"id": int, "email": str, "created_at": str}
```

All new routes inject this dependency. The JWT is read from the `accountiq_session` HTTP-only cookie automatically.

### Ownership Verification (apply to ALL routes touching management_team / ebitda_adjustments)

**Source:** `backend/main.py` lines 178–185 (documents upload route):
```python
async with db.execute(
    "SELECT id, exchange FROM companies WHERE id=? AND user_id=?",
    (company_id, current_user["id"])
) as cur:
    company = await cur.fetchone()
if not company:
    raise HTTPException(404, f"Company {company_id} not found.")
```

For Phase 3 child-table routes, use the simplified form (no `exchange` needed):
```python
async with db.execute(
    "SELECT id FROM companies WHERE id=? AND user_id=?",
    (company_id, current_user["id"])
) as cur:
    if not await cur.fetchone():
        raise HTTPException(404, "Company not found")
```

Return 404 (not 403) for unowned or missing resources — avoids leaking existence.

### Async DB Pattern (apply to ALL new backend routes)

**Source:** `backend/db.py` lines 111–117:
```python
async def get_db() -> aiosqlite.Connection:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db
```

All DB reads use `async with db.execute(...) as cur: rows = await cur.fetchall()` or `row = await cur.fetchone()`. Writes always follow with `await db.commit()`.

### SQL Parameterization (apply to ALL SQL in main.py and test helpers)

**Source:** throughout `backend/main.py` (e.g., lines 107–110):
```python
async with db.execute("""
    INSERT INTO companies (name, ticker, exchange, sector, country, user_id)
    VALUES (?, ?, ?, ?, ?, ?)
""", (name, ticker, exchange, sector, country, current_user["id"])) as cur:
```

Never use f-string interpolation in SQL. Always use `?` placeholder tuples.

### Error Handling — HTTPException conventions

**Source:** `backend/main.py` lines 114–117 (UNIQUE conflict), lines 132–133 (not found):
```python
# Not found / not owned:
raise HTTPException(404, "Company not found")

# Conflict:
if "UNIQUE constraint" in str(e):
    raise HTTPException(409, f"Company '{name}' on {exchange} already exists.")

# Server error (fallthrough):
raise HTTPException(500, str(e))
```

### Frontend XSS Prevention (apply to ALL user-supplied content in index.html)

**Source:** `frontend/index.html` lines 1097–1104 (narrative modal) and throughout `loadCompanies()`:
```javascript
// CORRECT — use textContent for all user-entered or AI-generated text
const strong = document.createElement('strong');
strong.textContent = c.name;   // c.name is user-supplied

// WRONG — never use innerHTML for user content
element.innerHTML = userInputVariable;  // XSS risk
```

For profile data specifically: `name`, `title`, `bio`, `label`, `rationale` are all user-entered text — always render with `.textContent` or `document.createTextNode()`.

### Badge CSS Pattern (apply to profile completion badge in index.html)

**Source:** `frontend/index.html` lines 54–60 (existing badge classes):
```css
.badge{display:inline-block;padding:.2rem .6rem;border-radius:12px;font-size:.72rem;font-weight:600}
.badge-done{background:#e8f5e9;color:var(--green)}
.badge-pending{background:#fff8e1;color:var(--amber)}
```

New Phase 3 badge classes follow the same naming convention — prefix `badge-profile-`:
```css
.badge-profile-complete { background: #e8f5e9; color: var(--green); }
.badge-profile-partial  { background: #fff8e1; color: var(--amber); }
.badge-profile-empty    { background: #f5f5f5; color: var(--muted); }
```

### Form CSS Pattern (apply to profile section forms in index.html)

**Source:** `frontend/index.html` lines 36–41 (form-group, form-grid):
```css
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
.form-group{display:flex;flex-direction:column;gap:.4rem}
label{font-size:.8rem;font-weight:600;color:var(--muted)}
input,select,textarea{padding:.5rem .75rem;border:1px solid var(--border);border-radius:6px;font-size:.9rem;width:100%}
```

Use `.form-group` for every label+input pair in profile sections. Use `.form-grid` for 2-column layouts (name + title in management team; label + amount in EBITDA add-backs).

---

## No Analog Found

None. All Phase 3 patterns have exact analogs in the existing codebase.

---

## Metadata

**Analog search scope:** `backend/db.py`, `backend/main.py`, `backend/auth.py`, `frontend/index.html`, `tests/conftest.py`, `tests/test_isolation.py`
**Files scanned:** 6
**Pattern extraction date:** 2026-05-08
