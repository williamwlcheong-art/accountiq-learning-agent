# Phase 3.5: Admin Gate + User Wizard Shell — Research

**Researched:** 2026-05-12
**Domain:** FastAPI dependency injection, SQLite migrations, vanilla JS auth branching, multi-step wizard UI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** `ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0` via `try/except` (established migration pattern).
- **D-02:** On registration, if `email.lower() == OWNER_EMAIL.lower()` (from `.env`), set `is_admin = 1`. All others default to `0`. If OWNER_EMAIL is unset, no auto-admin.
- **D-03:** `GET /auth/me` returns `{id, email, is_admin, created_at}`. Extend `get_current_user` to also SELECT `is_admin` from DB.
- **D-04:** All existing routes under `/companies/*`, `/documents/*`, `/financials/*`, `/patterns/*`, `/analytics/*`, `/settings/*` become admin-only. A `require_admin` dependency raises `HTTPException(403, "Admin access required")` for non-admins.
- **D-05:** `/wizard/*` routes are NOT admin-gated — authenticated non-admin users' entry point.
- **D-06:** `POST /wizard/upload` accepts `FormData {business_name, file}`. Creates company + uploads doc atomically, reusing `_run_ingestion`. Returns `{company_id, document_id, status}`.
- **D-07:** Wizard step 1: "Business name *" (text) + "Upload financials *" (file), single Continue button. Calls `POST /wizard/upload`.
- **D-08:** `checkAuth()` / `initApp()` branches on `is_admin` after `/auth/me`: `false` → show `#wizard-page`, hide nav/tabs; `true` → existing tab UI unchanged.
- **D-09:** Reuse existing CSS variables and component classes — no new CSS tokens.
- **D-10:** Step 2 = 5 report type selectable cards; Step 3 = static confirmation with user email. Report generation deferred to Phase 5.

### Claude's Discretion
- **Wizard step ordering:** Step 1 upload, Step 2 report type, Step 3 confirmation — fixed.
- **403 vs 404:** Use 403 (not 404) for admin-gated routes called by non-admins.
- **No back-button state management** in v1. A "Back" text button within wizard is sufficient.
- **`/wizard/upload` ingestion:** Reuse `_run_ingestion` background task exactly — no separate wizard ingestion path.

### Deferred Ideas (OUT OF SCOPE)
- None — scope was kept tight. Report generation, email delivery, payment gating are Phase 5/6.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-09 | Admin role: `is_admin` column on users, set by OWNER_EMAIL, guarded by `require_admin` dependency on all existing routes | DB migration pattern verified; FastAPI router-level dependency pattern verified against FastAPI 0.136.0 |
| UX-01 | User wizard shell: 3-step wizard (upload → report type → confirmation) shown to non-admin users after login | Existing `initApp()` / `showMainApp()` extension pattern identified; CSS reuse confirmed |
</phase_requirements>

---

## Summary

This phase bifurcates the AccountIQ UI based on role. The backend changes are precise: one migration column, one new dependency function, one new router, and extensions to two existing functions (`get_current_user`, `register`). The frontend changes are equally targeted: extend `initApp()` to branch on `is_admin`, inject a `#wizard-page` div for non-admin users, and hide the nav tabs.

The codebase is in clean shape. All 37 existing tests pass. The migration pattern (`try/except ALTER TABLE`) is already established and used in Phases 2 and 3. FastAPI's router-level `dependencies=[]` parameter is the right mechanism for applying `require_admin` to every route in a router in one line — no per-route changes needed. The `_run_ingestion` background task already accepts the exact parameters that `/wizard/upload` will provide.

The primary implementation risk is the `require_admin` dependency chain: it must call `get_current_user` internally (not be an independent auth check), so that a 401 (no session) is still returned for unauthenticated callers rather than being silently transformed to a 403.

**Primary recommendation:** Apply `require_admin` at the router level via `dependencies=[Depends(require_admin)]` on each existing APIRouter (or on individual route functions that are not yet router-grouped). Do not gate `/health`, `/auth/*`, or `/wizard/*`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `is_admin` persistence | Database / Storage | — | Column on `users` table; set once at registration |
| Admin role assignment (OWNER_EMAIL) | API / Backend | — | Registration endpoint owns this logic |
| Route authorization (403 gate) | API / Backend | — | `require_admin` FastAPI dependency on existing routers |
| `/wizard/upload` ingestion | API / Backend | — | Reuses existing `_run_ingestion` background task |
| Auth branching (is_admin check) | Frontend (JS) | — | `initApp()` reads `/auth/me`, branches on `is_admin` |
| Wizard UI (3 steps) | Frontend (JS/HTML) | — | Vanilla JS/HTML in `frontend/index.html` |

