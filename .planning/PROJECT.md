# AccountIQ

## What This Is

AccountIQ is a SaaS financial intelligence platform for SME business owners. Users upload their financial statements (PDFs, Excel files, and other formats), the system extracts and normalises the financial data, and then generates first-draft quality professional reports — valuations, bank credit papers, financial forecasts, capital raising documents, and information memorandums — that users select and purchase on a pay-per-report basis.

## Core Value

A business owner uploads their financials, answers a few questions about their business, and receives a first-draft professional financial report in minutes — the kind that would otherwise cost thousands and take days through an advisor.

## Requirements

### Validated

<!-- Capabilities that already exist in the codebase. -->

- ✓ PDF text extraction with pdfplumber + OCR fallback for scanned pages — existing
- ✓ Excel ingestion (.xlsx/.xls/.xlsm via pandas) — existing
- ✓ Claude tool-use extraction with GAAP/IFRS system prompt — existing
- ✓ Rule-based extraction fallback (works when no API key or Claude fails) — existing
- ✓ Pattern learning (label → canonical key mapping improves over time) — existing
- ✓ Company and document management (CRUD + upload flow) — existing
- ✓ Next.js frontend UI for auth, wizard, admin dashboard, companies, uploads, documents, financials, patterns, settings — Next.js refactor
- ✓ CORS restricted to localhost:8765 (no wildcard) — Phase 1
- ✓ Filename sanitisation via Path(file.filename).name — Phase 1
- ✓ XSS eliminated: all server/AI data uses textContent/createTextNode — Phase 1
- ✓ User registration + login with Argon2-hashed passwords and HttpOnly/SameSite=Lax cookies — Phase 1
- ✓ JWT session cookies (7-day expiry, 15 protected routes) — Phase 1
- ✓ Frontend auth wall gates the app via `/auth/me` and role-based Next.js redirects — Phase 1 + Next.js refactor

### Active

<!-- Hypotheses — all in scope for v1. -->

**Extraction quality:**
- ✓ Correctly extract all major statement types: income statement, balance sheet, cash flow, changes in equity — Validated in Phase 4: Extraction Quality
- ✓ Handle sign conventions correctly (_normalize_signs pure function, cost keys flipped) — Validated in Phase 4: Extraction Quality
- ✓ Assign financial data to the correct fiscal period (no period mismatch) — Validated in Phase 4: Extraction Quality
- ✓ Map non-standard line item labels to canonical keys (CF_SYNS, EQ_SYNS, AU/NZ SME synonyms) — Validated in Phase 4: Extraction Quality
- ✓ Extract multi-page statements without dropping rows (filter-then-sort, lowest-score eviction) — Validated in Phase 4: Extraction Quality

**File format coverage:**
- ✓ Support Word documents (.docx) as an upload format (extract_docx_text via python-docx) — Validated in Phase 4: Extraction Quality
- ✓ Support scanned image-only PDFs (OCR at 300 DPI, 100% row recovery verified) — Validated in Phase 4: Extraction Quality
- [ ] Support structured HTML financial filings

**Business profile intake:**
- [ ] User can describe their business (industry, products/services, market position)
- [ ] User can select industry/sector for comparable multiples and benchmarking
- [ ] User can provide management team details (founders, key staff)
- [ ] User can enter EBITDA add-backs / owner adjustments

**Authentication & accounts:**
- ✓ User can create an account and log in — Validated in Phase 1: Security & Auth Foundation
- ✓ Each user's companies and documents are isolated (no cross-user data leakage) — Validated in Phase 2: Multi-User Data Isolation
- [ ] User can manage their account and report purchase history

**Report generation:**
- [ ] Valuation report — DCF and/or EV/EBITDA multiple, supported by extracted financials
- [ ] Bank credit paper — structured write-up suitable for a lending submission
- [ ] Financial forecast — forward projections based on historical financials and growth assumptions
- [ ] Capital raising document — investor-ready summary of business and financials
- [ ] Information memorandum (IM) — full document suitable for selling the business

**Report delivery:**
- [ ] Web viewer — reports readable in-app after generation
- [ ] PDF export — downloadable, professionally formatted document
- [ ] Pay-per-report purchasing — user selects and pays for a report before it is generated

### Out of Scope

- Full advisor-replacement quality — first-draft quality is the bar; a professional can edit and finalise
- Team / multi-user accounts — individual business owners only for v1
- API access or third-party integrations — web UI only for v1
- Automated financial ratio dashboards — focus is on narrative reports, not analytics screens

## Context

- The backend is Python FastAPI with SQLite (aiosqlite). The primary frontend is a Next.js App Router app in `web/`; the old `frontend/index.html` app is now an opt-in legacy fallback.
- Extraction already uses Claude (claude-sonnet-4-6) with forced tool-use and a GAAP/IFRS system prompt. The same Claude API will power report generation.
- Security gaps from pre-Phase 1 (wildcard CORS, unsanitised filenames, innerHTML XSS, no auth) are now fixed. 4 code review criticals remain (empty SECRET_KEY, exception message leakage, env path disclosure, unvalidated claude_model write) — flagged for Phase 1 gap closure before external launch.
- Phase 2 isolation: all company/document routes enforce `WHERE user_id=?` filters; IDOR returns 404 not 403 (D-01); analytics scoped per-user; `label_patterns` intentionally global (D-03). 3 code review criticals remain (retry_document write scope, analytics/overview label_patterns leakage, executescript transaction split) — flagged for gap closure.
- The codebase map is at `.planning/codebase/` — read it before planning any backend phase.

## Constraints

- **Tech stack**: Python FastAPI + SQLite + Next.js — keep FastAPI as the backend of record for uploads, extraction, reports, and DB writes
- **AI**: Anthropic Claude API — already integrated, continue using it for both extraction and report generation
- **Quality bar**: Report output must be first-draft quality — accurate enough that a professional would use it as a starting point, not start over
- **Security**: Auth, input sanitisation, and CORS lockdown must ship before any external user access
- **No lockfile**: `requirements.txt` uses `>=` constraints — pin versions when adding dependencies to avoid reproducibility issues

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Pay-per-report (not subscription) | Matches infrequent, high-value use case for SME owners | — Pending |
| First-draft quality bar | Makes accuracy achievable; professionals still add value | — Pending |
| All 5 report types in v1 | User wants full offering from launch | — Pending |
| Keep FastAPI as backend of record and migrate UI to Next.js | Preserves working ingestion/report engine while fixing frontend maintainability | — Accepted |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-01 — Next.js refactor in progress*
