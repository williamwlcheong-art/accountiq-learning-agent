---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: PRs #15 to #23 merged; synthetic Decimal FCFF rehearsal passed
stopped_at: Open and merge the synthetic rehearsal runner PR; live UAT requires explicit approval
last_updated: "2026-07-22T10:45:00+12:00"
progress:
  total_phases: 9
  completed_phases: 5
  total_plans: 21
  completed_plans: 20
  percent: 95
---

# AccountIQ - Project State

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

The working backlog lives at `.planning/BACKLOG.md`. The detailed implementation plan lives at `docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md`. Payment checkout gating, the technical admin review-before-release gate, professional PDF delivery, purchase history, and the public valuation offer are complete. William's live report UAT and production approval/disclaimer review follow.

Completed PVM-08A input-authority slices:

- PR #15 / PR 1A: immutable, hashed upload revisions and explicit `(company, statement, period)` authority. Only completed extractions qualify, failed replacements preserve prior authority, and unrelated overlaps surface conflicts.
- PR #16 / PR 1B: checkout freezes authoritative documents, financial rows, profile data, adjustments, and intake in a versioned snapshot. Generation and retry verify and consume only that snapshot.
- PR #17 / PR 2A: typed valuation inputs and the explicit EV-to-equity bridge.
- PR #18: UI polish.
- PR #19 / PR 3A: frozen FCFF assumptions, one active adviser-approved WACC set, schema 2 snapshots, admin WACC UI, and intake changes.
- PR #20 / PR 3B: deterministic Decimal FCFF, approved WACC scenarios, terminal value, EV-to-equity reconciliation, equity-level DLOM, and fail-closed numeric validation.
- PR #21 / PR 3C: all six structured valuation tables are Python-owned, display-rounded, digested, and authoritative at persistence while Claude supplies narrative only.

PR #22 is merged. It lets a customer submit current FCFF inputs for a failed paid pre-Decimal valuation, atomically replaces the old snapshot and intake, preserves the existing report and paid purchase, clears stale review/PDF state, and requeues without Stripe or a second payment.

PR #23 is merged. It removes a higher-specificity mobile purchase-table minimum width, allows long account details to wrap, and uses the supported horizontal Arrow key for the report-table keyboard check. The complete development and production Playwright suites pass.

The synthetic UAT fixture and guarded runner now cover complete confirmed FCFF assumptions, one active approved synthetic WACC set, schema 2 snapshots, `fcff-decimal-v1`, exact three-scenario equity reconciliation, and all six Python-owned valuation tables. The 2026-07-22 no-network rehearsal passed through real generation, persistence, admin-review gating, private HTML/PDF rendering, and immutable evidence with both external AI boundaries replaced by fixed synthetic outputs.

Current valuation sequence:

1. Open, review, and merge the synthetic rehearsal runner PR.
2. Run live Anthropic UAT only with separate explicit approval, then record William's domain disposition.
3. Close or explicitly waive launch gates for a private pilot.

Public payments remain blocked while all eight launch gates are open. Valuation is the only self-serve launch product. Bank credit papers, forecasts, capital raising documents, and information memorandums remain adviser pilots.

Latest verification for PR #23:

- Frontend: `pnpm typecheck`, `pnpm lint`, and `pnpm build` passed.
- Development Playwright: 17 passed.
- Standalone production Playwright: 17 passed.
- `git diff --check` passed.

Latest synthetic rehearsal verification:

- Focused UAT safety/runner suite: 19 passed.
- Full backend suite: 304 passed, 1 skipped.
- Standalone no-network rehearsal: passed with 10/10 checks, `awaiting_review`, private HTML/PDF, and immutable evidence outside the repository.
- Snapshot schema: `2`; valuation engine: `fcff-decimal-v1`.
- Decimal FCFF equity reconciliation: exact in all three scenarios.
- Python-owned deterministic tables: 6/6 matched their digested authority.
- External AI calls: none.

No live UAT has run.

Earlier per-PR verification:

- PR #15: focused authority/migration/profile/upload tests 30 passed; full backend 184 passed, 1 skipped.
- PR #16: backend 202 passed, 1 skipped; lint, typecheck, build, and both Playwright suites passed with 13 tests each.
- `git diff --check` passed for both slices.

Previous verified checks on `codex/pvm-08-live-report-uat`:

