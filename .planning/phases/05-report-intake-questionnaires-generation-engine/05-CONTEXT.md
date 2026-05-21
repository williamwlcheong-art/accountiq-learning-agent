# Phase 5: Report Intake Questionnaires + Generation Engine - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

For each of the 5 report types, the user completes a structured intake questionnaire that provides methodology inputs. The application applies those inputs (not assumptions) to generate the report. Valuation Advisory: guided diagnostic questions recommend DCF / multiples / both → Python algorithm computes all numbers → Claude writes the narrative around calculated outputs (not assumptions). All other reports pass user-supplied answers to Claude alongside extracted financials. Reports are generated async and the user receives a real email when generation completes. Phase 5 bypasses the `pending_payment` state — Phase 6 inserts the payment gate without touching generation logic.

</domain>

<decisions>
## Implementation Decisions

### Wizard flow
- **D-01:** The intake questionnaire lives at **Step 2b** — between type selection (Step 2) and confirmation (Step 3). Keeps 3 named steps; intake is an inline sub-step rendered after the user selects a report type. Step 3 confirmation now confirms generation is queued (not just "we'll email you someday").
- **D-02:** Each report type's intake renders as a **single scrollable card**. All questions for that report type appear in one card; user scrolls, fills in answers, clicks "Generate Report". JS shows/hides one div per report type (5 divs, only the selected one visible). Reuses existing `.card`, `.form-group`, `.btn-primary` CSS classes — no new CSS tokens.
- **D-03:** If industry or business description is missing from the company profile, show an **amber warning banner** at the top of the intake card: "Some profile data is incomplete — your report may have gaps." Generation can still proceed. No hard block at wizard level.

### Generation trigger + job state machine
- **D-04:** Phase 5 **bypasses `pending_payment`** entirely. Submitting the intake form sets report status to `queued` and immediately queues the background generation task. Phase 6 inserts the `pending_payment` gate before queuing without touching generation logic.
- **D-05:** **Minimal DB schema** for Phase 5. `reports` table: `id INTEGER PRIMARY KEY, company_id INTEGER, user_id INTEGER, report_type TEXT, status TEXT (queued/generating/done/failed), content TEXT, error_message TEXT, created_at TEXT DEFAULT (datetime('now')), completed_at TEXT`. `report_intake` table: `id INTEGER PRIMARY KEY, report_id INTEGER REFERENCES reports(id), answers TEXT (JSON string), created_at TEXT DEFAULT (datetime('now'))`. Phase 6 adds `stripe_payment_intent_id` and `purchased_at` to `reports` via `ALTER TABLE` with `try/except`.
- **D-06:** **Manual retry only** for failed reports. Failed reports show a Retry button in the wizard at Step 3. Clicking resets status to `queued` and re-queues the background task. No automatic exponential backoff — deferred to a later phase if needed.

### Valuation Advisory algorithm
- **D-07:** Intake for Valuation Advisory starts with **3–4 diagnostic questions** to determine methodology before collecting method-specific inputs:
  - Q1: Business type — asset-heavy (manufacturing/property), service/professional, tech/SaaS, retail/distribution
  - Q2: Revenue type — recurring contracts, project-based, transactional
  - Q3: Growth stage — stable, moderate growth, high growth
  - Q4: Transaction context — trade sale, financial/PE buyer, internal planning
  
  System maps answers to a methodology recommendation (DCF / EV/EBITDA multiples / both). User confirms or overrides. Then collects method-specific inputs (WACC components + terminal growth rate + forecast years for DCF; user-entered EV/EBITDA comparable range for multiples).
- **D-08:** **Python computes all numbers; Claude writes only the narrative.** DCF: FCFF projections from historical EBITDA × stated growth rate, discounted at WACC, plus terminal value → enterprise value. EV/EBITDA: normalised EBITDA × user-confirmed comparable low/high multiple range → EV (low/mid/high). Claude receives the calculated EV outputs and inputs used and writes ONLY the narrative — Claude does NOT estimate or adjust the numbers.
- **D-09:** **Bank Credit Paper Python computations** (deterministic, not Claude-generated): DSCR from extracted financials + user-entered facility amount and term, 3-year financial trend table from `financial_rows`, sensitivity table at −10% and −20% revenue on DSCR. Claude receives these computed tables and writes the credit narrative.

