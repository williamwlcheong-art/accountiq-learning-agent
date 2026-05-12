# Phase 3.5: Admin Gate + User Wizard Shell - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Split the application into two experiences on the same codebase. Users with `is_admin = true` (set automatically for `OWNER_EMAIL` on first registration) see the full existing UI unchanged. All other users see a clean 3-step wizard: (1) enter business name + upload financials, (2) select report type, (3) confirmation / "we'll email you". Admin-only routes return 403 for non-admin callers. A new `/wizard/*` route namespace handles non-admin uploads without exposing admin API surface.

</domain>

<decisions>
## Implementation Decisions

### Admin role model
- **D-01:** Add `is_admin INTEGER NOT NULL DEFAULT 0` column to the `users` table via `ALTER TABLE ... ADD COLUMN` with `try/except` (established migration pattern). Boolean stored as SQLite integer (0/1).
- **D-02:** On registration, if the submitted email (lowercased) matches `OWNER_EMAIL` from `.env`, set `is_admin = 1`. All other registrations default to `is_admin = 0`. OWNER_EMAIL is loaded via python-dotenv at startup; if unset, no account auto-receives admin — first registration is still a regular user.
- **D-03:** Add `GET /auth/me` route to the auth router. Returns `{id, email, is_admin, created_at}`. Frontend calls this on load (after existing auth wall) to determine which UI to render. The existing `get_current_user` dependency returns `{id, email, created_at}` — extend it to also return `is_admin` so all protected routes can check admin status.

### Admin gate (backend)
- **D-04:** All existing API routes under `/companies/*`, `/documents/*`, `/financials/*`, `/patterns/*`, `/analytics/*`, and `/settings/*` become admin-only. Add a `require_admin` FastAPI dependency (built on top of `get_current_user`) that raises `HTTPException(403, "Admin access required")` for non-admin callers. Apply via `Depends(require_admin)` on each router.
- **D-05:** The new `/wizard/*` routes are NOT admin-gated — they are the designated entry point for regular users. A regular user calling any existing admin route still gets a 403.

### Wizard upload route
- **D-06:** New `POST /wizard/upload` endpoint accepts `FormData {business_name, file}`. It creates a company (name = business_name, owned by the requesting user) and uploads the document in a single atomic operation, reusing the existing company creation and document ingestion logic. Returns `{company_id, document_id, status}`. This endpoint is authenticated (requires valid session cookie) but NOT admin-gated — it is the regular user's upload path.
- **D-07:** Wizard step 1 shows two fields: "Business name *" (text input) and "Upload financials *" (file input, same accepted types as the existing upload). On submit, calls `POST /wizard/upload`. The business name is stored as the company name in the `companies` table — same model as admin-created companies.

### Wizard frontend
- **D-08:** After `/auth/me` returns `is_admin = false`, hide the entire existing tab nav and content area; show a `#wizard-page` div instead. When `is_admin = true`, behavior is unchanged — existing tabs render normally. All gating is done in the JS `checkAuth()` flow (the existing function that calls `/auth/me` and shows the auth wall).
- **D-09:** The wizard has 3 steps, each a card panel within `#wizard-page`. Step indicator shows "Step N of 3" as simple text. Reuse existing CSS variables (`--navy`, `--blue`, `--card`, `--border`), `.card`, `.form-group`, `.btn .btn-primary`, and `.alert` classes — no new CSS tokens introduced.
- **D-10:** Wizard step 2 shows all 5 report type options as selectable cards (one click selects, highlighted with `--blue` border). Report type is stored in a JS variable for step 3. Step 3 is a static confirmation card: "Your report is being prepared. We'll email you at {email} when it's ready." (email read from `/auth/me` response). The actual report generation job is deferred to Phase 5 — step 3 only shows confirmation copy for now.

### Report type options (Step 2 copy — locked for Phase 5 consistency)
- **Valuation Advisory** — "Enterprise value using DCF and market multiples, based on your financials and industry benchmarks."
- **Bank Credit Paper** — "Structured credit submission covering business overview, financial performance, and lending rationale."
- **Financial Forecast** — "Three-year forward projections with base, bull, and bear scenarios derived from historical performance."
- **Capital Raising Document** — "Investor-ready summary covering business model, financials, growth strategy, and use of funds."
- **Information Memorandum** — "Full sale document covering business overview, operations, financials, and growth opportunities."

