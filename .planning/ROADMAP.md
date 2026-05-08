# AccountIQ — Roadmap

**7 phases** | **33 requirements** | All v1 requirements covered ✓

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

## Phase 2: Multi-User Data Isolation

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

## Phase 3: Business Profile Intake

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
- [ ] 03-02-PLAN.md — Add backend CRUD: profile patch, management-team CRUD, ebitda-adjustments CRUD, profile-status (gate + EBITDA bridge); enrich GET /companies with description + sections_complete

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 03-03-PLAN.md — Build frontend accordion: completion badge, Industry/Description/Mgmt Team/EBITDA forms with running bridge; apiDelete helper; human-verify checkpoint

---

## Phase 4: Extraction Quality

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

**Plans:**
- Fix multi-page aggregation: score and aggregate top-N pages instead of single-page selection
- Fix sign convention enforcement and period attribution in Claude prompt and rule extractor
- Add Word (.docx) ingestion via python-docx (new extraction path alongside PDF/Excel)
- Improve OCR reliability: better page detection, fallback handling, and OCR pre-processing

---

## Phase 5: Report Generation Engine

**Goal:** The system can generate all 5 report types as structured, accurate content using Claude — seeded with extracted financials, business profile, and industry multiples.

**Requirements:** REPT-01, REPT-02, REPT-03, REPT-04, REPT-05, REPT-06

**Success Criteria:**
1. A valuation report is generated with normalised EBITDA, industry multiple applied, DCF analysis, and a low/mid/high value range — no placeholder text
2. A bank credit paper includes DSCR calculation, 3-year financial trend table, and a sensitivity analysis at −10%/−20% revenue
3. A financial forecast includes a stated-assumptions section, 3-year projections, and base/bull/bear scenarios
4. A capital raising document includes use-of-funds breakdown and management team section drawn from business profile
5. An IM includes all 10 standard sections populated with company-specific content (not generic templates)
6. Every generated report section includes "indicative only" disclaimer language
7. A failed generation (Claude API error) sets report status to `failed` with a human-readable error message and allows retry

**UI hint:** no

**Plans:**
- Create `reports` DB table, job state machine (pending_payment → queued → generating → done/failed), and generation API endpoints
- Seed `industry_multiples` lookup table; build valuation and bank credit paper Claude prompts
- Build forecast, capital raising, and IM Claude prompts
- Add retry logic with exponential backoff for transient Claude API errors (429, 529)

---

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
- Build report viewer tab in frontend; wire up PDF download endpoint with auth guard
- Generate CLAUDE.md project instruction file

---

## Requirement Coverage

| Requirement | Phase |
|-------------|-------|
| AUTH-01–03  | Phase 1 — Security & Auth Foundation |
| AUTH-04–06, AUTH-08 | Phase 1 — Security & Auth Foundation |
| AUTH-07     | Phase 2 — Multi-User Data Isolation |
| DATA-01     | Phase 2 — Multi-User Data Isolation |
| PROF-01–04  | Phase 3 — Business Profile Intake |
| EXTR-01–05  | Phase 4 — Extraction Quality |
| FILE-01–02  | Phase 4 — Extraction Quality |
| REPT-01–06  | Phase 5 — Report Generation Engine |
| PAY-01–03   | Phase 6 — Payment Integration |
| DELIV-01–03 | Phase 7 — PDF Rendering & Delivery |

**Coverage check:** 33/33 requirements mapped ✓
