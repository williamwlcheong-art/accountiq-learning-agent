---
phase: 04-extraction-quality
verified: 2026-05-19T10:00:00Z
status: human_needed
score: 6/7 success criteria verified (SC7 requires human)
overrides_applied: 0
human_verification:
  - test: "Upload a scanned (image-only) PDF with a known set of financial rows and verify the extracted output"
    expected: "At least 80% of the rows that a text-layer PDF would produce are extracted via OCR"
    why_human: "OCR quality depends on scan resolution, font, and tesseract availability in the runtime environment — cannot be verified by static code analysis or unit tests alone. The code raises DPI to 300 and threshold to 100 chars (both tested), but actual row-recovery rate against a real scanned PDF requires a live run."
---

# Phase 4: Extraction Quality Verification Report

**Phase Goal:** Improve extraction quality — multi-page coverage, OCR reliability, CF/EQ statement detection, sign normalisation, Word (.docx) ingestion
**Verified:** 2026-05-19T10:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | Income statement, balance sheet, cash flow statement, and equity changes are each extracted and stored in separate statement-type buckets | VERIFIED | `_ROW_SCHEMA` enum = `["pnl","bs","cf","eq"]` (ingestion.py:172); `CF_ROWS` (4 entries, lines 78-83), `EQ_ROWS` (5 entries, lines 85-91); `persist_extraction()` stores `stmt` column to `financial_rows`; `SYSTEM_PROMPT` includes CF and EQ canonical key sections (lines 140-144); `test_row_schema_includes_cf_eq` and `test_cf_eq_statement_types` PASS |
| SC2 | All extracted costs/expenses carry a negative sign; all revenues and assets carry a positive sign regardless of source format | VERIFIED | `_COST_KEYS = frozenset({"cogs","operating_expenses","depreciation","interest_expense","tax"})` (ingestion.py:397); `_normalize_signs()` flips strictly positive values (lines 400-418); wired in `persist_extraction()` at line 436: `rows = _normalize_signs(parsed.get("rows", []))`; SYSTEM_PROMPT sign convention rule 7 instructs Claude; all 3 normalize-signs tests PASS |
| SC3 | A 3-year comparative P&L assigns each column's values to the correct fiscal year | VERIFIED | `_detect_periods()` in rule_extractor.py (line 230) uses regex `r'\b(FY\s?\d{2,4}|20\d{2})\b'` handling FY prefix; `test_detect_periods_normalizes_fy_prefix` PASS; period strings stored per-row in `financial_rows.period` column |
| SC4 | Common SME labels ("Owners Drawings", "Directors Fees", "Turnover", "Cost of Sales") map to the correct canonical keys | VERIFIED | `PNL_SYNS["operating_expenses"]` extended with "owners drawings", "drawings", "directors fees", "directors remuneration", "wages", etc. (rule_extractor.py:39-48); `PNL_SYNS["cogs"]` extended with "subcontractors", "subcontract costs", "contract labour" (lines 27-30); `test_sme_label_owners_drawings` and `test_sme_label_directors_fees` PASS |
| SC5 | A 20-row P&L spread across two PDF pages produces all 20 rows (not just the first page) | VERIFIED | D-05/D-06/D-07 filter-then-sort implemented in `extract_pdf_text()`: filters `score > 0` pages then sorts by page index (ingestion.py:242-244); D-06 drops lowest-scored page first when over 60K cap (lines 247-251); CF_SYNS/EQ_SYNS included in scoring (lines 233-237); all 3 multi-page tests (`test_multipage_includes_continuation`, `test_multipage_excludes_cover_page`, `test_multipage_truncation_drops_lowest_score`) PASS |
| SC6 | A .docx file containing a financial statement table is ingested and produces extracted financial rows | VERIFIED | `extract_docx_text()` implemented (ingestion.py:291-327) with table-first extraction, tab-separated cells, `--- TABLE N ---` markers, merged-cell dedup via `id(cell._tc)`; `.docx` elif dispatch in `ingest_document()` (lines 522-525) via `run_in_executor`; `.docx` in `allowed` set in both `/documents/upload` (main.py:533) and `/wizard/upload` (main.py:930); frontend `accept=` attributes (index.html:338, 497) and JS allowed arrays (lines 1987, 2094) updated; all 4 docx tests PASS |
| SC7 | A scanned PDF with no text layer is processed via OCR and produces at least 80% of the rows a text-layer PDF would | UNCERTAIN | `OCR_DPI = 300` (ingestion.py:42) verified; `_page_has_text()` threshold is `> 100` chars (line 205) verified; `test_ocr_dpi_is_300` and `test_page_has_text_threshold` PASS. **The 80% row-recovery quality claim requires running against a real scanned PDF — cannot be verified by static code analysis.** |

