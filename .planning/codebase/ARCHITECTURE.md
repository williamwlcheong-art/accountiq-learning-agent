---
last_mapped: 2026-05-04
---

# Architecture

## Pattern

**Monolithic single-repo, two-tier architecture:**
- **Backend:** Python FastAPI REST API (async)
- **Frontend:** Vanilla JS/HTML SPA served as a static mount from the backend

No separate frontend build step or bundler. The frontend HTML/JS file is served directly by FastAPI via `StaticFiles`. All API calls go to the same origin.

## Layers

```
┌─────────────────────────────────────────────────────┐
│  Frontend (frontend/index.html)                     │
│  Single-page Vanilla JS — tabs: Dashboard, Companies│
│  Documents, Patterns, Analytics, Settings           │
└───────────────────┬─────────────────────────────────┘
                    │ HTTP REST (JSON)
┌───────────────────▼─────────────────────────────────┐
│  FastAPI API Layer (backend/main.py)                 │
│  Routes: /companies /documents /financials           │
│          /patterns /analytics /settings              │
└───────────────────┬─────────────────────────────────┘
                    │
    ┌───────────────┴──────────────────┐
    │                                  │
┌───▼────────────────┐   ┌────────────▼────────────────┐
│  Ingestion Pipeline │   │  Database Layer              │
│  (backend/ingestion)│   │  (backend/db.py)             │
│  1. PDF/Excel text  │   │  SQLite via aiosqlite        │
│     extraction      │   │  WAL mode, foreign keys ON   │
│  2. Claude API call │   │  5 tables: companies,        │
│     (tool-use)      │   │  documents, financial_rows,  │
│  3. Rule-based      │   │  label_patterns,             │
│     fallback        │   │  extraction_log              │
│  4. Persist rows    │   └─────────────────────────────┘
│     + patterns      │
└─────────────────────┘
          │
┌─────────▼──────────┐
│  Claude API         │
│  (Anthropic SDK)    │
│  Tool-use forced    │
│  extract_financials │
│  GAAP/IFRS system   │
│  prompt + cache     │
└────────────────────┘
```

## Key Abstractions

### Ingestion Pipeline (`backend/ingestion.py`)

The core intelligence layer. Entry point: `ingest_document()`.

1. **Text extraction** — `extract_pdf_text()` uses `pdfplumber`; image pages fall back to `pytesseract` OCR. `extract_excel_text()` handles `.xlsx/.xls/.xlsm` via `pandas`.
2. **Page scoring** — `_score_page()` ranks PDF pages by financial synonym density so only the most relevant pages are sent to Claude (within `MAX_TEXT_CHARS = 60,000`).
3. **Claude tool-use** — `call_claude()` forces the `extract_financials` tool, getting structured JSON back (periods, rows, narrative, reporting standard).
4. **Rule-based fallback** — `rule_based_extract()` in `rule_extractor.py` runs when no API key is set or Claude fails due to billing/auth errors. Produces ~70-80% accuracy.
5. **Persistence** — `persist_extraction()` upserts financial rows and records label→canonical_key mappings for future learning.

### Pattern Learning (`backend/db.py` — `record_patterns`, `get_pattern_library`)

Every ingestion records which raw label (e.g., "Turnover") mapped to which canonical key (e.g., "revenue"). These are fed back as hints in subsequent Claude calls, improving accuracy over time.

### Rule Extractor (`backend/rule_extractor.py`)

Synonym dictionaries (PNL_SYNS, BS_SYNS) for 11 P&L rows and 16 BS rows. Uses longest-match scoring. Handles parenthetical negatives, NZ/AU/US number formats, multi-period column detection.

## Data Flow — Document Ingestion

```
POST /documents/upload
  → save file to data/pdfs/{company_id}/{filename}
  → INSERT documents record (status: pending)
  → BackgroundTasks.add_task(_run_ingestion)
  → return {document_id, status: "processing"}

_run_ingestion (background)
  → extract text (PDF or Excel)
  → load pattern_library from DB
  → call Claude (tool-use) OR rule_based fallback
  → persist financial_rows + label_patterns
  → UPDATE documents.extraction_status = 'done'

GET /documents/{id}/status
  → poll for completion + last 30 log entries
```

## Entry Points

- **API server:** `uvicorn main:app --reload --port 8765`
- **Frontend UI:** `http://localhost:8765/app`
- **Health check:** `GET /health`
- **DB initialization:** `init_db()` called on FastAPI startup event

## Concurrency Model

- FastAPI async routes with `aiosqlite` for all DB operations
- Ingestion runs in `BackgroundTasks` (separate async context with own DB connection)
- Claude API called via `asyncio.run_in_executor` (sync Anthropic SDK wrapped in executor)
- SQLite WAL mode enables concurrent reads during background writes
