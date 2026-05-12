"""
AccountIQ Learning Agent — FastAPI backend
Run with: uvicorn main:app --reload --port 8765
"""
import os
import json
import shutil
import asyncio
import secrets
import uuid
import urllib.request
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Header, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
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

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("APP_CORS_ORIGINS", "http://localhost:3000,http://localhost:8765").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR   = Path(__file__).parent.parent / "data"
PDF_DIR    = DATA_DIR / "pdfs"
EXPORT_DIR = DATA_DIR / "exports"

PDF_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

def require_admin(x_admin_token: str | None = Header(None)):
    """Protect local mutation endpoints when APP_ADMIN_TOKEN is configured."""
    token = os.environ.get("APP_ADMIN_TOKEN", "")
    if token and not secrets.compare_digest(x_admin_token or "", token):
        raise HTTPException(401, "Admin token required")


def require_service_token(x_service_token: str | None = Header(None)):
    token = os.environ.get("EXTRACTOR_SERVICE_TOKEN", "")
    if not token or not secrets.compare_digest(x_service_token or "", token):
        raise HTTPException(401, "Service token required")


def safe_upload_filename(filename: str | None) -> str:
    if not filename:
        raise HTTPException(400, "Filename is required")
    safe_name = Path(filename).name
    if safe_name != filename or "/" in filename or "\\" in filename or Path(filename).is_absolute():
        raise HTTPException(400, "Filename must not contain path separators")
    return safe_name


class ExtractMetadata(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=180)
    exchange: str | None = None
    report_type: str = "annual_report"
    entity_type: str = "listed"
    fiscal_year_end: str = ""
    original_filename: str | None = None
    local_file_path: str | None = None
    storage_bucket: str = "accountiq-uploads"
    supabase_document_id: str | None = None
    supabase_report_id: str | None = None
    supabase_upload_session_id: str | None = None


