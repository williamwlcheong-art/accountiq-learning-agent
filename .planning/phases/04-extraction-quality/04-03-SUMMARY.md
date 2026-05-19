---
phase: 04-extraction-quality
plan: "03"
subsystem: extraction
tags: [tdd, extraction, docx, python-docx, word-ingestion, file-formats, run-in-executor]
dependency_graph:
  requires:
    - phase: "04-01"
      provides: "HAS_PYTHON_DOCX guard; 4 Wave 3 RED test stubs in test_extraction.py"
    - phase: "04-02"
      provides: "run_in_executor dispatch pattern in ingest_document(); worktree ingestion.py state"
  provides:
    - backend/ingestion.py (extract_docx_text() function; .docx branch in ingest_document())
    - backend/main.py (.docx in allowed extensions in /documents/upload and /wizard/upload)
    - frontend/index.html (.docx in accept attributes and JS allowed arrays on both file inputs)
    - tests/test_extraction.py (test_ingest_dispatches_docx implemented from RED stub)
  affects:
    - Phase 5 report generation — Word doc financials now flow through to financial_rows
    - Phase 7 PDF rendering — no impact (extraction only)
tech_stack:
  added:
    - python-docx>=1.1.0 (already added to requirements.txt in Plan 01; now used in production code path)
  patterns:
    - Table-first docx extraction: tables as tab-separated rows with --- TABLE N --- markers, then paragraphs (D-12)
    - Merged cell deduplication via id(cell._tc) — prevents doubled column headers from horizontal merges
    - HAS_PYTHON_DOCX guard — mirrors HAS_TESSERACT optional dependency pattern
    - try/except around python-docx parse — T-04-03-01 mitigation for malformed .docx (ZIP bomb / bad XML)
key_files:
  created: []
  modified:
    - backend/ingestion.py (extract_docx_text() function added; .docx elif branch in ingest_document())
    - backend/main.py (.docx in allowed set in both /documents/upload and /wizard/upload)
    - frontend/index.html (.docx in accept attributes and JS allowed arrays on both file inputs)
    - tests/test_extraction.py (test_ingest_dispatches_docx implemented from RED stub)
key-decisions:
  - "extract_docx_text() wraps parse in try/except RuntimeError to satisfy T-04-03-01 (malformed .docx guard)"
  - "D-12 tables-first: doc.tables iterated before doc.paragraphs; paragraphs appended after all tables"
  - "Dispatch branch added between Excel and PDF fallback (not as else) to preserve correct extension routing"
  - "test_ingest_dispatches_docx implemented via monkeypatch of extract_docx_text attribute (not end-to-end async)"
requirements-completed: [FILE-01]
duration: 8min
completed: "2026-05-19"
---

# Phase 4 Plan 03: Word (.docx) Ingestion Summary

**extract_docx_text() with merged-cell dedup via id(cell._tc), .docx dispatch in ingest_document() via run_in_executor, and .docx allowed in both upload routes and frontend file pickers — all 17 extraction tests GREEN**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-19T09:15:00Z
- **Completed:** 2026-05-19T09:23:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `extract_docx_text()` implemented with table-first extraction (D-12): tab-separated cells per row, `--- TABLE N ---` markers, paragraphs appended after tables
- Merged cell deduplication via `id(cell._tc)` prevents `"2025\t2025"` doubling on horizontally spanned header cells
- `try/except` wrapper handles malformed .docx (ZIP bomb / bad XML) — T-04-03-01 security mitigation
- `.docx` elif branch added to `ingest_document()` dispatch between Excel and PDF fallback, using `run_in_executor`
- Both upload routes (`/documents/upload`, `/wizard/upload`) now accept `.docx` with updated error messages
- Frontend `accept=` attributes and JS allowed arrays on both file inputs updated to include `.docx`
- All 17 tests in `tests/test_extraction.py` GREEN; full suite 66 passed 1 skipped

## Task Commits

1. **Task 1: extract_docx_text() + ingest_document() .docx dispatch** — `cd60dfc` (feat)
2. **Task 2: Accept .docx in upload routes and frontend** — `6041cc2` (feat)

**Plan metadata:** (added after SUMMARY commit)

## Files Created/Modified

