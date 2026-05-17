# Phase 4: Extraction Quality - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 4-Extraction-Quality
**Areas discussed:** Statement type buckets, Multi-page coverage, Sign convention enforcement, Word doc extraction

---

## Statement Type Buckets

| Option | Description | Selected |
|--------|-------------|----------|
| Add 'cf' and 'eq' as new statement types | Cleanest separation; each row tagged to its source statement; clean filter targets for Phase 5 | ✓ |
| Keep only 'pnl' and 'bs', sub-key via canonical_key prefix | Avoids schema change but conflates two dimensions into one field | |

**User's choice:** Add 'cf' and 'eq' as new statement types

| Option | Description | Selected |
|--------|-------------|----------|
| Core operating CF only — 4 rows | operating_cashflow, investing_cashflow, financing_cashflow, net_change_in_cash | |
| Detailed CF breakdown | Sub-items like capex, dividends paid, proceeds from borrowings | |
| You decide | Claude picks the canonical CF rows | ✓ |

**User's choice:** You decide (Claude: 4 summary rows — standard indirect method)

| Option | Description | Selected |
|--------|-------------|----------|
| Succeed with empty cf rows — no failure | Extraction valid if only P&L and BS present | ✓ |
| Warn but succeed | Same but surfaced as extraction note | |

**User's choice:** Succeed with empty cf rows — no failure

---

## Multi-page Coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Include all pages scoring above zero, sorted by page index | Any page with at least one financial synonym included; continuation pages never cut | ✓ |
| Consecutive grouping — if page N is selected, always include N+1 | Catches more continuation pages but may include irrelevant pages | |
| Top-N pages only, N configurable | Less precise — doesn't guarantee continuation pages are always included | |

**User's choice:** Include all pages scoring above zero, sorted by page index

| Option | Description | Selected |
|--------|-------------|----------|
| Still truncate at 60K, lowest-scored pages dropped first | Keeps budget cap; truncation only hits edge cases | ✓ |
| Raise budget cap to 80K or 100K | More cost per extraction | |
| You decide | | |

**User's choice:** Still truncate at 60K, lowest-scored pages dropped first

| Option | Description | Selected |
|--------|-------------|----------|
| Score > 0 — include any page with at least one financial keyword | Most permissive; false-positive pages harmless | ✓ |
| Score ≥ 2 — require at least 2 keyword matches | Tighter filter; risks cutting continuation rows | |

**User's choice:** Score > 0

---

## Sign Convention Enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Post-processing normalization layer | Deterministic; applies after both Claude and rule extractor; zero false positives for standard SME financials | ✓ |
| Strengthen the prompt only | No extra code; relies on Claude consistency | |
| Both — stronger prompt + post-processing | Belt-and-suspenders; best accuracy, most code | |

**User's choice:** Post-processing normalization layer

| Option | Description | Selected |
|--------|-------------|----------|
| Leave zero as-is — only flip when strictly positive | No false positives; zero stays zero | ✓ |
| Leave zero as-is and log a warning for any flip | Same behavior, surfaced in extraction notes | |

**User's choice:** Leave zero as-is — no logging

| Option | Description | Selected |
|--------|-------------|----------|
| 4-digit year string key — e.g. {'2025': 1234} | Already in schema; Claude normalizes from FY2025 etc | ✓ |
| ISO date strings — e.g. {'2025-03-31': 1234} | More precise but requires inference; fragile | |
| You decide | | |

**User's choice:** 4-digit year string key

---

## Word Doc Extraction

| Option | Description | Selected |
|--------|-------------|----------|
| Table-first extraction — tables as structured text, paragraphs as plain text | Preserves column alignment; Claude gets same quality as Excel | ✓ |
| Paragraph text only — flat extraction | Simpler but loses period→value alignment | |
| You decide | | |

**User's choice:** Table-first extraction

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — fall back to paragraph text, Claude infers structure | No-tables docx still ingested at reduced quality | ✓ |
| Yes — fall back and log a warning | Same with extraction note | |

**User's choice:** Fall back to paragraph text, no warning

| Option | Description | Selected |
|--------|-------------|----------|
| .docx only | python-docx supports only .docx; covers all modern Word files | ✓ |
| .docx and .doc (legacy binary) | Requires LibreOffice or python-docx2txt; out of scope | |
| You decide | | |

**User's choice:** .docx only

---

## Claude's Discretion

- Canonical CF row keys (D-02): `operating_cashflow`, `investing_cashflow`, `financing_cashflow`, `net_change_in_cash`
- Canonical EQ row keys (D-03): `opening_equity`, `net_profit`, `dividends_paid`, `other_equity_movements`, `closing_equity`
- EXTR-04 label mapping improvements: Claude prompt synonym examples and rule extractor synonym dictionaries — no specific user preference stated
- `_normalize_signs()` placement: last step of `persist_extraction()` before DB insert, so both paths go through normalization

## Deferred Ideas

None — discussion stayed within phase scope.
