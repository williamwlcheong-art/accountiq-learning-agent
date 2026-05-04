# Pitfalls Research

## Extraction Quality Pitfalls

### SME Accounts Differ from Public Company Filings
**Warning signs:** Extraction works well on large-company annual reports but fails on management accounts, Xero exports, or accountant-prepared PDFs for SMEs
**Prevention strategy:**
- Train extraction prompts on SME-specific formats (Xero P&L, MYOB balance sheets, accountant-prepared one-pagers)
- Expect non-standard line item names: "Owners Drawings", "Goodwill Amortisation", "Intercompany Loans", "Directors Fees"
- Add SME-specific synonyms to the rule extractor's synonym dictionaries
**Phase:** Phase 4 — Extraction Quality

### Tax-Minimised Accounts Understate EBITDA
**Warning signs:** Very low or zero net profit despite healthy revenue; owner salary appears as "Consulting Fees" or "Management Fees" to a related entity
**Prevention strategy:**
- Prompt Claude to flag unusual expense-to-revenue ratios that suggest owner distributions
- Surface high consulting/management fee lines as potential add-back candidates
- The EBITDA add-back flow (Phase 3 business profile) is the mitigation — don't try to auto-correct in extraction
**Phase:** Phase 3 — Business Profile Intake

### Multi-Period Documents with Inconsistent Layout
**Warning signs:** A 3-year comparative P&L where year columns shift position between pages, or restated prior-year figures differ from previously extracted values
**Prevention strategy:**
- Extract period headers explicitly and validate consistency across statement pages
- Flag where the same period appears with different values (restatement detection)
- Require user confirmation when comparative figures conflict
**Phase:** Phase 4 — Extraction Quality

### Sign Convention Varies by Accounting System
**Warning signs:** Costs of sales appear positive (correct in some formats) but are subtracted in the gross profit calculation; user sees double-negatives in the UI
**Prevention strategy:**
- Enforce a canonical sign convention: revenue positive, all costs negative (income statement normal form)
- Validate: Revenue − COGS = Gross Profit must be positive for a viable business
- Rule extractor must handle parenthetical negatives `(1,234)` and explicit negatives `−1,234`
**Phase:** Phase 4 — Extraction Quality

### Single-Page Rule Extractor Misses Multi-Page Statements
**Warning signs:** Balance sheet totals don't balance; cash flow statement is truncated; only 3 rows extracted from a 20-row P&L
**Prevention strategy:**
- The existing rule extractor picks only the highest-scoring page — fix to aggregate across top-N pages
- Pass all relevant pages to Claude (up to token limit), not just the highest-scoring one
**Phase:** Phase 4 — Extraction Quality

---

## Report Quality Pitfalls

### Wrong Industry Multiple Applied
**Warning signs:** Valuation report applies a tech multiple (8-12x) to a manufacturing business, or a retail multiple to a professional services firm
**Prevention strategy:**
- Maintain a curated industry multiple lookup keyed to standardised sector codes
- Require user to confirm industry selection before report generation
- State the source and basis of multiples explicitly in the report
**Phase:** Phase 5 — Report Generation Engine

### DCF Terminal Value Dominates Total Value
**Warning signs:** Terminal value represents >80% of enterprise value — common in mechanically generated DCFs
**Prevention strategy:**
- Cap terminal growth rate at GDP growth (2-3%) unless user explicitly justifies higher
- Display terminal value as % of total EV in the report; flag if >75%
- Consider excluding DCF for businesses with <3yr track record; use multiples only
**Phase:** Phase 5 — Report Generation Engine

### No EBITDA Normalisation = Meaningless Valuation
**Warning signs:** Valuation is based on reported EBITDA without adjusting for owner salary, non-recurring costs, or related-party rents
**Prevention strategy:**
- Block report generation if business profile has no adjustments and EBITDA is suspiciously low vs revenue
- Show "un-adjusted" and "adjusted" EBITDA side by side so the user sees the impact
**Phase:** Phase 3 + Phase 5

### Projections Without Stated Assumptions
**Warning signs:** Forecast shows 20% revenue growth with no explanation of what drives it
**Prevention strategy:**
- Each projection assumption must be stored as user input (not implied by Claude)
- Report template requires an Assumptions section; generation fails if assumptions are empty
**Phase:** Phase 5 — Report Generation Engine