---

## Standard Stack

### Core (all already installed — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.136.0 | Router-level dependencies, HTTPException | Already in use [VERIFIED: pip show fastapi] |
| aiosqlite | (existing) | Async SQLite for `is_admin` SELECT | Established DB pattern |
| python-dotenv | (existing) | Load `OWNER_EMAIL` from `.env` | Established env pattern |
| pytest-asyncio | (existing) | Async test framework | All existing tests use it |
| httpx | (existing) | AsyncClient for integration tests | Used in all existing tests |

No new packages are required for this phase. [VERIFIED: codebase inspection]

**Installation:** None required.

---

## Architecture Patterns

### System Architecture Diagram

```
POST /auth/register
  → check email == OWNER_EMAIL → is_admin = 1 or 0
  → INSERT users (is_admin)
  → set session cookie

GET /auth/me (extended)
  → SELECT id, email, is_admin, created_at FROM users
  → return {id, email, is_admin, created_at}

initApp() [frontend]
  → GET /auth/me
  → is_admin = true  → showMainApp() (existing tabs, unchanged)
  → is_admin = false → showWizard() (hide nav, show #wizard-page)

POST /wizard/upload [new, authenticated, NOT admin-gated]
  → Depends(get_current_user) — 401 if no session
  → INSERT companies (name=business_name, user_id=current_user.id)
  → INSERT documents (company_id, filename, filepath, user_id=current_user.id)
  → BackgroundTasks.add_task(_run_ingestion, ...)
  → return {company_id, document_id, status: "processing"}

GET/POST /companies/* (all existing admin routes)
  → Depends(require_admin) → calls get_current_user internally
    → 401 if no session
    → 403 if is_admin = 0
    → proceed if is_admin = 1
```

### Recommended Project Structure

No new files are introduced for the DB migration or dependency. One new file for the wizard router is cleaner than extending `main.py`:

```
backend/
├── auth.py          # extend: get_current_user returns is_admin; register checks OWNER_EMAIL; new require_admin dep
├── main.py          # extend: add require_admin to existing route dependencies; include wizard_router
├── wizard.py        # new: wizard_router with POST /wizard/upload
└── db.py            # extend: _migrate_db adds is_admin column

frontend/
└── index.html       # extend: initApp() → branch on is_admin; add #wizard-page div + 3-step JS
```

### Pattern 1: Router-Level Dependency (require_admin on existing routes)

**What:** FastAPI allows `dependencies=[Depends(fn)]` on `APIRouter` creation and on individual route decorators. When placed on the router, every route in that router runs the dependency.

**When to use:** When all routes in a file/router share the same authorization requirement.

**The problem in this codebase:** All existing routes are on `app` directly (not on sub-routers). This means `require_admin` must be added as a second `Depends` parameter on each existing route function, or the routes must be moved into sub-routers.

**Confirmed pattern from codebase inspection:** [VERIFIED: backend/main.py, all existing routes use `Depends(get_current_user)` inline, not via a router-level `dependencies=[]`]

```python
# Option A: Per-route dependency (matches existing code style — least refactor)
@app.get("/companies")
async def list_companies(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),   # replaces get_current_user
):
    ...

# require_admin in auth.py:
async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Return user if admin, else 403."""
    if not current_user.get("is_admin"):
        raise HTTPException(403, "Admin access required")
    return current_user
```

**Why Option A is correct here:** The existing routes already declare `current_user: dict = Depends(get_current_user)`. Replacing `get_current_user` with `require_admin` in each route signature is a mechanical one-liner change per route. Since `require_admin` calls `get_current_user` internally, there is no DB query duplication — FastAPI caches dependency results within a single request.

**Option B (sub-router):** Move existing routes to `APIRouter(dependencies=[Depends(require_admin)])` and `app.include_router(admin_router)`. This is cleaner architecturally but requires restructuring all existing routes. Given this is a running application with 37 passing tests, Option A is lower risk. [ASSUMED: Option A is preferred — confirm with planner if refactor is acceptable]