- Backend pytest: 169 passed, 1 skipped
- Focused UAT safety suite: 17 passed
- `pnpm lint`
- `pnpm typecheck`
- `pnpm build`
- Full dev Playwright: 13 passed
- Full production Playwright: 13 passed against `next start`
- `git diff --check`
- No database, PDF, credentials, or private UAT evidence in git status

External parity review follow-up (2026-07-01):

- Fixed customer parity blockers: repeat upload resets the file input, valuation risk ratings are required, failed-report retry restarts polling, authenticated `/login` redirects to the correct app surface, and direct FastAPI report-viewer back links point at `APP_BASE_URL/wizard`.
- Fixed admin parity blockers: restored the Business Profile editor in the Next companies screen (sector, description, management team CRUD, EBITDA adjustment CRUD, completion badge, EBITDA bridge) and prevented Settings from overwriting the configured Claude model before async settings load completes.
- Expanded E2E coverage: admin profile completion is now covered; customer wizard covers repeat upload and valuation-specific intake.
- Remaining non-blocking admin polish gaps: Documents page still lacks the legacy company filter, narrative summary/logs actions, and FY/page/OCR metadata columns; Financials still lacks status-aware empty states for processing/failed documents; global admin nav does not yet surface the API-key warning outside Settings; admin upload does not display the backend-resolved `company_name` after auto-resolution.

Commercialization review (2026-07-01):

- Strongest wedge: launch a focused **Indicative SME Valuation + Exit Readiness Report** for NZ/AU owners and advisors, not all five report types at once.
- Best initial motion: productized service with automation underneath; manually review the first 20 to 50 paid reports before fully self-serve delivery.
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
| 2026-05-06 | Phase 1 complete, auth wall, CORS, XSS, path-traversal all hardened | All 6 success criteria verified; 4 code review criticals documented for gap closure |
| 2026-05-07 | Phase 2 planned, 3 plans in 3 waves covering AUTH-07 and DATA-01 | DB migration → route filtering → integration tests; verification passed (0 blockers) |
| 2026-05-13 | Phase 3.5 complete, admin/wizard split, OWNER_EMAIL gate, require_admin on all 25 routes | AUTH-09 + UX-01 delivered; 49 tests passing; drag-and-drop added post-checkpoint |
| 2026-07-01 | Migrated primary frontend to Next.js App Router | Replaces single-file vanilla UI while preserving FastAPI uploads, extraction, reports, auth cookies, and SQLite writes |
| 2026-07-01 | Added deterministic Playwright E2E in dev and standalone modes | Validates auth, wizard, admin workflows, upload/report generation, report viewer escaping, and responsive smoke checks |
| 2026-07-01 | Narrow launch strategy to valuation wedge first | Paid launch should prove trust and willingness-to-pay with one high-value report before broadening to all five report families |
| 2026-07-12 | Persist the active report ID per authenticated user in the wizard | Customers must be able to resume a long-running review/delivery state after reload; report access remains owner-filtered by the backend |
| 2026-07-13 | Use early-access fixed-fee language without a public numeric valuation price | Conflicting planning figures are not approved marketing claims; checkout remains the source of the fee before payment |
| 2026-07-18 | Use typed valuation inputs and an explicit EV-to-equity bridge in PR 2A | Normalise supported units to whole currency units; require one currency and compatible annual periods; classify debt, unrestricted cash, and approved surplus assets explicitly; use reported EBITDA before same-period EBIT plus depreciation; keep FCFF corrections in PR 2B |
| 2026-07-19 | Sequence valuation corrections through PRs 3A, 3B, and 3C before service rehearsal | PR 3A freezes FCFF and adviser-approved WACC assumptions; PR 3B introduces Decimal FCFF; PR 3C makes valuation tables deterministic and Python-owned before any explicitly approved live Anthropic UAT |

---
## Session Continuity

Last session: 2026-07-22
Stopped at: PRs #15 to #23 are merged and the no-network synthetic rehearsal passes. Open and merge the rehearsal runner PR next; live Anthropic UAT remains blocked on separate explicit approval, followed by William's disposition and launch-gate closure/private pilot.
Resume file: .planning/phases/05.1-valuation-advisory-redesign/PVM-08-UAT.md

---
*Initialized: 2026-05-04 | Next.js refactor merged: 2026-07-01 | Paid valuation plan merged: 2026-07-02*
