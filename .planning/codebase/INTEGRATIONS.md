# External Integrations

**Analysis Date:** 2026-05-04

## APIs & External Services

**AI / LLM:**
- Anthropic Claude API - Core extraction engine; all financial data extraction from PDFs and Excel files
  - SDK/Client: `anthropic` 0.96.0 (`anthropic.Anthropic(api_key=key)`)
  - Auth: `ANTHROPIC_API_KEY` env var (must start with `sk-ant-`)
  - Usage: Synchronous client called inside `asyncio.get_event_loop().run_in_executor()` to avoid blocking the async loop (`backend/ingestion.py:288`)
  - Call pattern: Forced tool-use via `tool_choice={"type": "tool", "name": "extract_financials"}` — Claude is required to return structured JSON, never free text
  - System prompt: GAAP/IFRS financial extraction specialist with `cache_control: ephemeral` applied to reduce token costs (`backend/ingestion.py:291-298`)
  - Max tokens per call: 4096
  - Default model: `claude-sonnet-4-6`; configurable via `CLAUDE_MODEL` env var or `/settings` API endpoint
  - Fallback: If API key is missing or billing errors occur, the pipeline silently falls back to `rule_based_extract()` in `backend/rule_extractor.py`

**OCR (System Binary):**
- Tesseract OCR - Image-to-text for scanned PDF pages
  - Integration: `pytesseract` Python wrapper around the `tesseract` system binary
  - Auth: None (local system install)
  - Optional: If `pytesseract` or `tesseract` binary is unavailable, `HAS_TESSERACT = False` and OCR pages produce empty strings (`backend/ingestion.py:20-24`)

## Data Storage

**Databases:**
- SQLite (local file, no external server)
  - File path: `data/accountiq_learning.db` (relative to project root; created at startup)
  - Connection: `DB_PATH = Path(__file__).parent.parent / "data" / "accountiq_learning.db"` (`backend/db.py:10`)
  - Client: `aiosqlite` 0.22.1 (async) for all FastAPI routes; `sqlite3` stdlib (sync) for initial schema creation
  - Mode: WAL (`PRAGMA journal_mode=WAL`) — improves concurrent read performance
  - Foreign keys: enforced (`PRAGMA foreign_keys=ON`)
  - Tables: `companies`, `documents`, `financial_rows`, `label_patterns`, `extraction_log`
  - Schema defined in: `backend/db.py:12-92`
  - Migration: `_migrate_db()` in `backend/db.py:111-121` adds v2 columns (`narrative`, `reporting_standard`) safely via `ALTER TABLE ... ADD COLUMN` with error suppression

**File Storage:**
- Local filesystem only
  - Uploaded PDFs and Excel files: `data/pdfs/<company_id>/<filename>` (`backend/main.py:42-46`)
  - Exported JSON (pattern library): `data/exports/patterns_export.json` (`backend/main.py:301-305`)
  - Both directories created at startup if absent

**Caching:**
- None (no Redis, Memcached, or in-memory cache layer)
- Anthropic prompt caching: `cache_control: {"type": "ephemeral"}` applied to the system prompt to reduce API costs on repeated calls (`backend/ingestion.py:294`)

## Authentication & Identity

**Auth Provider:**
- None — no user authentication or session management
- The application is single-user/local-only with no login system
- API key management is handled as a settings concern, not auth: `POST /settings` endpoint writes the Anthropic key to `.env` (`backend/main.py:368-392`)

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Datadog, or equivalent)

**Logs:**
- Per-document extraction log written to `extraction_log` SQLite table (`backend/db.py:77-84`)
- Accessible via `GET /documents/{document_id}/status` which returns last 30 log entries (`backend/main.py:220-227`)
- `print()` statements to stdout at key ingestion steps (startup, extraction start, completion, errors)

## CI/CD & Deployment

**Hosting:**
- No deployment configuration detected
- Designed for local development use: single Python process, file-based SQLite database

**CI Pipeline:**
- None detected (no `.github/`, no CI config files)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Environment Configuration

**Required env vars:**
- `ANTHROPIC_API_KEY` - Anthropic API key beginning with `sk-ant-`; ingestion degrades to rule-based if absent

**Optional env vars:**
- `CLAUDE_MODEL` - Override Claude model; defaults to `claude-sonnet-4-6`

**Secrets location:**
- `.env` file at project root (gitignored; created manually or via `POST /settings`)
- Template: `.env.example` committed to the repo with placeholder values

## Document Ingestion Integration Points

The ingestion pipeline in `backend/ingestion.py` orchestrates the following external calls in sequence:

1. **pdfplumber** - Extract text from PDF pages; falls back to...
2. **pytesseract/Tesseract** - OCR for image-only PDF pages (optional)
3. **pandas/openpyxl** - Parse Excel files as an alternative input format
4. **Anthropic Claude API** - Send extracted text with forced tool-use; receive structured financial JSON
5. **Rule-based extractor** (`backend/rule_extractor.py`) - Fallback when Claude API is unavailable

---

*Integration audit: 2026-05-04*
