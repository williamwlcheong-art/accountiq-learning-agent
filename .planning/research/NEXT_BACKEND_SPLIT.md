# Next.js / FastAPI Split

**Date:** 2026-07-01

## Decision

AccountIQ uses Next.js for the frontend and keeps FastAPI as the backend of record.

Next.js owns:

- App routing and layouts
- React UI state
- Login/register screens
- Regular-user wizard
- Admin workflows
- Browser E2E tests
- Same-origin `/api/backend/:path*` proxy

FastAPI owns:

- Auth cookies and role checks
- SQLite schema and all durable writes
- File uploads and local file storage
- PDF, Excel, and Word extraction
- OCR and synchronous document-processing libraries
- Claude extraction/report calls
- Valuation/research logic
- Background jobs
- Report viewer HTML
- Email notifications

## Why Not Rewrite The Backend Into Next.js Now?

- Upload, OCR, extraction, and report generation are long-running workloads that fit the existing Python runtime better than Next route handlers.
- The backend already has a substantial pytest suite and working data-isolation/auth behavior.
- The Python code uses local SQLite and local files. Moving those writes into a serverless-style Next deployment would create deployment constraints before the product needs them.
- The biggest maintainability problem was the single-file UI, not the extraction backend.

## Development Topology

```text
http://localhost:3000
  -> Next.js app in web/
  -> /api/backend/:path* rewrite
  -> http://127.0.0.1:8765/:path*
  -> FastAPI backend
```

## Production Topology

Run Next.js and FastAPI as separate services behind one public origin.

Recommended routing:

- `/_next/*`, `/login`, `/wizard`, `/admin/*`, `/account`, `/` -> Next.js
- `/api/backend/*` -> FastAPI, either through the Next rewrite or a reverse proxy rule
- Large upload and report routes should ultimately bypass serverless limits and land on FastAPI directly or through a streaming-capable reverse proxy.

## E2E Strategy

Playwright uses deterministic backend mode:

- `ACCOUNTIQ_DB_PATH=data/accountiq_e2e.db`
- `ACCOUNTIQ_E2E_MODE=true`
- `OWNER_EMAIL=owner-e2e@example.com`

This validates browser workflows without touching the dev DB or external services.

## Legacy UI

`frontend/index.html` is retained as rollback/reference code only. FastAPI serves it at `/app` only when:

```bash
ACCOUNTIQ_SERVE_LEGACY_FRONTEND=true
```
