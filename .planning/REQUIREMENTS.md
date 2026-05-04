# AccountIQ — v1 Requirements

## v1 Requirements

### Security & Authentication

- [ ] **AUTH-01**: Platform restricts CORS to known origins (no wildcard `*` on write endpoints)
- [ ] **AUTH-02**: File upload sanitises filename to basename only (no path traversal via `../../`)
- [ ] **AUTH-03**: Frontend renders all server/AI-generated text as plain text, not `innerHTML` (XSS fix)
- [ ] **AUTH-04**: User can create an account with email and password
- [ ] **AUTH-05**: User can log in and remain logged in across browser sessions
- [ ] **AUTH-06**: User can log out from any page
- [ ] **AUTH-07**: Each user's companies and documents are private (no cross-user data leakage)
- [ ] **AUTH-08**: User can view their account details and report purchase history

### Extraction Quality

- [ ] **EXTR-01**: System correctly extracts income statement, balance sheet, cash flow statement, and changes-in-equity from uploaded documents
- [ ] **EXTR-02**: Extracted values use a consistent sign convention (revenue/assets positive; costs/liabilities negative) regardless of source format
- [ ] **EXTR-03**: Financial data is attributed to the correct fiscal period when documents contain multiple periods
- [ ] **EXTR-04**: Non-standard SME line item labels (e.g. "Owners Drawings", "Directors Fees", "Turnover") are correctly mapped to canonical financial keys
- [ ] **EXTR-05**: Multi-page financial statements are extracted in full without dropping rows from secondary pages

### File Formats

- [ ] **FILE-01**: User can upload Word (.docx) documents containing financial statements
- [ ] **FILE-02**: OCR extraction from scanned/image-only PDF pages is reliable (low blank-page and garbled-text failures)

### Business Profile

- [ ] **PROF-01**: User can specify industry and sector for a company (used for valuation multiples and benchmarking)
- [ ] **PROF-02**: User can provide a business description and overview (used in IM and capital raising narrative)
- [ ] **PROF-03**: User can enter management team details (names, titles, brief bios) for a company
- [ ] **PROF-04**: User can enter EBITDA add-backs / owner adjustments with label and amount for each adjustment (e.g. owner salary above market rate, non-recurring costs, related-party rents)

### Report Generation

- [ ] **REPT-01**: System generates a valuation report including normalised EBITDA derivation, industry comparable multiples, DCF analysis, and concluded enterprise value range (low/mid/high)
- [ ] **REPT-02**: System generates a bank credit paper including 3-year financial trend analysis, DSCR, debt/EBITDA, sensitivity table, and risk assessment
- [ ] **REPT-03**: System generates a financial forecast including 3-year historical performance, key assumptions, 3-year projections, and base/bull/bear scenario analysis
- [ ] **REPT-04**: System generates a capital raising document including investment thesis, business overview, financial performance and projections, use of funds, and management team
- [ ] **REPT-05**: System generates an information memorandum (IM) including executive summary, business overview, operations, management, financial performance, projections, and transaction structure
- [ ] **REPT-06**: All generated reports include an "indicative only — not financial advice" disclaimer on every page

### Payment & Delivery

- [ ] **PAY-01**: User can purchase any report at a single flat price via Stripe Checkout
- [ ] **PAY-02**: Report generation begins only after Stripe webhook confirms successful payment (not on client-side callback)
- [ ] **PAY-03**: User receives an email notification with a link when their report is ready
- [ ] **DELIV-01**: User can read their generated report in a web viewer before downloading
- [ ] **DELIV-02**: User can download their generated report as a professionally formatted PDF
- [ ] **DELIV-03**: PDF includes company name and generation date watermark on every page

### Data Migration

- [ ] **DATA-01**: Existing companies and documents in the database are visible as shared demo data to all authenticated users (no private ownership assigned)

---

## v2 Requirements (deferred)

- HTML financial filings support (ASIC / Companies House structured HTML)
- Tiered pricing by report type
- On-screen wait experience with progress indicator (in addition to email)
- Email notification when report generation fails (not just success)
- Comparable transactions database (live industry multiples vs static lookup)
- Report editing in-app
- White-label / advisor mode
- API access for third-party integrations
- Multi-currency support
- Account deletion with full data wipe

---

## Out of Scope

- Financial advice, certified valuations, or CPA-signed documents — platform generates indicative drafts only
- Subscription / recurring billing — pay-per-report only
- Team / multi-user accounts — individual users only
- Report generation for businesses with fewer than 1 full year of financial data

---

## Traceability

| Requirement | Phase |
|-------------|-------|
| AUTH-01–03  | TBD — Security & Auth Foundation |
| AUTH-04–08  | TBD — Security & Auth Foundation |
| EXTR-01–05  | TBD — Extraction Quality |
| FILE-01–02  | TBD — Extraction Quality |
| PROF-01–04  | TBD — Business Profile Intake |
| REPT-01–06  | TBD — Report Generation Engine |
| PAY-01–03   | TBD — Payment Integration |
| DELIV-01–03 | TBD — PDF Rendering & Delivery |
| DATA-01     | TBD — Security & Auth Foundation |

---

*Created: 2026-05-04 | v1 scope locked*
