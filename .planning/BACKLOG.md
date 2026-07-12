# AccountIQ Backlog

Last updated: 2026-07-12

This is the lightweight working backlog for the paid Valuation Advisory MVP. Keep the detailed implementation instructions in `docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md`; keep this file as the current source of truth for what is done, in progress, next, and waiting on domain review.

## Working Rules

- Keep `main` deployable.
- Land commercial MVP work as small PRs.
- Start each feature slice from latest `main`.
- Update this backlog when a PR opens, merges, or changes scope.
- Treat William as domain owner for accounting, banking-credit, valuation methodology, report language, and output quality.
- Treat Dave/Codex as technical owner for implementation, tests, delivery workflow, and integration.

## Current Focus

Paid Valuation Advisory MVP:

Customer uploads financials, completes valuation intake, pays, generation starts after confirmed payment, William/admin reviews the draft, then the customer can view and download the final report.

## Status Board

| ID | Item | Status | PR | Owner | Notes |
|----|------|--------|----|-------|-------|
| PVM-01 | Focus self-serve wizard on Valuation Advisory | Done | #5 | Technical | Merged to `main`; valuation is selectable and other report types are visible as Advisor pilot. |
| PVM-02 | Add payment job model and Stripe helpers | Done | #6 | Technical | Merged to `main`; adds `purchases`, Stripe config, price env vars, and checkout helper groundwork. |
| PVM-03 | Gate valuation generation behind checkout | Done | #7 | Technical | Merged to `main`; `pending_payment` -> Stripe Checkout -> webhook -> `queued`. |
| PVM-04 | Add admin review before customer delivery | Done | #8 | Technical + William | Merged to `main`; paid valuations enter `awaiting_review`, admins approve release, and reviewer identity/time are audited. William still owns the approval checklist/quality criteria. |
| PVM-05 | Add professional PDF export | Done | #10 | Technical + William | Branded A4 export, safe narrative/table rendering, approved owner-only download, caching, and resumable customer status are implemented and verified. William still owns final disclaimer wording. |
| PVM-06 | Add account purchase history | Done | #11 | Technical | Owner-filtered purchase API and account table show payment/delivery status; released reports expose viewer and PDF actions. Backend, build, and full browser regression gates pass. |
| PVM-07 | Add public valuation offer page | Pending | - | Product + Technical | Public pricing/offer page for the valuation wedge. |
| PVM-08 | Live report UAT with William | Pending | - | William + Technical | Validate live Claude output, assumptions, wording, and quality bar. |

## Next Three PRs

1. PVM-07: Add public valuation offer page.
2. PVM-08: Run live report UAT with William.
3. Define payment failure, cancellation, void, and refund states before live Stripe activation.

## William Review Queue

These should not be treated as purely technical decisions:

- Valuation report structure and professional wording.
- Risk/rating question language and scoring interpretation.
- WACC, DCF, multiple cross-check, and illiquidity assumptions.
- Admin approval criteria before a paid report is released.
- PDF disclaimer language and whether disclaimers must appear per-page.
- Pricing tiers and what is included in self-serve vs advisor-reviewed reports.

## Later Backlog

| ID | Item | Status | Notes |
|----|------|--------|-------|
| LATER-01 | Re-enable Bank Credit Paper self-serve | Later | Keep as Advisor pilot until valuation wedge proves quality and payment flow. |
| LATER-02 | Re-enable Forecast self-serve | Later | Needs quality gates and report-specific review. |
| LATER-03 | Re-enable Capital Raising self-serve | Later | Needs investor-document QA and likely stronger profile intake. |
| LATER-04 | Re-enable IM self-serve | Later | Likely advisor-assisted first. |
| LATER-05 | Admin polish gaps | Later | Documents filters/metadata, financial status-aware empty states, global API-key warning. |
| LATER-06 | CSS consolidation | Later | `web/app/globals.css` still has layered legacy shell styling; working but worth simplifying after paid MVP slices. |

## Definition Of Done For Feature PRs

- Small, focused PR from latest `main`.
- Backend tests pass when backend is touched.
- `pnpm lint`, `pnpm typecheck`, and `pnpm build` pass when web is touched.
- Relevant Playwright E2E passes.
- Backlog row updated if scope/status changes.
- Domain-sensitive changes are flagged for William review.
