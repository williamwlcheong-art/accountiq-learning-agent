# Phase 4: Extraction Quality — Research

**Researched:** 2026-05-17
**Domain:** Financial statement extraction — Python NLP, OCR, file format parsing, schema evolution
**Confidence:** HIGH (all key claims verified against live codebase, installed packages, and official docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Add `"cf"` and `"eq"` as two new statement types to `_ROW_SCHEMA` enum (alongside existing `"pnl"` and `"bs"`).
- **D-02:** Canonical CF row keys: `operating_cashflow`, `investing_cashflow`, `financing_cashflow`, `net_change_in_cash`.
- **D-03:** Canonical EQ row keys: `opening_equity`, `net_profit`, `dividends_paid`, `other_equity_movements`, `closing_equity`.
- **D-04:** Missing CF/EQ statements are silent (zero rows), not an error.
- **D-05:** Multi-page: include ALL pages scoring `> 0`, sorted by page index. Replace greedy score-sort with filter-then-sort.
- **D-06:** Truncation under 60K cap drops lowest-scored pages first (not last-by-index pages).
- **D-07:** Minimum page score threshold: `score > 0` (at least one financial synonym match).
- **D-08:** `_normalize_signs()` post-processing layer after Claude and rule extractor. Flip strictly positive values on: `cogs`, `operating_expenses`, `depreciation`, `interest_expense`, `tax`.
- **D-09:** Zero values (0.0) are left as-is. No logging of flips.
- **D-10:** Period keys stored as 4-digit year strings (e.g., `"2025"`).
- **D-11:** Add `extract_docx_text()` alongside existing extractors; dispatched by `.docx` extension.
- **D-12:** Table-first extraction: tab-separated cells per row, one row per line. Non-table paragraphs appended after tables.
- **D-13:** No-table docx falls back to paragraph text only — no error.
- **D-14:** Accept `.docx` only. No `.doc` legacy format.
- **D-15:** Raise `_page_has_text()` threshold from 20 to 100 chars.
- **D-16:** Increase OCR DPI from 200 to 300.
- **D-17:** Keep `--psm 6` (single uniform block) for Tesseract.
- **D-18:** `HAS_TESSERACT` flag stays; image pages silently return empty string if Tesseract absent.

### Claude's Discretion

- Canonical CF and EQ row key sets (D-02, D-03): standard summary-level keys for SME accountants.
- `_normalize_signs()` placement: last step of `persist_extraction()` before DB insert.
- EXTR-04 label mapping improvements: Claude prompt enhancements and synonym dictionary additions.

### Deferred Ideas (OUT OF SCOPE)

- None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXTR-01 | Extract income statement, balance sheet, cash flow, and equity changes into separate buckets | D-01/D-02/D-03: add `"cf"` and `"eq"` to `_ROW_SCHEMA` enum; add CF/EQ canonical key rows; update `SYSTEM_PROMPT` and `ALL_ROWS` |
| EXTR-02 | Consistent sign convention (revenue/assets positive; costs negative) regardless of source format | D-08/D-09: `_normalize_signs()` pure function applied at `persist_extraction()` for both Claude and rule-based paths |
| EXTR-03 | Financial data attributed to correct fiscal period when documents contain multiple periods | D-10: period keys as 4-digit year strings; `_detect_periods()` already handles FY prefix; Claude prompt reinforces |
| EXTR-04 | Non-standard SME labels mapped to canonical keys | Add Australian/NZ SME synonyms to `PNL_SYNS`; add CF/EQ synonym dicts; strengthen Claude prompt examples |
| EXTR-05 | Multi-page statements extracted in full without dropping secondary page rows | D-05/D-06/D-07: replace greedy score-sort with filter-then-sort in `extract_pdf_text()` |
| FILE-01 | Accept Word (.docx) documents containing financial statements | D-11/D-12/D-13/D-14: `extract_docx_text()` using `python-docx 1.2.0`; `HAS_PYTHON_DOCX` guard; dispatch in `ingest_document()` and both upload routes |
| FILE-02 | OCR from scanned/image-only PDF pages is reliable | D-15/D-16/D-17: raise `_page_has_text()` threshold to 100 chars; raise DPI to 300; keep `--psm 6` |
</phase_requirements>

---

## Summary

Phase 4 improves extraction accuracy and adds two new file format paths. The changes are surgically confined to `backend/ingestion.py` and `backend/rule_extractor.py`, with supporting changes to `backend/db.py` (only for schema comments), `backend/requirements.txt` (add python-docx), `backend/main.py` (allowed extensions + wizard route), and `frontend/index.html` (accept attribute).

The most critical finding is the **depreciation key conflict**: `ingestion.py` defines `"depreciation"` as the canonical P&L key (line 45), but the Phase 3 EBITDA bridge in `main.py` (line 224) queries for both `depreciation_amortisation` AND `depreciation` as a fallback. The test at `tests/test_profile.py:246` inserts a row with key `depreciation_amortisation`. This dual-key lookup is already correctly handled — the bridge prefers `depreciation_amortisation` and falls back to `depreciation`. No rename is needed; Phase 4 must ensure the `depreciation` canonical key continues to exist in `PNL_ROWS` and is not renamed.

The **DB schema** is confirmed clean: `financial_rows.statement` is `TEXT NOT NULL` with no CHECK constraint blocking `"cf"` or `"eq"`. No migration SQL is required — the new values will be accepted by SQLite immediately. The `label_patterns.statement` column is equally unconstrained.

**Primary recommendation:** Implement the four areas (CF/EQ statement types, multi-page fix, sign normalization, docx ingestion) as separate plans in dependency order. Wave 1 adds the schema-free infrastructure (CF/EQ row definitions, `_normalize_signs()`), Wave 2 fixes page selection and OCR thresholds, Wave 3 adds docx support.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Statement type expansion (CF/EQ) | API / Backend (`ingestion.py`) | — | Schema enum lives in tool definition; Claude prompt owns classification |
| Sign normalization | API / Backend (`ingestion.py` `persist_extraction`) | Rule extractor path | Must run after all extraction paths before DB write |
| Multi-page page selection | API / Backend (`ingestion.py` `extract_pdf_text`) | — | Page scoring is synchronous pre-processing before Claude call |
| Word doc extraction | API / Backend (`ingestion.py` `extract_docx_text`) | — | Mirrors existing `extract_pdf_text` / `extract_excel_text` pattern |
| OCR reliability | API / Backend (`ingestion.py` `_page_has_text`, `_ocr_page`) | — | Threshold and DPI are config constants in ingestion.py |
| SME label mapping | API / Backend (`rule_extractor.py` synonym dicts) | Claude prompt | Rule extractor synonyms + Claude prompt hints both contribute |
| File extension dispatch | API / Backend (`main.py` upload routes + `ingestion.py` `ingest_document`) | Frontend accept attr | Three places: two upload routes in main.py, one dispatch in ingest_document |
| Frontend file accept | Browser / Client (`frontend/index.html`) | — | `accept=".pdf,.xlsx,.xls,.xlsm"` on two `<input type="file">` elements |

---

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| pdfplumber | 0.11.9 | PDF text extraction + image rendering | Installed [VERIFIED: pip show] |
| pytesseract | 0.3.13 | Python wrapper for Tesseract OCR | Installed [VERIFIED: pip show] |
| Pillow | 12.2.0 | Image handling for OCR pipeline | Installed [VERIFIED: pip show] |

### New Dependency
| Library | Version | Purpose | Install |
|---------|---------|---------|---------|
| python-docx | 1.2.0 | Word .docx table and paragraph extraction | `pip install python-docx` [VERIFIED: pip index versions] |
| lxml | 6.1.0 | Required transitive dependency of python-docx | Installed automatically with python-docx |

### System Dependencies
| Tool | Version | Purpose | Status |
|------|---------|---------|--------|
| tesseract | 5.5.2 | OCR engine (called by pytesseract) | Installed at `/opt/homebrew/bin/tesseract` [VERIFIED: which + version] |

**Installation:**
```bash
pip install python-docx
```
Also add to `backend/requirements.txt`:
```
python-docx>=1.1.0
```

**Version verification:** [VERIFIED: pip index versions python-docx — 2026-05-17]
- python-docx: latest = 1.2.0 (confirmed); 1.1.x series also safe

---

## Architecture Patterns

### System Architecture Diagram

```
POST /documents/upload (admin) or POST /wizard/upload (user)
  │
  ├── suffix check: {.pdf, .xlsx, .xls, .xlsm} → add .docx
  │
  ▼
_run_ingestion(document_id, filepath, ...)
  │
  ├── .docx  → extract_docx_text()   [NEW — python-docx]
  ├── .xlsx/.xls/.xlsm → extract_excel_text()
  └── .pdf   → extract_pdf_text()
                 │
                 ├── pdfplumber.page.extract_text()
                 └── if len(text) <= 100 chars → _ocr_page() [threshold raised]
                       └── page.to_image(resolution=300) → pytesseract --psm 6
                 │
                 └── score & select pages [D-05 fix]
                       filter score > 0, sort by page index
                       if total > 60K: drop lowest-scored pages first
  │
  ▼
call_claude(text, pattern_lib, ...)     OR     rule_based_extract(pages)
  │                                                  │
  └─────────────────────────────────────────────────┘
                       │
                       ▼
              _normalize_signs(rows)   [NEW — D-08]
              flip strictly positive: cogs, operating_expenses,
              depreciation, interest_expense, tax
                       │
                       ▼
              persist_extraction(db, document_id, ...)
              INSERT INTO financial_rows (statement ∈ {pnl, bs, cf, eq})
```

### Recommended Project Structure

No new directories needed. All new code is in existing files:

```
backend/
├── ingestion.py          # Core changes: extract_docx_text(), _normalize_signs(),
│                         #   D-05 page selection, D-15 threshold, D-16 DPI
├── rule_extractor.py     # CF_SYNS, EQ_SYNS, SME synonym additions
├── main.py               # .docx in allowed extensions (2 routes)
├── db.py                 # Comment-only update to statement column docs
├── requirements.txt      # Add python-docx>=1.1.0
frontend/
└── index.html            # Add .docx to both <input accept="..."> attributes

tests/
└── test_extraction.py    # NEW — unit tests for all Phase 4 logic (Wave 0)
```

### Pattern 1: Optional Dependency Guard (HAS_PYTHON_DOCX)

Mirrors the existing `HAS_TESSERACT` pattern exactly. [VERIFIED: backend/ingestion.py lines 20-24]

```python
# In ingestion.py — after other imports, before local imports
try:
    from docx import Document as DocxDocument
    HAS_PYTHON_DOCX = True
except ImportError:
    HAS_PYTHON_DOCX = False
```

Then in `extract_docx_text()`:
```python
def extract_docx_text(filepath: str) -> tuple[str, list[str], int, bool]:
    if not HAS_PYTHON_DOCX:
        raise ImportError("python-docx is required for Word ingestion: pip install python-docx")
    # ...
```

### Pattern 2: python-docx Table Extraction

[VERIFIED: Context7 /websites/python-docx_readthedocs_io_en]

```python
from docx import Document

def extract_docx_text(filepath: str) -> tuple[str, list[str], int, bool]:
    doc = DocxDocument(filepath)
    parts = []

    for i, table in enumerate(doc.tables):
        parts.append(f"--- TABLE {i+1} ---")
        for row in table.rows:
            # row.cells always returns grid_cols cells (merged cells repeat same object)
            # Use dict-of-seen-ids to deduplicate horizontally merged cells
            seen = {}
            cells_text = []
            for cell in row.cells:
                cell_id = id(cell._tc)
                if cell_id not in seen:
                    seen[cell_id] = True
                    cells_text.append(cell.text.strip())
            parts.append("\t".join(cells_text))

    # Append non-table paragraphs after tables
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            parts.append(t)

    combined = "\n".join(parts)
    return combined[:MAX_TEXT_CHARS], [combined], 1, False
```

**Merged cell gotcha (CRITICAL):** When cells are horizontally merged, `row.cells` returns the same cell object repeated for each column it spans. Without deduplication by `id(cell._tc)`, merged header rows produce doubled text (e.g., `"2025\t2025"` instead of `"2025"`). The pattern above deduplicates using the underlying `_tc` element identity. [VERIFIED: Context7 — "length of row.cells always equals the number of grid columns"]

### Pattern 3: _normalize_signs() Pure Function

[ASSUMED] — No official source; derived from D-08/D-09 decisions and Python best practices.

```python
# Keys that must always be negative (costs/expenses)
_COST_KEYS = frozenset({"cogs", "operating_expenses", "depreciation", "interest_expense", "tax"})

def _normalize_signs(rows: list[dict]) -> list[dict]:
    """Return new row dicts with sign-corrected values for known cost keys.
    Only flips strictly positive values; leaves zero and None unchanged.
    Pure function — does not modify rows in place.
    """
    result = []
    for row in rows:
        key = row.get("canonical_key", "")
        if key in _COST_KEYS:
            new_values = {}
            for period, val in row.get("values", {}).items():
                if val is not None and val > 0:
                    new_values[period] = -val
                else:
                    new_values[period] = val
            result.append({**row, "values": new_values})
        else:
            result.append(row)
    return result
```

### Pattern 4: Multi-Page Fix (D-05/D-06)

[VERIFIED: backend/ingestion.py lines 198-216 — existing code being replaced]

Current code (lines 200-208):
```python
scored.sort(key=lambda x: -x[0])          # sort by score descending
for score, idx, pt in scored:
    chunk = ...
    if total_chars + len(chunk) > MAX_TEXT_CHARS:
        break                              # drops all remaining pages including continuation
    claude_parts.append((idx, chunk))
```

Replacement (D-05/D-06):
```python
# 1. Filter: keep only pages scoring > 0
selected = [(score, i, pt) for score, i, pt in scored if score > 0]
# 2. Sort by page index (document order)
selected.sort(key=lambda x: x[1])
# 3. Truncate: if over 60K, drop lowest-scored pages first
total_chars = sum(len(f"--- PAGE {i+1} ---\n{pt}") for _, i, pt in selected)
while total_chars > MAX_TEXT_CHARS and len(selected) > 1:
    # remove the page with the lowest score (stable — keep order for ties)
    min_idx = min(range(len(selected)), key=lambda k: selected[k][0])
    removed = selected.pop(min_idx)
    total_chars -= len(f"--- PAGE {removed[1]+1} ---\n{removed[2]}")
claude_parts = [(i, f"--- PAGE {i+1} ---\n{pt}") for _, i, pt in selected]
```

### Anti-Patterns to Avoid

- **Do not rename `depreciation` to `depreciation_amortisation`** in `PNL_ROWS`: The Phase 3 EBITDA bridge queries both keys with fallback logic — `depreciation` is the existing key that real documents produce. Renaming breaks existing extraction data. [VERIFIED: main.py:224+238-240, test_profile.py:246]
- **Do not use `row.cells` naively for merged tables**: Merged cells repeat the same object per covered column. Always deduplicate with `id(cell._tc)`. [VERIFIED: Context7 python-docx docs]
- **Do not add CHECK constraint to `financial_rows.statement`**: The column is plain `TEXT NOT NULL` — no constraint exists or is needed. Adding one would require a table-rename migration. [VERIFIED: live DB DDL]
- **Do not pass `all_page_texts` to rule_based_extract for docx**: The rule extractor expects page-separated text lists; for docx, pass `[combined]` (one "page"). [VERIFIED: rule_extractor.py:308]
- **Do not place `_normalize_signs()` before period-attribution**: The function operates on the `rows` list after `call_claude()`/`rule_based_extract()` return — it must not touch the `values` dict structure, only individual values. [ASSUMED — follows D-08 design]
- **Do not run OCR on the full PDF if only 1-2 pages need it**: `_ocr_page()` is called per-page only when `_page_has_text()` returns False. The 300 DPI change only applies to those pages. [VERIFIED: ingestion.py:193-194]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Word doc parsing | Custom XML parser for .docx | `python-docx` | DOCX is ZIP+XML; python-docx handles XML namespace complexity, merged cells, nested tables, styles |
| OCR image rendering | Custom PDF-to-image converter | `pdfplumber.page.to_image(resolution=300)` | Already used at line 176; pdfplumber wraps pypdfium2 for rendering |
| Period year extraction | Custom regex parser | `_detect_periods()` in rule_extractor.py | Already handles FY prefix, 2-digit years, multi-column header detection |
| Parenthetical negative parsing | Custom negative number parser | `_extract_numbers()` in rule_extractor.py | Already handles `(1,234)` → `-1234` and em-dash null detection |
| DB schema migration | Full Alembic migration | `ALTER TABLE ... ADD COLUMN` try/except pattern | Project convention established in Phase 2; `_migrate_db()` in db.py |

**Key insight:** The extraction infrastructure already handles the hardest problems. Phase 4 is targeted surgery on specific failure modes, not a rearchitecture.

---

## Runtime State Inventory

> Phase 4 is not a rename/refactor/migration phase. The statement column is unconstrained TEXT — no migration touches existing data. Including a brief inventory to confirm no runtime state is affected.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `financial_rows` has existing rows with `statement IN ('pnl', 'bs')` only — confirmed by live DB query. No cf/eq rows exist yet. | None — new values write into same table without affecting existing rows |
| Live service config | No external services configured with statement-type references | None |
| OS-registered state | None | None |
| Secrets/env vars | None reference statement types | None |
| Build artifacts | None | None |

---

## Common Pitfalls

### Pitfall 1: Merged Cells Producing Doubled Column Headers
**What goes wrong:** A financial statement .docx with a merged "Year ended" header cell produces `"Year ended 31 March 2025\tYear ended 31 March 2025"` when iterating `row.cells` naively. Claude sees two identical period columns and may produce duplicate or misaligned values.
**Why it happens:** When cells are horizontally merged, `row.cells` returns the same cell object reference for each column it spans (length equals grid_cols, not logical cell count). [VERIFIED: Context7 python-docx docs — "length of row.cells always equals the number of grid columns"]
**How to avoid:** Deduplicate by `id(cell._tc)` before joining with `\t`. See Pattern 2 above.
**Warning signs:** Column count in `--- TABLE ---` output is twice the expected number; Claude returns duplicate period keys.

### Pitfall 2: Continuation Page Score Too Low to Beat First-Page Greedy Fill
**What goes wrong:** Page 1 of a 2-page P&L has 8 keyword matches; page 2 has 3 (fewer headers, more line items). Under current greedy fill, if page 1 alone fills 58K of 60K, page 2 is dropped at the `break` on line 207.
**Why it happens:** Current sort is by score descending, fill-until-full. Continuation pages have fewer section headers so their score is lower. [VERIFIED: ingestion.py:200-208]
**How to avoid:** D-05 fix — filter score > 0, then sort by page index. Truncation drops lowest-scored pages, not last-by-index pages. Continuation pages with score ≥ 1 are retained unless all budget is exhausted.
**Warning signs:** Rule extractor finds all 20 rows but Claude only returns 12 — first-page rows only.

### Pitfall 3: OCR Threshold at 20 Chars Misses Sparse Image Pages
**What goes wrong:** A scanned PDF page with only a page number (`"Page 2"` = 6 chars) OR a page with a few artifact characters from the scan (~25 chars) goes down the `extract_text()` path, returns mostly garbage, and is NOT OCR-processed. Result: garbled text sent to Claude.
**Why it happens:** The current threshold is 20 chars — `len("Report of the Directors") = 23 > 20` so it's treated as text-layer. [VERIFIED: ingestion.py:169-170]
**How to avoid:** D-15 fix — raise threshold to 100 chars. Pages with < 100 chars of pdfplumber text are sent to OCR. Most real financial pages have hundreds of chars; 100 chars cleanly separates "real text layer" from "sparse artifact".
**Warning signs:** `used_ocr = False` in extraction log even though the uploaded PDF was clearly scanned; extracted text contains isolated characters or symbols.

### Pitfall 4: Sign Convention Depends on Source Document Format
**What goes wrong:** Some accountants present costs as positive numbers in the PDF (e.g., `COGS 450,000`); others use brackets (`(450,000)`) or explicit negatives. Claude sometimes returns positive COGS; the rule extractor also returns positive COGS when the source is positive.
**Why it happens:** Both extraction paths faithfully preserve source sign, which is correct for data fidelity but inconsistent for downstream consumers (Phase 5 report calculations assume costs are negative). [VERIFIED: SYSTEM_PROMPT analysis — no sign normalization instruction exists currently]
**How to avoid:** D-08 `_normalize_signs()` applied after all extraction paths, before DB write. Only flips strictly positive values on the 5 cost keys.
**Warning signs:** Phase 5 EBITDA calculation returns double the expected value (e.g., `net_profit + cogs` instead of `net_profit - cogs`).

### Pitfall 5: CF/EQ Rows Stored with Wrong Statement Type
**What goes wrong:** Claude might classify a cash flow row as `statement: "pnl"` because the system prompt only lists `"pnl"` and `"bs"` in the enum, causing schema validation failure or silent misclassification.
**Why it happens:** `_ROW_SCHEMA` currently has `"enum": ["pnl", "bs"]`. If Claude returns `"cf"` before the enum is updated, the tool-use schema will reject it. [VERIFIED: ingestion.py:137]
**How to avoid:** Update `_ROW_SCHEMA` enum to `["pnl", "bs", "cf", "eq"]` and add CF/EQ canonical key sections to `SYSTEM_PROMPT` before any production use.
**Warning signs:** Claude returns `extraction_notes` mentioning cash flow was found but no CF rows appear in the DB.

### Pitfall 6: rule_based_extract Produces No CF/EQ rows (Expected)
**What goes wrong:** After adding CF/EQ support to Claude path, developers may expect the rule-based fallback to also extract CF/EQ rows. It will NOT — `rule_based_extract()` only handles PNL_SYNS and BS_SYNS.
**Why it happens:** Rule extractor is a targeted fallback for the 2-statement case. CF/EQ extraction requires Claude.
**How to avoid:** Accept this limitation. D-04 says missing CF/EQ rows are silent — the rule-based path will naturally produce zero CF/EQ rows. No error handling needed.
**Warning signs:** Developers adding CF_SYNS/EQ_SYNS to rule_extractor.py — not needed for v1.

### Pitfall 7: Depreciation Key Conflict with Phase 3 EBITDA Bridge
**What goes wrong:** If `"depreciation"` is renamed to `"depreciation_amortisation"` in `PNL_ROWS`, the Phase 3 EBITDA bridge's fallback query at `main.py:240` (`da = fin_rows.get("depreciation") or 0`) stops working for newly ingested documents.
**Why it happens:** `PNL_ROWS` defines `"depreciation"` as the canonical key; Phase 3 bridge prefers `"depreciation_amortisation"` with `"depreciation"` as fallback. The test at `test_profile.py:246` uses `depreciation_amortisation` directly inserted via DB, bypassing extraction. [VERIFIED: main.py:224+238-240, ingestion.py:45]
**How to avoid:** Do NOT rename the `depreciation` canonical key. The bridge already handles both; extraction must continue producing `"depreciation"` as the key.
**Warning signs:** `reported_ebitda` is None for companies where depreciation was recently extracted.

---

## Code Examples

### python-docx — Reading a Document
```python
# Source: Context7 /websites/python-docx_readthedocs_io_en
from docx import Document

doc = Document("financials.docx")

# Iterate tables
for i, table in enumerate(doc.tables):
    for row in table.rows:
        for cell in row.cells:
            print(cell.text)

# Iterate paragraphs (fallback when no tables)
for para in doc.paragraphs:
    print(para.text)
```

### python-docx — Document Order Iteration
```python
# Source: Context7 /websites/python-docx_readthedocs_io_en
# Generates Paragraph or Table objects in document order
for block in doc.iter_inner_content():
    # isinstance(block, Table) or isinstance(block, Paragraph)
    pass
```

### python-docx — Handling Merged Cells (CRITICAL)
```python
# Source: Context7 — "length of row.cells always equals the number of grid columns"
# Merged cells return the same object for each spanned column position.
# Must deduplicate to avoid doubled column text.
seen_ids = {}
cells_text = []
for cell in row.cells:
    cid = id(cell._tc)
    if cid not in seen_ids:
        seen_ids[cid] = True
        cells_text.append(cell.text.strip())
line = "\t".join(cells_text)
```

### pdfplumber — DPI 300 rendering (existing pattern, new value)
```python
# Source: verified from ingestion.py:176 + pdfplumber.page.Page.to_image signature
OCR_DPI = 300  # was 200

def _ocr_page(page) -> str:
    if not HAS_TESSERACT:
        return ""
    img = page.to_image(resolution=OCR_DPI).original
    return pytesseract.image_to_string(img, config="--psm 6")
```

### _page_has_text — Updated Threshold
```python
# Source: verified from ingestion.py:168-170 (current code being changed)
def _page_has_text(page) -> bool:
    text = page.extract_text() or ""
    return len(text.strip()) > 100  # was 20
```

---

## SME Label Synonym Gaps

**Current state of PNL_SYNS** [VERIFIED: rule_extractor.py]:

The following Australian/NZ SME labels that appear in the success criteria (EXTR-04) are MISSING from `PNL_SYNS`:

| Missing Label | Maps To | Rationale |
|--------------|---------|-----------|
| `"owners drawings"`, `"drawings"` | `operating_expenses` | Common NZ/AU sole trader P&L line item — owner salary equivalent |
| `"directors fees"`, `"directors remuneration"` | `operating_expenses` | Standard NZ/AU SME expense line |
| `"cost of sales"` | `cogs` | **Already present** (line 23) |
| `"turnover"` | `revenue` | **Already present** (line 19) |
| `"wages"`, `"wages and salaries"`, `"salaries and wages"` | `operating_expenses` | Very common AU/NZ SME P&L line |
| `"administration expenses"`, `"admin expenses"` | `operating_expenses` | Common AU/NZ SME expense category |
| `"other income"`, `"sundry income"`, `"miscellaneous income"` | `revenue` | AU/NZ SME income items |
| `"motor vehicle expenses"`, `"vehicle costs"` | `operating_expenses` | Common AU/NZ SME line |
| `"subcontractors"`, `"subcontract costs"`, `"contract labour"` | `cogs` | Trade/construction SMEs |

Note: `"directors fees"` maps to `operating_expenses` not a new canonical key — it is a sub-line within total operating expenses. The rule extractor accumulates into `operating_expenses` via `SUM_KEYS` for accumulation.

**New synonym dicts needed for CF/EQ:**

These need to be added to `rule_extractor.py` for completeness (even though rule extractor won't produce CF/EQ rows, the `_score_page()` function in CF/EQ pages would benefit for multi-page scoring — CF pages scoring > 0 ensures they're included):

```python
CF_SYNS = {
    "operating_cashflow":   ["cash flows from operating activities", "net cash from operations",
                             "operating activities", "cash generated from operations"],
    "investing_cashflow":   ["cash flows from investing activities", "investing activities",
                             "net cash used in investing"],
    "financing_cashflow":   ["cash flows from financing activities", "financing activities",
                             "net cash from financing"],
    "net_change_in_cash":   ["net increase in cash", "net decrease in cash",
                             "net change in cash and cash equivalents",
                             "increase in cash held", "decrease in cash held"],
}

EQ_SYNS = {
    "opening_equity":       ["balance at beginning", "opening balance", "balance brought forward",
                             "equity at start of year"],
    "net_profit":           ["profit for the year", "net profit", "net income"],
    "dividends_paid":       ["dividends paid", "distributions paid", "drawings paid",
                             "dividends declared", "owner distributions"],
    "other_equity_movements": ["other comprehensive income", "other movements",
                               "share capital issued"],
    "closing_equity":       ["balance at end", "closing balance", "equity at end of year",
                             "total equity"],
}
```

[ASSUMED] — CF_SYNS and EQ_SYNS synonyms are based on training knowledge of standard NZ/AU financial statement terminology. Correctness should be verified against actual SME documents in the project's `data/pdfs/` directory.

---

## DB Schema Findings

**CONFIRMED: No CHECK constraint on `financial_rows.statement`** [VERIFIED: live DB DDL query]

```sql
-- Live DDL — no CHECK constraint present
CREATE TABLE financial_rows (
    ...
    statement   TEXT    NOT NULL,    -- 'pnl' | 'bs'
    ...
)
```

The `-- 'pnl' | 'bs'` is a comment only. SQLite will accept `"cf"` and `"eq"` without any schema change. **No migration required.**

**Same for `label_patterns.statement`** — also unconstrained TEXT. [VERIFIED: live DB DDL query]

**Existing data:** Live DB contains rows with `statement IN ('pnl', 'bs')` only. New CF/EQ rows will coexist without affecting queries that filter on existing statement types. [VERIFIED: live DB query `SELECT DISTINCT statement FROM financial_rows`]

---

## Test Infrastructure Findings

**Framework:** pytest 9.0.3 + pytest-asyncio 1.3.0 [VERIFIED: pip show]
**Config:** `pytest.ini` — `asyncio_mode = auto`, `testpaths = tests` [VERIFIED: pytest.ini]
**Quick run:** `pytest tests/test_extraction.py -x`
**Full suite:** `pytest tests/ -x`
**Current test count:** 50 tests collected, all in `tests/` [VERIFIED: pytest --collect-only]

**Test pattern:** All existing tests use `AsyncClient(transport=ASGITransport(app=app))` with a temp SQLite DB. Extraction tests use in-memory fixture data (direct DB inserts) or `monkeypatch` — no real PDF fixtures exist. [VERIFIED: tests/conftest.py, test_profile.py, test_upload_auto.py]

**No existing extraction-logic unit tests:** There are no tests for `_normalize_signs()`, `_score_page()`, `extract_docx_text()`, `_page_has_text()`, or `_extract_statement()`. All Phase 4 logic needs a new `tests/test_extraction.py`.

**No fixture files:** `tests/` has no `.pdf`, `.docx`, or binary fixture files. Tests use fake bytes (`io.BytesIO(b"%PDF-1.4 fake")`). Phase 4 unit tests for docx and OCR logic should follow the same fake-bytes or in-memory pattern where possible, using monkeypatching for calls into python-docx and pytesseract. [VERIFIED: test_upload_auto.py:35-38]

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `pytest.ini` — `asyncio_mode = auto`, `testpaths = tests` |
| Quick run command | `pytest tests/test_extraction.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXTR-01 | CF/EQ rows stored under correct statement types | unit | `pytest tests/test_extraction.py::test_cf_eq_statement_types -x` | Wave 0 |
| EXTR-01 | `_ROW_SCHEMA` enum includes "cf" and "eq" | unit | `pytest tests/test_extraction.py::test_row_schema_includes_cf_eq -x` | Wave 0 |
| EXTR-02 | `_normalize_signs()` flips positive cost keys | unit | `pytest tests/test_extraction.py::test_normalize_signs_flips_positive_costs -x` | Wave 0 |
| EXTR-02 | `_normalize_signs()` leaves zero and None unchanged | unit | `pytest tests/test_extraction.py::test_normalize_signs_preserves_zero_and_none -x` | Wave 0 |
| EXTR-02 | `_normalize_signs()` does not flip revenue or asset keys | unit | `pytest tests/test_extraction.py::test_normalize_signs_does_not_flip_revenue -x` | Wave 0 |
| EXTR-03 | Period keys normalized to 4-digit year strings | unit | `pytest tests/test_extraction.py::test_detect_periods_normalizes_fy_prefix -x` | Wave 0 |
| EXTR-04 | "Owners Drawings" maps to operating_expenses | unit | `pytest tests/test_extraction.py::test_sme_label_owners_drawings -x` | Wave 0 |
| EXTR-04 | "Directors Fees" maps to operating_expenses | unit | `pytest tests/test_extraction.py::test_sme_label_directors_fees -x` | Wave 0 |
| EXTR-05 | Multi-page: continuation page (score > 0) is included | unit | `pytest tests/test_extraction.py::test_multipage_includes_continuation -x` | Wave 0 |
| EXTR-05 | Multi-page: pages scoring 0 (cover page) are excluded | unit | `pytest tests/test_extraction.py::test_multipage_excludes_cover_page -x` | Wave 0 |
| EXTR-05 | Multi-page: 60K overflow drops lowest-scored not last-indexed | unit | `pytest tests/test_extraction.py::test_multipage_truncation_drops_lowest_score -x` | Wave 0 |
| FILE-01 | extract_docx_text() returns tab-separated rows per table | unit | `pytest tests/test_extraction.py::test_docx_table_extraction -x` | Wave 0 |
| FILE-01 | extract_docx_text() deduplicates merged header cells | unit | `pytest tests/test_extraction.py::test_docx_merged_cells_dedup -x` | Wave 0 |
| FILE-01 | .docx upload dispatched correctly in ingest_document | unit | `pytest tests/test_extraction.py::test_ingest_dispatches_docx -x` | Wave 0 |
| FILE-01 | .docx accepted in /documents/upload and /wizard/upload | integration | `pytest tests/test_extraction.py::test_upload_routes_accept_docx -x` | Wave 0 |
| FILE-02 | Pages with <100 chars are sent to OCR | unit | `pytest tests/test_extraction.py::test_page_has_text_threshold -x` | Wave 0 |
| FILE-02 | OCR uses DPI 300 | unit | `pytest tests/test_extraction.py::test_ocr_dpi_is_300 -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_extraction.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite (50+ tests) green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_extraction.py` — new file covering all 17 REQs above
- [ ] No conftest changes needed — `fresh_all_db` fixture already covers DB cleanup

---

## Security Domain

> `security_enforcement` not set in config.json — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Ingestion routes already protected by `require_admin` / `get_current_user` |
| V3 Session Management | no | No new session logic |
| V4 Access Control | no | No new routes; docx upload reuses existing auth guards |
| V5 Input Validation | yes | File extension validation on upload routes |
| V6 Cryptography | no | No new crypto |

### Known Threat Patterns for Phase 4 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed .docx (ZIP bomb or malformed XML) | Tampering | python-docx raises `BadZipFile` or `lxml` parse error — catch `Exception` in `extract_docx_text()` and let `ingest_document()` set status to `failed` |
| Path traversal via .docx filename | Elevation of Privilege | Already mitigated: `Path(file.filename).name` (basename only) enforced in both upload routes [VERIFIED: main.py:532, main.py:929] |
| OCR producing large garbage strings | Spoofing | `MAX_TEXT_CHARS = 60_000` cap applied to all extraction paths including docx output [VERIFIED: ingestion.py:35] |
| .docx containing macros or embedded scripts | Tampering | python-docx is read-only and does not execute macros; no action needed |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Greedy score-sort page selection (drops continuation pages) | Filter score>0 + sort by index + truncate-by-lowest-score | Phase 4 | Multi-page P&L/BS fully covered |
| 20-char OCR threshold (misses sparse artifact pages) | 100-char threshold | Phase 4 | Fewer garbled scanned pages; more pages correctly OCR'd |
| 200 DPI OCR | 300 DPI OCR | Phase 4 | Better character recognition on small-font financial tables |
| pnl/bs only statement types | pnl/bs/cf/eq | Phase 4 | Phase 5 report generation can use CF and equity data |
| No sign normalization (source sign preserved) | `_normalize_signs()` post-processing | Phase 4 | Consistent sign convention for Phase 5 calculations |
| PDF/Excel only ingestion | PDF/Excel/docx ingestion | Phase 4 | Word doc financials from SME accountants now supported |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | CF_SYNS and EQ_SYNS synonym lists are representative of AU/NZ SME cash flow and equity statement terminology | SME Label Synonym Gaps | If wrong, `_score_page()` won't score CF/EQ pages > 0, and they'll be excluded from multi-page aggregation — but CF/EQ extraction via Claude will still work as Claude doesn't rely on these syns for extraction |
| A2 | `_normalize_signs()` should be a pure function (no in-place mutation) | Pattern 3 code example | If project convention prefers in-place mutation, the implementation is functionally equivalent but style differs |
| A3 | The merged-cell deduplication approach (`id(cell._tc)`) is stable across python-docx versions | Pattern 2 | If `_tc` identity changes across versions, deduplication fails; alternate: use `cell._element` |
| A4 | "Owners Drawings" and "Directors Fees" map to `operating_expenses` not a dedicated canonical key | SME Label Synonym Gaps | If Phase 5 needs these as separate keys for add-back reconciliation, the canonical key list would need expansion |
| A5 | PSM 6 is optimal for financial statement page layouts | OCR section | PSM 4 (single column) may perform better for tables; no empirical testing done in this session |

**Verified claims:** All DB schema, installed package versions, existing code structure, test infrastructure details, Tesseract installation, and python-docx API behavior were verified via tool calls in this session.

---

## Open Questions (RESOLVED)

1. **Should CF_SYNS/EQ_SYNS be added to `_score_page()` for multi-page scoring?**
   - What we know: `_score_page()` currently only accepts a `syns` dict parameter; it's called with `PNL_SYNS` and `BS_SYNS` in `extract_pdf_text()`
   - What's unclear: Should CF/EQ pages be scored and included in multi-page selection (they may be adjacent to P&L pages in annual reports)?
   - Recommendation: Yes — add `CF_SYNS` and `EQ_SYNS` to the scoring call in `extract_pdf_text()` so CF/EQ pages score > 0 and are included. Claude will ignore irrelevant content. [Follows D-07 rationale: false-positive pages are harmless]

2. **Should `extract_docx_text()` use `doc.iter_inner_content()` instead of `doc.tables` + `doc.paragraphs` separately?**
   - What we know: `iter_inner_content()` yields `Paragraph | Table` in document order; `doc.tables` and `doc.paragraphs` give all items but in separate lists
   - What's unclear: Some .docx files interleave tables and paragraphs (e.g., a paragraph heading before each table); processing tables-first would lose that ordering
   - Recommendation: Use `iter_inner_content()` for correct document order — matches CONTEXT.md D-12's "non-table paragraphs appended after all tables" intent, which suggests tables-first is acceptable. Use `doc.tables` + `doc.paragraphs` approach for simplicity (D-12 explicitly says tables-first).

3. **What is the 80% OCR success criterion measurement method?**
   - What we know: Success criterion 7 says "at least 80% of the rows a text-layer PDF would" — this is a relative comparison
   - What's unclear: The project has no scanned PDF test fixture. Automating this test requires either a real scanned PDF or a synthetic one
   - Recommendation: For Phase 4 testing, verify the 80% criterion manually using a real scanned document from `data/pdfs/`. The automated test for FILE-02 covers the configuration changes (threshold=100, DPI=300) rather than the end-to-end OCR accuracy. Document this as a manual verification step in the Phase 4 verifier.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| tesseract | FILE-02 OCR | Yes | 5.5.2 | `HAS_TESSERACT=False` — image pages return empty string |
| python-docx | FILE-01 Word | No — not installed | 1.2.0 available | Install via `pip install python-docx`; `HAS_PYTHON_DOCX=False` if not installed |
| pdfplumber | All PDF extraction | Yes | 0.11.9 | Required; already in requirements.txt |
| pytesseract | FILE-02 OCR | Yes | 0.3.13 | `HAS_TESSERACT=False` guard already in place |
| Pillow | OCR image handling | Yes | 12.2.0 | Required by pytesseract |

**Missing dependencies with no fallback:**
- `python-docx` must be installed for FILE-01. Wave 0 task should add `pip install python-docx` and `python-docx>=1.1.0` to `backend/requirements.txt`.

**Missing dependencies with fallback:**
- tesseract is installed but `HAS_TESSERACT` guard allows graceful degradation if absent on other machines.

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 4 |
|-----------|-------------------|
| All DB operations use `aiosqlite` with async/await | `extract_docx_text()` is sync — must be wrapped in `run_in_executor` like `extract_excel_text()` |
| Wrap sync library calls in `asyncio.get_running_loop().run_in_executor(None, ...)` | python-docx is sync; wrap in executor in `ingest_document()` |
| File uploads save to `data/pdfs/{company_id}/` using `Path(filename).name` | Both upload routes already enforce this; no change needed for docx |
| Never hardcode API keys | Not affected |
| Never use `allow_origins=["*"]` on write endpoints | Not affected |
| Always use `.textContent` / `.createTextNode()` for user-influenced text | Not affected (no new UI) |
| JWT validated on every protected route via middleware | Not affected; no new routes |

---

## Sources

### Primary (HIGH confidence)
- `backend/ingestion.py` — ingestion pipeline code, scoring logic, OCR constants [VERIFIED: file read]
- `backend/rule_extractor.py` — synonym dicts, `_score_page()`, `_extract_statement()` [VERIFIED: file read]
- `backend/db.py` — table DDL, `_migrate_db()`, constraint verification [VERIFIED: file read + live DB query]
- `backend/main.py` — upload routes, allowed extensions, EBITDA bridge queries [VERIFIED: file read]
- `tests/conftest.py`, `tests/test_profile.py`, `tests/test_upload_auto.py` — test patterns [VERIFIED: file reads]
- `pytest.ini` — test framework configuration [VERIFIED: file read]
- Context7 `/websites/python-docx_readthedocs_io_en` — python-docx table API, merged cell behavior [VERIFIED: ctx7 CLI]
- pip registry — python-docx 1.2.0 latest, pytesseract 0.3.13, pdfplumber 0.11.9 [VERIFIED: pip show, pip index versions]
- Live DB DDL query — no CHECK constraint on `statement` column [VERIFIED: sqlite3 python query]
- Tesseract PSM modes — `tesseract --help-psm` [VERIFIED: shell command]
- pdfplumber `to_image()` signature — `resolution` parameter confirmed [VERIFIED: Python inspect]

### Secondary (MEDIUM confidence)
- `.planning/phases/04-extraction-quality/04-CONTEXT.md` — 18 locked implementation decisions
- `.planning/codebase/ARCHITECTURE.md` — ingestion pipeline data flow
- `.planning/codebase/CONVENTIONS.md` — async pattern, import ordering, logging style

### Tertiary (LOW confidence — see Assumptions Log)
- CF_SYNS/EQ_SYNS synonym lists — based on training knowledge of AU/NZ financial statement terminology [ASSUMED — A1]
- SME label additions for `PNL_SYNS` ("Owners Drawings", "Directors Fees" etc.) [ASSUMED — A4]
- PSM 6 optimality for financial tables [ASSUMED — A5]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all package versions verified against pip registry and live install
- DB schema: HIGH — live DDL query confirms no CHECK constraint
- python-docx API: HIGH — verified via Context7 official docs with specific merged-cell behavior
- Architecture: HIGH — verified against live codebase
- SME synonym additions: LOW — based on training knowledge, no validation against real SME PDFs

**Research date:** 2026-05-17
**Valid until:** 2026-06-17 (python-docx API is stable; pip package versions change more quickly)
