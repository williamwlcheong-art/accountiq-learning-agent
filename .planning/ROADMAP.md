# AccountIQ Roadmap

**9 phases** | **35 requirements** | All requirements mapped

---

## Phase 1: Security & Auth Foundation ✅ Complete (2026-05-06)

**Goal:** The application is hardened against known vulnerabilities and users can register, log in, and manage their account.

**Requirements:** AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-08

**Success Criteria:**
1. ✅ A request from an unknown origin to a write endpoint receives a CORS error (not 200)
2. ✅ Uploading a file with a path-traversal filename (e.g. `../../evil.py`) saves only to the intended directory
3. ✅ Claude-generated narrative text displayed in the UI contains no executable script even when the source text includes `<script>` tags
4. ✅ A new user can register with email + password and receive a JWT token
5. ✅ A logged-in user's session persists after browser refresh and expires after 7 days
6. ✅ A logged-out user is redirected to the login page when accessing any protected route

**UI hint:** yes

**Plans:**
- ✅ Fix CORS wildcard, filename sanitisation, and innerHTML XSS vulnerabilities
- ✅ Build user registration, login, and JWT auth middleware
- ✅ Add logout flow and account/purchase-history page to frontend

---

## Phase 2: Multi-User Data Isolation ✅ Complete

**Goal:** Every user sees only their own companies and documents. Existing NULL user_id rows become invisible to all users (D-02). The `label_patterns` table remains global.

**Requirements:** AUTH-07, DATA-01

**Success Criteria:**
1. User A cannot retrieve User B's companies or documents via any API endpoint (even with a valid JWT and guessed IDs)
2. Existing companies and documents (with no owner, NULL user_id) are not visible to any authenticated user
3. A newly registered user's uploaded documents are not visible to any other user
4. All API routes that return companies or documents enforce the user_id filter

**UI hint:** no

**Plans:** 3 plans

Plans:
- [x] 02-01-PLAN.md — Add user_id columns to companies and documents; rebuild UNIQUE constraint; add indexes
- [x] 02-02-PLAN.md — Update all API route handlers to filter by authenticated user's user_id
- [x] 02-03-PLAN.md — Add fresh_all_db fixture and cross-user IDOR integration smoke tests

---

## Phase 3: Business Profile Intake ✅ Complete (2026-05-12)

**Goal:** Users can build a complete company profile capturing industry, business description, management team, and EBITDA add-backs — the inputs required for accurate report generation.

**Requirements:** PROF-01, PROF-02, PROF-03, PROF-04

**Success Criteria:**
1. User can select an industry/sector from a categorised list and save it to a company
2. User can write and save a business description (free text, min 50 chars) for a company
3. User can add, edit, and remove management team members with name, title, and bio
4. User can add, edit, and remove EBITDA add-back line items with label, amount, and rationale
5. Profile completion status is visible (e.g. "3/4 sections complete") before report generation
6. Report generation is blocked with a clear message if industry or EBITDA add-backs are missing

**UI hint:** yes

**Plans:** 3 plans

Plans:
**Wave 1**
- [x] 03-01-PLAN.md — Extend `_migrate_db` (description column + management_team + ebitda_adjustments tables); update fresh_all_db fixture; add 9 RED test stubs for PROF-01..PROF-04, D-05, D-06

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 03-02-PLAN.md — Add backend CRUD: profile patch, management-team CRUD, ebitda-adjustments CRUD, profile-status (gate + EBITDA bridge); enrich GET /companies with description + sections_complete

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 03-03-PLAN.md — Build frontend accordion: completion badge, Industry/Description/Mgmt Team/EBITDA forms with running bridge; apiDelete helper; human-verify checkpoint. Legacy implementation was ported into the Next.js admin Companies screen during the 2026-07-01 parity review.

---

## Phase 3.5: Admin Gate + User Wizard Shell ✅ Complete (2026-05-13)

**Goal:** Split the application into two experiences on the same codebase. The current full UI (Companies, Documents, Patterns, Financials, Settings) becomes admin-only, accessible only to users with `is_admin = true`. All other users see a clean user-facing wizard: upload financials → select report type → confirmation. The admin owner account is designated by `OWNER_EMAIL` in `.env`.

**Requirements:** AUTH-09 (new — admin role), UX-01 (new — user wizard shell)

