# AccountIQ Learning Agent

AccountIQ is a financial intelligence prototype for SME business owners. Users upload financial statements, complete business-profile intake, and generate first-draft professional reports such as valuation advisory, bank credit papers, financial forecasts, capital raising documents, and information memorandums.

## Architecture

- `backend/` - FastAPI backend, SQLite persistence, uploads, ingestion, valuation, report generation, and email.
- `web/` - Next.js App Router frontend for login, wizard, admin workflows, and E2E tests.
- `frontend/` - legacy vanilla SPA kept as an opt-in rollback/reference fallback.
- `.planning/` - project, backlog, roadmap, codebase, and phase planning docs.

FastAPI remains the backend of record. The Next.js frontend calls `/api/backend/*`, which is proxied at runtime to `FASTAPI_ORIGIN`.

## Current Development Status

As of 2026-09-14, the paid Valuation Advisory MVP is built: checkout, admin review, PDF delivery, purchase history, the public offer page and a customer portal. The primary app UI is `web/`; `frontend/` is kept only as a legacy rollback/reference surface.

The working backlog and PR status board live at `.planning/BACKLOG.md`; the original implementation plan at `docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md` is kept for context. Keep `main` deployable and land new feature work through small PRs rather than one large long-lived branch.

Commercial launch gates and production architecture decisions live in `.planning/commercial/`. The shipped public offer page is described in `docs/superpowers/specs/2026-07-12-public-valuation-offer-design.md`.

## Local Development

Create `.env` from `.env.example`, then start the two runtimes.

Backend:

```bash
source venv/bin/activate
cd backend
uvicorn main:app --reload --port 8765
```

In a linked git worktree that does not have its own `venv/`, use the parent checkout virtualenv, for example `source ../../venv/bin/activate`.

Frontend:

```bash
cd web
pnpm install
pnpm dev
```

Open `http://localhost:3000`.

The legacy UI is available at `http://localhost:8765/app` only when `ACCOUNTIQ_SERVE_LEGACY_FRONTEND=true`.

## Tests

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

Playwright uses deterministic E2E mode through `scripts/start-e2e-backend.sh` and a disposable SQLite database at `data/accountiq_e2e.db`.

## Agent Notes

Coding-agent guidance lives in `AGENTS.md`. Next.js-specific warnings for the `web/` subtree live in `web/AGENTS.md`.