### Key Person Risk Not Addressed
**Warning signs:** IM or valuation makes no mention of what happens if the owner leaves — lenders and buyers will always ask this
**Prevention strategy:**
- Detect from business profile if management team has only 1 person (the owner)
- Automatically include a Key Person Risk section in valuation, IM, and credit paper
**Phase:** Phase 5

---

## Legal & Liability Pitfalls

### Financial Advice Regulation (ASIC / FCA / SEC)
**Warning signs:** Report language says "you should sell your business for $X" or "we recommend this investment" — this constitutes financial advice in most jurisdictions
**Prevention strategy:**
- All reports must carry a prominent disclaimer: "This report is indicative only and does not constitute financial, investment, or legal advice. It should not be relied upon without independent professional verification."
- Claude system prompt must avoid prescriptive recommendations; use "indicative range" and "based on provided data" language throughout
- This disclaimer must appear on every page of the PDF (footer)
**Phase:** Phase 7 — PDF Rendering

### Users Submitting AI Reports as Certified Documents
**Warning signs:** User submits a bank credit paper to a lender without disclosing it is AI-generated
**Prevention strategy:**
- Watermark or footer on every PDF: "Generated by AccountIQ — Indicative Only — Not a Certified Financial Report"
- Terms of Service must clearly state reports are for preliminary purposes only
**Phase:** Phase 7 — PDF Rendering

### Data Retention and Privacy
**Warning signs:** Financial data stored indefinitely with no retention policy; breach exposes sensitive SME financial information
**Prevention strategy:**
- State in privacy policy how long financial data is retained
- Implement account deletion that removes all financial data
- Never log full financial row data to application logs
**Phase:** Phase 1 — Security & Auth Foundation

---

## Payment & Fraud Pitfalls

### Generating Reports Before Payment Confirmation
**Warning signs:** Race condition: user completes payment client-side, frontend triggers report generation, but Stripe webhook hasn't confirmed payment yet
**Prevention strategy:**
- Never trigger report generation from the client-side success callback
- Always wait for Stripe webhook (`payment_intent.succeeded`) to set status to `queued`
- Client polls report status; generation only starts after webhook confirmation
**Phase:** Phase 6 — Payment Integration

### Chargebacks After Report Delivery
**Warning signs:** User claims "report didn't meet expectations" after downloading the PDF
**Prevention strategy:**
- Web viewer shows report before PDF is unlocked — user explicitly confirms to download
- Log timestamp of web view and PDF download; provide to Stripe on chargeback dispute
- Terms of Service must state no refunds once PDF downloaded
**Phase:** Phase 7 — PDF Rendering

### Sharing Downloaded PDFs (Bypass Pay-Per-Report)
**Warning signs:** One user purchases an IM template and shares it for other businesses
**Prevention strategy:**
- PDFs are company-specific and contain the company name and financial data — hard to repurpose
- Accept this as low risk for v1; watermark with company name and generation date
**Phase:** Phase 7

---

## Architecture Pitfalls

### Long Claude Calls in BackgroundTasks with No Retry
**Warning signs:** 30-60s Claude API call fails silently; user sees "failed" status with no recovery path
**Prevention strategy:**
- Add `retry_count` to `reports` table; retry up to 3 times on transient errors (429 rate limit, 529 overload)
- Implement exponential backoff before retry
- Surface error reason in UI so user knows if it was a transient error vs a data problem
**Phase:** Phase 5 — Report Generation Engine

### Blocking Sync Calls in Async Route (pdfplumber, pandas, WeasyPrint)
**Warning signs:** PDF generation (WeasyPrint is synchronous) blocks the async event loop while running in a background task
**Prevention strategy:**
- Wrap WeasyPrint calls in `asyncio.get_running_loop().run_in_executor(None, ...)` — same pattern as the existing Claude call
- Same applies to pdfplumber and pandas calls in the extraction pipeline (already flagged in CONCERNS.md)
**Phase:** Phase 4 + Phase 7

### SQLite Write Contention Under Concurrent Report Generation
**Warning signs:** DB timeout errors when 5+ users generate reports simultaneously; writes block each other
**Prevention strategy:**
- WAL mode already enabled — helps concurrent reads
- Keep write transactions short: write JSON content first, write PDF path after rendering completes (two separate small writes)
- Set `PRAGMA busy_timeout = 5000` to allow retries before failing
- Monitor: if this triggers in production, migrate to PostgreSQL
**Phase:** Phase 5 — Report Generation Engine

---

*Research date: 2026-05-04*
