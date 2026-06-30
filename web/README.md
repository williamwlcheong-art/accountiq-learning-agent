# AccountIQ Web

Next.js App Router frontend for AccountIQ.

FastAPI remains the backend of record. Browser requests go through the same-origin proxy:

```text
/api/backend/:path* -> FASTAPI_ORIGIN/:path*
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
npm run dev
```

Open:

```text
http://localhost:3000
```

## Scripts

```bash
npm run typecheck
npm run lint
npm run build
npm run test:e2e
npm run test:e2e:prod
npm run openapi:fetch
npm run openapi:types
```

## E2E

`npm run test:e2e` starts:

- FastAPI via `../scripts/start-e2e-backend.sh`
- Next.js via `npm run dev`

The E2E backend uses `ACCOUNTIQ_E2E_MODE=true` and a disposable SQLite DB at `data/accountiq_e2e.db`.

`npm run test:e2e:prod` builds Next.js first, then runs the same Playwright suite against the standalone production server.
