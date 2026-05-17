# Phase 4: Extraction Quality - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the extraction pipeline accurate and complete across all financial statement types (income statement, balance sheet, cash flow, equity changes), consistent sign conventions, correct period attribution, non-standard SME label mapping, and multi-page document coverage. Also adds two new file format paths: Word (.docx) documents and scanned/image-only PDFs via OCR. Report generation readiness (Phase 5) depends on clean, correctly-signed, correctly-attributed financial rows.

</domain>

<decisions>
## Implementation Decisions

### Statement type buckets (EXTR-01)
- **D-01:** Add `"cf"` and `"eq"` as two new statement types to the `_ROW_SCHEMA` enum (alongside existing `"pnl"` and `"bs"`). The `statement` field in `financial_rows` must accept all four values.
- **D-02:** Canonical cash flow (`"cf"`) row keys: `operating_cashflow`, `investing_cashflow`, `financing_cashflow`, `net_change_in_cash`. (Claude's discretion — standard indirect-method summary that most SME accountants produce.)
- **D-03:** Canonical equity changes (`"eq"`) row keys: `opening_equity`, `net_profit` (links back to P&L), `dividends_paid`, `other_equity_movements`, `closing_equity`. (Claude's discretion — standard changes-in-equity presentation.)
- **D-04:** If a document has no cash flow or equity changes statement (common for SMEs), ingestion succeeds silently with zero rows for those statement types — no failure, no warning. Missing statements are normal and Phase 5 handles them gracefully.

### Multi-page coverage (EXTR-05)
- **D-05:** Replace the current greedy score-sort page selection with: include ALL pages scoring above zero (at least one financial keyword), sorted by page index. This ensures continuation pages (page 2 of a 2-page P&L) are never dropped because they have fewer headers than page 1.
- **D-06:** When total content across all scored pages exceeds 60K chars (MAX_TEXT_CHARS), still truncate — but drop the lowest-scored pages first (not the last pages by index). 60K cap stays unchanged.
- **D-07:** Minimum score threshold: `score > 0` (at least one financial synonym match). Pages scoring 0 (cover pages, directors' reports, notes) are excluded. Claude ignores irrelevant content in included pages — false-positive pages are harmless.

### Sign convention enforcement (EXTR-02)
- **D-08:** Add a deterministic post-processing normalization layer (`_normalize_signs()`) that runs after Claude returns rows (and also after the rule-based extractor path). Known cost/expense canonical keys must always carry a negative sign: `cogs`, `operating_expenses`, `depreciation`, `interest_expense`, `tax`. If any of these are returned as strictly positive, flip the sign.
- **D-09:** Zero values (0.0) are left as-is regardless of the canonical key — only strictly positive values on known cost keys are flipped. No logging of flips needed (keeps output clean for Phase 5 consumers).
- **D-10:** Period keys are stored as 4-digit year strings (e.g., `"2025"`, `"2024"`). If the source shows `"FY2025"`, `"Year ended 31 March 2025"`, or similar, extract just the 4-digit year. Claude handles normalization; the schema enforces the string type.

### Word document ingestion (FILE-01)
- **D-11:** Add `extract_docx_text()` alongside the existing `extract_pdf_text()` and `extract_excel_text()` functions. Dispatched by file extension (`.docx`) in the ingestion router.
- **D-12:** Table-first extraction: iterate `doc.tables`, render each row as tab-separated cells (`"Label\t2025\t2024\t2023"`), one row per line. Preserves column→period alignment for Claude. Non-table paragraphs appended as plain text after all tables.
- **D-13:** If a `.docx` has no tables, fall back to paragraph text only — Claude infers structure from the flat text. No error; extraction proceeds at reduced quality.
- **D-14:** Accept `.docx` only. Legacy `.doc` (binary format) is not supported — python-docx does not handle it and adding LibreOffice conversion is out of scope for v1.

### OCR reliability (FILE-02)
- **D-15:** Raise the `_page_has_text()` threshold from 20 chars to 100 chars. Pages with < 100 chars of pdfplumber-extracted text are classified as image-only and sent to OCR. This catches pages with sparse text artifacts that would otherwise miss the OCR path.
- **D-16:** Increase OCR DPI from 200 to 300 for better accuracy on financial tables with small fonts.
- **D-17:** Keep `--psm 6` (single uniform block) for Tesseract — appropriate for financial statement pages. No deskew or Pillow pre-processing needed for v1; most scanned SME documents are reasonably upright.
- **D-18:** `HAS_TESSERACT` flag stays. If Tesseract is not installed, image pages silently produce empty strings — same behavior as today. No user-facing error for missing Tesseract.

### Claude's Discretion
- Canonical CF and EQ row key sets (D-02, D-03): chosen to match the standard summary-level that SME accountants produce — not a full sub-line breakdown.
- `_normalize_signs()` placement: runs as the last step of `persist_extraction()` before DB insert, so both Claude and rule-extractor paths go through the same normalization.
- EXTR-04 (non-standard label mapping): the existing `label_patterns` pattern library already handles this. Phase 4 improvements to the Claude prompt (add more SME synonym examples) and rule extractor synonym dictionaries are at Claude's discretion — no specific user preference stated.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — EXTR-01 (all statement types), EXTR-02 (sign convention), EXTR-03 (period attribution), EXTR-04 (label mapping), EXTR-05 (multi-page), FILE-01 (Word), FILE-02 (OCR)
- `.planning/ROADMAP.md` — Phase 4 goal, 7 success criteria, and 4 plan descriptions

### Core extraction code (MUST read before changing)
- `backend/ingestion.py` — full ingestion pipeline: `extract_pdf_text()` (page scoring to fix for D-05/D-06), `_page_has_text()` (threshold to raise for D-15), `_ocr_page()` (DPI to raise for D-16), `EXTRACT_TOOL` schema (add cf/eq for D-01), `SYSTEM_PROMPT` (update for new statement types + sign convention examples), `call_claude()`, `persist_extraction()` (add `_normalize_signs()` call per D-08)
- `backend/rule_extractor.py` — `PNL_SYNS`, `BS_SYNS`, `_score_page()` (page scoring logic), `rule_based_extract()` (sign convention enforcement needed here too per D-08)

### Database schema
- `backend/db.py` — `financial_rows` table: `statement` column must accept `"cf"` and `"eq"` in addition to `"pnl"` and `"bs"` (no schema migration needed if stored as TEXT, but verify no enum/check constraint blocks new values)

### Conventions and patterns
- `.planning/codebase/CONVENTIONS.md` — async DB pattern, `run_in_executor` wrapping for sync libraries, error handling style
- `.planning/codebase/ARCHITECTURE.md` — ingestion pipeline data flow; `_run_ingestion` background task entry point

### Prior phase context
- `.planning/phases/03-business-profile-intake/03-CONTEXT.md` — D-05 specifics: the EBITDA bridge queries `depreciation_amortisation` and `depreciation` as fallback; Phase 4 must ensure `depreciation` (or `depreciation_amortisation`) is reliably extracted as a canonical key in the `"pnl"` statement
- `.planning/phases/03-5-admin-gate-wizard-shell/03-5-CONTEXT.md` — `/wizard/upload` reuses `_run_ingestion` — any changes to the ingestion pipeline apply to wizard uploads too

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `extract_pdf_text()` in `backend/ingestion.py` — existing page scoring and aggregation; D-05/D-06 are changes to the internal sorting/filtering logic only, not a rewrite
- `extract_excel_text()` in `backend/ingestion.py` — pattern to follow for `extract_docx_text()` (same signature: returns `(claude_text, sheet_texts, count, used_ocr=False)`)
- `_ocr_page()` in `backend/ingestion.py` — raises DPI from 200 to 300 (D-16); no structural change
- `_page_has_text()` in `backend/ingestion.py` — threshold raised from 20 to 100 chars (D-15)
- `rule_based_extract()` in `backend/rule_extractor.py` — sign normalization from `_normalize_signs()` must also apply to this path (D-08)
- `persist_extraction()` in `backend/ingestion.py` — `_normalize_signs()` inserted before DB write

### Established Patterns
- New file format path: add `extract_docx_text()` alongside the two existing extractors; file extension routing in `ingest_document()` dispatches to the right extractor
- `asyncio.get_running_loop().run_in_executor(None, ...)` — used to wrap sync pdfplumber and pandas calls; `python-docx` is also sync, same pattern applies
- `try/except ImportError` for optional dependencies — python-docx added with same guard pattern as pytesseract
- `HAS_TESSERACT` flag pattern — consider `HAS_PYTHON_DOCX` flag for graceful degradation if python-docx not installed

### Integration Points
- `EXTRACT_TOOL` schema (`_ROW_SCHEMA`) — add `"cf"` and `"eq"` to the `statement` enum (D-01)
- `SYSTEM_PROMPT` — update canonical key sections to include CF and EQ keys; add sign convention examples
- File extension routing in `ingest_document()` — `.docx` dispatches to `extract_docx_text()` (alongside existing `.pdf` and `.xlsx/.xls/.xlsm` branches)
- Frontend upload accept attribute — add `.docx` to the accepted file types list in `frontend/index.html` (both admin upload and wizard upload inputs)
- `financial_rows` DB table — verify `statement TEXT` column has no check constraint blocking `"cf"`/`"eq"` values; if so, migration needed

</code_context>

<specifics>
## Specific Ideas

- The `_normalize_signs()` function should be a pure function (takes a list of rows, returns a list of rows) so it's testable independently. It should not modify rows in-place — return new row dicts with corrected values.
- For the docx table renderer: use `"\t".join(cell.text.strip() for cell in row.cells)` per row, then join rows with `"\n"`. Prefix the table with `--- TABLE N ---` markers (matching the `--- PAGE N ---` convention already used for PDF pages).
- Page scoring change (D-05): replace the current `scored.sort(key=lambda x: -x[0])` + greedy fill with a filter: `selected = [(i, pt) for i, pt in enumerate(all_pages) if score(pt) > 0]`, then sort by index, then truncate at MAX_TEXT_CHARS by dropping lowest-score pages if needed.
- The EBITDA bridge in Phase 3 uses `depreciation_amortisation` as the canonical key. The ingestion code currently defines `depreciation` as the P&L canonical key (line 46: `("depreciation", "Depreciation & amortisation")`). These need to be consistent. Either rename the canonical key to `depreciation_amortisation` or update the Phase 3 bridge query to use `depreciation`. Check `backend/ingestion.py:46` and `financial_rows` existing data before deciding — do not silently break the Phase 3 EBITDA bridge.

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.

</deferred>

---

*Phase: 4-Extraction-Quality*
*Context gathered: 2026-05-17*