**Success Criteria:**
1. A user with `is_admin = true` sees the full current UI unchanged after login
2. A regular user (`is_admin = false`) sees only the user wizard after login — no access to Companies, Patterns, Financials, or Settings tabs
3. Attempting to access `/companies`, `/patterns`, `/financials/*` API routes as a non-admin returns 403
4. The `OWNER_EMAIL` in `.env` is automatically granted `is_admin = true` on first registration
5. The user wizard shell renders the three steps: (1) Upload financials, (2) Select report type, (3) Confirmation / "we'll email you"
6. All 5 report type options are present in step 2 with name and short description
7. The user wizard correctly identifies the logged-in user and associates uploads with their account

**UI hint:** yes

**Plans:** 3 plans

Plans:
**Wave 1**
- [x] 03-5-01-PLAN.md — Add `is_admin` column to users table; OWNER_EMAIL env var; extend `get_current_user`; add `require_admin` dependency; Wave 0 test stubs

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 03-5-02-PLAN.md — Apply `Depends(require_admin)` to all 25 existing admin routes; 403 for non-admin callers

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 03-5-03-PLAN.md — Add `POST /wizard/upload` backend route; build 3-step wizard frontend; extend `initApp()` to branch on `is_admin`; human-verify checkpoint

---

## Phase 4: Extraction Quality ✅ Complete

**Goal:** Financial statements are extracted accurately across all statement types, sign conventions, fiscal periods, non-standard labels, multi-page layouts, Word documents, and scanned PDFs.

**Requirements:** EXTR-01, EXTR-02, EXTR-03, EXTR-04, EXTR-05, FILE-01, FILE-02

**Success Criteria:**
1. Income statement, balance sheet, cash flow statement, and equity changes are each extracted and stored in separate statement-type buckets
2. All extracted costs/expenses carry a negative sign; all revenues and assets carry a positive sign regardless of source format
3. A 3-year comparative P&L assigns each column's values to the correct fiscal year
4. Common SME labels ("Owners Drawings", "Directors Fees", "Turnover", "Cost of Sales") map to the correct canonical keys
5. A 20-row P&L spread across two PDF pages produces all 20 rows (not just the first page)
6. A .docx file containing a financial statement table is ingested and produces extracted financial rows
7. A scanned PDF with no text layer is processed via OCR and produces at least 80% of the rows a text-layer PDF would

**UI hint:** no

**Plans:** 3 plans

Plans:
**Wave 1**
- [x] 04-01-PLAN.md — CF/EQ infrastructure: test stubs (17 RED), _normalize_signs(), CF_ROWS/EQ_ROWS, updated _ROW_SCHEMA enum, SYSTEM_PROMPT CF/EQ sections + sign rule, CF_SYNS/EQ_SYNS + SME synonyms in rule_extractor, python-docx dependency

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 04-02-PLAN.md — Multi-page fix (D-05/D-06/D-07 filter-then-sort + CF/EQ scoring), OCR threshold 100 chars (D-15), OCR DPI 300 (D-16), run_in_executor wrapping

**Wave 3** *(blocked on Wave 1 and Wave 2 completion)*
- [x] 04-03-PLAN.md — Word (.docx) ingestion: extract_docx_text() with merged-cell dedup, .docx dispatch in ingest_document(), allowed extensions in both upload routes, frontend accept attributes

---

## Phase 5: Report Intake Questionnaires + Generation Engine

**Goal:** For each of the 5 report types, the user completes a structured intake questionnaire that provides the methodology inputs. The application applies those inputs (not assumptions) to generate the report. Valuation Advisory runs a Python DCF/multiples algorithm before Claude writes the narrative. All other reports pass user-supplied answers to Claude alongside the extracted financials. Reports are generated async and delivered by email.

**Requirements:** REPT-01, REPT-02, REPT-03, REPT-04, REPT-05, REPT-06

**Report types and intake:**

| Report | Key Intake Questions | Algorithm |
|--------|---------------------|-----------|
| **Valuation Advisory** | Methodology (DCF / multiples / both), WACC components (risk-free rate, ERP, beta, cost of debt, capital structure), terminal growth rate, forecast years, EV/EBITDA comparable range, discount/premium factors | Python computes DCF + multiples → Claude writes narrative around calculated outputs |
| **Bank Credit Paper** | Facility type, amount requested, proposed term, repayment structure, security/collateral, loan purpose, existing debt facilities | No separate algorithm — Claude applies inputs to standard credit analysis framework |
| **Information Memorandum** | Sale rationale, key business highlights (user-written), growth opportunities, target buyer type, transaction structure preference, any exclusions | No separate algorithm |
| **Financial Forecast** | Forecast horizon (1/3/5 years), revenue growth rate per year, key business drivers, planned capex, headcount changes, any one-off events | No separate algorithm |
| **Capital Raising Document** | Amount, instrument type (equity/convertible/debt/hybrid), use of proceeds (itemised), business stage, target investor profile, key milestones the raise funds | No separate algorithm |

