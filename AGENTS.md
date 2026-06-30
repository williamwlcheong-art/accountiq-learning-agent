# AccountIQ - Agent Guide

## Project Snapshot

AccountIQ is an SME financial intelligence SaaS platform. Users upload financial statements, answer business-profile questions, and generate first-draft professional reports: valuation advisory, bank credit paper, financial forecast, capital raising document, and information memorandum.

## Current Architecture

- Backend: Python FastAPI in `backend/`, SQLite via `aiosqlite`, local files under `data/`.
- Frontend: Next.js App Router in `web/`.
- Legacy UI: `frontend/index.html` is rollback/reference only. It is served at `/app` only when `ACCOUNTIQ_SERVE_LEGACY_FRONTEND=true`.
- API proxy: browser calls use `/api/backend`; Next proxies through `web/app/api/backend/[...path]/route.ts` to `FASTAPI_ORIGIN`.
- AI: Anthropic Claude API with forced tool-use for extraction/report generation; deterministic fallbacks exist for tests.

## Run Locally

Backend:

```bash
source venv/bin/activate
cd backend
uvicorn main:app --reload --port 8765
```

Frontend:

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:3000`.

In git worktrees that do not have their own `venv/`, use the parent checkout virtualenv, for example `../../venv/bin/python -m pytest tests -q`.

## Verification Commands

Backend:

```bash
python -m pytest tests -q
```

Frontend:

```bash
cd web
npm run typecheck
npm run lint
npm run build
npm run test:e2e
npm run test:e2e:prod
```

Playwright starts FastAPI through `scripts/start-e2e-backend.sh`, resets `data/accountiq_e2e.db`, and sets `ACCOUNTIQ_E2E_MODE=true`.

## Planning And Codebase Docs

- `.planning/PROJECT.md` - living product context
- `.planning/STATE.md` - current status and decision log
- `.planning/codebase/` - architecture, stack, conventions, concerns
- `docs/superpowers/plans/2026-07-01-nextjs-refactor-final.md` - final Next.js migration plan
- `web/AGENTS.md` - Next.js version warning for agents working under `web/`

Read `.planning/codebase/CONVENTIONS.md` before larger backend/frontend changes.

## Important Conventions

- Keep FastAPI as the backend of record for auth cookies, SQLite writes, uploads, extraction, valuation, report generation, and email.
- Keep new product UI in `web/`; do not add features to `frontend/index.html` unless explicitly restoring the legacy app.
- Use async `aiosqlite`; do not introduce sync DB calls in async routes.
- Wrap synchronous document-processing libraries in `asyncio.get_running_loop().run_in_executor(None, ...)`.
- Save uploads with `Path(file.filename).name`; never trust raw upload filenames.
- Render user/AI-influenced text as text in React; do not inject unsanitized HTML.
- Browser API calls should go through `web/lib/api-client.ts`; server-side auth checks should go through `web/lib/auth.ts` / `web/lib/server-api.ts`.
- Admin pages belong under `web/app/admin/*`; regular-user report flow belongs under `web/app/wizard/page.tsx` and `web/components/wizard/*`.

## Current Status

As of 2026-07-01, the Next.js refactor is complete on branch `codex/nextjs-refactor-e2e` and ready for PR review. Latest verified checks:

- Backend pytest: 116 passed, 1 skipped, 1 xpassed
- `npm run lint`
- `npm run typecheck`
- `npm run build`
- Dev Playwright: 9 passed
- Standalone production Playwright: 9 passed
