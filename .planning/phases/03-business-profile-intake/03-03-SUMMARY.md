---
phase: 03-business-profile-intake
plan: "03"
subsystem: frontend-profile-ui
tags:
  - vanilla-js
  - accordion-ui
  - crud-forms
  - ebitda-bridge
  - xss-safe
dependency_graph:
  requires:
    - 03-02  # all 11 backend profile routes (management-team, ebitda-adjustments, profile-status, profile patch)
  provides:
    - profile accordion UI on Companies tab
    - completion badge (N/4 complete) per company row
    - Industry picker (D-04 canonical 15-item list)
    - Description textarea with live char counter and 50-char validation
    - Management Team CRUD (add/edit/remove, inline form, window.confirm)
    - EBITDA Add-Backs CRUD with running EBITDA bridge
    - apiDelete helper (DELETE, returns bool, no .json() on 204)
  affects:
    - Phase 5 report generation gate (companies tab now shows can_generate readiness visually)
tech_stack:
  added: []
  patterns:
    - createElement + .textContent for all user/AI content (no .innerHTML for user data)
    - Promise.all for parallel panel data fetch (management-team + ebitda-adjustments + profile-status)
    - window.__companiesCache for company context in loadProfilePanel without re-fetch
    - raw fetch with method: PUT for edit operations (apiPost is POST-only)
    - apiDelete returns bool, never calls .json() on 204 No Content responses
    - badge threshold: 0=amber (badge-profile-empty), 1-3=blue (badge-profile-partial), 4=green (badge-profile-complete)
key_files:
  created: []
  modified:
    - frontend/index.html
decisions:
  - INDUSTRY_OPTIONS canonical 15-item D-04 list hardcoded as JS constant; legacy free-text sector falls back to empty string (Pitfall 4)
  - loadCompanies extended (not rewritten) to add badge column and accordion row per company
  - renderEbitdaBridge re-called via loadProfilePanel after every add/edit/remove to prevent stale bridge (Pitfall 3)
  - PUT requests use raw fetch (not apiPost) since apiPost is POST-only; 401 handled inline
  - window.confirm() used for destructive confirmations — plain text, no XSS vector
metrics:
  duration: "25 minutes"
  completed_date: "2026-05-08"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 1
---

# Phase 3 Plan 3: Profile Accordion UI Summary

**One-liner:** Vanilla JS profile accordion UI wired into Companies tab — completion badges, industry picker, description field, management team CRUD, and EBITDA bridge, all rendered via .textContent with no innerHTML on user data.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add CSS, INDUSTRY_OPTIONS constant, apiDelete helper, and update Companies table markup | 06744e1 | frontend/index.html |
| 2 | Extend loadCompanies + add profile accordion functions (toggle, load, save, member CRUD, adjustment CRUD, EBITDA bridge) | 8b6242e | frontend/index.html |

## Changes Made

### New Functions Added

| Function | Type | Purpose |
|----------|------|---------|
| `toggleProfilePanel(companyId)` | sync | Opens/closes accordion; closes all other panels first |
| `_findCachedCompany(companyId)` | sync | Looks up company data from `window.__companiesCache` |
| `loadProfilePanel(companyId)` | async | Parallel-fetches management-team + ebitda-adjustments + profile-status; builds full panel via createElement |
| `_sectionWrapper(titleText)` | sync | Shared helper that returns a `.profile-section` div with `.profile-section-title` |
| `_renderIndustrySection(companyId, company)` | sync | Builds industry select with D-04 options; pre-populates if sector is in canonical list |
| `saveIndustry(companyId)` | async | POSTs sector to `/companies/{id}/profile`; refreshes badge via loadCompanies |
| `_renderDescriptionSection(companyId, company)` | sync | Builds textarea with live char counter (N / 50 minimum → N characters when >=50) |
| `saveDescription(companyId)` | async | Validates >=50 chars client-side; POSTs description; refreshes badge |
| `_renderManagementTeamSection(companyId, members)` | sync | Renders list of members with Add/Edit/Remove controls |
| `_renderMemberItem(companyId, m)` | sync | Single inline-list-item for a team member |
| `_showAddMemberForm(companyId)` | sync | Calls `_showMemberForm(companyId, null)` |
| `_showEditMemberForm(companyId, member)` | sync | Calls `_showMemberForm(companyId, member)` with existing data |
| `_showMemberForm(companyId, existing)` | sync | Builds Name/Title/Bio form; Add Member uses apiPost, Edit uses raw PUT fetch |
| `removeMember(companyId, memberId, memberName)` | async | window.confirm → apiDelete → refreshes panel and badge |
| `_renderEbitdaSection(companyId, adjustments, status)` | sync | Renders add-backs list + Add Adjustment button + EBITDA bridge |
| `_formatAmount(v)` | sync | Returns a span: positive → `$N,NNN`, negative → `($N,NNN)` in var(--red) |
| `_renderAdjustmentItem(companyId, a)` | sync | Single inline-list-item for an EBITDA adjustment |
| `_showAdjustmentForm(companyId, existing)` | sync | Builds Label/Amount/Rationale form; Add uses apiPost, Edit uses raw PUT fetch |
| `removeAdjustment(companyId, adjId, label)` | async | window.confirm → apiDelete → refreshes panel (list + bridge) and badge |
| `renderEbitdaBridge(container, status, adjustments)` | sync | Builds EBITDA bridge: placeholder if no financials, else Reported EBITDA + adjustments + Normalised total |

