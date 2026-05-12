# Phase 3.5: Admin Gate + User Wizard Shell - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-12
**Phase:** 3.5 — Admin Gate + User Wizard Shell
**Areas discussed:** Wizard company model, Admin gate scope, Wizard visual style

---

## Wizard Company Model

| Option | Description | Selected |
|--------|-------------|----------|
| Ask for business name in step 1 | Wizard step 1 shows a 'Business name' field above the file upload. On submit, create company + upload in one call. User sees their business name in the confirmation screen. | ✓ |
| Auto-create silently | No business name asked. Backend creates a company named after the user's email on first upload. Cleaner UX, but low-quality data (no real business name stored). | |

**User's choice:** Ask for business name in step 1
**Notes:** Business name + file in one combined step 1 form ("Continue →" submits both). Company is created in the same API call as the upload via `POST /wizard/upload`.

---

## Admin Gate Scope

| Option | Description | Selected |
|--------|-------------|----------|
| New /wizard/* routes for non-admins | POST /wizard/upload handles company-create + doc-upload in one step for regular users. Existing /companies, /documents/* stay admin-only. Clean separation — wizard users never call admin API routes. | ✓ |
| Leave upload open, gate only browse/view routes | POST /documents/upload and POST /companies remain open to all users. Only GET list/browse endpoints become admin-only. Simpler, but leaks some admin surface to regular users. | |

**User's choice:** New /wizard/* routes for non-admins
**Notes:** All existing routes under /companies/*, /documents/*, /financials/*, /patterns/*, /analytics/*, /settings/* become admin-only (403). /wizard/upload is the only non-admin upload path.

---

## Wizard Visual Style

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing design system | Same --navy, --blue, --card CSS variables and card patterns. Wizard panel is a centered card with step indicators. Fast to build, consistent codebase. | ✓ |
| Cleaner minimal product look | New hero-style layout — large heading, minimal chrome, brand-forward. Feels more like a product landing page. Requires new CSS. | |

**User's choice:** Reuse existing design system
**Notes:** No new CSS tokens. Step indicator as simple "Step N of 3" text. Cards, form-groups, btn-primary all reused.

---

## Claude's Discretion

- 403 (not 404) for admin-gated routes — intentional exception to Phase 2 D-01 policy; admin route existence is not sensitive
- Wizard step ordering locked by roadmap: step 1 = upload+name, step 2 = report type, step 3 = confirmation
- Report type copy drafted by Claude (5 types with one-line descriptions) — locked in D-10 for Phase 5 consistency
- No back-button state management in v1; "Back" text button within wizard is sufficient
- `/wizard/upload` reuses `_run_ingestion` background task identically — no separate ingestion path

## Deferred Ideas

None — discussion stayed within phase scope.
