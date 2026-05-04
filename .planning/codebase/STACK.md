# Technology Stack

**Analysis Date:** 2026-05-04

## Languages

**Primary:**
- Python 3.13.6 - Backend API, ingestion pipeline, database layer, rule-based extraction

**Secondary:**
- HTML/CSS/JavaScript (vanilla, no framework) - Single-file frontend at `frontend/index.html`

## Runtime

**Environment:**
- CPython 3.13.6 (system install: `/Library/Frameworks/Python.framework/Versions/3.13`)
- Virtual environment: `venv/` (Python 3.13, stdlib only, no system site-packages)

**Package Manager:**
- pip (no lockfile — `requirements.txt` uses `>=` version constraints, not pinned)
- Lockfile: absent (risk: non-reproducible installs)

## Frameworks

**Core:**
- FastAPI 0.136.0 - REST API framework; async routes via `Depends`, `BackgroundTasks`, `UploadFile`
- Uvicorn 0.44.0 - ASGI server; dev command: `uvicorn main:app --reload --port 8765`

**Build/Dev:**
- No build tooling (Python backend runs directly; frontend is a single static HTML file)
- `setup.sh` - One-shot shell script: creates venv and installs dependencies

## Key Dependencies

**AI/LLM:**
- `anthropic` 0.96.0 - Anthropic Python SDK; used in `backend/ingestion.py` via `anthropic.Anthropic` client with forced tool-use (`tool_choice={"type": "tool", "name": "extract_financials"}`)
- Default model: `claude-sonnet-4-6` (overridable via `CLAUDE_MODEL` env var; configurable at runtime via `/settings` endpoint)

**PDF Processing:**
- `pdfplumber` 0.11.9 - Text extraction from digital PDFs (`backend/ingestion.py:extract_pdf_text`)
- `Pillow` 12.2.0 - Image rendering of scanned/image-only PDF pages for OCR input
- `pytesseract` 0.3.13 - OCR wrapper for Tesseract; requires system `tesseract` binary; gracefully degrades if absent (`HAS_TESSERACT` flag)

**Excel Processing:**
- `pandas` 3.0.2 - `pd.ExcelFile` + `xl.parse()` for reading `.xlsx`/`.xls`/`.xlsm` sheets (`backend/ingestion.py:extract_excel_text`)
- `openpyxl` 3.1.5 - pandas Excel engine dependency

**Database:**
- `aiosqlite` 0.22.1 - Async SQLite driver for FastAPI dependency injection; WAL mode enabled

**Data Formatting:**
- `tabulate` 0.10.0 - Listed as dependency; not observed in active code paths (likely reserved for future CLI output)

**HTTP/API:**
- `python-multipart` 0.0.26 - Required by FastAPI for `Form(...)` and `UploadFile` multipart parsing
- `python-dotenv` 1.2.2 - Loads `.env` at startup; supports runtime `set_key()` to persist settings

## Configuration

**Environment:**
- Loaded from `<project-root>/.env` via `python-dotenv` at `backend/main.py:18-20`
- Required: `ANTHROPIC_API_KEY` (must start with `sk-ant-`)
- Optional: `CLAUDE_MODEL` (defaults to `claude-sonnet-4-6`)
- Template: `.env.example` at project root
- Note: `.env` is gitignored; never committed

**Runtime settings:**
- API key and model can be updated live via `POST /settings` endpoint, which writes back to `.env` and hot-patches the running process's `os.environ` and `ingestion` module globals

**Build:**
- No build config files; no `pyproject.toml`, `setup.py`, or `Makefile`
- `backend/requirements.txt` - sole dependency manifest

## Platform Requirements

**Development:**
- Python 3.13+
- System `tesseract` binary (optional, for OCR on scanned PDFs)
- Run: `source venv/bin/activate && cd backend && uvicorn main:app --reload --port 8765`
- Frontend served at `http://localhost:8765/app` (static mount of `frontend/` directory)

**Production:**
- No deployment configuration detected (no `Dockerfile`, no `Procfile`, no cloud config)
- Single-process ASGI app; SQLite is local file-based (`data/accountiq_learning.db`)
- Not suitable for multi-process/multi-instance deployment without replacing SQLite

---

*Stack analysis: 2026-05-04*
