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

In linked git worktrees that do not have their own `venv/`, use the parent checkout virtualenv, for example `source ../../venv/bin/activate`.

Frontend:

```bash
cd web
pnpm install
pnpm dev
```

Open `http://localhost:3000`.

For one-off test commands in those worktrees, call the parent interpreter directly, for example `../../venv/bin/python -m pytest tests -q`.

## Verification Commands

Backend:

```bash
python -m pytest tests -q
```

Frontend:

```bash
cd web
pnpm typecheck
pnpm lint
pnpm build
pnpm test:e2e
pnpm test:e2e:prod
```

Playwright starts FastAPI through `scripts/start-e2e-backend.sh`, resets `data/accountiq_e2e.db`, and sets `ACCOUNTIQ_E2E_MODE=true`.

## Planning And Codebase Docs

- `.planning/PROJECT.md` - living product context
- `.planning/BACKLOG.md` - current paid Valuation Advisory MVP backlog and review queue
- `.planning/STATE.md` - current status and decision log
- `.planning/codebase/` - architecture, stack, conventions, concerns
- `.planning/commercial/` - launch gates, production architecture decisions, and commercial assumptions
- `docs/superpowers/plans/2026-07-01-nextjs-refactor-final.md` - final Next.js migration plan
- `docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md` - paid Valuation Advisory MVP implementation plan
- `docs/superpowers/plans/2026-07-01-marketing-site-offer.md` - public valuation offer implementation plan
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

As of 2026-09-14, the paid Valuation Advisory MVP is built end to end: valuation-only picker, Stripe checkout gating, webhook handling for failed, expired and refunded payments, admin review before release, WeasyPrint PDF export, purchase history, the public offer page, quarterly NZ market intelligence, and a customer portal at `/reports` with a shared shell and profile menu. The primary app is the Next.js frontend in `web/`; `frontend/index.html` is legacy rollback/reference only.

Track active work in `.planning/BACKLOG.md` (status board with PR numbers); `.planning/commercial/LAUNCH-GATES.md` lists what still blocks a live launch. `docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md` is the original implementation plan and is kept for context only.

Preferred workflow for the commercial MVP:

- Start feature slices from the latest `main`.
- Keep `main` deployable.
- Use small PRs for each slice: valuation-only picker, payment model, checkout/webhook, admin review, PDF delivery, and account/public offer surfaces.
- Update `.planning/BACKLOG.md` when a PR opens, merges, or changes scope.
- Rebase or merge latest `main` before starting a new slice if another contributor has landed changes.

Latest verified checks (2026-09-14, branch `codex/nz-market-intelligence-review-fixes`):

- Backend pytest: 331 passed, 1 skipped
- `pnpm lint`, `pnpm typecheck`
- Dev Playwright: 17 passed