**Key safety constraint:** `require_admin` MUST call `Depends(get_current_user)` internally. If it were to replicate JWT decoding, it would bypass the 401 path for unauthenticated callers and turn all unauthenticated requests into 403s. The dependency chain must be: no cookie → 401 (from `get_current_user`), valid cookie + non-admin → 403 (from `require_admin`), valid cookie + admin → proceed. [VERIFIED: FastAPI dependency chaining behavior confirmed by codebase pattern]

### Pattern 2: SQLite `NOT NULL DEFAULT` on ALTER TABLE

**What:** SQLite allows `ALTER TABLE ... ADD COLUMN` with `NOT NULL DEFAULT value` when a default is supplied. The default fills all existing rows immediately.

**Confirmed behavior:** [VERIFIED: SQLite documentation behavior; codebase uses this pattern for `ADD COLUMN user_id INTEGER` (nullable) in Phase 2 and `ADD COLUMN description TEXT` in Phase 3]

```python
# In _migrate_db() in db.py — add to the existing loop:
"ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0",
```

This is safe: all existing users get `is_admin = 0`. The column constraint `NOT NULL DEFAULT 0` is enforced by SQLite for subsequent inserts that do not specify `is_admin`. [VERIFIED: SQLite ALTER TABLE docs + existing migration pattern in db.py lines 122-134]

**No table-rename needed:** Unlike the `companies` UNIQUE constraint migration in Phase 2 (which required a full table-rename pattern), adding `is_admin` is a simple `ALTER TABLE ADD COLUMN`. SQLite supports `NOT NULL DEFAULT` on ADD COLUMN since SQLite 3.37.0; the runtime Python 3.13 / macOS SQLite is well above this version.

### Pattern 3: OWNER_EMAIL check at registration

**What:** At startup, `OWNER_EMAIL` is loaded from `.env`. In the `register` route, after INSERT, if the new user's email matches `OWNER_EMAIL`, run an UPDATE to set `is_admin = 1`.

**Pattern from codebase:** `os.getenv("OWNER_EMAIL", "")` matches the existing pattern for `ANTHROPIC_API_KEY` and `SECRET_KEY` loading in `auth.py`. [VERIFIED: backend/auth.py lines 23-28; backend/main.py ENV_PATH pattern]

```python
# In auth.py module scope:
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "").strip().lower()

# In register() after the INSERT/commit:
if OWNER_EMAIL and email == OWNER_EMAIL:
    await db.execute(
        "UPDATE users SET is_admin = 1 WHERE id = ?", (user_id,)
    )
    await db.commit()
```

**Why UPDATE after INSERT (not INSERT with is_admin):** The INSERT SQL uses `(email, hashed_pw)` — adding `is_admin` to the INSERT is cleaner, but the UPDATE approach keeps the INSERT consistent with the default column behavior and makes the OWNER_EMAIL logic easy to read and test in isolation. Either works; the UPDATE approach is slightly more explicit. [ASSUMED: prefer UPDATE-after-INSERT for clarity — either approach is valid]

### Pattern 4: `get_current_user` extension for `is_admin`

**Current query (auth.py line 90-92):**
```python
async with db.execute(
    "SELECT id, email, created_at FROM users WHERE id=?", (user_id,)
) as cur:
```

**Extended query:**
```python
async with db.execute(
    "SELECT id, email, is_admin, created_at FROM users WHERE id=?", (user_id,)
) as cur:
```

The returned `dict(user)` will then include `is_admin`. Because `aiosqlite.Row` mirrors `sqlite3.Row`, the dict conversion picks up all selected columns automatically. The `/auth/me` route already returns `current_user` directly — no change needed there once `get_current_user` returns `is_admin`. [VERIFIED: backend/auth.py lines 90-96, 173-175]

### Pattern 5: Frontend auth branching (`initApp` extension)

**Current `initApp()` (frontend/index.html lines 2145-2157):**
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

**Extended pattern:**
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

`showWizard(user)` hides `#main-app`, shows `#wizard-page`, and displays the user email in the nav (for the Sign Out button). The wizard state machine (currentStep, selectedReportType, uploadResult) lives in module-scope JS variables — no framework needed. [VERIFIED: frontend/index.html `initApp` lines 2145-2157; `showMainApp` lines 1999-2011]

### Pattern 6: `POST /wizard/upload` implementation

