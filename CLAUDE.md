# AccountIQ — Project Guide

## What This Project Is

AccountIQ is an SME financial intelligence SaaS platform. Business owners upload financial statements (PDF, Excel, Word) and purchase AI-generated professional reports — valuations, IMs, bank credit papers, financial forecasts, and capital raising documents. Pay-per-report model. First-draft quality bar.

## Stack

- **Backend:** Python FastAPI (async) + SQLite (aiosqlite) — `backend/`
- **Frontend:** Vanilla JS/HTML single-page app — `frontend/index.html`
- **AI:** Anthropic Claude API (claude-sonnet-4-6) with forced tool-use
- **DB:** SQLite at `data/accountiq_learning.db`, WAL mode, foreign keys ON
- **Dev server:** `source venv/bin/activate && cd backend && uvicorn main:app --reload --port 8765`
- **Frontend:** `http://localhost:8765/app`

## Planning Structure

All planning docs live in `.planning/`:

| File | Purpose |
|------|---------|
| `PROJECT.md` | Living project context — what we're building and why |
| `REQUIREMENTS.md` | v1 requirements with REQ-IDs and phase mapping |
| `ROADMAP.md` | 7-phase execution plan |
| `STATE.md` | Current phase and decision log |
| `config.json` | GSD workflow settings |
| `research/` | Domain research (stack, features, architecture, pitfalls) |
| `codebase/` | Codebase map (architecture, stack, concerns, conventions) |

## GSD Workflow

This project uses the GSD (Get Shit Done) planning workflow. Commands:

```
/gsd-discuss-phase N    — gather context before planning a phase
/gsd-plan-phase N       — create execution plan for phase N
/gsd-execute-phase N    — execute the plan
/gsd-progress           — check current status
/gsd-verify-work        — verify phase deliverables
```

**Current state:** Initialized — ready for Phase 1 (`/gsd-discuss-phase 1`)

## Roadmap Summary

| Phase | Name | Key Deliverable |
|-------|------|----------------|
| 1 | Security & Auth Foundation | Secure app, users can register and log in |
| 2 | Multi-User Data Isolation | Each user sees only their own data |
| 3 | Business Profile Intake | Company profile: industry, management, EBITDA add-backs |
| 4 | Extraction Quality | Accurate extraction across all statement types and formats |
| 5 | Report Generation Engine | All 5 report types generated via Claude |
| 6 | Payment Integration | Stripe pay-per-report with webhook-gated generation |
| 7 | PDF Rendering & Delivery | Web viewer + professional PDF download |

## Known Issues (before any external launch)

See `.planning/codebase/CONCERNS.md` for full list. Critical items:
- Wildcard CORS on write endpoints (Phase 1 fix)
- Unsanitised filename path traversal (Phase 1 fix)
- XSS via innerHTML with AI-generated content (Phase 1 fix)
- No authentication (Phase 1 fix)
- Rule extractor limited to single-page analysis (Phase 4 fix)

## Code Conventions

- All DB operations use `aiosqlite` with async/await — never use sync DB calls in async routes
- Wrap synchronous library calls (pdfplumber, pandas, WeasyPrint) in `asyncio.get_running_loop().run_in_executor(None, ...)`
- File uploads save to `data/pdfs/{company_id}/` — always use `Path(filename).name` for the basename
- Environment loaded from `.env` via `python-dotenv` — never hardcode API keys
- See `.planning/codebase/CONVENTIONS.md` for full conventions

## Key Security Rules

- Never use `allow_origins=["*"]` on endpoints that write to disk or DB
- Always use `Path(file.filename).name` when saving uploads (never use the raw filename)
- Always use `.textContent` or `.createTextNode()` for user-influenced text in the frontend (never `.innerHTML`)
- JWT tokens must be validated on every protected route via middleware — no route-level opt-in
