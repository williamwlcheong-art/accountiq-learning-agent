# Phase 3: Business Profile Intake - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can build a complete company profile capturing four sections — industry/sector, business description, management team members, and EBITDA add-back adjustments. All four sections feed directly into Phase 5 report generation prompts. Phase 3 also exposes a profile completion status that Phase 5 uses to gate report generation. This phase does not generate any reports — it only captures and stores profile data.

</domain>

<decisions>
## Implementation Decisions

### Profile data model
- **D-01:** Extend the `companies` table with a `description TEXT` column via `ALTER TABLE ... ADD COLUMN description TEXT`. Reuse the existing `sector TEXT` column for industry classification — no new column needed for industry. Follow the existing `try/except` migration pattern in `backend/db.py`.
- **D-02:** New `management_team` table: `id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE, name TEXT NOT NULL, title TEXT, bio TEXT, created_at TEXT DEFAULT (datetime('now'))`. Three user-facing fields per member: name (required), title, bio. Ownership is derived through `company_id` — no `user_id` column on this table (same as `financial_rows` / `extraction_log` from Phase 2). Routes must verify `company_id` belongs to the requesting user before touching child records.
- **D-03:** New `ebitda_adjustments` table: `id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE, label TEXT NOT NULL, amount REAL NOT NULL, rationale TEXT, created_at TEXT DEFAULT (datetime('now'))`. Three user-facing fields per line item: label (required), amount (required), rationale. Same ownership model as D-02.

### Industry taxonomy
- **D-04:** Use a custom SME-focused flat list of ~15 plain-English categories, hardcoded as a JS array in `frontend/index.html`. Single-level picker (no sub-sectors). Value stored in the existing `sector TEXT` column. Phase 5 MUST use this same list when seeding the `industry_multiples` lookup table — they must match exactly. Canonical category list:
  - Retail
  - Construction
  - Professional Services
  - Hospitality & Food Service
  - Healthcare & Medical
  - Manufacturing
  - Technology & Software
  - Agriculture & Horticulture
  - Transport & Logistics
  - Property & Real Estate
  - Wholesale & Distribution
  - Financial Services
  - Media & Communications
  - Education & Training
  - Other

### EBITDA running total
- **D-05:** The add-backs entry UI shows a full EBITDA bridge:
  - Reported EBITDA (auto-fetched from `financial_rows` for this company)
  - + Sum of add-back adjustments
  - = Normalised EBITDA
  - Uses the most recent period (`SELECT MAX(period) FROM financial_rows WHERE company_id = ? AND row_key IN ('net_profit', 'depreciation_amortisation')`) 
  - Base EBITDA = `net_profit + depreciation_amortisation` values from `financial_rows`; fall back to `net_profit` alone if `depreciation_amortisation` is not present for that period.
  - If no `financial_rows` exist yet for the company: show a "Upload financials first to see your Normalised EBITDA" placeholder — do not block the add-backs entry form itself.

### Profile completion gate
- **D-06:** A `GET /companies/{id}/profile-status` endpoint returns completion state: which of the 4 sections are complete, a percentage, and whether report generation is unblocked. Required for unblocked generation: `sector` (industry) must be set AND at least one `ebitda_adjustments` row must exist. Optional sections (description, management team) contribute to the completion percentage but do not block generation. Phase 5 calls this endpoint to gate report creation. Phase 3 must surface completion status visibly in the Companies tab UI (e.g., "2/4 sections complete" badge on the company row).

### Claude's Discretion
- **UI placement (not discussed):** Add an "Edit Profile" button on each company row in the Companies tab. Clicking it expands an inline profile section below that row (accordion pattern). The accordion shows all four profile sections. Completion badge ("2/4 sections complete") appears on the company row alongside the existing company info. This is consistent with vanilla JS tab navigation pattern and avoids adding a new tab or modal.
- **Sort ordering:** No explicit sort_order column on management_team or ebitda_adjustments — use `ORDER BY id ASC` (insertion order) for display. Add/Remove only; no drag-to-reorder needed for v1.
- **Validation:** Description minimum 50 chars enforced frontend-only (HTML `minlength` or JS check). Amount field should accept negative values (some add-backs are subtractions, e.g. removing a one-time windfall). Backend stores whatever is submitted — no server-side sign restriction.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — PROF-01 (industry/sector), PROF-02 (business description), PROF-03 (management team), PROF-04 (EBITDA add-backs)
- `.planning/ROADMAP.md` — Phase 3 goal, success criteria (6 items), and plan descriptions