The wizard upload creates a company and document in the same request, then hands off to `_run_ingestion`. The key insight from the existing `/documents/upload` route is that `_run_ingestion` takes `(document_id, company_id, filepath, entity_type, exchange, fiscal_year_end)` — all of which the wizard endpoint can supply.

```python
# backend/wizard.py
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, HTTPException
import aiosqlite
from pathlib import Path
from auth import get_current_user
from db import get_db, DB_PATH
from main import _run_ingestion, PDF_DIR   # reuse existing helpers

wizard_router = APIRouter(prefix="/wizard", tags=["wizard"])

@wizard_router.post("/upload", status_code=201)
async def wizard_upload(
    background_tasks: BackgroundTasks,
    business_name: str = Form(...),
    file: UploadFile = File(...),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),   # NOT require_admin
):
    suffix = Path(file.filename).suffix.lower()
    allowed = {".pdf", ".xlsx", ".xls", ".xlsm"}
    if suffix not in allowed:
        raise HTTPException(400, f"Only PDF and Excel files are accepted. Got: {suffix}")

    name = business_name.strip()
    if not name:
        raise HTTPException(400, "Business name is required")

    # Create company (or reuse existing by name for this user)
    async with db.execute(
        "SELECT id FROM companies WHERE lower(name)=lower(?) AND user_id=?",
        (name, current_user["id"])
    ) as cur:
        existing = await cur.fetchone()
    if existing:
        company_id = existing["id"]
    else:
        async with db.execute(
            "INSERT INTO companies (name, exchange, user_id) VALUES (?, 'Private', ?)",
            (name, current_user["id"])
        ) as cur:
            company_id = cur.lastrowid
        await db.commit()

    # Save file
    company_dir = PDF_DIR / str(company_id)
    company_dir.mkdir(exist_ok=True)
    safe_name = Path(file.filename).name
    dest = company_dir / safe_name
    with open(dest, "wb") as f:
        import shutil
        shutil.copyfileobj(file.file, f)

    # Insert document
    async with db.execute(
        "INSERT INTO documents (company_id, filename, filepath, report_type, entity_type, user_id) "
        "VALUES (?, ?, ?, 'compilation', 'sme', ?)",
        (company_id, safe_name, str(dest), current_user["id"])
    ) as cur:
        document_id = cur.lastrowid
    await db.commit()

    background_tasks.add_task(
        _run_ingestion, document_id, company_id, str(dest), "sme", "Private", ""
    )

    return {"company_id": company_id, "document_id": document_id, "status": "processing"}
```

**Import concern:** `_run_ingestion` and `PDF_DIR` are defined in `main.py`. Importing from `main.py` into `wizard.py` creates a circular import because `main.py` will `include_router(wizard_router)` from `wizard.py`. The resolution: move `_run_ingestion` and `PDF_DIR` to a shared helper module (e.g., `ingestion_tasks.py`), or inline `_run_ingestion` logic in `wizard.py`, or define the wizard router directly in `main.py`. [VERIFIED: circular import risk confirmed by reading import chain in main.py lines 25-26]

**Recommended resolution:** Define `wizard_router` and `wizard_upload` directly in `main.py`, below the existing routes, to avoid the circular import entirely. This is consistent with the existing pattern (all routes are currently in `main.py`). [ASSUMED: inline in main.py preferred — the phase can instead create wizard.py only if _run_ingestion is extracted first]

### Anti-Patterns to Avoid

- **Independent auth in `require_admin`:** Do not re-decode the JWT in `require_admin`. Call `Depends(get_current_user)` to get the user, then check `is_admin`. Bypassing this causes unauthenticated requests to receive 403 instead of 401.
- **Applying admin gate to `/health`, `/auth/*`, `/wizard/*`:** These must remain public (health) or authenticated-but-not-admin-gated (auth, wizard). Gating them would break login and wizard flows.
- **Frontend-only admin gate:** Never rely solely on `is_admin` check in JS to restrict access. The backend 403 gate is the authoritative enforcement. The JS branching is for UX only.
- **`innerHTML` in wizard UI:** The existing XSS rule applies. All user-supplied values (email, business_name, etc.) must be set via `.textContent`, never `.innerHTML`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dependency chaining | Custom JWT decode in `require_admin` | `Depends(get_current_user)` | FastAPI caches deps per request; avoids 401/403 confusion |
| DB migration | Migration framework | `try/except ALTER TABLE` | Already established; no new dep needed |
| Role storage | Separate `roles` table | `is_admin INTEGER` on `users` | Only two roles in v1; join overhead not warranted |
| Wizard state | localStorage / sessionStorage | JS module-scope variables | No persistence needed; cleared on page reload |

