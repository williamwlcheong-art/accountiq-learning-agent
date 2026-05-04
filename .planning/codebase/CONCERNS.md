---
last_mapped: 2026-05-04
---

# Concerns

## Security

### High Priority

**Wildcard CORS on a write endpoint (`main.py:35-40`)**
`allow_origins=["*"]` permits any origin to POST to `/settings`, which writes the Anthropic API key to disk. In a production context this is a serious misconfiguration.

**Unsanitized filename used for disk paths (`main.py:166`)**
```python
dest = company_dir / file.filename
```
`file.filename` comes directly from the multipart form. A crafted filename like `../../etc/passwd` or `../main.py` could write outside the intended directory. Should use `Path(file.filename).name` (basename only).

**XSS via `innerHTML` with server data (`frontend/index.html`)**
The frontend renders Claude-generated narrative text and extraction log messages using `innerHTML` without sanitization. Claude responses are user-influenced (they reflect PDF content), creating a stored XSS vector.

**No authentication on any endpoint**
All API endpoints are publicly accessible with no auth layer. Fine for localhost dev, must be addressed before any network exposure.

### Low Priority

**Module-level global mutation (`ingestion.py`)**
`ANTHROPIC_API_KEY` and `CLAUDE_MODEL` are module-level globals mutated by the settings POST endpoint. This is not thread-safe if the app ever runs with multiple workers.

## Technical Debt

**Deprecated FastAPI startup event (`main.py:55`)**
```python
@app.on_event("startup")
```
Deprecated since FastAPI 0.93. Should use `lifespan` context manager instead.

**Deprecated `asyncio.get_event_loop()` (`ingestion.py:287`)**
```python
loop = asyncio.get_event_loop()
response = await loop.run_in_executor(...)
```
`get_event_loop()` is deprecated in Python 3.10+. Should use `asyncio.get_running_loop()`.

**Manual schema migration with no version tracking (`db.py:111`)**
`_migrate_db()` applies `ALTER TABLE` statements wrapped in try/except. No migration versioning, no rollback capability. Fine for a prototype; becomes fragile with multiple developers.

## Performance

**Synchronous blocking calls in async context (`ingestion.py`)**
`pdfplumber` and `pandas` are synchronous libraries called directly in an async background task. Large PDFs will block the event loop. The Claude call correctly uses `run_in_executor`, but the text extraction steps do not.

**No file upload size limit**
`POST /documents/upload` has no `Content-Length` check or `max_size` guard. A very large file will be accepted and could exhaust disk or memory.

**Pattern library reloaded on every ingestion**
`get_pattern_library(db)` queries the full `label_patterns` table on every document ingestion. With many patterns this becomes a growing overhead. Should be cached with invalidation on write.

**Frontend 3-second polling**
`setInterval` at 3000ms per active job. With many documents in-flight this generates significant request volume. SSE or WebSocket would be more efficient.

## Fragile Areas

**Background task silently discards errors**
`_run_ingestion` catches exceptions and logs them, but the caller (the upload endpoint) has already returned a 200 response. If the background task fails, the only signal to the user is polling `/documents/{id}/status` and seeing `extraction_status: "failed"`.

**Rule extractor limited to single-page analysis**
`_extract_statement()` picks the single best-scoring page for each statement type. Multi-page financials (common in annual reports) will miss rows on secondary pages.

**Broken CSS animation reference**
The shimmer progress animation is applied in CSS but `@keyframes shimmer` is never defined in `frontend/index.html`. The processing indicator animation is broken.

**No retry/backoff for Claude API rate limits**
`call_claude()` propagates all Claude API errors except auth/billing errors (which fall back to rule-based). Rate limit errors (429) will surface as 500s to the client instead of triggering a retry.

## Missing Features / Gaps

- No file deduplication (same PDF can be uploaded multiple times)
- No document deletion endpoint
- No validation of `fiscal_year_end` format (accepts any string)
- No pagination on `/documents` or `/financials/{id}` (unbounded response size)
- No export for financial rows (only pattern export exists)
- Zero test coverage (see TESTING.md)