- `backend/ingestion.py` — Added `extract_docx_text()` function (lines 287–330) and `.docx` elif branch in `ingest_document()` dispatch (after Excel branch, before PDF else)
- `backend/main.py` — `.docx` added to `allowed` set in `/documents/upload` (line 533) and `/wizard/upload` (line 930); error messages updated to "PDF, Excel, and Word files are accepted"
- `frontend/index.html` — `.docx` added to `accept=` attribute on `#up-file` (line 338) and `#wiz-file` (line 497); `.docx` added to JS `allowed` arrays in admin upload handler (line 1987) and wizard upload handler (line 2094)
- `tests/test_extraction.py` — `test_ingest_dispatches_docx` implemented from RED stub using monkeypatch

## Decisions Made

- **Malformed .docx guard (T-04-03-01):** Wrapped `DocxDocument(filepath)` and all processing in `try/except Exception` that re-raises as `RuntimeError`. This lets `ingest_document()` catch it at its outer `except Exception` and set `extraction_status='failed'` — per the threat model disposition.
- **Dispatch branch position:** `.docx` elif placed between Excel (`endswith((".xlsx", ".xls", ".xlsm"))`) and PDF else, not as a parallel if — ensures PDF fallback is still the catch-all for unrecognised extensions.
- **test_ingest_dispatches_docx implementation:** Used monkeypatch to replace `extract_docx_text` on the module directly, then exercised the dispatch logic inline (not via the async `ingest_document()` function which requires a DB). This tests the conditional branching without an integration test overhead.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added try/except wrapper for malformed .docx parsing**
- **Found during:** Task 1 (implementing extract_docx_text())
- **Issue:** T-04-03-01 in the plan's threat model specifies `mitigate` disposition: wrap extract_docx_text() body in try/except for BadZipFile or lxml parse errors
- **Fix:** Added `try/except Exception` around the full `DocxDocument(filepath)` and processing block; re-raises as `RuntimeError` so `ingest_document()` catches it at its outer exception handler and marks the document as `failed`
- **Files modified:** backend/ingestion.py
- **Verification:** Function raises RuntimeError for exceptions from python-docx; ingest_document outer handler catches it
- **Committed in:** cd60dfc (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical — threat model mitigation T-04-03-01)
**Impact on plan:** Necessary for security/reliability. No scope creep.

## Issues Encountered

None — both tasks executed cleanly. The test infrastructure from Plans 01-02 (monkeypatch patterns, conftest fixtures, sys.path setup) was immediately usable.

## Known Stubs

None — all code is functional. The `extract_docx_text()` function produces real output; the `.docx` dispatch branch routes real files.

## Threat Flags

No new security-relevant surface beyond what the plan's threat model already covers:
- T-04-03-01 (malformed .docx): MITIGATED — try/except wrapper in extract_docx_text()
- T-04-03-02 (path traversal): ACCEPTED — already mitigated by Path(file.filename).name in both upload routes
- T-04-03-03 (garbage text size): ACCEPTED — MAX_TEXT_CHARS cap applied in extract_docx_text() return
- T-04-03-04 (.docx macros): ACCEPTED — python-docx is read-only XML parser
- T-04-03-05 (frontend bypass): ACCEPTED — backend allowed-set check is the authoritative guard

## Next Phase Readiness

- All 7 Phase 4 requirements covered across Plans 01-03: EXTR-01, EXTR-02, EXTR-03, EXTR-04, EXTR-05, FILE-01, FILE-02
- Word documents uploaded via either route now flow through `extract_docx_text()` → `call_claude()` or `rule_based_extract()` → `persist_extraction()` → `financial_rows` table — same pipeline as PDF/Excel
- Phase 5 report generation can access CF/EQ rows and docx-sourced financial data without further extraction changes

---
*Phase: 04-extraction-quality*
*Completed: 2026-05-19*

## Self-Check: PASSED

Files verified:
- backend/ingestion.py — EXISTS, contains extract_docx_text, id(cell._tc), endswith(".docx")
- backend/main.py — EXISTS, contains .docx in both allowed sets and updated error messages
- frontend/index.html — EXISTS, contains .docx in both accept attributes and JS allowed arrays
- tests/test_extraction.py — EXISTS, contains test_ingest_dispatches_docx with monkeypatch
- .planning/phases/04-extraction-quality/04-03-SUMMARY.md — EXISTS

Commits verified:
- cd60dfc — feat(04-03): extract_docx_text() + .docx dispatch in ingest_document()
- 6041cc2 — feat(04-03): accept .docx in upload routes (main.py) and frontend (index.html)