### Claude's Discretion
- **Wizard step ordering:** Step 1 = upload + business name, Step 2 = report type, Step 3 = confirmation. This order is fixed by the roadmap.
- **403 vs 404 for admin routes:** Use 403 (not 404) for admin-gated routes called by non-admins. This is an exception to the Phase 2 rule (D-01 in 02-CONTEXT.md used 404 to avoid leaking existence). Admin route existence is not sensitive — 403 is the correct semantic here and matches the roadmap success criterion 3.
- **No wizard navigation back-button state management:** Wizard steps advance forward only in v1. Browser back button is not handled. A "Back" text button within the wizard is sufficient.
- **`/wizard/upload` ingestion:** Reuse `_run_ingestion` background task exactly — same extraction pipeline as admin upload. No separate wizard ingestion path needed.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap and requirements
- `.planning/ROADMAP.md` — Phase 3.5 goal, success criteria (7 items), and plan descriptions
- `.planning/REQUIREMENTS.md` — AUTH-09 (admin role), UX-01 (user wizard shell)

### Auth and user model
- `backend/auth.py` — `get_current_user` dependency (extend to return `is_admin`); `register` route (add OWNER_EMAIL check); `auth_router` prefix `/auth`
- `backend/db.py` — `users` table definition (lines 87–92); migration pattern at lines 157–230

### Backend patterns
- `backend/main.py` — existing route structure; router includes; how `Depends(get_current_user)` is applied across routers
- `.planning/codebase/CONVENTIONS.md` — async DB pattern, `HTTPException` error handling, env var loading
- `.planning/codebase/ARCHITECTURE.md` — document ingestion flow (`_run_ingestion`, `BackgroundTasks`) that `/wizard/upload` reuses

### Frontend patterns
- `frontend/index.html` — existing `checkAuth()` function that calls `/auth/me` and toggles the auth wall; tab nav show/hide pattern (`showPage()`, `.page.active`); `apiFetch`/`apiPost` helpers; CSS variable tokens

### Prior phase context
- `.planning/phases/02-multi-user-data-isolation/02-CONTEXT.md` — D-01: 404 vs 403 policy (Phase 3.5 deliberately uses 403 for admin gates — documented exception)
- `.planning/phases/03-business-profile-intake/03-CONTEXT.md` — D-04: canonical industry list (15 items); wizard must not conflict with the profile accordion added in Phase 3

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_current_user` in `backend/auth.py` — extend return dict to include `is_admin`; all 15 protected routes already inject it
- `_run_ingestion` background task in `backend/main.py` — `/wizard/upload` calls this directly after inserting company + document records
- `checkAuth()` in `frontend/index.html` — already calls `/auth/me` and shows/hides auth wall; extend to also branch on `is_admin` to show wizard vs full UI
- `apiFetch` / `apiPost` helpers in `frontend/index.html` — wizard calls use these for `/wizard/upload` (via `apiPost`) and `/auth/me` (via `apiFetch`)
- `.card`, `.form-group`, `.btn`, `.btn-primary`, `.alert-success`, `.alert-error` CSS classes — all reused in wizard panels; no new classes required

### Established Patterns
- `try/except ALTER TABLE` migration — add `is_admin INTEGER NOT NULL DEFAULT 0` column to users
- `FastAPI Depends(get_current_user)` — new `require_admin` dependency wraps this
- `os.getenv("OWNER_EMAIL", "")` — matches existing env var access pattern in `backend/main.py`
- `raise HTTPException(403, "Admin access required")` — new error code; existing convention for `detail` as a string
- `BackgroundTasks.add_task(_run_ingestion, ...)` — reused by `/wizard/upload` identically

### Integration Points
- `/auth/me` response gains `is_admin` field — frontend reads this to route to admin UI vs wizard
- `/wizard/upload` → creates company row → creates document row → adds `_run_ingestion` background task → returns `{company_id, document_id, status: "processing"}`
- Wizard step 3 confirmation email copy references `{email}` from the `/auth/me` response already held in JS state

</code_context>

<specifics>
## Specific Ideas

- Wizard step 1 combined field layout: "Business name *" input above "Upload financials *" file input, then a single "Continue →" button. No separate company-creation step — one form, one submit.
- Step 2 report type cards: each card shows the report name in bold and a one-line description below. Selected card gets a `2px solid var(--blue)` border and light blue background (`#e3f2fd`). Matches existing `.badge-processing` color token.
- Step 3 confirmation: static — no polling needed in Phase 3.5. Report job and email delivery is Phase 5. Just show the "we'll email you" message with the user's email address.
- `OWNER_EMAIL` should be added to `.env.example` with a placeholder comment: `# Set to your email to auto-grant admin access on first registration`.

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope. Report generation, email delivery, and payment gating are Phase 5/6 concerns.

</deferred>

---

*Phase: 3.5-Admin-Gate-Wizard-Shell*
*Context gathered: 2026-05-12*