### Report content format + email
- **D-10:** Generated report content stored as **structured JSON** (TEXT column) in `reports.content`. Format: `{"section_name": "content string", ...}`. Section keys differ per report type but follow a stable schema (e.g., Valuation: `executive_summary`, `business_overview`, `financial_analysis`, `valuation_methodology`, `dcf_analysis`, `multiples_analysis`, `concluded_value`, `disclaimer`). Phase 7's Jinja2 templates iterate sections by key.
- **D-11:** Phase 5 includes **real email delivery** via a `send_report_ready_email()` function in a new `backend/email.py` module. Implementation: Python `smtplib` with SMTP config from `.env` (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`). The function is abstracted so Phase 6 can swap it to Resend without touching generation logic. Phase 5 SC-8 ("user receives email with report link on completion") is fully met.

### Claude's Discretion
- **Section key schema per report type:** Claude defines the section names for each of the 5 report types, consistent with the ROADMAP's described content (e.g., IM: 10 standard sections). Schema should be documented, consistent, and stable between Phase 5 and Phase 7.
- **Claude prompt structure:** System prompt design, section-by-section instruction, disclaimer enforcement for all 5 report types. Claude's discretion as long as output is valid JSON matching the agreed section schema.
- **DSCR and sensitivity computations (Bank Credit Paper):** Implementation detail for how to extract historical EBITDA, interest, and repayment data from `financial_rows` to compute DSCR. Claude's discretion.
- **Report link in email:** For Phase 5, the email report link can point to `/app` (base URL). Phase 7 implements the viewer and can update the link format without changing `send_report_ready_email()`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — REPT-01 (valuation), REPT-02 (bank credit), REPT-03 (forecast), REPT-04 (capital raising), REPT-05 (IM), REPT-06 (disclaimer)
- `.planning/ROADMAP.md` — Phase 5 goal, intake table (5 report types × key intake questions × algorithm column), 9 success criteria, and 5 plan descriptions

### Existing backend patterns to follow
- `backend/main.py` — existing route structure, `BackgroundTasks.add_task(_run_ingestion)` pattern (new `generate_report` task follows same model), `/wizard/*` route namespace
- `backend/db.py` — `_migrate_db()` migration pattern with `ALTER TABLE` + `try/except`; `init_db()` startup hook; `financial_rows` table schema (read before querying for report generation)
- `backend/ingestion.py` — `call_claude()` function (Claude API call pattern; report generation uses same Anthropic SDK but without tool-use forcing)
- `backend/auth.py` — `get_current_user` dependency; `require_admin` dependency (wizard routes are NOT admin-gated — they are the regular user path)

### Frontend patterns
- `frontend/index.html` — wizard step show/hide logic (`showWizardStep()`), step indicator ("Step N of 3"), `apiFetch`/`apiPost` helpers, `setInterval` polling pattern (currently used for document status — same pattern for report status polling)

### Prior phase context (critical)
- `.planning/phases/03-5-admin-gate-wizard-shell/03-5-CONTEXT.md` — D-10: Step 2 report type cards (one-click selection, `--blue` border highlight), D-09: 5 report type option copy (locked — reuse verbatim), D-06/D-07: `/wizard/upload` pattern (new `/wizard/report/generate` follows same shape)
- `.planning/phases/03-business-profile-intake/03-CONTEXT.md` — D-04: canonical industry list (15 items, same list used in Valuation Advisory diagnostic Q1 mapping), EBITDA add-back structure, management team schema (Capital Raising and IM pull from these)
- `.planning/phases/04-extraction-quality/04-CONTEXT.md` — D-01: all 4 statement types (pnl, bs, cf, eq) stored in `financial_rows`; D-02/D-03: canonical CF and EQ row keys; D-08/D-09: `_normalize_signs()` ensures cost rows are negative — report generation can trust sign convention

### Codebase maps
- `.planning/codebase/ARCHITECTURE.md` — background task data flow; Claude API integration; async/executor pattern
- `.planning/codebase/CONVENTIONS.md` — async DB pattern, `HTTPException` error handling, logging with `print()`, frontend API helper patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_run_ingestion` background task in `backend/main.py` — direct pattern for `generate_report` background task (same `BackgroundTasks.add_task`, same own DB connection, same status update flow)
- `call_claude()` in `backend/ingestion.py` — Claude API call using Anthropic SDK; report generation uses the same client setup but calls `client.messages.create()` without tool-use forcing (plain JSON response via prompt instruction instead)
- `apiFetch` / `apiPost` in `frontend/index.html` — intake form submission and status polling both use these helpers
- `.card`, `.form-group`, `.btn`, `.btn-primary`, `.alert-success`, `.alert-error` CSS classes — intake card and confirmation card reuse these; no new CSS classes needed
- `setInterval` polling at 3s for `GET /documents/{id}/status` — same pattern for `GET /wizard/report/{id}/status`

### Established Patterns
- `BackgroundTasks.add_task(fn, arg1, arg2)` — async background job entry point; `generate_report` follows this exactly
- `async with aiosqlite.connect(DB_PATH) as db:` — background tasks open their own DB connection (same as `_run_ingestion`)
- `try/except ALTER TABLE ADD COLUMN` — schema migration pattern for new `reports` and `report_intake` tables
- `os.getenv("SMTP_HOST", "")` — env var access pattern for new email config values
- `raise HTTPException(403, "Admin access required")` — wizard routes return 401 (not 403) for unauthenticated callers (requires valid session cookie, but not admin)

### Integration Points
- **New endpoint:** `POST /wizard/report/generate` — body: `{company_id, report_type, intake_answers: {...}}`. Creates `reports` row (status=queued) + `report_intake` row (answers as JSON string). Queues `generate_report` background task. Returns `{report_id, status: "queued"}`.
- **New endpoint:** `GET /wizard/report/{report_id}/status` — returns `{status, error_message, completed_at}`. Frontend polls this at Step 3.
- **New endpoint:** `POST /wizard/report/{report_id}/retry` — resets status to queued, re-queues `generate_report`. Only callable when status is `failed`.
- **Wizard JS flow:** Step 2 type selection → user clicks type card → "Continue to intake" appears → Step 2b shows intake card for that type → user fills + clicks "Generate Report" → `apiPost('/wizard/report/generate', ...)` → move to Step 3 confirmation → poll status.
- **generate_report background task inputs:** reads `financial_rows` for the company (all 4 statement types), reads `report_intake.answers`, reads company profile (industry, description, management team, EBITDA add-backs from Phase 3 tables), runs Python algorithm if Valuation Advisory, calls Claude, stores JSON in `reports.content`, calls `send_report_ready_email()`.

</code_context>

<specifics>
## Specific Ideas

- Valuation Advisory methodology recommendation mapping: asset-heavy + trade sale → multiples; service/tech + financial buyer → DCF; high-growth SaaS → DCF or both; stable recurring → both. The mapping logic is a simple Python dict/if-else — no ML. User always gets to override.
- The `send_report_ready_email()` function signature: `async def send_report_ready_email(user_email: str, user_name: str, report_type: str, report_id: int) -> None`. Runs in the background task after `reports.status` is set to `done`.
- Report section schema should be defined as a Python dict constant per report type (e.g., `VALUATION_SECTIONS = ["executive_summary", "business_overview", ...]`) used by both the Claude prompt builder and Phase 7's template registry.
- Bank Credit Paper: extract DSCR from `financial_rows` by querying `net_profit`, `interest_expense`, `depreciation` from `pnl` statement for the most recent 3 fiscal years. DSCR = (EBITDA + interest) / (interest + scheduled principal repayment). Scheduled principal comes from intake (user-entered proposed facility amount ÷ proposed term).
- The intake form for non-Valuation reports is simpler (4–7 fields each). Use HTML `<select>`, `<textarea>`, and `<input type="number">` fields with `name` attributes matching the JSON keys. Serialise the entire form as a JS object when submitting.

</specifics>

<deferred>
## Deferred Ideas

- **Automatic exponential backoff for transient Claude errors (429/529):** User chose manual retry only for Phase 5. Can be added in a maintenance phase if needed.
- **Resend email API:** Phase 6 will swap `send_report_ready_email()` to use Resend. Phase 5 uses `smtplib` as a working placeholder.
- **Static EV/EBITDA industry lookup table:** User chose a fully guided diagnostic approach rather than a static lookup. If industry default multiples are needed later, they can be added as optional hints to the diagnostic flow.
- **Claude methodology note section:** Commenting on whether the chosen methodology is appropriate for the business type. Deferred — Python computes, Claude narrates only, in Phase 5.
- **On-screen progress indicator during generation:** v2 requirement (REQUIREMENTS.md v2 backlog). Phase 5 polls for status but shows only a simple "Generating…" state, not a step-by-step progress bar.

</deferred>

---

*Phase: 5-Report-Intake-Questionnaires-Generation-Engine*
*Context gathered: 2026-05-21*
