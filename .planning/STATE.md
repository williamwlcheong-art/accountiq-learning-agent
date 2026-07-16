---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Valuation-first report pack work in progress on top of the merged Next.js refactor
stopped_at: Valuation-first intake, demo mode, browser report, PDF artifact and report-quality gates are active in the current worktree; launch/commercial gates remain
last_updated: "2026-07-07T00:00:00+12:00"
progress:
  total_phases: 9
  completed_phases: 5
  total_plans: 21
  completed_plans: 20
  percent: 95
---

# AccountIQ — Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-05)

**Core value:** Upload financials, answer a few questions, receive a first-draft professional financial report in minutes.
**Current focus:** Valuation-first report experience and paid Valuation Advisory MVP feature slices.

## Roadmap Status

| Phase | Name | Status |
|-------|------|--------|
| 1 | Security & Auth Foundation | ✅ Complete (2026-05-06) |
| 2 | Multi-User Data Isolation | ✅ Complete |
| 3 | Business Profile Intake | ✅ Complete (2026-05-12) |
| 3.5 | Admin Gate + User Wizard Shell | ✅ Complete (2026-05-13) |
| 4 | Extraction Quality | ✅ Complete |
| 5 | Report Generation Engine | ✅ Implemented; review launch gaps |
| 6 | Payment Integration | ⬜ Not started |
| 7 | PDF Rendering & Delivery | 🟡 Valuation browser/PDF report pack implemented in active worktree; production delivery flow still pending |

## Active Phase

**Paid Valuation Advisory MVP** - valuation-first implementation in progress in the active worktree.

The primary UI now lives in `web/` as a Next.js App Router app. FastAPI remains the backend of record. The old `frontend/index.html` app is a disabled-by-default legacy fallback.

The implementation plan lives at `docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md`. The current valuation-report specification lives at `docs/valuation-report-input-spec.md`.

Active worktree progress:

- Valuation Advisory is the only active self-serve report journey; other report families remain visible as coming-soon options rather than routing users into unrelated questionnaires.
- The wizard waits for extraction, then asks five required private valuation answers with progressive disclosure, a live required-answer checklist, optional public-source hints, optional private context, optional expert overrides, and a separate earnings-adjustment review.
- Local no-key demo mode is explicit via `ACCOUNTIQ_DEMO_MODE=true` or `scripts/start-demo-backend.sh`; live mode without a real Anthropic key fails before a report is queued instead of silently producing simulated work.
- The valuation report pack now includes a professional browser report and PDF artifact with cover, contents, formal report-letter/basis-of-preparation front matter, default AccountIQ valuation-team prepared-by identity, numbered sections, valuation snapshot, DCF/WACC/multiples/sensitivity content, source trail, management-input trail, demo labelling, and artifact audits.
- The browser report view is now treated as a first-class review surface for the valuation pack, not a temporary fallback; the route/OpenAPI description and regression coverage use this framing.
- Deterministic sample artifacts can be generated with `scripts/generate_sample_valuation_html.py` and `scripts/generate_sample_valuation_pdf.py`; the generators now run structured-content audits before rendering and rendered HTML/PDF audits after writing, while `scripts/audit_valuation_report.py` remains the explicit audit tool for saved artifacts and live-smoke outputs.
- Goal completion audit is captured in `docs/valuation-report-goal-audit.md`; structural example parity is captured in `docs/valuation-example-parity-checklist.md`; the current rendered AccountIQ visual review pack is generated at `output/html/valuation-visual-parity-review.html`, can accept original-report page images through `--reference-manifest`, and can generate a fill-in reference manifest template; completion is not yet claimed because mapped original-PDF side-by-side review and live provider-backed smoke evidence remain open.

Launch/commercial gaps still open:

- Stripe payment gate.
- Admin review-before-release queue and manual approval workflow.
- Purchase history/account surfaces.
- Production legal/trust pages and public acquisition/pricing surface.
- Production deployment hardening and end-to-end paid delivery flow.

Latest verified checks:

