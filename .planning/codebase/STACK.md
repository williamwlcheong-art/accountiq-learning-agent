# Technology Stack

**Analysis Date:** 2026-07-01

## Languages

- **Python 3.12:** FastAPI backend, ingestion, valuation, report generation, SQLite access
- **TypeScript:** Next.js frontend, React components, typed API helpers, Playwright tests
- **HTML/CSS/JavaScript:** Legacy `frontend/index.html` fallback only

## Backend Runtime

- **FastAPI 0.136.0:** Async REST API, route dependencies, uploads, background tasks
- **Uvicorn 0.44.0:** ASGI dev server
- **SQLite + aiosqlite 0.22.1:** Local database with WAL mode and foreign keys
- **python-dotenv 1.2.2:** Loads `.env`; settings endpoint can persist selected values
- **pyjwt 2.12.1 + pwdlib[argon2] 0.3.0:** Session cookies signed with `SECRET_KEY`; Argon2 password hashing
- **stripe 12.5.0:** Checkout sessions and webhook verification for paid valuations (`backend/payments.py`)
- **weasyprint 69.0:** Branded A4 PDF export of released reports (`backend/report_rendering.py`); needs Pango and GLib from Homebrew on macOS

Dev command:

```bash
source venv/bin/activate
cd backend
uvicorn main:app --reload --port 8765
```

## Frontend Runtime

- **Next.js 16.2.9:** App Router application in `web/`
- **React 19.2.4:** Client components for wizard/admin workflows
- **TypeScript 5:** Static checking via `tsc --noEmit`
- **ESLint 9 + eslint-config-next:** Frontend linting
- **openapi-typescript 7.13.0:** Generates `web/types/api.ts` from FastAPI OpenAPI

Dev command:

```bash
cd web
pnpm dev
```

Production smoke command:

```bash
cd web
pnpm build
pnpm start
```

## AI And Document Processing

- **anthropic 0.96.0:** Claude API client with forced tool-use for extraction/report generation
- **pdfplumber 0.11.9:** Digital PDF text extraction
- **Pillow 12.2.0 + pytesseract 0.3.13:** OCR path for scanned PDFs when system Tesseract is installed
- **pandas 3.0.2 + openpyxl 3.1.5:** Excel ingestion
- **python-docx:** Word document extraction

## Testing

- **pytest 9.0.3 + pytest-asyncio 1.3.0:** Backend integration/unit tests
- **httpx:** Async ASGI client for FastAPI tests
- **Playwright 1.61.1:** Browser E2E tests in `web/e2e/`

Core commands:

```bash
source venv/bin/activate && python -m pytest tests/ -q
cd web && pnpm typecheck
cd web && pnpm lint
cd web && pnpm build
cd web && pnpm test:e2e
cd web && pnpm test:e2e:prod
```

## Configuration

Runtime environment is loaded from project-root `.env`.

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `CLAUDE_MODEL` | Claude model override |
| `SECRET_KEY` | JWT signing key |
| `OWNER_EMAIL` | First admin email |
| `SMTP_*`, `FROM_EMAIL` | Optional SMTP delivery |
| `APP_BASE_URL` | Public Next.js app URL used in email links |
| `FASTAPI_ORIGIN` | Next.js backend runtime proxy target |
| `NEXT_PUBLIC_API_BASE` | Browser API base |
| `ACCOUNTIQ_DB_PATH` | Optional DB path override |
| `ACCOUNTIQ_E2E_MODE` | Deterministic backend mode for Playwright |
| `ACCOUNTIQ_SERVE_LEGACY_FRONTEND` | Opt-in legacy `/app` mount |

## Deployment Notes

FastAPI and Next.js are separate runtimes. For production, run both behind a reverse proxy:

- Route `/`, `/login`, `/wizard`, `/admin/*`, `/_next/*` to Next.js.
- Route `/api/backend/*` through the Next runtime proxy or directly to FastAPI after stripping the prefix.
- Keep large uploads and long-running extraction/report jobs in FastAPI, not serverless Next route handlers.
- SQLite remains local-file storage; multi-instance production requires a database migration plan.
