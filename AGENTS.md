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

**Current state:** Core security/auth, data isolation, extraction, wizard shell, and valuation-advisory redesign work have progressed beyond the initial roadmap state. Commercial MVP public-funnel planning is captured in `docs/superpowers/specs/2026-07-01-commercial-mvp-roadmap-context.md` and `docs/superpowers/plans/2026-07-01-commercial-mvp-launch-gates-and-assumptions.md`.

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

## Known Issues And Launch Gates (before any external launch)

See `.planning/codebase/CONCERNS.md`, `.planning/PROJECT.md`, and `.planning/commercial/LAUNCH-GATES.md` for current status.

Previously critical Phase 1 issues (wildcard CORS, filename path traversal, AI-text XSS, no authentication) are recorded as fixed in `.planning/PROJECT.md`, but must be re-verified before public launch.

Current Commercial MVP blockers:
- Re-verify auth, CORS, filename sanitisation, XSS controls, user data isolation, and paid report access
- Resolve compliance wording: indicative-only disclaimer, "reviewed by" wording, CAANZ/logo entitlement, refund policy, privacy policy, and financial-advice boundary
- Add pre-payment extraction/serviceability validation
- Define payment failure states: needs clarification, failed extraction, failed generation, failed review, cancellation, void, and refund
- Define Todd/reviewer capacity, review checklist, and turnaround SLA
- Decide Postgres vs SQLite before live Stripe payments
- Decide Next.js public site/app shell vs temporary split frontend
- Define analytics consent before PostHog/CRM tracking

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