**Success Criteria:**
1. Each report type shows its own intake questionnaire before generation is queued
2. Valuation Advisory: Python computes DCF (per stated WACC/growth inputs) and EV/EBITDA multiple range; both outputs are passed to Claude for narrative — Claude does not estimate the valuation
3. Bank Credit Paper includes DSCR calculation, 3-year financial trend table, and sensitivity at −10%/−20% revenue — all derived from extracted financials + user inputs
4. Financial Forecast includes a stated-assumptions section (drawn from intake answers), 3-year projections, and base/bull/bear scenarios
5. Capital Raising document includes use-of-funds breakdown (from intake) and management team section (from business profile)
6. IM includes all 10 standard sections populated with company-specific content (not generic templates)
7. Every generated report section includes "indicative only" disclaimer language
8. Report generation runs async; user receives email with report link on completion
9. A failed generation sets report status to `failed` with a human-readable error and allows retry

**Plans:**
- Create `reports` and `report_intake` DB tables; job state machine (pending_payment → queued → generating → done/failed); generation API endpoints
- Build per-report-type intake form in user wizard (step 2b — after report type selection)
- Build Valuation Advisory Python algorithm (DCF + EV/EBITDA multiples calculator)
- Build Claude prompts for all 5 report types (seeded with extracted financials + intake answers + algorithm outputs where applicable)
- Add retry logic with exponential backoff for transient Claude API errors (429, 529)

---

## Phase 05.1: Valuation Advisory Redesign

**Goal:** Replace the Phase 5 Valuation Advisory report with a Propellerhead-quality implementation. The current paid-valuation path selects one active, adviser-approved, versioned WACC assumption set and freezes it with the valuation inputs before checkout. Research can inform a future approved assumption-set version only. DCF is the primary method, with structured report tables owned by Python before any live UAT.

**Requirements:** REPT-01 (Valuation Advisory redesign)

**Depends on:** Phase 5

**Success Criteria:**
1. The valuation intake questionnaire shows: (a) narrative risk section with 4 qualitative areas, (b) normalisation table pre-filled from Phase 3 EBITDA add-backs with ability to add/edit/remove items, (c) financial assumptions section with forecast horizon, CAGR, and terminal growth rate
2. Authoritative WACC inputs come from exactly one active, adviser-approved, versioned set selected and frozen before checkout; generation-time research cannot change that selection
3. Python computes DCF scenarios from the frozen FCFF inputs and selected WACC set, and Claude writes narrative only
4. Generated report contains all 12 sections: introduction, business_overview, market_position, financial_performance, normalisations_schedule, balance_sheet_summary, valuation_methodology, wacc_assumptions, dcf_analysis, valuation_summary, multiples_crosscheck, disclaimer
5. Table sections (financial_performance, normalisations_schedule, balance_sheet_summary, wacc_assumptions, valuation_summary) contain structured JSON `{narrative, table: {headers, rows}}` format
6. The 23-question EV/EBITDA scoring questionnaire no longer appears in the current Next.js wizard
7. Decimal FCFF, Python-owned deterministic tables, a synthetic service rehearsal, and a separately approved live UAT are complete before public payment enablement

**UI hint:** yes

**Current delivery status:** PRs #15 to #18 are merged. The 3A branch, covering frozen FCFF assumptions and adviser-approved WACC sets, is pushed without a PR. Open and review that PR next. The next unimplemented work is PR 3B, the Decimal FCFF engine, then PR 3C, Python-owned deterministic valuation tables. These are followed by a synthetic service rehearsal and a separately approved live UAT.

**Historical plan status:** Summaries record Plans 05.1-01 and 05.1-02 as completed. There is no 05.1-03 summary. The 05.1-04 summary records its first task in the legacy `frontend/index.html` as complete and its human-verification task as awaiting verification. The product UI now lives in `web/`; the legacy file is rollback/reference only. These records do not establish completion of the current paid-valuation delivery sequence.

**Plans:** Historical plans: 2 completed summaries, 1 plan without a summary, and 1 legacy frontend task summary awaiting human verification

Plans:
**Wave 1**
- [x] 05.1-01-PLAN.md - Refactor valuation.py (remove scoring, add compute_wacc_scenarios), lock 12-section schema, Wave 0 RED tests
- [x] 05.1-02-PLAN.md - Build research_loop.py (Anthropic web_search agentic loop + ResearchBrief Pydantic + 4 guardrails) with offline guardrail tests. Its generation-time WACC role is superseded for authoritative paid inputs.

