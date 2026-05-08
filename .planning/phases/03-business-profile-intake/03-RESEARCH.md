# Phase 3: Business Profile Intake — Research

**Researched:** 2026-05-08
**Domain:** FastAPI CRUD extensions, SQLite schema migrations, vanilla JS accordion UI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Extend `companies` table with `description TEXT` via `ALTER TABLE ... ADD COLUMN`. Reuse existing `sector TEXT` column for industry. Follow the existing `try/except` migration pattern in `backend/db.py`.
- **D-02:** New `management_team` table: `id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE, name TEXT NOT NULL, title TEXT, bio TEXT, created_at TEXT DEFAULT (datetime('now'))`. Ownership via company_id (no user_id column). Routes verify company ownership with `WHERE id = ? AND user_id = ?`.
- **D-03:** New `ebitda_adjustments` table: `id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE, label TEXT NOT NULL, amount REAL NOT NULL, rationale TEXT, created_at TEXT DEFAULT (datetime('now'))`. Same ownership model as D-02.
- **D-04:** Flat ~15-item SME industry list hardcoded in frontend JS. Stored in existing `sector TEXT` column. Canonical list: Retail, Construction, Professional Services, Hospitality & Food Service, Healthcare & Medical, Manufacturing, Technology & Software, Agriculture & Horticulture, Transport & Logistics, Property & Real Estate, Wholesale & Distribution, Financial Services, Media & Communications, Education & Training, Other.
- **D-05:** EBITDA bridge in add-backs UI: Reported EBITDA (from `financial_rows` max period) + sum(add-backs) = Normalised EBITDA. Query: `SELECT MAX(period) FROM financial_rows WHERE company_id = ? AND row_key IN ('net_profit', 'depreciation_amortisation')`. Base EBITDA = net_profit + depreciation_amortisation; fall back to net_profit alone. If no rows: show placeholder, do not block the form.
- **D-06:** `GET /companies/{id}/profile-status` endpoint: returns which of 4 sections are complete, percentage, and unblocked flag. Required for generation: sector set AND at least one ebitda_adjustments row. Optional: description, management team. Phase 5 calls this endpoint.

### Claude's Discretion

- **UI placement:** "Edit Profile" button on each company row, expands inline accordion below the row. Completion badge ("2/4 sections complete") on the company row. Consistent with existing vanilla JS tab pattern.
- **Sort ordering:** `ORDER BY id ASC` (insertion order) for management_team and ebitda_adjustments. Add/Remove only; no drag-to-reorder.
- **Validation:** Description minimum 50 chars enforced frontend-only. Amount field accepts negative values. Backend stores whatever is submitted.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROF-01 | User can specify industry and sector for a company | D-01 (reuse `sector` column), D-04 (canonical 15-item list), `POST /companies/{id}/profile` endpoint |
| PROF-02 | User can provide a business description and overview | D-01 (`ALTER TABLE companies ADD COLUMN description TEXT`), `POST /companies/{id}/profile` endpoint |
| PROF-03 | User can enter management team details (names, titles, brief bios) | D-02 (`management_team` table + full CRUD routes), accordion sub-section |
| PROF-04 | User can enter EBITDA add-backs / owner adjustments with label and amount | D-03 (`ebitda_adjustments` table + full CRUD routes), D-05 (EBITDA bridge), D-06 (profile-status gate) |
</phase_requirements>

---

## Summary

Phase 3 adds structured profile data to the existing companies entity. The backend work is additive CRUD: one column migration, two new child tables, five new route groups (profile patch, management team CRUD, EBITDA adjustments CRUD, profile status, and EBITDA bridge data). All patterns are already established in the codebase — no new libraries are required.

The frontend work is the most substantial deliverable: an accordion panel injected as a `<tr>` beneath each company row, containing four sub-sections with live state management. The existing `apiFetch`/`apiPost` helpers, `.badge` classes, `.form-group` / `.form-grid` layout classes, and `showAlert` function are all reusable directly. The UI Spec (03-UI-SPEC.md) is fully approved and provides pixel-level detail — the executor should treat it as authoritative for all visual and copywriting decisions.

The ownership security model is identical to the Phase 2 pattern: child tables (`management_team`, `ebitda_adjustments`) carry `company_id` but no `user_id`. Every route that touches a child record must first verify `companies WHERE id = ? AND user_id = ?` to establish the ownership chain. Returning 404 (not 403) for unowned or missing resources is the established convention.

