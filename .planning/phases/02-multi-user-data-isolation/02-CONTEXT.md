# Phase 2: Multi-User Data Isolation - Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Add `user_id` ownership to `companies` and `documents` tables, filter every API route so users see only their own data, and update the UNIQUE constraint so each user has an independent company namespace. Existing rows in the DB (created pre-auth) have no owner and become invisible to all users via query filtering — they are NOT shared demo data. The `label_patterns` (pattern learning) table stays global and is not isolated. This phase does not touch the frontend beyond what is required to handle new API error responses.

</domain>

<decisions>
## Implementation Decisions

### Data ownership model
- **D-01:** All companies and documents are strictly private to the user who created them. There is no shared or demo company concept — DATA-01 as written in REQUIREMENTS.md is superseded by this decision.
- **D-02:** Existing rows in the DB (pre-auth, no user_id) become invisible after Phase 2. They are never returned by any API query. Implementation: all company/document queries include `WHERE user_id = ?` — NULL user_id rows simply drop out. No deletion required; rows remain in DB for safety.
- **D-03:** The `label_patterns` table stays global — pattern learning is cumulative across all users. No `user_id` column needed on `label_patterns`. Extraction quality benefits from every user's uploads.

### Company name uniqueness
- **D-04:** Change `UNIQUE(name, exchange)` to `UNIQUE(name, exchange, user_id)`. Each user gets their own company namespace — two different users can both create "Acme Corp / ASX" independently. Matches the multi-tenant SaaS model where users manage their own client portfolios.

### Analytics scope
- **D-05:** The `/analytics` endpoint must filter to the authenticated user's own companies only. Aggregate stats and trend data reflect only the current user's portfolio. No cross-user data leakage even in aggregate form.

### Claude's Discretion
- Migration mechanics: SQLite `ALTER TABLE ... ADD COLUMN user_id INTEGER` (nullable, no default) is the correct approach. No `NOT NULL` constraint since existing rows have no owner.
- Document access: documents are linked to companies via `company_id`. A user accessing a document must own the parent company. Both `companies` and `documents` get `user_id` columns; document `user_id` always equals the owning user's id and is set at upload time from `current_user["id"]`.
- `financial_rows` and `extraction_log` access is derived from document/company ownership — no `user_id` column needed on those tables (queries already join through company_id/document_id).
- Route filtering: use `WHERE user_id = ?` with `current_user["id"]` for all direct company/document lookups. For GET /companies, GET /documents, GET /financials — add user_id filter. For GET /companies/{id}, GET /documents/{id} — add user_id check and return 404 (not 403) if not owner, to avoid leaking existence.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Database schema
- `backend/db.py` — current SCHEMA; lines 17–46 are the `companies` and `documents` CREATE TABLE statements that need `user_id` added and `UNIQUE` constraint changed
- `backend/auth.py` — `get_current_user` dependency; returns `{"id": int, "email": str, "created_at": str}` — use `current_user["id"]` for ownership

### Routes to update
- `backend/main.py` — all API route handlers; every route that queries companies or documents needs user_id filtering added. Routes: GET/POST /companies, GET /companies/{id}, GET/POST /documents, POST /documents/upload, GET /documents/{id}/status, GET /financials/{company_id}, GET /patterns, GET /analytics, POST /analytics/retry/{id}

### Requirements
- `.planning/REQUIREMENTS.md` — AUTH-07 (user data private), DATA-01 (superseded — existing rows are invisible, not shared demo)
- `.planning/ROADMAP.md` — Phase 2 success criteria and plan descriptions

### Conventions
- `.planning/codebase/CONVENTIONS.md` — async DB pattern, error handling style
- `.planning/codebase/ARCHITECTURE.md` — data flow and table relationships

### Prior phase context
- `.planning/phases/01-security-auth-foundation/01-CONTEXT.md` — auth decisions (HTTP-only cookie, `get_current_user` Depends pattern)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_current_user` dependency in `backend/auth.py` — already injected into all 15 routes; `current_user["id"]` is the user_id to filter/assign on every operation
- `async with aiosqlite.connect(DB_PATH) as db` pattern in `backend/main.py` — all DB writes follow this; user_id assignment at INSERT time uses the same pattern

### Established Patterns
- Route parameter pattern: `current_user: dict = Depends(get_current_user)` is already on every route — Phase 2 just starts using `current_user["id"]` in the SQL
- Error handling: `raise HTTPException(404, "...")` for not-found (use 404 not 403 for missing resources to avoid leaking existence of other users' data)
- DB insert pattern: all INSERT statements already use parameterized queries — add `user_id` as an additional parameter

### Integration Points
- `POST /companies` — add `user_id = current_user["id"]` to the INSERT
- `GET /companies` — add `WHERE c.user_id = ?` to the SELECT
- `POST /documents/upload` — add `user_id` to documents INSERT (document inherits company ownership context but also stores its own user_id for direct filtering)
- `GET /analytics` — add user_id JOIN/filter on all aggregate queries

</code_context>

<specifics>
## Specific Ideas

- User's primary use case: each user independently uploads their own clients' financial statements. No cross-user visibility of any kind is expected or desired.
- Pattern learning is intentionally global — the system gets smarter with more data, benefiting all users even though their documents are private.

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.

</deferred>

---

*Phase: 2-Multi-User Data Isolation*
*Context gathered: 2026-05-06*
