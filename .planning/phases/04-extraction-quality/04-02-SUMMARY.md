---
phase: 04-extraction-quality
plan: "02"
subsystem: extraction
tags: [tdd, extraction, multi-page, ocr, page-scoring, filter-then-sort, run-in-executor]
dependency_graph:
  requires:
    - phase: "04-01"
      provides: "CF_SYNS/EQ_SYNS in rule_extractor for page scoring; 17 Wave 0 test stubs"
  provides:
    - backend/ingestion.py (D-05/D-06/D-07 filter-then-sort page selection; OCR_DPI=300; _page_has_text threshold=100; run_in_executor dispatch)
    - tests/test_extraction.py (test_multipage_truncation_drops_lowest_score implemented GREEN)
  affects:
    - Wave 3 plan (04-03) depends on run_in_executor dispatch pattern and worktree ingestion.py state
tech_stack:
  added: []
  patterns:
    - D-05 filter-then-sort: filter score > 0 first, sort by page index (not score) to preserve document order
    - D-06 cap enforcement: while loop drops lowest-scored page until under 60K cap
    - run_in_executor wrapping for all sync extraction calls in ingest_document()

key_files:
  created: []
  modified:
    - backend/ingestion.py (OCR_DPI 200→300, _page_has_text threshold 20→100, extract_pdf_text filter-then-sort, ingest_document dispatch wrapped)
    - tests/test_extraction.py (test_multipage_truncation_drops_lowest_score implemented from RED stub)

key-decisions:
  - "D-05 sort by page index (not score) after filtering: preserves narrative flow of continuation pages alongside high-scoring pages"
  - "D-06 drop lowest-scored pages first (not last-by-index): ensures continuation pages are not unfairly dropped when dense cover pages have score > 0"
  - "run_in_executor wraps both Excel and PDF dispatch branches for CONVENTIONS.md compliance (sync libs in async routes)"

requirements-completed: [EXTR-05, FILE-02]

duration: 2m
completed: "2026-05-19"
tasks_completed: 1
files_modified: 2
---

# Phase 4 Plan 02: Multi-Page Fix + OCR Reliability Summary

**filter-then-sort page selection (D-05/D-06/D-07) with CF_SYNS/EQ_SYNS scoring, OCR_DPI raised to 300, _page_has_text threshold raised to 100 chars, run_in_executor wrapping for PDF/Excel dispatch**

## Performance

- **Duration:** 2m
- **Started:** 2026-05-19T08:58:11Z
- **Completed:** 2026-05-19T09:00:32Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Replaced greedy score-sort page selection with filter-then-sort algorithm (D-05/D-06/D-07): continuation pages no longer dropped when they score lower than leading pages
- OCR now triggers on pages with < 100 chars of text (was 20 chars) and renders at 300 DPI (was 200), eliminating false text-layer detection and improving small-font table readability
- ingest_document() dispatch wrapped in run_in_executor for both PDF and Excel paths — CLAUDE.md convention compliance
- 3 new tests turned GREEN; full extraction suite at 13 passed / 4 RED stubs (Wave 3 docx targets)

## Task Commits

1. **Task 1: Fix page selection (D-05/D-06/D-07) and OCR settings (D-15/D-16)** — `8c45151` (feat)

**Plan metadata:** (added after SUMMARY commit)

## Files Created/Modified

- `backend/ingestion.py` — OCR_DPI=300, _page_has_text threshold=100, filter-then-sort page selection with CF_SYNS/EQ_SYNS, run_in_executor wrapping for Excel/PDF dispatch
- `tests/test_extraction.py` — test_multipage_truncation_drops_lowest_score implemented (was pytest.fail RED stub)

## Decisions Made

- D-05 sort by page index after filtering: ensures financial statements are presented to Claude in the order they appear in the document, preserving cross-page context (continuation rows on page N+1 follow page N naturally)
- D-06 drop-lowest-score-first: a low-scoring page that scores > 0 (e.g., a directors report with one financial reference) should be evicted before a higher-scoring financial statement page if we hit the 60K cap
- run_in_executor wraps the entire extraction function call (not just internal sync calls), consistent with CLAUDE.md convention and PATTERNS.md Edit 6

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Implemented test_multipage_truncation_drops_lowest_score**
- **Found during:** Task 1 (implementing GREEN for TDD cycle)
- **Issue:** The test stub in Plan 01 used `pytest.fail("RED — ...")` as a placeholder. The GREEN implementation needed the actual test assertion to verify D-06 behaviour.
- **Fix:** Replaced the `pytest.fail` placeholder with a proper assertion: constructs two pages (high-score and low-score), simulates the D-06 truncation loop with a small cap, and asserts the low-scored page is evicted first.
- **Files modified:** tests/test_extraction.py
- **Verification:** Test passes GREEN; correctly fails if order is reversed
- **Committed in:** 8c45151

---

**Total deviations:** 1 auto-fixed (1 missing critical — test implementation for Wave 2 stub)
**Impact on plan:** Necessary to verify D-06 behaviour. No scope creep.

## Issues Encountered

The plan's verify command specifies `cd /Users/William.Cheong/accountiq_learning && pytest tests/ -x -q` expecting exit 0. However, 4 Wave 3 docx stubs remain intentionally RED (extract_docx_text not yet implemented — Wave 3 / Plan 03). This is identical to the situation documented in Plan 01's Summary. The `-x` flag causes the suite to stop at the first Wave 3 failure. All non-docx tests pass (62 passed, 4 Wave 3 RED stubs, 1 skipped).

## Known Stubs

None — all code is functional. The 4 remaining RED tests in test_extraction.py are intentional Wave 3 stubs targeting extract_docx_text() (Plan 03).

## Threat Flags

No new security-relevant surface introduced. Changes are:
- Scoring algorithm change (read-only synonym dicts, same trust boundary as before)
- OCR threshold/DPI constants (no new input surface)
- run_in_executor wrapping (process-default thread pool, no privilege escalation)

All threat mitigations from the plan's threat model are implemented:
- T-04-02-01 (OCR output): MAX_TEXT_CHARS cap still applied — OCR garbage is bounded
- T-04-02-02 (page selection): read-only synonym dicts, no user-controlled input
- T-04-02-03 (300 DPI per-page): OCR only triggered when _page_has_text() returns False (< 100 chars)
- T-04-02-04 (run_in_executor): uses None (default thread pool), no privilege escalation

## Next Phase Readiness

- Wave 3 (Plan 04-03): ready to implement extract_docx_text(), .docx dispatch branch, and route accept changes — all stubs and infrastructure are in place
- ingest_document() dispatch already uses run_in_executor, so the .docx branch addition is a clean 1-liner insertion

---

*Phase: 04-extraction-quality*
*Completed: 2026-05-19*

## Self-Check: PASSED

Files verified:
- backend/ingestion.py — EXISTS, contains OCR_DPI = 300, threshold > 100, selected.sort(key=lambda x: x[1]), min_idx = min(range, CF_SYNS import, run_in_executor
- tests/test_extraction.py — EXISTS, contains test_multipage_truncation_drops_lowest_score with actual assertions

Commits verified:
- 8c45151 — feat(04-02): D-05/D-06/D-07 filter-then-sort + OCR threshold/DPI improvements
