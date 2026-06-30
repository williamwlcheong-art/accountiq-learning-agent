---
last_mapped: 2026-07-01
---

# Concerns

## Security

### High Priority Before External Launch

**Production secret handling**
`SECRET_KEY` must be strong and environment-specific. `.env.example` documents this, but deployment should enforce it.

**Development-only origins**
CORS is intentionally restricted for local development. Production needs an explicit allowed-origin list matching the deployed public origin.

**Legacy frontend fallback**
`frontend/index.html` exists for rollback/reference only and should stay disabled by default (`ACCOUNTIQ_SERVE_LEGACY_FRONTEND=false`). New security fixes and E2E coverage target the Next.js app.

**Report viewer authorization**
The viewer route is user-scoped and covered by E2E for escaping. Continue adding backend tests for any change to report ownership, sharing, or PDF delivery.

### Medium Priority

**Exception detail leakage**
Some backend routes still return raw exception strings in 500 responses. Before external launch, replace these with generic user-facing messages plus server-side logs.

**Runtime settings writes**
The settings endpoint persists model/API-key values to `.env` and mutates process environment. This is acceptable for local prototype use, but should become a safer secret/config path for production.

## Technical Debt

**Large FastAPI module**
`backend/main.py` still contains most routes and background task wiring. Split into routers/modules as the backend surface grows.

**Deprecated FastAPI startup event**
`@app.on_event("startup")` should eventually move to a lifespan context manager.

**Manual schema migrations**
`backend/db.py` applies `ALTER TABLE` statements directly with try/except. This is workable for the prototype, but a production launch should adopt versioned migrations.

**Duplicate/legacy email module**
`backend/report_email.py` is the active sender. `backend/mailer.py` appears to be legacy/duplicate code and should be removed or consolidated after confirming no import paths depend on it.

## Performance

**Synchronous document processing**
`pdfplumber`, `pandas`, OCR, and related extraction steps can block if called directly in async paths. Keep wrapping synchronous library calls in executors as these paths are touched.

**No upload size limit**
Uploads need a content-length/max-size guard before public launch.

**Polling**
The wizard and admin workflows poll for status. This is acceptable for current volume; SSE/WebSockets may be needed later.

**SQLite production ceiling**
SQLite is fine for local/single-instance prototype use. Multi-instance deployment requires a database migration plan.

## Missing Features / Gaps

- Stripe pay-per-report purchase gating
- Professional PDF rendering and download
- Report history/account management
- Document deletion and deduplication
- Pagination for unbounded list endpoints
- Production deployment configuration
