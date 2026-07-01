---
last_mapped: 2026-07-01
---

# Conventions

## Naming

| Scope | Convention | Example |
|-------|-----------|---------|
| Python files | `snake_case.py` | `rule_extractor.py` |
| Python functions | `snake_case` | `ingest_document`, `extract_pdf_text` |
| Python classes | `PascalCase` | (none currently, no custom classes) |
| Python constants | `UPPER_SNAKE_CASE` | `MAX_TEXT_CHARS`, `CLAUDE_MODEL`, `PNL_SYNS` |
| Private helpers | `_underscore_prefix` | `_score_page`, `_norm`, `_build_pattern_hints` |
| DB columns | `snake_case` | `extraction_status`, `fiscal_year_end` |
| Canonical financial keys | `snake_case` | `net_profit`, `cash_and_bank` |
| CSS variables/classes | `--kebab-case`, `kebab-case` | `--navy`, `admin-page` |
| React components | `PascalCase` file exports, kebab-case filenames | `Wizard`, `wizard.tsx` |
| TS functions | `camelCase` | `apiFetch`, `requireAdmin` |

## Python Code Style

**Import ordering:** stdlib → third-party → conditional (`try/except ImportError`) → local modules

```python
import os, json, re, asyncio  # stdlib
import anthropic, pdfplumber   # third-party
try:
    import pytesseract          # optional third-party
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
from db import init_db          # local
```

**Section separators:** Dashes used as structural dividers throughout backend files:

```python
# ---------------------------------------------------------------------------
# Section name
# ---------------------------------------------------------------------------
```

**Error handling (FastAPI routes):** Early validation → `raise HTTPException(status_code, detail_str)`:

```python
if not company:
    raise HTTPException(404, "Company not found")
if "UNIQUE constraint" in str(e):
    raise HTTPException(409, f"Company '{name}' on {exchange} already exists.")
raise HTTPException(500, str(e))
```

Common status codes used: 400 (bad input), 404 (not found), 409 (conflict), 500 (internal).

**Logging:** `print()` with bracketed level prefixes — no logging framework:

```python
print("[STARTUP] AccountIQ Learning Agent ready.")
print(f"[ERROR] Ingestion failed for doc {document_id}: {e}")
print(f"[DB] Initialised at {DB_PATH}")
```

**Async pattern:** FastAPI `Depends(get_db)` for route-level connections; background tasks open their own connection:

```python
async with aiosqlite.connect(DB_PATH) as db:
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
```

**Type hints:** Used on function signatures, `Optional[str]` for nullable params, `list[str]` / `dict` for returns.

## Database Patterns

- All queries use parameterized `?` placeholders (no f-string interpolation into SQL)
- Timestamps stored as `TEXT DEFAULT (datetime('now'))` — SQLite ISO format
- `ON CONFLICT DO UPDATE` for upsert (label_patterns)
- WAL journal mode + foreign_keys ON set via PRAGMA on every connection
- Schema migrations done manually via `ALTER TABLE ... ADD COLUMN` with try/except (no migration framework)

## Frontend Patterns

- Primary frontend code lives in `web/` as a Next.js App Router app.
- `frontend/index.html` is legacy fallback code only; do not add new product UI there unless explicitly restoring the legacy app.
- Browser API calls go through `web/lib/api-client.ts` and default to `NEXT_PUBLIC_API_BASE=/api/backend`.
- Server-side auth checks go through `web/lib/auth.ts` / `web/lib/server-api.ts`, forwarding cookies from `headers()`.
- Admin pages live under `web/app/admin/*` and should be protected by `requireAdmin()`.
- Regular-user report flow lives under `web/app/wizard/page.tsx` and `web/components/wizard/*`.
- Status badges use class `status-{value}` for `pending`, `processing`, `done`, and `failed`.
- Polling loops must stop when a terminal status is reached.
- User-influenced text must render as text, never as unsanitized HTML. Report viewer escaping is covered by Playwright.

## Configuration Pattern

- Runtime config via `.env` at project root, loaded by `python-dotenv` on startup
- `set_key(ENV_PATH, KEY, VALUE)` used to persist settings changes at runtime
- Global module-level variables (`ANTHROPIC_API_KEY`, `CLAUDE_MODEL`) mutated by the settings endpoint