### CSS Classes Added

| Class | Purpose |
|-------|---------|
| `.profile-panel-row` | Hidden by default (`display: none`) |
| `.profile-panel-row.open` | Shown as table-row when accordion is open |
| `.profile-panel-td` | Zero padding, 2px border-bottom, wraps the inner panel div |
| `.profile-panel-inner` | 1.5rem/1rem padding, white background |
| `.profile-section` | 1.5rem bottom margin between sub-sections |
| `.profile-section-title` | 0.8rem uppercase semibold muted label for each sub-section |
| `.profile-section-title.flex` | flex layout for section headers with right-aligned "+ Add" buttons |
| `.badge-profile-complete` | Green badge (4/4) |
| `.badge-profile-partial` | Blue badge (1-3/4) |
| `.badge-profile-empty` | Amber badge (0/4) |
| `.ebitda-bridge` | Light grey container for the EBITDA bridge table |
| `.ebitda-bridge table` | Full-width, 0.875rem, border-collapse |
| `.ebitda-bridge td` | 4px 8px padding |
| `.ebitda-bridge .bridge-total td` | Bold, blue, top border for the Normalised EBITDA row |
| `.inline-list-item` | Flex row for member/adjustment items |
| `.inline-list-item .item-body` | Flex-1, min-width:0 to prevent overflow |
| `.inline-list-item .item-actions` | Flex with 4px gap for Edit/Remove buttons |

### Badge Thresholds

| sections_complete | Class | Color | Copy |
|-------------------|-------|-------|------|
| 0 | `.badge-profile-empty` | Amber (`--amber`) | `0/4 complete` |
| 1, 2, or 3 | `.badge-profile-partial` | Blue (`--blue`) | `N/4 complete` |
| 4 | `.badge-profile-complete` | Green (`--green`) | `4/4 complete` |

### loadCompanies Extension

The existing `loadCompanies` function was extended (not rewritten) with:
1. `window.__companiesCache = data` — caches fetched companies for panel use without extra API calls
2. Profile completion badge `<td>` — inserted before the action column
3. "Edit Profile" button alongside "Upload PDF" in the action `<td>`
4. Accordion `<tr class="profile-panel-row">` inserted immediately after each company row

### XSS Safety Confirmation

No `.innerHTML` is used for any user-supplied content. All name/title/bio/label/rationale/sector/description values are set via:
- `element.textContent = value` (primary pattern)
- `document.createTextNode(value)` (for text node insertion)

The `window.confirm()` calls use string concatenation to build confirmation messages — this is safe because `confirm()` displays plain text (no HTML rendering).

Verified by grep:
- `grep -E "innerHTML\s*=" frontend/index.html | grep -E "m\.|a\.|c\."` — returns only static HTML strings, no user variable interpolation
- `.textContent = m.*` count: 3 (name, title, bio)
- `.textContent = a.*` count: 2 (label, rationale)

## Deviations from Plan

None — plan executed exactly as written. All functions, CSS classes, copy strings, and XSS constraints implemented per specification.

## Known Stubs

None. All four sub-sections are fully wired to the backend endpoints from Plan 02.

- Industry picker calls `POST /companies/{id}/profile` with `{sector}` — WIRED
- Description saves call `POST /companies/{id}/profile` with `{description}` — WIRED
- Management team CRUD calls `GET/POST/PUT/DELETE /companies/{id}/management-team[/{id}]` — WIRED
- EBITDA adjustments CRUD calls `GET/POST/PUT/DELETE /companies/{id}/ebitda-adjustments[/{id}]` — WIRED
- EBITDA bridge reads from `GET /companies/{id}/profile-status` for `reported_ebitda` and `has_financials` — WIRED

## Threat Surface Scan

No new network endpoints beyond those in the plan's threat_model. No new trust boundaries.

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-03-01 | All user content via .textContent — confirmed by grep. No innerHTML for m.name, m.title, m.bio, a.label, a.rationale. |
| T-03-03 | Backend returns 404 for unowned companies; frontend always uses JWT cookie via credentials:include |
| T-03-04 | apiDelete includes credentials:include and calls showAuthWall(true) on 401 |

## Human Verify Checkpoint

**Status:** APPROVED — all 13 verification steps passed (2026-05-12)

The full profile accordion UI is implemented and ready for browser verification. The dev server command is:

```bash
source venv/bin/activate && cd backend && uvicorn main:app --reload --port 8765
```

Then visit `http://localhost:8765/app` and verify the 13 steps in the plan's `<how-to-verify>` section.

## Self-Check: PASSED

- [x] `frontend/index.html` modified — commits 06744e1 and 8b6242e verified
- [x] All 20 new functions present in frontend/index.html
- [x] All 16 new CSS classes present in frontend/index.html
- [x] INDUSTRY_OPTIONS constant with all 15 D-04 industries present
- [x] apiDelete helper present — returns bool, never calls .json()
- [x] Companies table thead has "Profile" column (colspan verified at 8)
- [x] No innerHTML for user-supplied content
- [x] All copywriting contract strings present (Industry saved., Description saved., Team member added., etc.)
- [x] window.confirm() present for both member and adjustment removal (2 occurrences)
- [x] renderEbitdaBridge called both on initial render and after every adjustment change
- [x] Backend test suite: 30 passed, 1 skipped (no regression)
