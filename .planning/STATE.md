---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: PVM-05 professional PDF export complete
stopped_at: PVM-05 complete in PR #10; PVM-06 account purchase history is next
last_updated: "2026-07-12T18:35:00+12:00"
progress:
  total_phases: 9
  completed_phases: 5
  total_plans: 21
  completed_plans: 20
  percent: 95
---

# AccountIQ — Project State

## Project Reference

See: .planning/PROJECT.md and .planning/BACKLOG.md

**Core value:** Upload financials, answer a few questions, receive a first-draft professional financial report in minutes.
**Current focus:** Paid Valuation Advisory MVP feature slices.

## Roadmap Status

| Phase | Name | Status |
|-------|------|--------|
| 1 | Security & Auth Foundation | ✅ Complete (2026-05-06) |
| 2 | Multi-User Data Isolation | ✅ Complete |
| 3 | Business Profile Intake | ✅ Complete (2026-05-12) |
| 3.5 | Admin Gate + User Wizard Shell | ✅ Complete (2026-05-13) |
| 4 | Extraction Quality | ✅ Complete |
| 5 | Report Generation Engine | ✅ Implemented; review launch gaps |
| 6 | Payment Integration | 🟡 Checkout gate implemented; failure/refund paths remain |
| 7 | PDF Rendering & Delivery | 🟡 Web viewer and professional PDF export complete; domain wording review pending |

## Active Phase

**Paid Valuation Advisory MVP** - planning merged; implementation started with small PRs.

The primary UI now lives in `web/` as a Next.js App Router app. FastAPI remains the backend of record. The old `frontend/index.html` app is a disabled-by-default legacy fallback.

The working backlog lives at `.planning/BACKLOG.md`. The detailed implementation plan lives at `docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md`. Payment checkout gating and the technical admin review-before-release gate are merged. Professional PDF delivery is implemented and locally verified; purchase history, public offer page, and William's production approval/disclaimer review remain next.

Completed implementation slice:

- PR #10 / PVM-05: approved report owners can download a cached, branded A4 PDF with escaped narrative/table content and a per-page indicative-only disclaimer. Rendering runs outside the async event loop and writes atomically. The wizard preserves the active report across reloads so customers can resume the review/delivery state.

Next implementation slice:

- PVM-06: add customer account purchase history with report delivery status and viewer/PDF actions for released reports.

Latest verified checks:

- Backend pytest: 136 passed, 1 skipped
- `pnpm lint`
- `pnpm typecheck`
- `pnpm build`
- Focused PDF-delivery pytest: 4 passed
- Focused wizard Playwright: 2 passed, including reload/resume and PDF-link coverage
- WeasyPrint 69.0 visual check: branded 2-page A4 sample rendered and inspected

External parity review follow-up (2026-07-01):

- Fixed customer parity blockers: repeat upload resets the file input, valuation risk ratings are required, failed-report retry restarts polling, authenticated `/login` redirects to the correct app surface, and direct FastAPI report-viewer back links point at `APP_BASE_URL/wizard`.
- Fixed admin parity blockers: restored the Business Profile editor in the Next companies screen (sector, description, management team CRUD, EBITDA adjustment CRUD, completion badge, EBITDA bridge) and prevented Settings from overwriting the configured Claude model before async settings load completes.
- Expanded E2E coverage: admin profile completion is now covered; customer wizard covers repeat upload and valuation-specific intake.
- Remaining non-blocking admin polish gaps: Documents page still lacks the legacy company filter, narrative summary/logs actions, and FY/page/OCR metadata columns; Financials still lacks status-aware empty states for processing/failed documents; global admin nav does not yet surface the API-key warning outside Settings; admin upload does not display the backend-resolved `company_name` after auto-resolution.

Commercialization review (2026-07-01):

- Strongest wedge: launch a focused **Indicative SME Valuation + Exit Readiness Report** for NZ/AU owners and advisors, not all five report types at once.
- Best initial motion: productized service with automation underneath; manually review the first 20-50 paid reports before fully self-serve delivery.
- Highest launch gaps: Stripe payment gate, professional PDF artifact, purchase history, admin review-before-release queue, quality gates for missing profile/financial data, production legal/trust pages, and a public acquisition/pricing surface.
- Pricing hypothesis: free extraction/readiness teaser, $495 launch self-serve valuation moving toward $795-$995, $1,500-$2,500 advisor-reviewed valuation, and partner/broker bundles after pilot validation.

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-04 | Pay-per-report, single flat price | Matches infrequent, high-value use case |
| 2026-05-04 | Email notification when report ready | User doesn't wait on screen; better UX for 30-60s jobs |
| 2026-05-04 | Existing data kept as shared demo | Avoid data loss; useful for testing |
| 2026-05-04 | Extend existing stack (no rewrite) | Avoid migration cost; existing extraction already works |
| 2026-05-04 | First-draft quality bar | Makes accuracy achievable; professionals add value |
| 2026-05-06 | Phase 1 complete — auth wall, CORS, XSS, path-traversal all hardened | All 6 success criteria verified; 4 code review criticals documented for gap closure |
| 2026-05-07 | Phase 2 planned — 3 plans in 3 waves covering AUTH-07 and DATA-01 | DB migration → route filtering → integration tests; verification passed (0 blockers) |
| 2026-05-13 | Phase 3.5 complete — admin/wizard split, OWNER_EMAIL gate, require_admin on all 25 routes | AUTH-09 + UX-01 delivered; 49 tests passing; drag-and-drop added post-checkpoint |
| 2026-07-01 | Migrated primary frontend to Next.js App Router | Replaces single-file vanilla UI while preserving FastAPI uploads, extraction, reports, auth cookies, and SQLite writes |
| 2026-07-01 | Added deterministic Playwright E2E in dev and standalone modes | Validates auth, wizard, admin workflows, upload/report generation, report viewer escaping, and responsive smoke checks |
| 2026-07-01 | Narrow launch strategy to valuation wedge first | Paid launch should prove trust and willingness-to-pay with one high-value report before broadening to all five report families |
| 2026-07-12 | Persist the active report ID per authenticated user in the wizard | Customers must be able to resume a long-running review/delivery state after reload; report access remains owner-filtered by the backend |

---
## Session Continuity

Last session: 2026-07-12
Stopped at: PVM-05 complete in PR #10; PVM-06 account purchase history is next.
Resume file: docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md

---
*Initialized: 2026-05-04 | Next.js refactor merged: 2026-07-01 | Paid valuation plan merged: 2026-07-02*
