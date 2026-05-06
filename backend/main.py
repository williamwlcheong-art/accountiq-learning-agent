"""
AccountIQ Learning Agent — FastAPI backend
Run with: uvicorn main:app --reload --port 8765
"""
import os
import json
import shutil
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, Response
import aiosqlite

# Load .env from project root (one level up from backend/)
from dotenv import load_dotenv, set_key
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH, override=True)

from db import init_db, get_db, get_pattern_library, DB_PATH
from ingestion import ingest_document, ALL_ROWS
from auth import auth_router, get_current_user

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
    allow_origins=["http://localhost:8765"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

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
async def list_companies(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute("""
        SELECT c.*, COUNT(d.id) as doc_count
        FROM companies c
        LEFT JOIN documents d ON d.company_id = c.id
        WHERE c.user_id = ?
        GROUP BY c.id
        ORDER BY c.name
    """, (current_user["id"],)) as cur:
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
    current_user: dict = Depends(get_current_user),
):
    try:
        async with db.execute("""
            INSERT INTO companies (name, ticker, exchange, sector, country, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, ticker, exchange, sector, country, current_user["id"])) as cur:
            company_id = cur.lastrowid
        await db.commit()
        return {"id": company_id, "name": name}
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(409, f"Company '{name}' on {exchange} already exists.")
        raise HTTPException(500, str(e))


@app.get("/companies/{company_id}")
async def get_company(
    company_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute(
        "SELECT * FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
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
    current_user: dict = Depends(get_current_user),
):
    query = """
        SELECT d.*, c.name as company_name, c.exchange
        FROM documents d
        LEFT JOIN companies c ON c.id = d.company_id
        WHERE d.user_id = ?
    """
    params = [current_user["id"]]
    if company_id:
        query += " AND d.company_id = ?"
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
    current_user: dict = Depends(get_current_user),
):
    allowed = {".pdf", ".xlsx", ".xls", ".xlsm"}
    if Path(file.filename).suffix.lower() not in allowed:
        raise HTTPException(400, f"Only PDF and Excel files are accepted. Got: {Path(file.filename).suffix}")

    # Verify company exists and belongs to current user
    async with db.execute(
        "SELECT id, exchange FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        company = await cur.fetchone()
    if not company:
        raise HTTPException(404, f"Company {company_id} not found.")

    # Save file
    company_dir = PDF_DIR / str(company_id)
    company_dir.mkdir(exist_ok=True)
    dest = company_dir / Path(file.filename).name
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create document record
    safe_name = Path(file.filename).name
    async with db.execute("""
        INSERT INTO documents
            (company_id, filename, filepath, report_type, entity_type, fiscal_year_end, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (company_id, safe_name, str(dest),
          report_type, entity_type, fiscal_year_end, current_user["id"])) as cur:
        document_id = cur.lastrowid
    await db.commit()

    # Kick off async ingestion
    background_tasks.add_task(
        _run_ingestion, document_id, company_id, str(dest),
        entity_type, company["exchange"], fiscal_year_end
    )

    return {
        "document_id": document_id,
        "filename": safe_name,
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
async def document_status(
    document_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute("""
        SELECT d.*, c.name as company_name
        FROM documents d LEFT JOIN companies c ON c.id=d.company_id
        WHERE d.id=? AND d.user_id=?
    """, (document_id, current_user["id"])) as cur:
        doc = await cur.fetchone()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Fetch logs — join documents to enforce ownership so this query is
    # self-contained and safe if ever reused outside the outer guard.
    async with db.execute("""
        SELECT el.level, el.message, el.created_at
        FROM extraction_log el
        JOIN documents d ON d.id = el.document_id
        WHERE el.document_id=? AND d.user_id=?
        ORDER BY el.id DESC LIMIT 30
    """, (document_id, current_user["id"])) as cur:
        logs = [dict(r) for r in await cur.fetchall()]

    return {**dict(doc), "logs": logs}


@app.get("/documents/{document_id}/rows")
async def document_rows(
    document_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Verify ownership first — return 404 if the document does not belong to this user.
    async with db.execute(
        "SELECT id FROM documents WHERE id=? AND user_id=?",
        (document_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Document not found")

    async with db.execute("""
        SELECT fr.* FROM financial_rows fr
        WHERE fr.document_id=?
        ORDER BY fr.statement, fr.row_key, fr.period
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
    current_user: dict = Depends(get_current_user),
):
    """Return all financial rows for a company, aggregated across documents."""
    query = """
        SELECT fr.statement, fr.row_key, fr.row_label, fr.period,
               AVG(fr.value) as value, fr.currency, fr.unit,
               AVG(fr.confidence) as confidence,
               COUNT(*) as source_count
        FROM financial_rows fr
        JOIN documents d ON d.id = fr.document_id
        JOIN companies c ON c.id = fr.company_id
        WHERE fr.company_id = ? AND d.extraction_status = 'done'
          AND c.user_id = ?
    """
    params = [company_id, current_user["id"]]
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
    current_user: dict = Depends(get_current_user),
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
async def export_patterns(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Export patterns as JSON suitable for importing into the standalone SPA."""
    lib = await get_pattern_library(db)
    # Stream the response in-memory: avoids shared-file races and keeps I/O
    # off the event loop without needing run_in_executor for a small JSON blob.
    loop = asyncio.get_running_loop()
    buf = await loop.run_in_executor(None, lambda: json.dumps(lib, indent=2))
    return Response(
        content=buf,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=accountiq_patterns.json"},
    )


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@app.get("/analytics/overview")
async def analytics_overview(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute(
        "SELECT COUNT(*) as n FROM companies WHERE user_id=?",
        (current_user["id"],)
    ) as cur:
        companies = (await cur.fetchone())["n"]
    async with db.execute(
        "SELECT COUNT(*) as n FROM documents d WHERE d.user_id=?",
        (current_user["id"],)
    ) as cur:
        documents = (await cur.fetchone())["n"]
    async with db.execute(
        "SELECT COUNT(*) as n FROM documents d WHERE d.extraction_status='done' AND d.user_id=?",
        (current_user["id"],)
    ) as cur:
        done = (await cur.fetchone())["n"]
    async with db.execute("""
        SELECT COUNT(*) as n FROM financial_rows fr
        JOIN companies c ON c.id = fr.company_id
        WHERE c.user_id=?
    """, (current_user["id"],)) as cur:
        fin_rows = (await cur.fetchone())["n"]
    async with db.execute("""
        SELECT exchange, COUNT(*) as n FROM companies
        WHERE user_id=? GROUP BY exchange
    """, (current_user["id"],)) as cur:
        by_exchange = [dict(r) for r in await cur.fetchall()]

    # label_patterns is global shared ML data (D-03) — not exposed here to avoid
    # leaking information about other users' data volume.  Use GET /patterns for counts.
    return {
        "companies":   companies,
        "documents":   documents,
        "docs_done":   done,
        "financial_rows": fin_rows,
        "by_exchange": by_exchange,
    }


@app.get("/analytics/confidence")
async def confidence_stats(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute("""
        SELECT fr.row_key, AVG(fr.confidence) as avg_conf, COUNT(*) as n
        FROM financial_rows fr
        JOIN companies c ON c.id = fr.company_id
        WHERE c.user_id=?
        GROUP BY fr.row_key
        ORDER BY avg_conf ASC
    """, (current_user["id"],)) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Settings — API key management
# ---------------------------------------------------------------------------

@app.get("/settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    """Return current settings (API key masked)."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    import ingestion as ing
    return {
        "api_key_set": bool(key and not key.startswith("sk-ant-YOUR")),
        "api_key_preview": (key[:12] + "…" + key[-4:]) if len(key) > 20 else ("" if not key else "set"),
        "claude_model": os.environ.get("CLAUDE_MODEL") or ing.CLAUDE_MODEL,
        "env_file": str(ENV_PATH),
    }


@app.post("/settings")
async def update_settings(
    api_key:      str = Form(None),
    claude_model: str = Form(None),
    current_user: dict = Depends(get_current_user),
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
    current_user: dict = Depends(get_current_user),
):
    """Re-run ingestion on a previously failed or pending document."""
    # Join companies to get exchange
    async with db.execute("""
        SELECT d.*, c.exchange FROM documents d
        LEFT JOIN companies c ON c.id = d.company_id
        WHERE d.id=? AND d.user_id=?
    """, (document_id, current_user["id"])) as cur:
        doc = await cur.fetchone()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Reset status and clear old data — include user_id in every write to prevent TOCTOU/IDOR
    await db.execute(
        "UPDATE documents SET extraction_status='pending', updated_at=datetime('now') WHERE id=? AND user_id=?",
        (document_id, current_user["id"])
    )
    await db.execute(
        "DELETE FROM financial_rows WHERE document_id=? AND document_id IN (SELECT id FROM documents WHERE user_id=?)",
        (document_id, current_user["id"])
    )
    await db.execute(
        "DELETE FROM extraction_log WHERE document_id=? AND document_id IN (SELECT id FROM documents WHERE user_id=?)",
        (document_id, current_user["id"])
    )
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
