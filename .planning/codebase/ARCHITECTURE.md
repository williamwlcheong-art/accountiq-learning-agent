---
last_mapped: 2026-07-01
---

# Architecture

## Pattern

**Single repository, split runtime architecture:**

- **Frontend:** Next.js App Router application in `web/`
- **Backend:** Python FastAPI API in `backend/`
- **Database:** SQLite via `aiosqlite`, with WAL mode and foreign keys enabled
- **Legacy UI:** `frontend/index.html`, served at `/app` only when `ACCOUNTIQ_SERVE_LEGACY_FRONTEND=true`

Next.js owns routing, React state, presentation, route guards, and browser E2E coverage. FastAPI remains the system of record for auth cookies, SQLite writes, uploads, extraction, valuation, report generation, email, and all long-running work.

## Runtime Shape

```text
Browser
  |
  | http://localhost:3000
  v
Next.js app in web/
  | pages, layouts, React components
  | /api/backend/:path* rewrite
  v
FastAPI backend on http://127.0.0.1:8765
  | auth, uploads, ingestion, reports, settings
  v
SQLite + data/pdfs + Python extraction/report modules
```

## Layers

```text
Next.js UI
  - /login
  - /wizard
  - /admin/*
  - /account
  - /api/backend/:path* proxy

FastAPI API
  - /auth/*
  - /companies*
  - /documents*
  - /financials*
  - /patterns*
  - /analytics*
  - /settings
  - /wizard/*

Backend Services
  - ingestion.py: PDF, Excel, Word extraction
  - rule_extractor.py: no-API fallback extraction
  - report_prompts.py: report prompt construction and section schemas
  - valuation.py: DCF, multiples, risk scoring
  - research_loop.py: valuation research
  - report_email.py: report-ready notification email

Persistence
  - data/accountiq_learning.db
  - data/pdfs/{company_id}/
  - data/exports/
```

## Key Abstractions

### API Proxy (`web/next.config.ts`)

Next.js rewrites `/api/backend/:path*` to the FastAPI origin from `FASTAPI_ORIGIN` (default `http://127.0.0.1:8765`). Browser code calls the proxy so auth cookies stay same-origin to the Next.js app.

### API Clients (`web/lib/api-client.ts`, `web/lib/server-api.ts`)

Client components use typed fetch helpers that preserve credentials and normalize backend errors. Server components/layouts use `headers()` to forward cookies when checking the current user for redirects.

### Auth And Role Split (`backend/auth.py`, `web/lib/auth.ts`)

FastAPI issues the `accountiq_session` HttpOnly cookie. Next.js reads the user via `/auth/me`; admin routes require `is_admin`, while regular users land in `/wizard`.

### Ingestion Pipeline (`backend/ingestion.py`)

`ingest_document()` extracts text, calls Claude with forced tool-use when configured, falls back to rules when needed, and persists financial rows plus learned label patterns.

### Deterministic E2E Mode (`ACCOUNTIQ_E2E_MODE=true`)

E2E mode uses an isolated SQLite path (`ACCOUNTIQ_DB_PATH`) and short-circuits ingestion/report generation with deterministic content. This lets Playwright verify upload, status polling, report viewing, XSS escaping, and responsive behavior without Anthropic, OCR, SMTP, or the dev database.

## Data Flow: Wizard Report

```text
POST /wizard/upload
  -> save file under data/pdfs/{company_id}/
  -> create company + document for the authenticated user
  -> background ingestion starts

GET /wizard/document/{id}/status
  -> poll until extraction_status is done or failed

POST /wizard/report/generate
  -> persist intake answers
  -> background report generation starts

GET /wizard/report/{id}/status
  -> poll until report is done or failed

GET /wizard/report/{id}/view
  -> render escaped report HTML for the owning user
```

## Entry Points

- **FastAPI dev:** `source venv/bin/activate && cd backend && uvicorn main:app --reload --port 8765`
- **Next.js dev:** `cd web && npm run dev`
- **Next.js app:** `http://localhost:3000`
- **FastAPI health:** `GET http://127.0.0.1:8765/health`
- **Legacy UI fallback:** `ACCOUNTIQ_SERVE_LEGACY_FRONTEND=true` then `http://localhost:8765/app`

## Concurrency Model

- FastAPI routes are async and use `aiosqlite`.
- Background tasks open their own SQLite connection.
- Synchronous LLM and document-processing calls are wrapped in executors where implemented.
- SQLite WAL mode supports concurrent reads during background writes.