- Backend pytest from merged refactor baseline: 116 passed, 1 skipped, 1 xpassed
- Valuation report rendering/quality/PDF focused suite: 219 passed
- Report prompt/generation validation suite: 60 passed
- Local demo/admin/wizard focused suite: 72 passed, 1 warning
- Latest focused browser/PDF delivery checks: `tests/test_report_viewer.py` 34 passed; `tests/test_pdf_delivery.py` 6 passed
- Generated deterministic sample valuation artifacts: `output/html/accountiq-demo-sample-indicative-valuation.html` and `output/pdf/accountiq-demo-sample-indicative-valuation.pdf`
- Artifact audits passed for the generated sample browser report and 29-page PDF; PDF audit confirmed 29/29 demo-labelled pages and no non-public source URLs
- Visual PDF preview rendered key pages under `tmp/pdfs/valuation-preview/` covering cover, contents, report-letter/basis front matter, DCF, sensitivity, specific risks, sources, disclaimer, general principles and glossary
- Current flow/static checks: `tests/test_wizard_endpoints.py` 53 passed, 1 Starlette warning; `npm run typecheck`; `npm run lint`; `npm run build`
- Current valuation wizard browser flow: `PLAYWRIGHT_BASE_URL=http://localhost:3001 PLAYWRIGHT_FRONTEND_URL=http://localhost:3001 PLAYWRIGHT_FRONTEND_COMMAND='npx next dev --port 3001' npx playwright test e2e/wizard.spec.ts --project=chromium` 4 passed
- Current full frontend E2E flow: `PLAYWRIGHT_BASE_URL=http://localhost:3001 PLAYWRIGHT_FRONTEND_URL=http://localhost:3001 PLAYWRIGHT_FRONTEND_COMMAND='npx next dev --port 3001' npm run test:e2e` 12 passed
- Playwright config now supports alternate frontend URLs via `PLAYWRIGHT_BASE_URL` / `PLAYWRIGHT_FRONTEND_URL`, so focused E2E can run without taking over a user's active `localhost:3000` session
- Goal audit artifact added: `docs/valuation-report-goal-audit.md`; example parity checklist added: `docs/valuation-example-parity-checklist.md`; visual parity review pack generated at `output/html/valuation-visual-parity-review.html`; fresh artifact audits passed for the deterministic demo HTML and 29-page PDF.
- Visual preview/pack focused verification: `venv/bin/python -m pytest tests/test_pdf_preview_renderer.py -q --tb=short` 11 passed; generated pack has 20 images, 22 links and no missing image references, and reference PDF/page map plus reference image-manifest template generation are covered.
- Latest sample-generator/report-quality gate: `tests/test_report_rendering.py tests/test_report_viewer.py tests/test_report_quality.py tests/test_sample_html_generator.py tests/test_sample_pdf_generator.py` 219 passed; deterministic HTML/PDF sample generation reran successfully with built-in structured and rendered artifact audits.
- Dev Playwright baseline: 10 passed
- Standalone production Playwright baseline: 10 passed
- Focused valuation wizard Playwright execution was rerun on alternate port 3001 while the user's active localhost app remained on port 3000.

External parity review follow-up (2026-07-01):

- Fixed customer parity blockers: repeat upload resets the file input, valuation risk ratings are required, failed-report retry restarts polling, authenticated `/login` redirects to the correct app surface, and direct FastAPI report-viewer back links point at `APP_BASE_URL/wizard`.
- Fixed admin parity blockers: restored the Business Profile editor in the Next companies screen (sector, description, management team CRUD, EBITDA adjustment CRUD, completion badge, EBITDA bridge) and prevented Settings from overwriting the configured Claude model before async settings load completes.
- Expanded E2E coverage: admin profile completion is now covered; customer wizard covers repeat upload and valuation-specific intake.
- Remaining non-blocking admin polish gaps: Documents page still lacks the legacy company filter, narrative summary/logs actions, and FY/page/OCR metadata columns; Financials still lacks status-aware empty states for processing/failed documents; global admin nav does not yet surface the API-key warning outside Settings; admin upload does not display the backend-resolved `company_name` after auto-resolution.

Commercialization review (2026-07-01):

- Strongest wedge: launch a focused **Indicative SME Valuation + Exit Readiness Report** for NZ/AU owners and advisors, not all five report types at once.
- Best initial motion: productized service with automation underneath; manually review the first 20-50 paid reports before fully self-serve delivery.
- Highest launch gaps: Stripe payment gate, purchase history, admin review-before-release queue, production legal/trust pages, public acquisition/pricing surface, and full production delivery hardening. The professional valuation browser/PDF artifact and quality gates are now present in the active worktree but still need final review before release.
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
| 2026-07-05 | Make local demo mode explicit rather than automatic | Allows no-key valuation-flow testing while preventing production from silently delivering simulated research or valuation figures |
| 2026-07-05 | Treat the browser report as a first-class valuation-pack review surface | The user experience needs browser review plus PDF delivery to feel like a professional report pack, not a temporary HTML fallback |

---
## Session Continuity

Last session: 2026-07-05
Stopped at: Valuation-first report pack work in progress; docs/spec/tests reflect no-key demo mode and professional browser/PDF output.
Resume files:

- docs/valuation-report-input-spec.md
- docs/valuation-report-goal-audit.md
- docs/valuation-example-parity-checklist.md
- output/html/valuation-visual-parity-review.html
- docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md

---
*Initialized: 2026-05-04 | Next.js refactor merged: 2026-07-01 | Paid valuation plan merged: 2026-07-02 | Valuation report pack WIP: 2026-07-05*
