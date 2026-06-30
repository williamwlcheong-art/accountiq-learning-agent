---
last_mapped: 2026-07-01
---

# Testing

## Current State

The project has two active automated test layers:

- **Backend:** `pytest` tests in `tests/` cover auth, admin gates, data isolation, extraction, upload, business profile, valuation, report prompts, research loop behavior, and deterministic E2E backend mode.
- **Browser E2E:** Playwright tests in `web/e2e/` cover auth redirects, registration/login/logout, regular-user wizard upload/report generation/viewing, admin company/upload/document/financial workflows, admin route protection, report viewer escaping, and mobile overflow smoke checks.

The Next.js app also has static verification:

- `npm run typecheck`
- `npm run lint`
- `npm run build`

## Backend Test Commands

Run from the repo root:

```bash
source venv/bin/activate
python -m pytest tests/ -q
```

Focused examples:

```bash
python -m pytest tests/test_auth.py -q
python -m pytest tests/test_admin_gate.py -q
python -m pytest tests/test_e2e_mode.py -q
```

## Frontend Static Checks

Run from `web/`:

```bash
npm run typecheck
npm run lint
npm run build
```

## Browser E2E

Run from `web/`:

```bash
npm run test:e2e
```

Playwright starts two web servers:

1. `../scripts/start-e2e-backend.sh`
2. `npm run dev`

The backend launcher:

- Deletes `data/accountiq_e2e.db`, `-wal`, and `-shm`
- Sets `ACCOUNTIQ_DB_PATH=data/accountiq_e2e.db`
- Sets `ACCOUNTIQ_E2E_MODE=true`
- Sets `OWNER_EMAIL=owner-e2e@example.com`
- Starts FastAPI on `127.0.0.1:8765`

This keeps E2E deterministic and independent from local development data, Anthropic, OCR, SMTP, and long-running background work.

## Production E2E Smoke

Run from `web/`:

```bash
npm run test:e2e:prod
```

This builds Next.js first, then runs Playwright with `PLAYWRIGHT_FRONTEND_COMMAND="npm run start"` so the browser suite exercises the standalone production server rather than the dev server.

## E2E Coverage Map

| Spec | Coverage |
|------|----------|
| `auth.spec.ts` | Login redirect, registration, logout, login, short-password error |
| `wizard.spec.ts` | Regular upload, report type, intake, report generation, viewer link |
| `admin.spec.ts` | Owner admin registration, company create, upload, documents, financials |
| `security.spec.ts` | Regular user redirected away from admin |
| `report-viewer.spec.ts` | Generated report escapes script-like payloads |
| `responsive.spec.ts` | Wizard has no horizontal overflow on desktop/mobile profiles |

## Expectations For Future Changes

- Backend route/data changes need focused pytest coverage.
- Frontend workflow changes need either a Playwright update or a clear reason the existing E2E path covers the behavior.
- Any change touching uploads, report generation, auth cookies, route guards, or report viewing should run the full command set before merging:

```bash
source venv/bin/activate && python -m pytest tests/ -q
cd web && npm run typecheck && npm run lint && npm run build
cd web && npm run test:e2e
cd web && npm run test:e2e:prod
```
