# AccountIQ Web

Next.js App Router frontend for AccountIQ.

FastAPI remains the backend of record. Browser requests go through the same-origin runtime proxy:

```text
/api/backend/:path* -> web/app/api/backend/[...path]/route.ts -> FASTAPI_ORIGIN/:path*
```

## Development

Start FastAPI from the repo root:

```bash
source venv/bin/activate
cd backend
uvicorn main:app --reload --port 8765
```

Start Next.js from `web/`:

```bash
pnpm dev
```

Open:

```text
http://localhost:3000
```

## Scripts

```bash
pnpm typecheck
pnpm lint
pnpm build
pnpm test:e2e
pnpm test:e2e:prod
pnpm openapi:fetch
pnpm openapi:types
```

## E2E

`pnpm test:e2e` starts:

- FastAPI via `../scripts/start-e2e-backend.sh`
- Next.js via `pnpm dev`

The E2E backend uses `ACCOUNTIQ_E2E_MODE=true` and a disposable SQLite DB at `data/accountiq_e2e.db`.

`pnpm test:e2e:prod` builds Next.js first, then runs the same Playwright suite against the standalone production server.