**Wave 2** *(historical plan record)*
- [ ] 05.1-03-PLAN.md - Historical research-to-DCF orchestration plan. No completion summary is present; its WACC-research authority is superseded by the selected frozen adviser-approved set.

**Wave 3** *(historical plan record)*
- [ ] 05.1-04-PLAN.md - Historical legacy frontend intake plan. Its summary records Task 1 only, with human verification outstanding. Current implementation work belongs in the Next.js `web/` application.

## Phase 6: Payment Integration

**Goal:** Users can select and purchase a report at a flat price via Stripe; generation begins only after payment is confirmed via webhook.

**Requirements:** PAY-01, PAY-02, PAY-03

**Success Criteria:**
1. Clicking "Generate Report" presents a Stripe Checkout page for the flat report price
2. Completing payment on Stripe triggers the Stripe webhook, which sets report status to `queued` and starts generation
3. Abandoning the Stripe Checkout page does not trigger report generation
4. User receives an email with a direct link to their report within 2 minutes of generation completing
5. The purchase is recorded in the `purchases` table with Stripe payment intent ID and confirmation timestamp

**UI hint:** yes

**Plans:**
- Integrate Stripe SDK; implement PaymentIntent creation and Checkout session flow
- Implement Stripe webhook handler (`payment_intent.succeeded` → queue generation)
- Integrate Resend email API; send "report ready" email with report link on generation completion

---

## Phase 7: PDF Rendering & Delivery

**Goal:** Users can read their generated report in a web viewer and download a professionally formatted, watermarked PDF.

**Requirements:** DELIV-01, DELIV-02, DELIV-03

**Success Criteria:**
1. A completed report is readable in the web viewer with all sections, tables, and narrative text formatted clearly
2. Clicking "Download PDF" produces a PDF with professional typography, section headers, and page numbers
3. The PDF footer on every page shows the company name, generation date, and "Indicative Only — Not Financial Advice" disclaimer
4. The PDF is stored on disk and re-downloadable without re-rendering
5. A user who has not paid for a report cannot access its web viewer or PDF

**UI hint:** yes

**Plans:**
- Create Jinja2 HTML report templates for all 5 report types (shared layout, per-type content blocks)
- Implement WeasyPrint PDF rendering wrapped in `run_in_executor`; store output to `data/reports/`
- Build report viewer in user wizard (step 4 — post-generation); wire up PDF download endpoint with auth guard

---

## Requirement Coverage

| Requirement | Phase |
|-------------|-------|
| AUTH-01–03  | Phase 1 — Security & Auth Foundation |
| AUTH-04–06, AUTH-08 | Phase 1 — Security & Auth Foundation |
| AUTH-07     | Phase 2 — Multi-User Data Isolation |
| DATA-01     | Phase 2 — Multi-User Data Isolation |
| PROF-01–04  | Phase 3 — Business Profile Intake |
| AUTH-09 (admin role) | Phase 3.5 — Admin Gate + User Wizard Shell |
| UX-01 (user wizard) | Phase 3.5 — Admin Gate + User Wizard Shell |
| EXTR-01–05  | Phase 4 — Extraction Quality |
| FILE-01–02  | Phase 4 — Extraction Quality |
| REPT-01–06  | Phase 5 — Report Intake + Generation Engine |
| PAY-01–03   | Phase 6 — Payment Integration |
| DELIV-01–03 | Phase 7 — PDF Rendering & Delivery |

**Coverage check:** 33 original + 2 new (AUTH-09, UX-01) = 35 requirements mapped ✓

---

## Commercial MVP Overlay

The original seven-phase roadmap remains useful historical context. Current commercial execution is tracked in `.planning/BACKLOG.md` and focuses on the paid Valuation Advisory wedge.

- Commercial launch gates: `.planning/commercial/LAUNCH-GATES.md`
- Architecture decisions: `.planning/commercial/ARCHITECTURE-DECISIONS.md`
- Commercial assumptions: `.planning/commercial/COMMERCIAL-ASSUMPTIONS.md`
- Public funnel context: `.planning/phases/999.1-public-facing-commercial-funnel-advisor-review/999.1-CONTEXT.md`
- Marketing offer plan: `docs/superpowers/plans/2026-07-01-marketing-site-offer.md`

Do not accept public users or enable live Stripe payments until the launch gates are passed or explicitly waived for a private pilot. Public payments remain blocked.