class ExtractRequest(BaseModel):
    storage_object_path: str = Field(..., min_length=1)
    metadata: ExtractMetadata


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
    _admin: None = Depends(require_admin),
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
    _admin: None = Depends(require_admin),
):
    safe_name = safe_upload_filename(file.filename)
    allowed = {".pdf", ".xlsx", ".xlsm"}
    if Path(safe_name).suffix.lower() not in allowed:
        raise HTTPException(400, f"Only PDF and Excel files are accepted. Got: {Path(file.filename).suffix}")

    # Verify company exists
    async with db.execute("SELECT id, exchange FROM companies WHERE id=?", (company_id,)) as cur:
        company = await cur.fetchone()
    if not company:
        raise HTTPException(404, f"Company {company_id} not found.")

    # Save file
    company_dir = PDF_DIR / str(company_id)
    company_dir.mkdir(exist_ok=True)
    dest = company_dir / safe_name
    if dest.exists():
        raise HTTPException(409, f"Document '{safe_name}' already exists for this company.")

    async with db.execute("SELECT id FROM documents WHERE filepath=?", (str(dest),)) as cur:
        if await cur.fetchone():
            raise HTTPException(409, f"Document '{safe_name}' already exists for this company.")

    temp_dest = company_dir / f".{safe_name}.{uuid.uuid4().hex}.uploading"
    with open(temp_dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create document record
    try:
        async with db.execute("""
            INSERT INTO documents
                (company_id, filename, filepath, report_type, entity_type, fiscal_year_end)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (company_id, safe_name, str(dest),
              report_type, entity_type, fiscal_year_end)) as cur:
            document_id = cur.lastrowid
        os.replace(temp_dest, dest)
        await db.commit()
    except Exception:
        await db.rollback()
        temp_dest.unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        raise

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


def _download_supabase_object(storage_bucket: str, storage_path: str, dest: Path):
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not service_role_key:
        raise HTTPException(400, "Supabase storage credentials are not configured for extractor downloads")

    object_url = f"{supabase_url}/storage/v1/object/{storage_bucket}/{storage_path}"
    request = urllib.request.Request(
        object_url,
        headers={
            "Authorization": f"Bearer {service_role_key}",
            "apikey": service_role_key,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response, open(dest, "wb") as output:
            shutil.copyfileobj(response, output)
    except Exception as exc:
        raise HTTPException(502, f"Could not download storage object: {exc}") from exc


def _supabase_writeback_refs(metadata: ExtractMetadata) -> dict[str, str] | None:
    refs = {
        "document_id": metadata.supabase_document_id,
        "report_id": metadata.supabase_report_id,
        "upload_session_id": metadata.supabase_upload_session_id,
    }
    if any(refs.values()) and not all(refs.values()):
        raise HTTPException(400, "Supabase document, report, and upload session ids must be provided together")
    return refs if all(refs.values()) else None


async def build_supabase_report_payload(db: aiosqlite.Connection, document_id: int) -> dict:
    async with db.execute("""
        SELECT d.*, c.name as company_name
        FROM documents d
        JOIN companies c ON c.id = d.company_id
        WHERE d.id = ?
    """, (document_id,)) as cur:
        doc = await cur.fetchone()
    if not doc:
        raise ValueError(f"Document {document_id} not found")

    async with db.execute("""
        SELECT statement, row_label, period, value, confidence, currency, unit, source_text, row_key
        FROM financial_rows
        WHERE document_id = ?
        ORDER BY period DESC
    """, (document_id,)) as cur:
        sqlite_rows = await cur.fetchall()
    row_order = {(statement, key): index for index, (statement, key, _label) in enumerate(ALL_ROWS)}
    sqlite_rows = sorted(sqlite_rows, key=lambda row: (row_order.get((row["statement"], row["row_key"]), 999), row["period"]))

    rows = [
        {
            "statement": row["statement"],
            "label": row["row_label"],
            "period": row["period"],
            "value": row["value"],
            "confidence": row["confidence"] or 0,
        }
        for row in sqlite_rows
    ]
    full_rows = [
        {
            **rows[index],
            "canonicalKey": row["row_key"],
            "currency": row["currency"],
            "unit": row["unit"],
            "sourceText": row["source_text"],
        }
        for index, row in enumerate(sqlite_rows)
    ]

    summary = doc["narrative"] or "Extraction completed. Review the structured rows and confidence scores below."
    confidence = doc["confidence_score"]

    return {
        "document_update": {
            "extraction_status": "preview_ready",
            "extraction_metadata": {
                "local_document_id": document_id,
                "extraction_model": doc["extraction_model"],
                "page_count": doc["page_count"],
                "has_ocr": bool(doc["has_ocr"]),
                "reporting_standard": doc["reporting_standard"],
                "rows_saved": len(rows),
            },
        },
        "session_update": {
            "status": "preview_ready",
        },
        "report_update": {
            "confidence": confidence,
            "full_json": {
                "companyName": doc["company_name"],
                "rows": full_rows,
                "status": "ready",
                "summary": summary,
            },
            "locked_sections": ["Full P&L reconstruction", "Balance sheet mapping", "Source mapping"],
            "narrative": summary,
            "preview_json": {
                "companyName": doc["company_name"],
                "rows": rows[:5],
                "status": "ready",
                "summary": summary,
            },
        },
    }


def _patch_supabase_row(table: str, row_id: str, payload: dict):
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not service_role_key:
        raise RuntimeError("Supabase credentials are not configured for extractor write-back")

    request = urllib.request.Request(
        f"{supabase_url}/rest/v1/{table}?id=eq.{row_id}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {service_role_key}",
            "apikey": service_role_key,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    with urllib.request.urlopen(request, timeout=30):
        return


async def _write_supabase_success(db: aiosqlite.Connection, document_id: int, refs: dict[str, str] | None):
    if not refs:
        return

    payload = await build_supabase_report_payload(db, document_id)
    _patch_supabase_row("documents", refs["document_id"], payload["document_update"])
    _patch_supabase_row("upload_sessions", refs["upload_session_id"], payload["session_update"])
    _patch_supabase_row("reports", refs["report_id"], payload["report_update"])


def _write_supabase_failure(refs: dict[str, str] | None, message: str):
    if not refs:
        return

    metadata = {"extractor_error": message}
    _patch_supabase_row("documents", refs["document_id"], {
        "extraction_status": "failed",
        "extraction_metadata": metadata,
    })
    _patch_supabase_row("upload_sessions", refs["upload_session_id"], {"status": "failed"})
    _patch_supabase_row("reports", refs["report_id"], {
        "preview_json": {
            "rows": [],
            "status": "failed",
            "summary": "Extraction failed. The report needs manual review.",
        },
    })


@app.post("/extract")
async def create_extraction_job(
    payload: ExtractRequest,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db),
    _service: None = Depends(require_service_token),
):
    supabase_refs = _supabase_writeback_refs(payload.metadata)
    original_filename = payload.metadata.original_filename or Path(payload.storage_object_path).name
    safe_name = safe_upload_filename(original_filename)
    allowed = {".pdf", ".xlsx", ".xlsm"}
    if Path(safe_name).suffix.lower() not in allowed:
        raise HTTPException(400, f"Only PDF and Excel files are accepted. Got: {Path(safe_name).suffix}")

    async with db.execute(
        "SELECT id FROM companies WHERE name=? AND COALESCE(exchange, '')=COALESCE(?, '')",
        (payload.metadata.company_name, payload.metadata.exchange),
    ) as cur:
        company = await cur.fetchone()
    if company:
        company_id = company["id"]
    else:
        async with db.execute(
            "INSERT INTO companies (name, exchange) VALUES (?, ?)",
            (payload.metadata.company_name, payload.metadata.exchange),
        ) as cur:
            company_id = cur.lastrowid

    company_dir = PDF_DIR / "extract" / str(company_id)
    company_dir.mkdir(parents=True, exist_ok=True)
    dest = company_dir / f"{uuid.uuid4().hex}-{safe_name}"

    if payload.metadata.local_file_path:
        if os.environ.get("EXTRACTOR_ALLOW_LOCAL_FILES") != "1":
            raise HTTPException(400, "local_file_path is disabled")
        local_path = Path(payload.metadata.local_file_path).expanduser().resolve()
        if not local_path.exists() or not local_path.is_file():
            raise HTTPException(400, "local_file_path does not exist")
        shutil.copyfile(local_path, dest)
    else:
        _download_supabase_object(payload.metadata.storage_bucket, payload.storage_object_path, dest)

    async with db.execute("""
        INSERT INTO documents
            (company_id, filename, filepath, report_type, entity_type, fiscal_year_end)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        company_id,
        safe_name,
        str(dest),
        payload.metadata.report_type,
        payload.metadata.entity_type,
        payload.metadata.fiscal_year_end,
    )) as cur:
        document_id = cur.lastrowid
    await db.commit()

    background_tasks.add_task(
        _run_ingestion,
        document_id,
        company_id,
        str(dest),
        payload.metadata.entity_type,
        payload.metadata.exchange,
        payload.metadata.fiscal_year_end,
        supabase_refs,
    )

    return {"job_id": document_id, "document_id": document_id, "status": "processing"}