**Primary recommendation:** Implement in four sequential tasks — (1) DB migrations, (2) backend CRUD routes + profile-status endpoint, (3) companies-list integration (completion badge data), (4) frontend accordion with all four sub-sections. Tasks 1 and 2 are backend-only and can be verified with integration tests before any frontend work begins.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Industry picker + description save | API / Backend | Frontend | `PATCH`-style profile update on `companies` table; frontend sends FormData |
| Management team CRUD | API / Backend | Frontend | Child table with FK; ownership verified at API layer |
| EBITDA adjustments CRUD | API / Backend | Frontend | Child table with FK; ownership verified at API layer |
| EBITDA bridge calculation | API / Backend | — | Aggregates `financial_rows` + `ebitda_adjustments`; returned via profile-status endpoint |
| Profile completion status | API / Backend | — | Queries 4 sections server-side; gating logic not trusted to frontend |
| Accordion UI + inline forms | Browser / Client | — | Vanilla JS DOM manipulation; no server-side rendering |
| Completion badge rendering | Browser / Client | — | Reads `profile_completion` field from `GET /companies` response |
| Report generation block message | Browser / Client | API / Backend | Frontend reads profile-status; backend enforces gate at Phase 5 report creation time |

---

## Standard Stack

### Core (all already installed — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | Already installed | Route handlers for profile CRUD | Project stack |
| aiosqlite | Already installed | Async SQLite CRUD | Project stack — all DB operations must use this |
| python-dotenv | Already installed | Env config | Project stack |

### No New Dependencies

Phase 3 introduces zero new Python packages. All backend work uses the same `aiosqlite` + `FastAPI` + `Depends(get_current_user)` pattern already present. The frontend is vanilla JS with no build step. [VERIFIED: codebase inspection]

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (frontend/index.html)
    │
    │  loadCompanies() — GET /companies
    │  ← companies[] with profile_completion field (sections_complete, total)
    │
    │  toggleProfilePanel(companyId) — opens accordion
    │
    │  [Industry section]  POST /companies/{id}/profile  {sector}
    │  [Description section] POST /companies/{id}/profile {description}
    │
    │  [Mgmt Team section]
    │    GET /companies/{id}/management-team → [{id, name, title, bio}]
    │    POST /companies/{id}/management-team {name, title, bio}
    │    PUT  /companies/{id}/management-team/{member_id}
    │    DELETE /companies/{id}/management-team/{member_id}
    │
    │  [EBITDA section]
    │    GET /companies/{id}/ebitda-adjustments → [{id, label, amount, rationale}]
    │    POST /companies/{id}/ebitda-adjustments
    │    PUT  /companies/{id}/ebitda-adjustments/{adj_id}
    │    DELETE /companies/{id}/ebitda-adjustments/{adj_id}
    │    GET /companies/{id}/profile-status → {reported_ebitda, has_financials, ...}
    │
    ▼
FastAPI (backend/main.py)
    │  Depends(get_current_user) on all routes
    │  Verify company ownership: WHERE id=? AND user_id=?
    │  Then touch management_team / ebitda_adjustments via company_id
    ▼
SQLite (aiosqlite)
    companies  ←── management_team (company_id FK, CASCADE)
    companies  ←── ebitda_adjustments (company_id FK, CASCADE)
    companies  ←── financial_rows (company_id, used by EBITDA bridge)
```

### Recommended Project Structure (additions only)

```
backend/
└── main.py          # Add profile routes here (same file — project convention)

backend/
└── db.py            # Add Phase 3 migrations to _migrate_db()

frontend/
└── index.html       # Add CSS classes, accordion HTML structure, JS functions
```

No new files are needed. All additions go into existing files to maintain the project's single-file conventions.

### Pattern 1: Column Migration (D-01)

Add to `_migrate_db()` in `backend/db.py` alongside the Phase 2 migrations:

```python
# Phase 3: business profile columns
"ALTER TABLE companies ADD COLUMN description TEXT",
```

Each statement is wrapped in a try/except so re-running is idempotent. [VERIFIED: backend/db.py lines 121-132]

### Pattern 2: New Child Table Creation in `_migrate_db()`

For `management_team` and `ebitda_adjustments`, use `CREATE TABLE IF NOT EXISTS` — simpler and idempotent for new tables vs the column-alter pattern:

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
```

