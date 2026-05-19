---
status: partial
phase: 04-extraction-quality
source: [04-VERIFICATION.md]
started: 2026-05-19T09:26:14.794Z
updated: 2026-05-19T09:26:14.794Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. OCR quality — 80%+ row recovery from scanned PDFs
expected: Upload a scanned (image-only) PDF with a known set of financial rows. At least 80% of the expected rows appear in extraction results and `has_ocr=1` is set in the documents table. OCR_DPI=300 and _page_has_text threshold >100 are confirmed in code; this test verifies the live end-to-end quality with real tesseract + a real scanned PDF.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
