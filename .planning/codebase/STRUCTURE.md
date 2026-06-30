---
last_mapped: 2026-07-01
---

# Structure

## Directory Layout

```text
accountiq-learning-agent/
├── backend/                    # Python FastAPI backend
│   ├── main.py                 # App setup, API routes, background task wiring
│   ├── auth.py                 # Registration, login, JWT cookie auth, admin gate
│   ├── db.py                   # SQLite schema, async connection, migrations
│   ├── ingestion.py            # PDF/Excel/Word extraction + Claude pipeline
│   ├── report_prompts.py       # Report schemas and prompt construction
│   ├── report_email.py         # Report-ready email notification
│   ├── research_loop.py        # Valuation research helpers
│   ├── rule_extractor.py       # Rule-based fallback extractor
│   ├── valuation.py            # DCF, multiples, risk scoring
│   └── requirements.txt        # Python dependencies
│
├── web/                        # Next.js App Router frontend
│   ├── app/                    # Routes, layouts, pages, global CSS
│   ├── components/             # Auth, wizard, and admin React components
│   ├── e2e/                    # Playwright E2E tests and fixtures
│   ├── lib/                    # API clients and auth helpers
│   ├── scripts/                # OpenAPI fetch script
│   ├── types/                  # Generated OpenAPI + domain types
│   ├── next.config.ts          # FastAPI proxy rewrite
│   └── package.json            # Next, React, TypeScript, Playwright scripts
│
├── frontend/                   # Legacy vanilla SPA; opt-in fallback only
│   └── index.html
│
├── tests/                      # Backend pytest suite
├── scripts/
│   └── start-e2e-backend.sh    # Isolated backend launcher for Playwright
│
├── data/
│   ├── accountiq_learning.db   # Local SQLite database
│   ├── accountiq_e2e.db        # Disposable E2E DB when tests run
│   ├── pdfs/                   # Uploaded files by company_id
│   └── exports/                # Pattern export JSONs
│
├── docs/superpowers/plans/     # Implementation plans
├── .planning/                  # Project and codebase planning docs
├── .env.example
└── setup.sh
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI routes, startup, upload/report background tasks |
| `backend/auth.py` | Cookie auth and admin authorization |
| `backend/db.py` | SQLite path, schema, migrations, connection dependency |
| `backend/ingestion.py` | Document extraction pipeline |
| `backend/report_prompts.py` | Report-type schemas and AI prompt payloads |
| `web/app/page.tsx` | Server-side auth redirect entry point |
| `web/app/login/page.tsx` | Login/register page |
| `web/app/wizard/page.tsx` | Regular-user upload and report wizard |
| `web/app/admin/*` | Admin dashboard and workflows |
| `web/components/wizard/*` | Report selection, intake, status polling |
| `web/components/admin/*` | Companies, upload, documents, patterns, financials, settings |
| `web/lib/api-client.ts` | Browser API helper through `/api/backend` |
| `web/lib/server-api.ts` | Server-side API helper with forwarded cookies |
| `web/playwright.config.ts` | Playwright config for FastAPI + Next.js web servers |
| `scripts/start-e2e-backend.sh` | Resets E2E DB and starts deterministic FastAPI |

## Database Schema

Core tables include:

| Table | Purpose |
|-------|---------|
| `users` | Accounts, hashed passwords, admin flag |
| `companies` | Company master scoped to `user_id` |
| `documents` | Uploaded files and extraction status |
| `financial_rows` | Extracted financial statement rows by period |
| `label_patterns` | Global learned raw-label to canonical-key mappings |
| `extraction_log` | Per-document processing log |
| `management_team` | Company profile management entries |
| `ebitda_adjustments` | Valuation add-backs and owner adjustments |
| `reports` | Generated report records and status |
| `report_intake` | Report-specific questionnaire answers |

## API Surface

The OpenAPI contract is generated from FastAPI and checked into `web/openapi.json` with TypeScript types in `web/types/api.ts`.

Major route groups:

| Group | Purpose |
|-------|---------|
| `/auth/*` | Register, login, logout, current user |
| `/companies*` | Admin company/profile management |
| `/documents*` | Admin upload, listing, status, retry |
| `/financials*` | Extracted financial rows |
| `/patterns*` | Learned label patterns and export |
| `/analytics*` | Admin overview and confidence stats |
| `/settings` | API key/model settings |
| `/wizard/*` | Regular-user upload, intake, report status, report viewer |
| `/health` | Backend health check |

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Claude API authentication | required outside fallback paths |
| `CLAUDE_MODEL` | Claude model name | `claude-sonnet-4-6` |
| `SECRET_KEY` | JWT signing key | required |
| `OWNER_EMAIL` | Email granted admin on registration | unset |
| `APP_BASE_URL` | Public Next.js app URL for emails | `http://localhost:3000` |
| `FASTAPI_ORIGIN` | Next.js rewrite target | `http://127.0.0.1:8765` |
| `NEXT_PUBLIC_API_BASE` | Browser API base | `/api/backend` |
| `ACCOUNTIQ_DB_PATH` | Optional SQLite DB override | unset |
| `ACCOUNTIQ_E2E_MODE` | Deterministic backend mode for Playwright | `false` |
| `ACCOUNTIQ_SERVE_LEGACY_FRONTEND` | Opt-in legacy `/app` static mount | `false` |
