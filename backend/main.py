"""
AccountIQ Learning Agent — FastAPI backend
Run with: uvicorn main:app --reload --port 8765
"""
import os
import shutil
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
import aiosqlite

# Load .env from project root (one level up from backend/)
from dotenv import load_dotenv, set_key
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH, override=True)

from db import init_db, get_db, get_pattern_library, DB_PATH
from ingestion import ingest_document, ALL_ROWS

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AccountIQ Learning Agent",
    version="0.1.0",
    description="Ingest financial PDFs, learn patterns, improve over time.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR   = Path(__file__).parent.parent / "data"
PDF_DIR    = DATA_DIR / "pdfs"
EXPORT_DIR = DATA_DIR / "exports"

PDF_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# Serve the frontend
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


@app.on_event("startup")
def startup():
    init_db()
    print("[STARTUP] AccountIQ Learning Agent ready.")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "db": str(DB_PATH)}


# ---------------------------------------------------------------------------
# Companies CRUD
# ---------------------------------------------------------------------------

@app.get("/companies")
async def list_companies(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("""
        SELECT c.*, COUNT(d.id) as doc_count
        FROM companies c
        LEFT JOIN documents d ON d.company_id = c.id
        GROUP BY c.id
        ORDER BY c.name
    """) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.post("/companies")
async def create_company(
    name:     str = Form(...),
    ticker:   str = Form(None),
    exchange: str = Form(None),   # NZX | ASX | Private
    sector:   str = Form(None),
    country:  str = Form("NZ"),
    db: aiosqlite.Connection = Depends(get_db),
):
    try:
        async with db.execute("""
            INSERT INTO companies (name, ticker, exchange, sector, country)
            VALUES (?, ?, ?, ?, ?)
        """, (name, ticker, exchange, sector, country)) as cur:
            company_id = cur.lastrowid
        await db.commit()
        return {"id": company_id, "name": name}
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(409, f"Company '{name}' on {exchange} already exists.")
        raise HTTPException(500, str(e))


@app.get("/companies/{company_id}")
async def get_company(company_id: int, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM companies WHERE id=?", (company_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Company not found")
    return dict(row)


# ---------------------------------------------------------------------------
# Documents — upload & ingest
# ---------------------------------------------------------------------------

@app.get("/documents")
async def list_documents(
    company_id: Optional[int] = None,
    db: aiosqlite.Connection = Depends(get_db),
):
    query = """
        SELECT d.*, c.name as company_name, c.exchange
        FROM documents d
        LEFT JOIN companies c ON c.id = d.company_id
    """
    params = []
    if company_id:
        query += " WHERE d.company_id = ?"
        params.append(company_id)
    query += " ORDER BY d.created_at DESC"

    async with db.execute(query, params) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.post("/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file:           UploadFile = File(...),
    company_id:     int  = Form(...),
    report_type:    str  = Form("annual_report"),  # annual_report | compilation | management
    entity_type:    str  = Form("listed"),          # listed | sme
    fiscal_year_end: str = Form(""),
    db: aiosqlite.Connection = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted.")

    # Verify company exists
    async with db.execute("SELECT id, exchange FROM companies WHERE id=?", (company_id,)) as cur:
        company = await cur.fetchone()
    if not company:
        raise HTTPException(404, f"Company {company_id} not found.")

    # Save file
    company_dir = PDF_DIR / str(company_id)
    company_dir.mkdir(exist_ok=True)
    dest = company_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create document record
    async with db.execute("""
        INSERT INTO documents
            (company_id, filename, filepath, report_type, entity_type, fiscal_year_end)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (company_id, file.filename, str(dest),
          report_type, entity_type, fiscal_year_end)) as cur:
        document_id = cur.lastrowid
    await db.commit()

    # Kick off async ingestion
    background_tasks.add_task(
        _run_ingestion, document_id, company_id, str(dest),
        entity_type, company["exchange"], fiscal_year_end
    )

    return {
        "document_id": document_id,
        "filename": file.filename,
        "status": "processing",
        "message": "Ingestion started in background. Poll /documents/{id}/status for progress."
    }


async def _run_ingestion(document_id, company_id, filepath, entity_type, exchange, fiscal_year_end):
    """Background task — opens its own DB connection."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        try:
            await ingest_document(
                db, document_id, company_id, filepath,
                entity_type, exchange, fiscal_year_end
            )
        except Exception as e:
            print(f"[ERROR] Ingestion failed for doc {document_id}: {e}")


@app.get("/documents/{document_id}/status")
async def document_status(document_id: int, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("""
        SELECT d.*, c.name as company_name
        FROM documents d LEFT JOIN companies c ON c.id=d.company_id
        WHERE d.id=?
    """, (document_id,)) as cur:
        doc = await cur.fetchone()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Fetch logs
    async with db.execute("""
        SELECT level, message, created_at FROM extraction_log
        WHERE document_id=? ORDER BY id DESC LIMIT 30
    """, (document_id,)) as cur:
        logs = [dict(r) for r in await cur.fetchall()]

    return {**dict(doc), "logs": logs}


@app.get("/documents/{document_id}/rows")
async def document_rows(document_id: int, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("""
        SELECT * FROM financial_rows WHERE document_id=?
        ORDER BY statement, row_key, period
    """, (document_id,)) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Financial data queries
# ---------------------------------------------------------------------------

@app.get("/financials/{company_id}")
async def company_financials(
    company_id: int,
    statement:  Optional[str] = None,   # 'pnl' | 'bs'
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return all financial rows for a company, aggregated across documents."""
    query = """
        SELECT fr.statement, fr.row_key, fr.row_label, fr.period,
               AVG(fr.value) as value, fr.currency, fr.unit,
               AVG(fr.confidence) as confidence,
               COUNT(*) as source_count
        FROM financial_rows fr
        JOIN documents d ON d.id = fr.document_id
        WHERE fr.company_id = ? AND d.extraction_status = 'done'
    """
    params = [company_id]
    if statement:
        query += " AND fr.statement = ?"
        params.append(statement)
    query += " GROUP BY fr.statement, fr.row_key, fr.period ORDER BY fr.statement, fr.row_key, fr.period DESC"

    async with db.execute(query, params) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Pattern library
# ---------------------------------------------------------------------------

@app.get("/patterns")
async def list_patterns(
    statement: Optional[str] = None,
    db: aiosqlite.Connection = Depends(get_db),
):
    query = """
        SELECT canonical_key, statement, raw_label, entity_type, exchange,
               match_count, last_seen
        FROM label_patterns
    """
    params = []
    if statement:
        query += " WHERE statement=?"
        params.append(statement)
    query += " ORDER BY match_count DESC, canonical_key"

    async with db.execute(query, params) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/patterns/export")
async def export_patterns(db: aiosqlite.Connection = Depends(get_db)):
    """Export patterns as JSON suitable for importing into the standalone SPA."""
    lib = await get_pattern_library(db)
    export_path = EXPORT_DIR / "patterns_export.json"
    import json
    with open(export_path, "w") as f:
        json.dump(lib, f, indent=2)
    return FileResponse(str(export_path), media_type="application/json",
                        filename="accountiq_patterns.json")


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@app.get("/analytics/overview")
async def analytics_overview(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT COUNT(*) as n FROM companies") as cur:
        companies = (await cur.fetchone())["n"]
    async with db.execute("SELECT COUNT(*) as n FROM documents") as cur:
        documents = (await cur.fetchone())["n"]
    async with db.execute("SELECT COUNT(*) as n FROM documents WHERE extraction_status='done'") as cur:
        done = (await cur.fetchone())["n"]
    async with db.execute("SELECT COUNT(*) as n FROM financial_rows") as cur:
        fin_rows = (await cur.fetchone())["n"]
    async with db.execute("SELECT COUNT(*) as n FROM label_patterns") as cur:
        patterns = (await cur.fetchone())["n"]
    async with db.execute("""
        SELECT exchange, COUNT(*) as n FROM companies GROUP BY exchange
    """) as cur:
        by_exchange = [dict(r) for r in await cur.fetchall()]

    return {
        "companies":   companies,
        "documents":   documents,
        "docs_done":   done,
        "financial_rows": fin_rows,
        "label_patterns": patterns,
        "by_exchange": by_exchange,
    }


@app.get("/analytics/confidence")
async def confidence_stats(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("""
        SELECT row_key, AVG(confidence) as avg_conf, COUNT(*) as n
        FROM financial_rows
        GROUP BY row_key
        ORDER BY avg_conf ASC
    """) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Settings — API key management
# ---------------------------------------------------------------------------

@app.get("/settings")
async def get_settings():
    """Return current settings (API key masked)."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    import ingestion as ing
    return {
        "api_key_set": bool(key and not key.startswith("sk-ant-YOUR")),
        "api_key_preview": (key[:12] + "…" + key[-4:]) if len(key) > 20 else ("" if not key else "set"),
        "claude_model": ing.CLAUDE_MODEL,
        "env_file": str(ENV_PATH),
    }


@app.post("/settings")
async def update_settings(
    api_key:      str = Form(None),
    claude_model: str = Form(None),
):
    """Persist settings to .env and reload into the running process."""
    import ingestion as ing

    if api_key and api_key.startswith("sk-ant-"):
        set_key(str(ENV_PATH), "ANTHROPIC_API_KEY", api_key)
        os.environ["ANTHROPIC_API_KEY"] = api_key
        ing.ANTHROPIC_API_KEY = api_key
        msg = "API key saved."
    elif api_key:
        raise HTTPException(400, "Key must start with sk-ant-")
    else:
        msg = "No key change."

    if claude_model:
        set_key(str(ENV_PATH), "CLAUDE_MODEL", claude_model)
        os.environ["CLAUDE_MODEL"] = claude_model
        ing.CLAUDE_MODEL = claude_model
        msg += f" Model set to {claude_model}."

    return {"ok": True, "message": msg}


@app.post("/documents/{document_id}/retry")
async def retry_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Re-run ingestion on a previously failed or pending document."""
    # Join companies to get exchange
    async with db.execute("""
        SELECT d.*, c.exchange FROM documents d
        LEFT JOIN companies c ON c.id = d.company_id
        WHERE d.id=?
    """, (document_id,)) as cur:
        doc = await cur.fetchone()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Reset status and clear old data
    await db.execute(
        "UPDATE documents SET extraction_status='pending', updated_at=datetime('now') WHERE id=?",
        (document_id,)
    )
    await db.execute("DELETE FROM financial_rows WHERE document_id=?", (document_id,))
    await db.execute("DELETE FROM extraction_log WHERE document_id=?", (document_id,))
    await db.commit()

    background_tasks.add_task(
        _run_ingestion,
        document_id, doc["company_id"], doc["filepath"],
        doc["entity_type"], doc["exchange"], doc["fiscal_year_end"] or ""
    )
    return {"document_id": document_id, "status": "retrying"}


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "AccountIQ Learning Agent API. UI at /app"}