---

## Common Pitfalls

### Pitfall 1: Circular import when splitting wizard into `wizard.py`

**What goes wrong:** `wizard.py` imports `_run_ingestion` from `main.py`; `main.py` imports `wizard_router` from `wizard.py`. Python raises `ImportError: cannot import name`.

**Why it happens:** The background task helper lives in `main.py` alongside the app, creating a circular dependency.

**How to avoid:** Keep wizard route defined in `main.py` directly, OR extract `_run_ingestion` and `PDF_DIR` into a new `tasks.py` module that neither `main.py` nor `wizard.py` imports from the other.

**Warning signs:** `ImportError` at startup mentioning `wizard` or `main`.

### Pitfall 2: `require_admin` applied to auth or wizard routes

**What goes wrong:** Login, register, logout, or `/wizard/upload` return 403 for non-admin users.

**Why it happens:** Developer applies `require_admin` too broadly (e.g., to all routes on `app`, or forgets to exclude `/auth/*` and `/wizard/*`).

**How to avoid:** Apply `require_admin` only to the specific route function parameters of the existing admin-facing routes. Verify in tests that `POST /wizard/upload` returns 201 (not 403) for a non-admin user.

**Warning signs:** Integration test for wizard upload fails with 403; login/register fails for new users.

### Pitfall 3: `is_admin` not returned by `get_current_user` → `None` in `require_admin`

**What goes wrong:** `current_user.get("is_admin")` returns `None` for all users after migration, so `require_admin` always 403s even for the admin user.

**Why it happens:** Developer adds `is_admin` to the migration but forgets to add it to the `SELECT` in `get_current_user`.

**How to avoid:** The `SELECT` query in `get_current_user` must explicitly include `is_admin`: `SELECT id, email, is_admin, created_at FROM users WHERE id=?`. `dict(user)` will then include it.

**Warning signs:** Admin user receives 403 on all existing routes; `/auth/me` returns `{}` without `is_admin` field.

### Pitfall 4: OWNER_EMAIL comparison case-sensitivity

**What goes wrong:** Admin user registers with `Owner@Example.com` but `OWNER_EMAIL` in `.env` is `owner@example.com`. The comparison fails and they get `is_admin = 0`.

**Why it happens:** The `register` route already lowercases the submitted email (`email = email.strip().lower()`), but `OWNER_EMAIL` is read from `.env` without lowercasing.

**How to avoid:** Lowercase `OWNER_EMAIL` at load time: `OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "").strip().lower()`. The register route already lowercases the submitted email, so comparison is then `email == OWNER_EMAIL` (both lowercase).

**Warning signs:** Admin user sees wizard instead of full UI on first login.

### Pitfall 5: `fresh_db` fixture doesn't truncate users + is_admin for admin gate tests

**What goes wrong:** Test that registers OWNER_EMAIL user bleeds `is_admin = 1` into next test via shared DB.

**Why it happens:** `fresh_db` only truncates `users`; but the test DB is module-scoped. Since `fresh_db` truncates `users`, this is actually handled — the risk is if tests share a single registered user across tests using cookies.

**How to avoid:** Admin gate tests that need to verify 403 behavior should use `fresh_all_db` and register separate users per test. The `_register_admin` helper should set `OWNER_EMAIL` env var before calling register. [VERIFIED: conftest.py fresh_db and fresh_all_db patterns reviewed]

---

## Code Examples

### `require_admin` dependency

```python
# backend/auth.py — add after get_current_user
async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Require is_admin=1; raises 403 for regular users, 401 for unauthenticated."""
    if not current_user.get("is_admin"):
        raise HTTPException(403, "Admin access required")
    return current_user
```

[VERIFIED: pattern matches FastAPI 0.136.0 Depends chaining; codebase convention for HTTPException detail as string]

### Applying `require_admin` to an existing route

Before (example):
```python
@app.get("/companies")
async def list_companies(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
```

After:
```python
@app.get("/companies")
async def list_companies(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),   # replaces get_current_user
):
```

[VERIFIED: all existing routes in backend/main.py follow this exact signature pattern]

