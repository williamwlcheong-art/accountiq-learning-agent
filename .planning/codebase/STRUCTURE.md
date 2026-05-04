---
last_mapped: 2026-05-04
---

# Structure

## Directory Layout

```
accountiq_learning/
├── backend/                    # Python FastAPI backend
│   ├── main.py                 # App setup, all API routes, startup
│   ├── ingestion.py            # PDF/Excel extraction + Claude pipeline
│   ├── db.py                   # SQLite schema, async connection, pattern helpers
│   ├── rule_extractor.py       # Rule-based fallback extractor (no API needed)
│   └── requirements.txt        # Python dependencies
│
├── frontend/
│   └── index.html              # Complete SPA — all JS/CSS inline, no bundler
│
├── data/
│   ├── accountiq_learning.db   # SQLite database (WAL mode)
│   ├── pdfs/                   # Uploaded PDFs organized by company_id
│   │   ├── 1/                  # data/pdfs/{company_id}/{filename}
│   │   └── 2/
│   └── exports/                # Pattern export JSONs (patterns_export.json)
│
├── venv/                       # Python virtual environment (not tracked in git)
├── .env                        # ANTHROPIC_API_KEY, CLAUDE_MODEL (gitignored)
├── .env.example                # Template for env vars
├── .gitignore
└── setup.sh                    # Setup script (creates venv, installs deps)
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/main.py` | All FastAPI routes and app configuration |
| `backend/ingestion.py` | Core extraction pipeline + Claude integration |
| `backend/db.py` | Database schema, connection management, pattern learning |
| `backend/rule_extractor.py` | Synonym-based fallback extractor |
| `frontend/index.html` | Complete frontend SPA (no build step) |
| `data/accountiq_learning.db` | Live SQLite database |
| `.env` | Runtime secrets (not committed) |

## Database Schema

5 tables in `data/accountiq_learning.db`:

| Table | Purpose |
|-------|---------|
| `companies` | Company master (name, ticker, exchange, sector, country) |
| `documents` | Uploaded files + extraction status/results |
| `financial_rows` | Extracted P&L and balance sheet values by period |
| `label_patterns` | Learned mappings: raw label → canonical key |
| `extraction_log` | Per-document debug/progress log entries |

## API Surface

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| GET/POST | `/companies` | List/create companies |
| GET | `/companies/{id}` | Get company detail |
| GET | `/documents` | List documents (optional ?company_id=) |
| POST | `/documents/upload` | Upload PDF/Excel, trigger ingestion |
| GET | `/documents/{id}/status` | Poll ingestion status + logs |
| GET | `/documents/{id}/rows` | Get extracted financial rows |
| POST | `/documents/{id}/retry` | Re-run failed ingestion |
| GET | `/financials/{company_id}` | Aggregated financials across documents |
| GET | `/patterns` | List learned label patterns |
| GET | `/patterns/export` | Export patterns as JSON |
| GET | `/analytics/overview` | Summary stats |
| GET | `/analytics/confidence` | Per-row confidence stats |
| GET/POST | `/settings` | API key / model management |
| GET | `/app` | Frontend SPA (StaticFiles mount) |

## Naming Conventions

- **Python files:** `snake_case.py`
- **API routes:** `/snake_case/{id}` REST conventions
- **DB columns:** `snake_case`, timestamps as `TEXT DEFAULT (datetime('now'))`
- **Canonical financial keys:** `snake_case` (e.g., `net_profit`, `cash_and_bank`)
- **Frontend:** All inline in `index.html` — CSS variables prefixed `--`, JS functions `camelCase`

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Claude API authentication | (required for AI extraction) |
| `CLAUDE_MODEL` | Model to use | `claude-sonnet-4-6` |

Set in `.env` at project root (loaded by `python-dotenv` on startup).