Call `conn.commit()` after. [ASSUMED: `CREATE TABLE IF NOT EXISTS` inside `_migrate_db` is the right place; verified by pattern in db.py SCHEMA block for similar structural tables]

### Pattern 3: Ownership Verification for Child Records

All management_team and ebitda_adjustments routes must verify ownership through the company:

```python
@app.get("/companies/{company_id}/management-team")
async def list_management_team(
    company_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Verify company ownership first
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")
    # Now safe to query child table
    async with db.execute(
        "SELECT id, name, title, bio FROM management_team WHERE company_id=? ORDER BY id ASC",
        (company_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]
```

This is the identical pattern used for documents in Phase 2. [VERIFIED: backend/main.py lines 178-185, 262-274]

### Pattern 4: Profile Patch Endpoint (sector + description)

Rather than separate endpoints for sector and description, a single `POST /companies/{id}/profile` accepts optional form fields and updates whichever are provided:

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
        await db.execute("UPDATE companies SET sector=? WHERE id=?", (sector, company_id))
    if description is not None:
        await db.execute("UPDATE companies SET description=? WHERE id=?", (description, company_id))
    await db.commit()
    # Return updated record
    async with db.execute("SELECT sector, description FROM companies WHERE id=?", (company_id,)) as cur:
        row = await cur.fetchone()
    return dict(row)