### `_migrate_db` addition

```python
# In the existing for loop at db.py line 122:
"ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0",
```

[VERIFIED: existing loop pattern in db.py lines 122-134]

### Wizard step state machine (JS)

```javascript
// Module-scope state
let wizardStep = 1;
let wizardUploadResult = null;   // {company_id, document_id, status}
let wizardReportType = null;     // string

function showWizard(user) {
  document.getElementById('main-app').style.display = 'none';
  document.getElementById('wizard-page').style.display = 'block';
  // Show user email in wizard header for sign-out
  document.getElementById('wizard-user-email').textContent = user.email;
  renderWizardStep(1);
}

function renderWizardStep(step) {
  wizardStep = step;
  document.querySelectorAll('.wizard-step').forEach(el => {
    el.style.display = el.dataset.step == step ? 'block' : 'none';
  });
  // Update "Step N of 3" indicator
  const ind = document.getElementById('wizard-step-indicator');
  if (ind) ind.textContent = `Step ${step} of 3`;
}
```

[VERIFIED: matches `showMainApp` / `showAuthWall` patterns in index.html lines 1999-2011, 1973-1997]

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No role system | `is_admin` column on users | This phase | Bifurcates UI; admin routes 403 for regular users |
| Single UI experience | Admin UI + wizard shell | This phase | Regular users get clean 3-step wizard |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Option A (per-route dependency swap) preferred over sub-router refactor | Architecture Patterns Pattern 1 | If planner prefers sub-router, tasks must include moving routes to APIRouter; higher refactor scope |
| A2 | UPDATE-after-INSERT approach preferred for OWNER_EMAIL is_admin assignment | Pattern 3 | INSERT-with-is_admin is equally valid; either works; no correctness risk |
| A3 | Wizard router defined inline in main.py (not wizard.py) to avoid circular import | Pattern 6 | If planner creates wizard.py, tasks must include extracting _run_ingestion to tasks.py |

---

## Open Questions (RESOLVED)

1. **Circular import resolution preference** — RESOLVED: inline wizard route in `main.py`. No new file. Revisit in Phase 5.

2. **Wizard upload: entity_type and fiscal_year_end defaults** — RESOLVED: hardcode `entity_type="sme"`, `fiscal_year_end=""` for Phase 3.5. Phase 5 adds intake questions.

---

## Environment Availability