**Score:** 6/7 success criteria verified (SC7 requires human)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_extraction.py` | 17 pytest test functions | VERIFIED | 430 lines; all 17 functions present; all 17 PASS |
| `backend/ingestion.py` | `_normalize_signs()`, `CF_ROWS`, `EQ_ROWS`, updated `ALL_ROWS`, updated `_ROW_SCHEMA` enum, updated `SYSTEM_PROMPT`, `HAS_PYTHON_DOCX` guard, `extract_docx_text()`, filter-then-sort page selection, `OCR_DPI=300`, `_page_has_text` threshold 100 | VERIFIED | All symbols present at expected locations |
| `backend/rule_extractor.py` | `CF_SYNS`, `EQ_SYNS` dicts; extended `PNL_SYNS` with SME synonyms | VERIFIED | `CF_SYNS` at line 159, `EQ_SYNS` at line 179; "owners drawings" line 39, "directors fees" line 40, "subcontractors" line 29, "sundry income" line 22 |
| `backend/requirements.txt` | `python-docx>=1.1.0` | VERIFIED | Line 18: `python-docx>=1.1.0` |
| `backend/main.py` | `.docx` in allowed sets for both upload routes | VERIFIED | `.docx` at lines 533 and 930; error messages updated to "PDF, Excel, and Word files are accepted" at lines 535 and 932 |
| `frontend/index.html` | `.docx` in accept attributes and JS allowed arrays on both file inputs | VERIFIED | 4 occurrences: `accept=` on `#up-file` (line 338), `#wiz-file` (line 497), JS arrays at lines 1987 and 2094 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ingestion.py persist_extraction()` | `_normalize_signs()` | `rows = _normalize_signs(parsed.get("rows", []))` | WIRED | ingestion.py:436 — confirmed |
| `ingestion.py extract_pdf_text()` | `rule_extractor CF_SYNS / EQ_SYNS` | `from rule_extractor import _score_page, PNL_SYNS, BS_SYNS, CF_SYNS, EQ_SYNS` | WIRED | ingestion.py:233 — confirmed; scoring expression at lines 236-237 uses both |
| `ingestion.py _page_has_text()` | `_ocr_page()` | `if not _page_has_text(page): t = _ocr_page(page)` | WIRED | ingestion.py:203-211; threshold `> 100` at line 205 |
| `ingestion.py extract_pdf_text()` | D-05/D-06/D-07 filter-then-sort | `selected = [(s, i, pt) for s, i, pt in scored if s > 0]; selected.sort(key=lambda x: x[1])` | WIRED | ingestion.py:243-244; D-06 while loop at lines 247-251 |
| `ingestion.py ingest_document()` | `extract_docx_text()` | `elif fp_lower.endswith(".docx"): run_in_executor(None, extract_docx_text, filepath)` | WIRED | ingestion.py:522-525 |
| `backend/main.py /documents/upload` | `.docx` allowed | `allowed = {".pdf", ".xlsx", ".xls", ".xlsm", ".docx"}` | WIRED | main.py:533 |
| `backend/main.py /wizard/upload` | `.docx` allowed | `allowed = {".pdf", ".xlsx", ".xls", ".xlsm", ".docx"}` | WIRED | main.py:930 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `extract_docx_text()` | `combined` (tab-separated table rows) | `DocxDocument(filepath).tables` — real python-docx parse | Yes — iterates actual document tables | FLOWING |
| `_normalize_signs()` | `rows` (list of row dicts) | `parsed.get("rows", [])` from Claude API response | Yes — processes real rows from LLM output | FLOWING |
| `extract_pdf_text()` page selection | `selected` (filtered page list) | `_score_page()` against real page text from pdfplumber | Yes — filters real pages by keyword score | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 17 extraction tests pass | `pytest tests/test_extraction.py -v` | 17 passed, 0 failed, 2 warnings | PASS |
| Full test suite unbroken | `pytest tests/ -q` | 66 passed, 1 skipped, 2 warnings | PASS |
| `OCR_DPI = 300` in ingestion.py | `grep "OCR_DPI = 300" backend/ingestion.py` | Match at line 42 | PASS |
| `_page_has_text` threshold 100 | `grep "len(text.strip()) > 100" backend/ingestion.py` | Match at line 205 | PASS |
| D-05 sort by page index | `grep "selected.sort(key=lambda x: x\[1\])" backend/ingestion.py` | Match at line 244 | PASS |
| D-06 drop lowest scored | `grep "min_idx = min(range" backend/ingestion.py` | Match at line 248 | PASS |
| `.docx` in both upload routes | `grep -c "\.docx" backend/main.py` | 2 matches (lines 533, 930) | PASS |
| `.docx` in 4 frontend locations | `grep -c "\.docx" frontend/index.html` | 4 matches | PASS |
| `extract_docx_text` function defined | `grep -c "extract_docx_text" backend/ingestion.py` | 2 occurrences (definition + dispatch call) | PASS |
| Merged cell dedup present | `grep "cell_id = id(cell._tc)" backend/ingestion.py` | Match at line 312 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| EXTR-01 | 04-01 | System correctly extracts income statement, balance sheet, cash flow statement, and equity changes | SATISFIED | `_ROW_SCHEMA` enum expanded to `["pnl","bs","cf","eq"]`; `CF_ROWS`/`EQ_ROWS` defined; `SYSTEM_PROMPT` includes CF/EQ sections; all 4 statement types routed to `financial_rows` via `persist_extraction()` |
| EXTR-02 | 04-01 | Extracted values use consistent sign convention | SATISFIED | `_normalize_signs()` pure function flips positive cost keys; wired in `persist_extraction()` before row INSERT loop; SYSTEM_PROMPT rule 7 guides Claude output |
| EXTR-03 | 04-01 | Financial data attributed to correct fiscal period | SATISFIED | `_detect_periods()` handles `FY` prefix regex; `test_detect_periods_normalizes_fy_prefix` PASS; pre-existing behavior confirmed |
| EXTR-04 | 04-01 | Non-standard SME labels correctly mapped to canonical keys | SATISFIED | `PNL_SYNS["operating_expenses"]` extended with 11 AU/NZ SME labels; `PNL_SYNS["cogs"]` with 3 trade labels; `test_sme_label_owners_drawings` and `test_sme_label_directors_fees` PASS |
| EXTR-05 | 04-02 | Multi-page financial statements extracted in full | SATISFIED | D-05/D-06/D-07 filter-then-sort with CF/EQ scoring; continuation pages included; lowest-scored pages dropped first at 60K cap; all 3 multi-page tests PASS |
| FILE-01 | 04-03 | User can upload Word (.docx) documents | SATISFIED | `extract_docx_text()` implemented; `.docx` dispatch in `ingest_document()`; `.docx` in allowed sets in both upload routes; frontend file pickers updated; all 4 docx tests PASS |
| FILE-02 | 04-02 | OCR extraction from scanned/image-only PDFs is reliable | PARTIAL | `OCR_DPI = 300` and `_page_has_text` threshold 100 are implemented and tested. **Actual reliability (80%+ row recovery) against a real scanned PDF requires human testing — cannot be verified statically.** |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | No TODOs, stubs, placeholder returns, or empty handlers detected in any Phase 4 modified files | — | — |

### Human Verification Required

#### 1. OCR Row Recovery Rate (SC7 / FILE-02)

**Test:** Upload a scanned (image-only) PDF with a known set of financial statement rows (e.g., a P&L with 15-20 rows) where the file has no embedded text layer. Verify extraction results in the admin panel.

**Expected:** At least 80% of the rows extracted from an equivalent text-layer PDF are also extracted from the scanned version. OCR should trigger (check `has_ocr=1` in the documents table). Row labels should be legible and mapped to canonical keys.

**Why human:** OCR quality depends on the actual runtime environment (tesseract installed and on PATH, scan resolution, font rendering at 300 DPI). The code changes are correct — DPI raised to 300, threshold raised to 100 chars — but a unit test cannot confirm real-world OCR output quality. This requires a live system run with a real scanned PDF.

### Gaps Summary

No blocking gaps found. All must-have truths are VERIFIED except SC7 (OCR quality), which requires a human test with a real scanned PDF. All 17 extraction tests pass, the full suite (66 passed, 1 skipped) is green, and all 7 requirement IDs (EXTR-01 through EXTR-05, FILE-01, FILE-02) are accounted for and implemented.

---

_Verified: 2026-05-19T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
