---
last_mapped: 2026-05-04
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
| CSS variables | `--kebab-case` | `--navy`, `--accent`, `--border` |
| HTML IDs | `kebab-case` | (inline JS uses descriptive IDs) |
| JS functions | `camelCase` | `apiFetch`, `loadCompanies`, `renderPatterns` |

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

- All frontend code in a single `frontend/index.html` — CSS, HTML, and JS inline
- Two API helpers used throughout: `apiFetch(path)` (GET) and `apiPost(path, formData)` (POST)
- Tab navigation: `.nav-tab` buttons toggle `.page.active` divs
- Status badges: class `status-{value}` with CSS for `pending`, `processing`, `done`, `failed`
- Polling: `setInterval` at 3s to check `/documents/{id}/status` while `extraction_status` is non-terminal

## Configuration Pattern

- Runtime config via `.env` at project root, loaded by `python-dotenv` on startup
- `set_key(ENV_PATH, KEY, VALUE)` used to persist settings changes at runtime
- Global module-level variables (`ANTHROPIC_API_KEY`, `CLAUDE_MODEL`) mutated by the settings endpoint