All dependencies are already installed. No new tools required.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| FastAPI | require_admin dependency | ✓ | 0.136.0 | — |
| aiosqlite | is_admin DB reads | ✓ | (existing) | — |
| pytest / pytest-asyncio | Admin gate tests | ✓ | 9.0.3 / (existing) | — |
| httpx AsyncClient | Integration tests | ✓ | (existing) | — |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio |
| Config file | `pytest.ini` (asyncio_mode = auto, testpaths = tests) |
| Quick run command | `pytest tests/test_admin_gate.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-09 | `is_admin=1` set on registration when email == OWNER_EMAIL | unit | `pytest tests/test_admin_gate.py::test_owner_email_gets_admin -x` | ❌ Wave 0 |
| AUTH-09 | `is_admin=0` for all other registrations | unit | `pytest tests/test_admin_gate.py::test_regular_user_not_admin -x` | ❌ Wave 0 |
| AUTH-09 | `/auth/me` returns `is_admin` field | unit | `pytest tests/test_admin_gate.py::test_me_returns_is_admin -x` | ❌ Wave 0 |
| AUTH-09 | Non-admin GET /companies returns 403 | integration | `pytest tests/test_admin_gate.py::test_regular_user_companies_403 -x` | ❌ Wave 0 |
| AUTH-09 | Non-admin GET /financials/{id} returns 403 | integration | `pytest tests/test_admin_gate.py::test_regular_user_financials_403 -x` | ❌ Wave 0 |
| AUTH-09 | Non-admin GET /patterns returns 403 | integration | `pytest tests/test_admin_gate.py::test_regular_user_patterns_403 -x` | ❌ Wave 0 |
| AUTH-09 | Non-admin GET /settings returns 403 | integration | `pytest tests/test_admin_gate.py::test_regular_user_settings_403 -x` | ❌ Wave 0 |
| AUTH-09 | Admin user passes 403 gate on all existing routes | integration | `pytest tests/test_admin_gate.py::test_admin_user_companies_200 -x` | ❌ Wave 0 |
| AUTH-09 | Unauthenticated call returns 401 (not 403) on admin-gated routes | integration | `pytest tests/test_admin_gate.py::test_unauthenticated_returns_401_not_403 -x` | ❌ Wave 0 |
| UX-01 | POST /wizard/upload creates company + document for non-admin | integration | `pytest tests/test_admin_gate.py::test_wizard_upload_creates_company_and_document -x` | ❌ Wave 0 |
| UX-01 | POST /wizard/upload requires authentication (401 if no cookie) | integration | `pytest tests/test_admin_gate.py::test_wizard_upload_requires_auth -x` | ❌ Wave 0 |
| UX-01 | POST /wizard/upload is NOT admin-gated (non-admin gets 201) | integration | `pytest tests/test_admin_gate.py::test_wizard_upload_not_admin_gated -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_admin_gate.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green (`pytest tests/ -q`, currently 37 passed) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_admin_gate.py` — covers AUTH-09 and UX-01 (12 test stubs above)
- [ ] `tests/conftest.py` update — add `_register_admin(client, fresh_db)` helper that sets `OWNER_EMAIL` env var before calling register

*(Existing test infrastructure covers conftest.py, fresh_db, fresh_all_db — only the new test file and admin helper are needed)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing JWT HttpOnly cookie — unchanged |
| V3 Session Management | yes | Existing 7-day expiry — unchanged |
| V4 Access Control | yes | `require_admin` dependency — 403 for non-admin callers |
| V5 Input Validation | yes | `business_name` stripped; `file.filename` sanitized via `Path(file.filename).name` (existing pattern) |
| V6 Cryptography | no | No new crypto in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Role escalation (regular user calls admin route) | Elevation of Privilege | `require_admin` dependency on every admin route — 403 enforced server-side |
| Privilege bypass (OWNER_EMAIL env var not set) | Elevation of Privilege | Code check: `if OWNER_EMAIL and email == OWNER_EMAIL` — no match if OWNER_EMAIL is empty |
| Path traversal in wizard file upload | Tampering | `Path(file.filename).name` — established project convention (Phase 1 fix, AUTH-02) |
| XSS via wizard user input rendered in confirmation | Tampering | `.textContent` / `createTextNode` — project XSS rule (AUTH-03) |
| Admin route existence disclosure | Information Disclosure | 403 (not 404) is deliberate — documented exception to Phase 2 policy; admin route existence is not sensitive |

---

## Sources

### Primary (HIGH confidence)
- `backend/auth.py` — `get_current_user` implementation, existing `me` route, register route, cookie pattern [VERIFIED: direct codebase read]
- `backend/db.py` — `users` table schema, `_migrate_db` migration loop, `ALTER TABLE ADD COLUMN` pattern [VERIFIED: direct codebase read]
- `backend/main.py` — all existing route signatures, `_run_ingestion` background task signature, `PDF_DIR`, `_resolve_or_create_company` pattern [VERIFIED: direct codebase read]
- `frontend/index.html` — `initApp()`, `showMainApp()`, `showAuthWall()`, `apiFetch`, `apiPost`, CSS tokens, nav/page structure [VERIFIED: direct codebase read]
- `tests/conftest.py` — `client`, `fresh_db`, `fresh_all_db` fixtures, DB patching pattern [VERIFIED: direct codebase read]
- `tests/test_auth.py` — test style, helper function pattern (`_register`, `_login`) [VERIFIED: direct codebase read]
- `pytest.ini` — `asyncio_mode = auto`, `testpaths = tests` [VERIFIED: direct codebase read]

### Secondary (MEDIUM confidence)
- FastAPI 0.136.0 `Depends` chaining behavior — confirmed by existing multi-dependency route signatures in `main.py` (e.g., `Depends(get_db)` + `Depends(get_current_user)` on same route)

### Tertiary (LOW confidence — none)
No low-confidence claims remain. All claims are grounded in direct codebase inspection or established FastAPI dependency mechanics observable from existing code.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all existing
- Architecture: HIGH — verified against actual code in main.py, auth.py, db.py, index.html
- Pitfalls: HIGH — circular import risk verified by reading import chain; OWNER_EMAIL case issue verified by reading register code; is_admin SELECT gap verified by reading get_current_user

**Research date:** 2026-05-12
**Valid until:** 2026-07-12 (stable stack; 60-day validity)