@app.get("/extract/{job_id}")
async def extraction_job_status(job_id: int, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("""
        SELECT id, extraction_status, extraction_model, confidence_score, updated_at
        FROM documents
        WHERE id=?
    """, (job_id,)) as cur:
        doc = await cur.fetchone()
    if not doc:
        raise HTTPException(404, "Extraction job not found")

    return {
        "job_id": doc["id"],
        "status": doc["extraction_status"],
        "model": doc["extraction_model"],
        "confidence": doc["confidence_score"],
        "updated_at": doc["updated_at"],
    }


async def _run_ingestion(document_id, company_id, filepath, entity_type, exchange, fiscal_year_end, supabase_refs=None):
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
            try:
                _write_supabase_failure(supabase_refs, str(e))
            except Exception as writeback_error:
                print(f"[ERROR] Supabase failure write-back failed for doc {document_id}: {writeback_error}")
        else:
            try:
                await _write_supabase_success(db, document_id, supabase_refs)
            except Exception as writeback_error:
                print(f"[ERROR] Supabase success write-back failed for doc {document_id}: {writeback_error}")


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

    doc_payload = dict(doc)
    latest_error = next((log["message"] for log in logs if log["level"].lower() == "error"), None)
    return {
        **doc_payload,
        "status": doc_payload.get("extraction_status"),
        "error_message": latest_error,
        "logs": logs,
    }


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
        "claude_model": os.environ.get("CLAUDE_MODEL") or ing.CLAUDE_MODEL,
        "env_file": str(ENV_PATH),
    }


@app.post("/settings")
async def update_settings(
    api_key:      str = Form(None),
    claude_model: str = Form(None),
    _admin: None = Depends(require_admin),
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
    _admin: None = Depends(require_admin),
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