```

[VERIFIED: pattern matches existing `update_settings` style — backend/main.py lines 444-468]

### Pattern 5: Profile Status Endpoint (D-06)

```python
@app.get("/companies/{company_id}/profile-status")
async def profile_status(
    company_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute(
        "SELECT sector, description FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        company = await cur.fetchone()
    if not company:
        raise HTTPException(404, "Company not found")

    # Section 1: industry
    sector_complete = bool(company["sector"])

    # Section 2: description (min 50 chars)
    desc = company["description"] or ""
    desc_complete = len(desc.strip()) >= 50

    # Section 3: management team
    async with db.execute(
        "SELECT COUNT(*) as n FROM management_team WHERE company_id=?",
        (company_id,)
    ) as cur:
        mgmt_count = (await cur.fetchone())["n"]
    mgmt_complete = mgmt_count > 0

    # Section 4: EBITDA adjustments
    async with db.execute(
        "SELECT COUNT(*) as n FROM ebitda_adjustments WHERE company_id=?",
        (company_id,)
    ) as cur:
        adj_count = (await cur.fetchone())["n"]
    ebitda_complete = adj_count > 0

    # EBITDA bridge: reported EBITDA from financial_rows
    # Use most recent period with net_profit
    reported_ebitda = None
    has_financials = False
    async with db.execute("""
        SELECT MAX(period) as max_period FROM financial_rows
        WHERE company_id=? AND row_key IN ('net_profit', 'depreciation_amortisation')
    """, (company_id,)) as cur:
        period_row = await cur.fetchone()
    max_period = period_row["max_period"] if period_row else None
    if max_period:
        has_financials = True
        async with db.execute("""
            SELECT row_key, value FROM financial_rows
            WHERE company_id=? AND period=?
              AND row_key IN ('net_profit', 'depreciation_amortisation', 'depreciation')
        """, (company_id, max_period)) as cur:
            fin_rows = {r["row_key"]: r["value"] for r in await cur.fetchall()}
        net_profit = fin_rows.get("net_profit") or 0
        da = fin_rows.get("depreciation_amortisation") or fin_rows.get("depreciation") or 0
        reported_ebitda = net_profit + da

    sections_complete = sum([sector_complete, desc_complete, mgmt_complete, ebitda_complete])
    can_generate = sector_complete and ebitda_complete

    return {
        "sections_complete": sections_complete,
        "total": 4,
        "sector_complete": sector_complete,
        "description_complete": desc_complete,
        "management_complete": mgmt_complete,
        "ebitda_complete": ebitda_complete,
        "can_generate": can_generate,
        "reported_ebitda": reported_ebitda,
        "has_financials": has_financials,
    }
```

[VERIFIED: logic sourced from D-05, D-06, and CONTEXT.md specifics section]

### Pattern 6: `GET /companies` Response Enrichment

The existing `list_companies` query must be extended to include `description` and a `profile_completion` summary so the Companies tab can render badges without extra calls per row.

The current query uses `SELECT c.*` — since `description` will be added as a column, it will automatically appear in `c.*` once the migration runs. The `profile_completion` summary requires either a subquery join or a separate pass. The most readable approach for this codebase is a subquery in the SELECT:

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

[ASSUMED: correlated subqueries in SQLite SELECT are legal and performant for small N — no index concern for typical SME user with < 50 companies]

### Pattern 7: Frontend Accordion Injection

The accordion `<tr>` is injected immediately after each company row in `loadCompanies()`. The panel toggle function:

```javascript
function toggleProfilePanel(companyId) {
  // Close all other panels first
  document.querySelectorAll('.profile-panel').forEach(p => {
    if (p.dataset.companyId != companyId) p.classList.remove('open');
  });
  const panel = document.getElementById(`profile-panel-${companyId}`);
  const isOpen = panel.classList.toggle('open');
  if (isOpen) loadProfilePanel(companyId);
}
```

`loadProfilePanel(companyId)` performs `GET /companies/{id}/management-team`, `GET /companies/{id}/ebitda-adjustments`, and uses the already-loaded company data from the `data` array (sector, description, sections_complete) to pre-populate forms. [VERIFIED: apiFetch pattern confirmed in frontend/index.html lines 1037-1044]

### Anti-Patterns to Avoid

- **Using `.innerHTML` for user content:** All name, title, bio, label, rationale values must use `.textContent` or `document.createTextNode()`. This is a hard CLAUDE.md requirement. [VERIFIED: CLAUDE.md, 03-UI-SPEC.md accessibility contracts]
- **Trusting frontend completion state:** The profile-status endpoint must independently compute completion — the frontend badge is display-only. Phase 5 will call the endpoint, not trust frontend state.
- **Using `f""` string interpolation in SQL:** All SQL must use `?` parameterized placeholders. [VERIFIED: CONVENTIONS.md, main.py throughout]
- **Returning 403 for unowned resources:** Return 404 for any company not found or not owned — avoids leaking resource existence. [VERIFIED: main.py pattern, CONTEXT.md code context section]
- **Putting `user_id` on child tables:** management_team and ebitda_adjustments use company_id-based ownership only. [VERIFIED: D-02, D-03]
- **Calling `db.execute` without `PRAGMA foreign_keys=ON`:** The `get_db` dependency already sets this per connection. Background tasks that open their own connection also need it — see `_run_ingestion` pattern. [VERIFIED: db.py get_db(), main.py _run_ingestion()]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Auth dependency | Custom token parser per route | `Depends(get_current_user)` | Already implemented in auth.py; middleware validates JWT from cookie |
| Async DB connection | Synchronous sqlite3 calls | `async with aiosqlite.connect(DB_PATH) as db` | Blocking calls in async routes stall the event loop |
| Schema migration | A migration framework | `try/except` ALTER TABLE in `_migrate_db()` | Established project pattern; SQLite doesn't need Alembic for 1-2 column changes |
| Amount formatting (negative) | Custom formatter | `.toLocaleString()` with parentheses pattern | Already in `numCell` helper in Financials tab (frontend/index.html line ~916) |
| Success alert dismissal | Custom timer | `showAlert()` helper (already auto-dismisses after 5s on non-error) | VERIFIED: frontend/index.html lines 1056-1065 |

**Key insight:** Every new pattern in Phase 3 has an exact existing analogue in the codebase. No new abstractions are needed.

---

## Common Pitfalls

### Pitfall 1: `fresh_all_db` Fixture Missing New Tables

**What goes wrong:** Integration tests using `fresh_all_db` truncate a hardcoded list of tables. After Phase 3 adds `management_team` and `ebitda_adjustments`, the fixture leaves stale rows between test runs if these tables are not included.

**Why it happens:** `fresh_all_db` in `tests/conftest.py` lists tables explicitly: `["financial_rows", "extraction_log", "documents", "companies", "users"]`. New child tables are not automatically included.

**How to avoid:** Add `"management_team"` and `"ebitda_adjustments"` to the deletion list in `fresh_all_db`, before `"companies"` (FK ordering — children first). [VERIFIED: tests/conftest.py lines 79-89]

**Warning signs:** Tests that create companies in one test affect assertion counts in a subsequent test.

### Pitfall 2: `GET /companies` Query Breaks on Missing Tables

**What goes wrong:** If the enriched `list_companies` query references `management_team` and `ebitda_adjustments` before `_migrate_db` runs (e.g., on a fresh DB where schema runs but migration hasn't added the tables yet), the query fails with "no such table".

**Why it happens:** `executescript(SCHEMA)` runs first and creates only the original 6 tables. `_migrate_db` runs after and creates the two new tables. If the SELECT in `list_companies` uses correlated subqueries referencing these tables, they must exist before the route is called.

**How to avoid:** Ensure `CREATE TABLE IF NOT EXISTS` for both tables runs in `_migrate_db()` during `init_db()` at startup — before any request can be processed. The FastAPI `@app.on_event("startup")` already calls `init_db()` synchronously. [VERIFIED: main.py lines 60-63]

### Pitfall 3: EBITDA Bridge Shows Wrong Value After Add-Back Edit

**What goes wrong:** The bridge shows a stale Reported EBITDA total after a user edits an existing add-back, because the bridge fetches its data separately from the add-backs list refresh.

**Why it happens:** The bridge reads `reported_ebitda` from `GET /companies/{id}/profile-status`, while the add-backs list reads from `GET /companies/{id}/ebitda-adjustments`. If only one endpoint is re-fetched, the bridge falls out of sync.

**How to avoid:** On every successful add, edit, or remove of an add-back, re-fetch both `GET /companies/{id}/ebitda-adjustments` (list) AND `GET /companies/{id}/profile-status` (bridge data) before re-rendering the bridge. [VERIFIED: 03-UI-SPEC.md Component 6, bridge update spec]

### Pitfall 4: `sector` Pre-Population Fails for Legacy Free-Text Values

**What goes wrong:** Existing companies in the DB may have arbitrary free-text in `sector` (typed when creating the company via the old "Sector" text input). When the accordion opens and tries to pre-select the industry dropdown, `select.value = company.sector` silently no-ops if the value isn't in the option list.

**Why it happens:** The old Add Company form had a free-text `<input id="co-sector">`. Some companies may have "Aviation", "Tech", or blank values.

**How to avoid:** After setting `select.value`, check `if (select.value === '') { /* show hint to user to select industry */ }`. The UI spec already covers this: "If the existing sector value does not match any option (legacy free-text), it falls back to `""` (no selection, user prompted to re-save)." No backend change needed. [VERIFIED: 03-UI-SPEC.md Component 3]

### Pitfall 5: DELETE returning 204 breaks `apiPost` helper

**What goes wrong:** The existing `apiPost` helper calls `res.json()` unconditionally. A DELETE that returns 204 No Content has no body — calling `.json()` throws a parse error.

**Why it happens:** `apiPost` was written for POST operations that always return a JSON body. DELETE endpoints conventionally return 204.

**How to avoid:** For remove operations (member delete, adjustment delete), use a raw `fetch()` call with `method: 'DELETE'` and `credentials: 'include'`, checking `res.ok` rather than parsing a body. Do not use `apiPost` for DELETE. Or add a dedicated `apiDelete(path)` helper following the same auth-redirect pattern as `apiFetch`. [ASSUMED: apiPost is not suitable for DELETE — verified by reading its implementation at lines 1046-1054]

### Pitfall 6: `description` Column Missing from `GET /companies/{id}` Response

**What goes wrong:** The single-company GET (`GET /companies/{company_id}`) uses `SELECT *` — but only after `_migrate_db` adds the column. If the column doesn't exist in schema at schema creation time, `*` won't include it on a fresh DB created before `_migrate_db`.

**Why it happens:** The `SCHEMA` constant uses `CREATE TABLE IF NOT EXISTS` for the original companies table definition. `ALTER TABLE ... ADD COLUMN description` is in `_migrate_db`. On a fresh install, `init_db()` runs both in sequence, so the column will be present. But automated tests that reinitialise the DB in-process may see the old schema if `_migrate_db` is not called.

**How to avoid:** `init_db()` always calls `_migrate_db(conn)` — confirm the test fixture calls `_db_module.init_db()`. [VERIFIED: tests/conftest.py line 43 calls `_db_module.init_db()`]

---

## Code Examples

Verified patterns from the existing codebase:

### Ownership verification (from main.py documents upload pattern)
```python
# Source: backend/main.py lines 178-185
async with db.execute(
    "SELECT id, exchange FROM companies WHERE id=? AND user_id=?",
    (company_id, current_user["id"])
) as cur:
    company = await cur.fetchone()
if not company:
    raise HTTPException(404, f"Company {company_id} not found.")
```

### showAlert (non-error auto-dismiss after 5s)
```javascript
// Source: frontend/index.html lines 1056-1065
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

### Number formatting (negative in red parens — matches EBITDA bridge requirement)
```javascript
// Source: frontend/index.html ~line 916 (numCell helper)
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

### Migration try/except pattern (from db.py)
```python
# Source: backend/db.py lines 122-132
for sql in [
    "ALTER TABLE documents ADD COLUMN narrative TEXT",
    "ALTER TABLE documents ADD COLUMN reporting_standard TEXT DEFAULT 'UNKNOWN'",
    "ALTER TABLE companies ADD COLUMN user_id INTEGER",
    "ALTER TABLE documents ADD COLUMN user_id INTEGER",
]:
    try:
        conn.execute(sql)
    except sqlite3.OperationalError:
        pass  # column already exists
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Free-text sector input on Add Company form | Dropdown picker from canonical 15-item list (Phase 3) | Phase 3 | Legacy free-text values in DB need UI fallback handling |
| No profile data on companies | sector + description + management team + add-backs (Phase 3) | Phase 3 | `GET /companies` response gains `sections_complete` field; report gen gated by profile status |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `CREATE TABLE IF NOT EXISTS` inside `_migrate_db()` is the correct pattern for new tables (vs adding to SCHEMA) | Architecture Patterns, Pattern 2 | Tables might not exist on app startup if SCHEMA is the only place checked; but _migrate_db always runs after SCHEMA, so risk is low |
| A2 | Correlated subqueries in the `GET /companies` SELECT are performant for typical SME user (< 50 companies) | Architecture Patterns, Pattern 6 | Could be slow for large datasets; SQLite handles small N well |
| A3 | `apiPost` must not be used for DELETE (no body — `.json()` would throw) | Common Pitfalls, Pitfall 5 | If FastAPI returns a JSON body on DELETE, `apiPost` would work — but 204 No Content is the REST standard and what the UI spec specifies |

---

## Open Questions

1. **`DELETE /companies/{id}/management-team/{member_id}` — should it return 204 or `{"ok": true}`?**
   - What we know: The UI spec says DELETE returns 204 No Content. The existing `doLogout()` endpoint in auth.py returns `{"ok": True}`.
   - What's unclear: Whether the executor should prefer consistency with logout (returning JSON) over REST convention (204).
   - Recommendation: Return 204 No Content for DELETE operations (REST convention). Use a dedicated `apiDelete` helper in the frontend that doesn't call `.json()`.

2. **EBITDA bridge: `depreciation` vs `depreciation_amortisation` key**
   - What we know: CONTEXT.md specifics note that the extractor may surface "depreciation" without "_amortisation" on some documents. The bridge query should use `IN ('depreciation_amortisation', 'depreciation')`.
   - What's unclear: Whether `financial_rows` in the current DB actually has any rows with key `depreciation` alone (Phase 4 will clean this up).
   - Recommendation: Use `IN ('depreciation_amortisation', 'depreciation')` in the MAX(period) query and the bridge fetch — defensive coding costs nothing and prevents silent zero values.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python / FastAPI / aiosqlite | All backend routes | Yes | Existing install | — |
| SQLite DB at `data/accountiq_learning.db` | All DB operations | Yes | Existing | — |
| `pytest` / `pytest-asyncio` / `httpx` | Integration tests | Yes | `pytest.ini` present, `conftest.py` exists | — |

No missing dependencies. [VERIFIED: pytest.ini, tests/conftest.py, backend/db.py confirmed present]

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio |
| Config file | `/Users/William.Cheong/accountiq_learning/pytest.ini` (asyncio_mode = auto, testpaths = tests) |
| Quick run command | `cd /Users/William.Cheong/accountiq_learning && source venv/bin/activate && pytest tests/test_profile.py -x -q` |
| Full suite command | `cd /Users/William.Cheong/accountiq_learning && source venv/bin/activate && pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROF-01 | Save sector to company via POST /companies/{id}/profile | integration | `pytest tests/test_profile.py::test_save_industry -x` | Wave 0 |
| PROF-01 | Unowned company returns 404 on profile save | integration | `pytest tests/test_profile.py::test_profile_ownership_403 -x` | Wave 0 |
| PROF-02 | Save description >= 50 chars | integration | `pytest tests/test_profile.py::test_save_description -x` | Wave 0 |
| PROF-03 | Add management team member; list returns it | integration | `pytest tests/test_profile.py::test_management_team_crud -x` | Wave 0 |
| PROF-03 | Remove member via DELETE; confirm 404 on re-fetch | integration | `pytest tests/test_profile.py::test_management_team_delete -x` | Wave 0 |
| PROF-04 | Add EBITDA adjustment; list returns it | integration | `pytest tests/test_profile.py::test_ebitda_adjustments_crud -x` | Wave 0 |
| PROF-04 | profile-status returns ebitda_complete=true after first adjustment | integration | `pytest tests/test_profile.py::test_profile_status_gate -x` | Wave 0 |
| PROF-04 (D-06) | profile-status can_generate=false when sector null or no adjustments | integration | `pytest tests/test_profile.py::test_profile_status_blocked -x` | Wave 0 |
| PROF-04 (D-05) | reported_ebitda in profile-status when financial_rows exist | integration | `pytest tests/test_profile.py::test_ebitda_bridge_calculation -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_profile.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_profile.py` — covers PROF-01 through PROF-04 and D-05/D-06 logic (all rows above marked "Wave 0")
- [ ] `tests/conftest.py` — update `fresh_all_db` to include `management_team` and `ebitda_adjustments` in deletion list (before `companies`)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `Depends(get_current_user)` on all new routes |
| V3 Session Management | no | JWT cookie already handled by Phase 1 |
| V4 Access Control | yes | Ownership verified: `WHERE id=? AND user_id=?` before touching child records; 404 not 403 |
| V5 Input Validation | yes | Description length check (frontend); required fields (name, label, amount) enforced at API via `Form(...)` not-null |
| V6 Cryptography | no | No new crypto in this phase |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR on management_team/ebitda_adjustments | Elevation of Privilege | Verify company ownership with `WHERE id=? AND user_id=?` before all child table operations |
| XSS via user-entered name/bio/label in frontend | Tampering | All user content rendered via `.textContent` / `document.createTextNode()` — never `.innerHTML` |
| SQL injection via form fields | Tampering | All queries use `?` parameterized placeholders — never f-string interpolation |
| Path traversal | Tampering | Not applicable to this phase (no file uploads) |

---

## Sources

### Primary (HIGH confidence)

- `backend/db.py` — schema, migration pattern, DB_PATH, `_migrate_db()` implementation verified by direct read
- `backend/main.py` — route structure, ownership verification pattern, `Depends(get_current_user)` usage, all CRUD patterns verified by direct read
- `backend/auth.py` — `get_current_user` dependency return shape `{"id": int, "email": str, "created_at": str}` verified by direct read
- `frontend/index.html` — `apiFetch`, `apiPost`, `showAlert`, `numCell`, badge classes, form structure — verified by direct read
- `.planning/phases/03-business-profile-intake/03-CONTEXT.md` — all locked decisions verified
- `.planning/phases/03-business-profile-intake/03-UI-SPEC.md` — approved visual/interaction contract verified
- `.planning/codebase/CONVENTIONS.md` — naming, async, DB, frontend patterns verified
- `.planning/codebase/ARCHITECTURE.md` — ownership model, concurrency, data flow verified
- `tests/conftest.py` — `fresh_all_db` fixture table list verified (missing new tables identified as pitfall)

### Secondary (MEDIUM confidence)

- `.planning/REQUIREMENTS.md` — PROF-01 through PROF-04 requirements confirmed in scope
- `.planning/ROADMAP.md` — Phase 3 success criteria cross-checked against CONTEXT.md decisions

### Tertiary (LOW confidence)

None — all claims sourced from direct codebase inspection or official locked decisions.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed; no new dependencies
- Architecture: HIGH — patterns directly sourced from existing backend/main.py and db.py
- Pitfalls: HIGH — sourced from direct code reading (conftest.py fixture gap, apiPost DELETE issue, legacy sector values)
- UI patterns: HIGH — sourced from 03-UI-SPEC.md (approved) and frontend/index.html direct read

**Research date:** 2026-05-08
**Valid until:** 2026-06-08 (stable stack — FastAPI, aiosqlite, vanilla JS)
