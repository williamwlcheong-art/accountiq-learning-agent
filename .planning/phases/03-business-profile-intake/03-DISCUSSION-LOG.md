# Phase 3: Business Profile Intake - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 3-Business Profile Intake
**Areas discussed:** Profile data model, Industry taxonomy, EBITDA running total

---

## Profile data model

### Simple fields (description, industry)

| Option | Description | Selected |
|--------|-------------|----------|
| Extend companies table | Add description TEXT and industry TEXT columns directly to companies via ALTER TABLE. No extra join when fetching company + profile. | ✓ |
| New business_profiles table | 1:1 table keyed by company_id with own created_at/updated_at. Requires JOIN on every company read. | |
| JSON blobs on companies | Store management_team and ebitda_adjustments as JSON TEXT columns. Avoids new tables but makes individual row CRUD awkward. | |

**User's choice:** Extend companies table (recommended)
**Notes:** No additional notes.

### management_team fields

| Option | Description | Selected |
|--------|-------------|----------|
| Name + title + bio | name NOT NULL, title, bio. Bio used in IM and capital raising narrative. | ✓ |
| Name + title only | Skip bio — Phase 5 prompts list names and titles only. | |
| Name + title + bio + equity % | Add equity_pct REAL for founder equity split. | |

**User's choice:** Name + title + bio (recommended)
**Notes:** No additional notes.

### ebitda_adjustments fields

| Option | Description | Selected |
|--------|-------------|----------|
| Label + amount + rationale | label NOT NULL, amount NOT NULL, rationale. Rationale feeds into valuation narrative. | ✓ |
| Label + amount only | Skip rationale. Phase 5 uses generic justification. | |
| Label + amount + rationale + type | Add type ENUM (owner_compensation, non_recurring, related_party). | |

**User's choice:** Label + amount + rationale (recommended)
**Notes:** No additional notes.

### Existing sector column

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse sector column | Populate existing sector TEXT with categorised industry value. No migration for the column itself. | ✓ |
| Add new industry column | Keep sector as-is, add separate industry TEXT column. Allows two-level categorisation. | |
| Rename sector → industry | Requires table rebuild (SQLite doesn't support column rename). Too complex for the gain. | |

**User's choice:** Reuse sector column (recommended)
**Notes:** No additional notes.

---

## Industry taxonomy

### Which taxonomy

| Option | Description | Selected |
|--------|-------------|----------|
| Custom SME list | ~15 plain-English categories familiar to NZ/AU business owners. Phase 5 seeds multiples against these exact labels. | ✓ |
| GICS sectors | 11 standard sectors — designed for listed companies, too abstract for SME owners. | |
| ANZSIC codes | Hundreds of granular codes — too complex, SME owners won't know their code. | |

**User's choice:** Custom SME list (recommended)
**Notes:** No additional notes.

### Where it lives

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded in frontend | JS array of ~15 labels. No DB lookup, no admin needed. Phase 5 uses the same array. | ✓ |
| DB lookup table | New `industries` table seeded on startup. More extensible but overkill for v1 static list. | |

**User's choice:** Hardcoded in frontend (recommended)
**Notes:** No additional notes.

### Single vs two-level

| Option | Description | Selected |
|--------|-------------|----------|
| Single-level | One dropdown, ~15 categories. Easy to select and match for multiples. | ✓ |
| Two-level (industry → sub-sector) | More precise but adds UI complexity and requires more multiples data in Phase 5. | |

**User's choice:** Single-level (recommended)
**Notes:** No additional notes.

---

## EBITDA running total

### What the running total displays

| Option | Description | Selected |
|--------|-------------|----------|
| Full bridge | Reported EBITDA (from financial_rows) + Adjustments = Normalised EBITDA. Shows real adjusted number. Placeholder if no financials yet. | ✓ |
| Adjustments sum only | Show total adjustments only. Phase 5 handles the full bridge computation. | |
| Manual entry | Add 'Reported EBITDA' input field. Avoids querying financial_rows but redundant if financials uploaded. | |

**User's choice:** Full bridge (recommended)
**Notes:** No additional notes.

### Which period to use

| Option | Description | Selected |
|--------|-------------|----------|
| Most recent period | MAX(period) from financial_rows. Most relevant for normalisation. | ✓ |
| User-selectable period | Dropdown to pick year. Adds UI complexity. | |
| All periods, latest highlighted | Mini table with all years. Overkill — add-backs normalised against one base year. | |

**User's choice:** Most recent period (recommended)
**Notes:** No additional notes.

### EBITDA base calculation

| Option | Description | Selected |
|--------|-------------|----------|
| net_profit + depreciation add-back | Compute EBITDA = net_profit + depreciation_amortisation from financial_rows. Fallback to net_profit only if D&A missing. | ✓ |
| ebitda canonical key if present | Check for explicit 'ebitda' row_key first, fall back to net_profit + D&A. Depends on extractor surfacing EBITDA directly. | |
| net_profit only | Simplest base. Less accurate but avoids needing D&A extraction to be reliable. | |

**User's choice:** net_profit + depreciation add-back (recommended)
**Notes:** No additional notes.

---

## Claude's Discretion

- **Profile UI placement** — User did not select this area. Claude will use an inline accordion on the Companies tab: each company row gets an "Edit Profile" button that expands a profile section below it. Completion badge on the row shows "N/4 sections complete".
- **Sort ordering** — No drag-to-reorder; display order is insertion order (ORDER BY id ASC).
- **Validation** — Description 50-char minimum enforced frontend-only. Amount accepts negative values (some add-backs subtract). No server-side sign restriction.

## Deferred Ideas

None — discussion stayed within phase scope.