### Database schema and migrations
- `backend/db.py` — current schema; the `companies` table (lines 17–26, plus Phase 2 migrations) is the base for D-01 extension. Financial_rows table (lines 48–62) is queried by the EBITDA bridge (D-05). Follow the existing `try/except ALTER TABLE` migration pattern for new columns and tables.

### API and auth patterns
- `backend/main.py` — existing CRUD patterns for companies and documents; all new profile routes must follow the same `Depends(get_current_user)` pattern and return 404 (not 403) when a resource is not found or not owned by the requesting user.
- `backend/auth.py` — `get_current_user` dependency; returns `{"id": int, "email": str, "created_at": str}`. Routes query child tables via `company_id` after verifying company ownership with `WHERE id = ? AND user_id = ?`.

### Phase context
- `.planning/phases/02-multi-user-data-isolation/02-CONTEXT.md` — Phase 2 isolation decisions: child tables (financial_rows, extraction_log) derive ownership through company_id without their own user_id column. Management_team and ebitda_adjustments should follow the same pattern (D-02, D-03).

### Code conventions
- `.planning/codebase/CONVENTIONS.md` — async DB pattern, error handling style, frontend apiFetch/apiPost helpers, CSS naming conventions
- `.planning/codebase/ARCHITECTURE.md` — data flow, table relationships, concurrency model

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_current_user` dependency in `backend/auth.py` — already on all routes; all new profile routes inject it. Verify company ownership with `WHERE id = ? AND user_id = ?` before touching child records.
- `async with aiosqlite.connect(DB_PATH) as db` pattern — all new CRUD routes for management_team and ebitda_adjustments follow this exact pattern.
- `apiFetch(path)` and `apiPost(path, formData)` in `frontend/index.html` — use these for all new profile API calls. No new HTTP helpers needed.
- Existing tab nav (`showPage()`, `.page.active`, `.nav-tab.active`) — "Edit Profile" accordion expands within the Companies tab page without needing a new tab.
- `financial_rows` table already contains `net_profit` and `depreciation_amortisation` row keys for extracted companies — the EBITDA bridge query can run immediately against existing data.

### Established Patterns
- Error handling: `raise HTTPException(404, "Company not found")` for not-found or not-owned resources (no 403 — avoids leaking existence). `raise HTTPException(409, ...)` for conflicts.
- DB insert: parameterized `?` placeholders only — no f-string SQL interpolation.
- Timestamps: `TEXT DEFAULT (datetime('now'))` — SQLite ISO format, no datetime library needed.
- Frontend rendering: `.textContent` or `.createTextNode()` for all user-supplied and AI-generated content — no `.innerHTML` for profile data (name, bio, rationale are user-entered text).
- Status badges: `class="status-{value}"` CSS pattern exists — can extend for profile completion (e.g., `class="profile-complete"` vs `class="profile-incomplete"`).

### Integration Points
- `GET /companies` response — add `sector` (already returned), `description` (new column), and profile completion summary to each company object so the Companies tab can render completion badges without an extra API call per company.
- `GET /companies/{id}/profile-status` (new) — queried by Phase 5 report generation gate and by the frontend completion badge.
- `financial_rows` table — queried by the EBITDA bridge: `SELECT row_key, value, period FROM financial_rows WHERE company_id = ? AND row_key IN ('net_profit', 'depreciation_amortisation') AND period = (SELECT MAX(period) FROM financial_rows WHERE company_id = ?)`.

</code_context>

<specifics>
## Specific Ideas

- Industry list must be a canonical constant shared between frontend and Phase 5 (backend). Consider defining it in the frontend JS and documenting the exact labels in this CONTEXT.md so Phase 5 doesn't drift. The 15 categories above (D-04) are the locked list.
- EBITDA bridge calculation note: "depreciation_amortisation" is the canonical row key used by the extractor. If the extractor surfaces it as "depreciation" only, the bridge query may need to check both. Phase 4 (Extraction Quality) may clean this up — but Phase 3's bridge should be defensive and use `IN ('depreciation_amortisation', 'depreciation')` as a fallback.
- Profile completion badge: the ROADMAP example says "3/4 sections complete". The 4 sections map to: (1) sector not null, (2) description not null and length ≥ 50, (3) at least one management_team row, (4) at least one ebitda_adjustments row.

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.

</deferred>

---

*Phase: 3-Business-Profile-Intake*
*Context gathered: 2026-05-07*
