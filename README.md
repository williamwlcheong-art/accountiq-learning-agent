# AccountIQ Learning Agent

AccountIQ is a financial intelligence prototype for SME business owners. Users upload financial statements, complete business-profile intake, and generate first-draft professional reports such as valuation advisory, bank credit papers, financial forecasts, capital raising documents, and information memorandums.

## Architecture

- `backend/` - FastAPI backend, SQLite persistence, uploads, ingestion, valuation, report generation, and email.
- `web/` - Next.js App Router frontend for login, wizard, admin workflows, and E2E tests.
- `frontend/` - legacy vanilla SPA kept as an opt-in rollback/reference fallback.
- `.planning/` - project, roadmap, codebase, and phase planning docs.

FastAPI remains the backend of record. The Next.js frontend calls `/api/backend/*`, which is proxied at runtime to `FASTAPI_ORIGIN`.

## Local Development

Create `.env` from `.env.example`, then start the two runtimes.

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

The legacy UI is available at `http://localhost:8765/app` only when `ACCOUNTIQ_SERVE_LEGACY_FRONTEND=true`.

## Tests

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

Playwright uses deterministic E2E mode through `scripts/start-e2e-backend.sh` and a disposable SQLite database at `data/accountiq_e2e.db`.

## Agent Notes

Coding-agent guidance lives in `AGENTS.md`. Next.js-specific warnings for the `web/` subtree live in `web/AGENTS.md`.
