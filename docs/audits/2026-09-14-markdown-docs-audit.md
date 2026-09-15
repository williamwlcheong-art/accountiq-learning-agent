# Markdown docs audit, 2026-09-14

Every markdown file in the repo was checked against the working tree on branch `codex/nz-market-intelligence-review-fixes` (7 commits ahead of `main`, open as PR #26, which adds the NZ market intelligence layer, payment hardening, auth polish and the customer portal). Claims below were re-verified with grep and cat; findings the small-model pass got wrong were dropped (for example, it said PR #26 does not exist, but `gh pr list` shows it open).

Counts: 121 files reviewed. 39 stale, 4 superseded, 42 historical (fine as archives), 36 current.

## Flagged files

| Path | Verdict | What is wrong | Action |
|---|---|---|---|
| `AGENTS.md` | stale | Says "admin review, PDF delivery, purchase history, and full failure/refund handling remain", but `backend/report_rendering.py`, `web/app/reports/page.tsx` and the refund path in `backend/main.py` (line 1833) all exist; test counts read "116 passed" and "10 passed" while pytest collects 331 and Playwright has 15 test declarations. | Rewrite the Current Status section and refresh the verified checks. |
| `README.md` | stale | "As of 2026-07-02, the Next.js refactor has been merged" is the only status line and predates PVM-04 to PVM-10. | Replace with a one-line pointer to `.planning/BACKLOG.md` plus today's date. |
| `.planning/PROJECT.md` | stale | Line 90 says "PR #21 is open"; PR #21 merged on 2026-07-22 and PRs #22 to #25 merged since; footer still reads "Last updated: 2026-07-22". | Update the PR references, add the customer portal and market intelligence work, redate. |
| `.planning/STATE.md` | stale | `last_updated: 2026-07-22`; nothing about PVM-09, PVM-10 or PR #26. | Add a session continuity entry for the current branch. |
| `.planning/BACKLOG.md` | stale | "Last updated: 2026-09-01" but the PVM-10 row was added today (commit 3d0224d). Status rows are correct. | Fix the date line only. |
| `.planning/REQUIREMENTS.md` | stale | All 32 requirement boxes are unchecked although phases 1 to 5.1 and the paid valuation MVP are done; DATA-01 still describes shared demo data, which contradicts decision D-01 in phase 2. | Tick completed requirements, correct DATA-01, mark REPT-02 to REPT-05 as adviser pilots. |
| `.planning/codebase/ARCHITECTURE.md` | stale | Line 116: "`cd web && npm run dev`"; the project uses pnpm. | Replace npm with pnpm. |
| `.planning/codebase/STACK.md` | stale | "Python 3.13" (venv is 3.12.13), pinned versions that do not match requirements.txt, nine `npm run` commands, and no mention of `stripe==12.5.0` or `weasyprint==69.0`. | Refresh versions from requirements.txt, add Stripe and WeasyPrint, use pnpm. |
| `.planning/codebase/TESTING.md` | stale | `npm run typecheck` and the other npm commands should be pnpm. | Replace npm with pnpm. |
| `.planning/codebase/CONCERNS.md` | stale | Missing features list (lines 58 to 60) still names Stripe gating, PDF rendering and report history; all three ship in `backend/payments.py`, `backend/report_rendering.py` and `web/app/reports/page.tsx`. | Delete those three items and note the remaining ones. |
| `.planning/codebase/INTEGRATIONS.md` | stale | Line 51: "The application is single-user/local-only with no login system"; auth, Stripe, WeasyPrint and the admin review routes are all live. | Rewrite; this is the most out-of-date codebase doc. |
| `.planning/codebase/STRUCTURE.md`, `CONVENTIONS.md` | current | No issues found. | Keep. |
| `.planning/research/SUMMARY.md` | stale | Recommends "FastAPI + SQLite + Vanilla JS" and `python-jose` + `passlib`; the app uses Next.js, `pyjwt` and `pwdlib[argon2]`. | Add an archived banner pointing to `NEXT_BACKEND_SPLIT.md`. |
| `.planning/research/STACK.md` | stale | Same as SUMMARY: vanilla JS stack, python-jose, passlib, and "do not add Next.js". | Archived banner. |
| `.planning/research/ARCHITECTURE.md` | stale | Diagram shows passlib and python-jose; frontend described as `frontend/index.html`. | Archived banner. |
| `.planning/research/FEATURES.md` | stale | Report type names (`valuation`, `bank_credit`, `forecast`) differ from the API values (`valuation_advisory`, `bank_credit_paper`, `financial_forecast`). | Archived banner. |
| `.planning/commercial/LAUNCH-GATES.md` | stale | Line 14: "The database has no implemented cancelled, refund_needed, or refunded purchase or report path", yet `backend/main.py` handles `status == "refunded"`; line 16 cites an unmerged `feature/fcff-assumptions` branch that no longer exists (FCFF landed in PRs #19 to #21); "All eight gates are open" is dated 2026-07-20. | Re-assess each gate after PR #26 merges and redate. |
| `.planning/commercial/COMMERCIAL-ASSUMPTIONS.md` | historical | Draft pricing assumptions from 2026-07-01, correctly labelled as draft. | Keep, add archived banner. |
| `docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md` | stale | Line 3: "PVM-01 through PVM-03 are implemented on main"; PVM-01 to PVM-08 are merged and PVM-09 and PVM-10 are in PR #26. | Fix the execution status line. |
| `docs/superpowers/plans/2026-07-01-nextjs-refactor-final.md` | stale | "backend/main.py, 1,794 lines" and "37 operations"; today it is 3,326 lines and 49 routes. | Archived banner; the refactor itself is done. |
| `docs/superpowers/plans/2026-07-01-marketing-site-offer.md` | superseded | Plans `web/lib/marketingCopy.ts`, `web/lib/analytics.ts` and `web/components/marketing/`, none of which exist; PVM-07 shipped one page at `web/app/valuation/page.tsx`. | Archived banner pointing to the 2026-07-12 design. |
| `docs/superpowers/plans/2026-07-13-public-valuation-offer.md` | stale | Written as a forward plan but every step is ticked and PVM-07 merged as PR #12. | Archived banner. |
| `docs/superpowers/plans/2026-07-01-commercial-mvp-architecture.md` | stale | Says "Planning output completed" while the body is a task list with unchecked boxes; the real output is `.planning/commercial/ARCHITECTURE-DECISIONS.md`. | One-line note that this is the method guide, not the decision record. |
| `docs/superpowers/plans/2026-07-01-commercial-mvp-launch-gates-and-assumptions.md` | stale | "Completed planning artifact" reads as if gates are resolved; all eight remain open per LAUNCH-GATES.md. | One-line clarification. |
| `docs/superpowers/specs/2026-07-01-commercial-mvp-roadmap-context.md` | stale | Line 178 lists report states (`uploaded`, `validated`, `awaiting_payment`, `generating`, `approved`, `delivered`) that were never implemented; line 231 says "default to Postgres" while the app runs on SQLite. | Replace the state list with the real one or delete it. |
| `docs/superpowers/specs/2026-07-01-marketing-site-offer-spec.md` | superseded | Six-page site at "NZD 2,250 + GST" with CTAs to `/signup?intent=...`; the shipped page publishes no price (E2E asserts it) and links to `/login?mode=register`. | Archived banner; superseded by `2026-07-12-public-valuation-offer-design.md`. |
| `docs/audits/2026-08-16-full-app-customer-journey-audit.md` | stale | P0 "wizard redirects to Stripe before saving the report identifier" was fixed by the idempotency key in commit abab6b5; the dashboard gap closed in cc91039. Still true: four "Coming later" products in `report-type-picker.tsx` and a 631-line `intake-form.tsx`. | Archived banner; carry the two open items into BACKLOG (they are already in the PVM-10 row). |
| `.impeccable/critique/2026-09-01T19-24-44Z__web-app.md` | stale | Four items carry "[fixed]"; P1 items 4 and 5 (intake split, product picker) and P2 item 6 are still open. | Mark which items are still open, or leave as a dated snapshot. |
| `.planning/phases/01-security-auth-foundation/01-VALIDATION.md` | stale | `status: draft` with every validation row pending, although 01-VERIFICATION passed 6/6 on 2026-05-06. | Set status complete. |
| `.planning/phases/01-security-auth-foundation/01-REVIEW.md` | stale | `status: issues_found` with four criticals; CR-03 is still true (`main.py:1311` returns `"env_file": str(ENV_PATH)`) and `create_access_token` still has no SECRET_KEY guard. Phase was closed anyway. | Record the deferral decision or open follow-up tasks. |
| `.planning/phases/02-multi-user-data-isolation/02-VALIDATION.md` | stale | `status: draft`, `wave_0_complete: false`, all rows pending; 02-VERIFICATION passed 13/13. | Set status complete. |
| `.planning/phases/02-multi-user-data-isolation/02-REVIEW.md` | stale | Frontmatter says `status: fixed` but line 24 says `Status: issues_found` and the body describes blockers in the present tense. | Update the body to match the frontmatter. |
| `.planning/phases/03-business-profile-intake/03-VALIDATION.md` | stale | `status: draft`, `wave_0_complete: false`; `tests/test_profile.py` passes. | Set status complete. |
| `.planning/phases/03-business-profile-intake/03-CONTEXT.md` | stale | D-04 and line 89 place the UI in `frontend/index.html`; product UI now lives in `web/`. | Add a migration note. |
| `.planning/phases/03-business-profile-intake/03-PATTERNS.md`, `03-UI-SPEC.md` | stale | Both describe the vanilla JS UI only. | Archived banner. |
| `.planning/phases/03-5-admin-gate-wizard-shell/03-5-VALIDATION.md` | stale | `status: draft`, `wave_0_complete: false`; all three plans completed 2026-05-13. | Set status complete. |
| `.planning/phases/03-5-admin-gate-wizard-shell/03-5-REVIEW.md` | current, open findings | Status is honest, but CR-02 (no SECRET_KEY guard) and CR-04 (`file.filename` None) are still unfixed four months on. | Open follow-up tasks or record deferral. |
| `.planning/phases/04-extraction-quality/04-REVIEW.md` | stale | Marked complete elsewhere but CR-01 still stands (`rule_extractor.py:297` indexes `scores[best_idx]` when `scores` can be empty) and CR-03 still stands (`ingestion.py:379` uses `asyncio.get_event_loop()`). | Fix the two small bugs or record deferral. |
| `.planning/phases/05-report-intake-questionnaires-generation-engine/05-CONTEXT.md` | stale | "Status: Ready for planning"; the phase shipped 2026-05-22 and phase 05.1 replaced it. | Archived banner. |
| `.planning/phases/05-report-intake-questionnaires-generation-engine/05-REVIEW.md` | stale | `status: issues_found`, but CR-01 (`report_email.py:160` now uses `run_in_executor`) and CR-03 (`main.py:1624` isinstance check) are fixed. | Mark fixed, archive. |
| `.planning/phases/05-report-intake-questionnaires-generation-engine/05-HUMAN-UAT.md` | stale | Three UAT cases still "[pending]" since 2026-05-24; never run, replaced by the synthetic rehearsal in PVM-08. | Archived banner. |
| `.planning/phases/05-5-valuation-advisory-redesign/05-5-CONTEXT.md` | superseded | Pre-execution copy of `05.1-CONTEXT.md` (131 diff lines) with "Status: Ready for planning". | Delete the `05-5` folder. |
| `.planning/phases/05-5-valuation-advisory-redesign/05-5-DISCUSSION-LOG.md` | superseded | Near-duplicate of `05.1-DISCUSSION-LOG.md`. | Delete with the folder. |
| `.planning/phases/05.1-valuation-advisory-redesign/05.1-CONTEXT.md` | stale | Status line says "PR #21 Python-owned deterministic valuation tables open"; #21 merged and the rehearsal (PRs #24, #25) is done. | Update the status line. |
| `.planning/phases/05.1-valuation-advisory-redesign/05.1-03-PLAN.md` | current, no summary | Work landed in commit 776b639 but `05.1-03-SUMMARY.md` was never written. | Write the summary. |
| `.planning/phases/05.1-valuation-advisory-redesign/05.1-VALIDATION.md` | stale | `status: draft`, `wave_0_complete: false`; all five Wave 0 test files exist and pass. | Set status complete. |
| `.planning/phases/05.1-valuation-advisory-redesign/05.1-04-PLAN.md`, `05.1-04-SUMMARY.md`, `05.1-UI-SPEC.md` | historical | Target `frontend/index.html`; the human-verify checkpoint in the summary was never closed and is now moot. | Archived banner. |
| `.planning/phases/03-5-admin-gate-wizard-shell/03-5-03-SUMMARY.md` | historical | "awaiting human verification" checkpoint from 2026-05-13 never closed. | One-line note that the checkpoint is obsolete. |

## Historical phase artifacts that are fine as archives

These directories hold context, research, discussion logs, patterns and execution summaries. They describe what happened at the time and make no current-state claims beyond the files flagged above.

- `.planning/phases/01-security-auth-foundation/` (CONTEXT, DISCUSSION-LOG, PATTERNS, RESEARCH, UI-SPEC, four SUMMARY files, VERIFICATION)
- `.planning/phases/02-multi-user-data-isolation/` (CONTEXT, three SUMMARY files, PATTERNS, RESEARCH, DISCUSSION-LOG, VERIFICATION)
- `.planning/phases/03-business-profile-intake/` (three SUMMARY files, DISCUSSION-LOG, RESEARCH)
- `.planning/phases/03-5-admin-gate-wizard-shell/` (CONTEXT, three PLAN and three SUMMARY files, DISCUSSION-LOG, PATTERNS, RESEARCH)
- `.planning/phases/04-extraction-quality/` (CONTEXT, three SUMMARY files, RESEARCH, PATTERNS, DISCUSSION-LOG, VERIFICATION, HUMAN-UAT)
- `.planning/phases/05-report-intake-questionnaires-generation-engine/` (four SUMMARY files, DISCUSSION-LOG, VALUATION-ALGORITHM)
- `.planning/phases/05.1-valuation-advisory-redesign/` (01 and 02 SUMMARY, AI-SPEC, DISCUSSION-LOG, PATTERNS, RESEARCH, PVM-08-UAT)
- `.planning/phases/999.1-public-facing-commercial-funnel-advisor-review/` (CONTEXT is current)
- `.impeccable/critique/` (the two earlier critiques are dated snapshots)

## Duplicates and contradictions

- `.planning/phases/05-5-valuation-advisory-redesign/` and `.planning/phases/05.1-valuation-advisory-redesign/` cover the same phase. The `05-5` folder is the pre-execution copy and should go.
- `docs/superpowers/plans/2026-07-01-marketing-site-offer.md` plus `docs/superpowers/specs/2026-07-01-marketing-site-offer-spec.md` describe a six-page site that was never built; `docs/superpowers/specs/2026-07-12-public-valuation-offer-design.md` and `docs/superpowers/plans/2026-07-13-public-valuation-offer.md` describe what shipped.
- `.planning/research/STACK.md` and `SUMMARY.md` recommend python-jose and passlib; `requirements.txt` has `pyjwt==2.12.1` and `pwdlib[argon2]==0.3.0`.
- `.planning/REQUIREMENTS.md` DATA-01 says existing data is "visible as shared demo data"; phase 2 decision D-01 and the code make it invisible. 02-VERIFICATION already notes this.
- `AGENTS.md` says four MVP features "remain"; `.planning/BACKLOG.md` marks them done. BACKLOG is right.
- `.planning/commercial/LAUNCH-GATES.md` says there is no refund path; `backend/main.py` has one.
- Five VALIDATION files say `status: draft` while the matching VERIFICATION files say passed.
- `02-REVIEW.md` frontmatter says fixed, body says issues found.
- Three code reviews (01, 03-5, 04) list critical findings that are still in the code while ROADMAP and STATE mark those phases complete.

## Suggested cleanup, by value

1. Rewrite the Current Status block in `AGENTS.md` and the status line in `README.md`. Every agent reads these first and both are wrong about what is built.
2. Rewrite `.planning/codebase/INTEGRATIONS.md` and trim the missing features list in `CONCERNS.md`; swap npm for pnpm and fix the Python version in `STACK.md`, `ARCHITECTURE.md` and `TESTING.md`.
3. Fix the two live bugs the 04 review still points at: guard the empty `scores` list in `backend/rule_extractor.py:297` and replace `get_event_loop()` in `backend/ingestion.py:379`. Then decide on the 01 and 03-5 review criticals (SECRET_KEY guard, `env_file` disclosure, `file.filename` None) and record it.
4. Update `.planning/PROJECT.md`, `STATE.md` and `05.1-CONTEXT.md` to say PR #21 merged and PR #26 is in review; fix the BACKLOG date line.
5. Re-assess `.planning/commercial/LAUNCH-GATES.md` once PR #26 merges; the refund and FCFF claims are already false.
6. Tick `.planning/REQUIREMENTS.md` and set the five VALIDATION files to complete.
7. Delete `.planning/phases/05-5-valuation-advisory-redesign/`.
8. Add a one-line archived banner to the four research docs, the two marketing site docs, the three 2026-07-01 plan docs, the 2026-08-16 audit, and the phase 3 and 5.1 legacy UI specs.
9. Write `05.1-03-SUMMARY.md`.
