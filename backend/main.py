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

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends, BackgroundTasks, Request
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
from auth import auth_router, get_current_user, require_admin
from report_email import send_report_ready_email, REPORT_TYPE_LABELS

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
    current_user: dict = Depends(require_admin),
):
    async with db.execute("""
        SELECT c.*,
               COUNT(DISTINCT d.id) as doc_count,
               (CASE WHEN c.sector IS NOT NULL AND c.sector != '' THEN 1 ELSE 0 END
                + CASE WHEN c.description IS NOT NULL AND LENGTH(TRIM(c.description)) >= 50 THEN 1 ELSE 0 END
                + CASE WHEN (SELECT COUNT(*) FROM management_team mt WHERE mt.company_id = c.id) > 0 THEN 1 ELSE 0 END
                + CASE WHEN (SELECT COUNT(*) FROM ebitda_adjustments ea WHERE ea.company_id = c.id) > 0 THEN 1 ELSE 0 END
               ) as sections_complete
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
    current_user: dict = Depends(require_admin),
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
    current_user: dict = Depends(require_admin),
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
# Business profile (Phase 3)
# ---------------------------------------------------------------------------

@app.post("/companies/{company_id}/profile")
async def update_company_profile(
    company_id: int,
    sector:      Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Patch sector and/or description on a company. Either field may be omitted."""
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")
    if sector is not None:
        await db.execute(
            "UPDATE companies SET sector=? WHERE id=?",
            (sector, company_id)
        )
    if description is not None:
        await db.execute(
            "UPDATE companies SET description=? WHERE id=?",
            (description, company_id)
        )
    await db.commit()
    async with db.execute(
        "SELECT sector, description FROM companies WHERE id=?",
        (company_id,)
    ) as cur:
        row = await cur.fetchone()
    return dict(row)


@app.get("/companies/{company_id}/profile-status")
async def profile_status(
    company_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Return profile completion status + EBITDA bridge inputs for a company.
    Used by Phase 5 to gate report generation and by the frontend completion badge."""
    async with db.execute(
        "SELECT sector, description FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        company = await cur.fetchone()
    if not company:
        raise HTTPException(404, "Company not found")

    # Section 1: industry / sector
    sector_complete = bool(company["sector"])

    # Section 2: description (>= 50 chars after trim)
    desc = company["description"] or ""
    desc_complete = len(desc.strip()) >= 50

    # Section 3: management team — at least one row
    async with db.execute(
        "SELECT COUNT(*) as n FROM management_team WHERE company_id=?",
        (company_id,)
    ) as cur:
        mgmt_count = (await cur.fetchone())["n"]
    mgmt_complete = mgmt_count > 0

    # Section 4: EBITDA adjustments — at least one row
    async with db.execute(
        "SELECT COUNT(*) as n FROM ebitda_adjustments WHERE company_id=?",
        (company_id,)
    ) as cur:
        adj_count = (await cur.fetchone())["n"]
    ebitda_complete = adj_count > 0

    # EBITDA bridge: most recent period with net_profit / depreciation_amortisation / depreciation
    reported_ebitda = None
    has_financials = False
    async with db.execute("""
        SELECT MAX(period) as max_period FROM financial_rows
        WHERE company_id=? AND row_key IN ('net_profit', 'depreciation_amortisation', 'depreciation')
    """, (company_id,)) as cur:
        period_row = await cur.fetchone()
    max_period = period_row["max_period"] if period_row else None
    if max_period:
        has_financials = True
        async with db.execute("""
            SELECT row_key, value FROM financial_rows
            WHERE company_id=? AND period=?
              AND row_key IN ('net_profit', 'depreciation_amortisation', 'depreciation')
        """, (company_id, max_period)) as cur:
            fin_rows = {r["row_key"]: r["value"] for r in await cur.fetchall()}
        net_profit = fin_rows.get("net_profit") or 0
        # Prefer depreciation_amortisation; fall back to depreciation alone
        da = fin_rows.get("depreciation_amortisation")
        if da is None:
            da = fin_rows.get("depreciation") or 0
        reported_ebitda = net_profit + da

    sections_complete = sum([sector_complete, desc_complete, mgmt_complete, ebitda_complete])
    can_generate = sector_complete and ebitda_complete

    return {
        "sections_complete": sections_complete,
        "total": 4,
        "sector_complete": sector_complete,
        "description_complete": desc_complete,
        "management_complete": mgmt_complete,
        "ebitda_complete": ebitda_complete,
        "can_generate": can_generate,
        "reported_ebitda": reported_ebitda,
        "has_financials": has_financials,
    }


# --- Management team CRUD -----------------------------------------------

@app.get("/companies/{company_id}/management-team")
async def list_management_team(
    company_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")
    async with db.execute(
        "SELECT id, name, title, bio FROM management_team WHERE company_id=? ORDER BY id ASC",
        (company_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.post("/companies/{company_id}/management-team", status_code=201)
async def add_management_team_member(
    company_id: int,
    name:  str           = Form(...),
    title: Optional[str] = Form(None),
    bio:   Optional[str] = Form(None),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")
    async with db.execute(
        "INSERT INTO management_team (company_id, name, title, bio) VALUES (?, ?, ?, ?)",
        (company_id, name, title, bio)
    ) as cur:
        member_id = cur.lastrowid
    await db.commit()
    return {"id": member_id, "name": name, "title": title, "bio": bio}


@app.put("/companies/{company_id}/management-team/{member_id}")
async def update_management_team_member(
    company_id: int,
    member_id: int,
    name:  str           = Form(...),
    title: Optional[str] = Form(None),
    bio:   Optional[str] = Form(None),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")
    async with db.execute(
        "UPDATE management_team SET name=?, title=?, bio=? WHERE id=? AND company_id=?",
        (name, title, bio, member_id, company_id)
    ) as cur:
        if cur.rowcount == 0:
            raise HTTPException(404, "Member not found")
    await db.commit()
    return {"id": member_id, "name": name, "title": title, "bio": bio}


@app.delete("/companies/{company_id}/management-team/{member_id}", status_code=204)
async def delete_management_team_member(
    company_id: int,
    member_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")
    await db.execute(
        "DELETE FROM management_team WHERE id=? AND company_id=?",
        (member_id, company_id)
    )
    await db.commit()
    return Response(status_code=204)


# --- EBITDA adjustments CRUD --------------------------------------------

@app.get("/companies/{company_id}/ebitda-adjustments")
async def list_ebitda_adjustments(
    company_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")
    async with db.execute(
        "SELECT id, label, amount, rationale FROM ebitda_adjustments WHERE company_id=? ORDER BY id ASC",
        (company_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.post("/companies/{company_id}/ebitda-adjustments", status_code=201)
async def add_ebitda_adjustment(
    company_id: int,
    label:     str           = Form(...),
    amount:    float         = Form(...),
    rationale: Optional[str] = Form(None),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")
    async with db.execute(
        "INSERT INTO ebitda_adjustments (company_id, label, amount, rationale) VALUES (?, ?, ?, ?)",
        (company_id, label, amount, rationale)
    ) as cur:
        adj_id = cur.lastrowid
    await db.commit()
    return {"id": adj_id, "label": label, "amount": amount, "rationale": rationale}


@app.put("/companies/{company_id}/ebitda-adjustments/{adj_id}")
async def update_ebitda_adjustment(
    company_id: int,
    adj_id: int,
    label:     str           = Form(...),
    amount:    float         = Form(...),
    rationale: Optional[str] = Form(None),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")
    async with db.execute(
        "UPDATE ebitda_adjustments SET label=?, amount=?, rationale=? WHERE id=? AND company_id=?",
        (label, amount, rationale, adj_id, company_id)
    ) as cur:
        if cur.rowcount == 0:
            raise HTTPException(404, "Adjustment not found")
    await db.commit()
    return {"id": adj_id, "label": label, "amount": amount, "rationale": rationale}


@app.delete("/companies/{company_id}/ebitda-adjustments/{adj_id}", status_code=204)
async def delete_ebitda_adjustment(
    company_id: int,
    adj_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")
    await db.execute(
        "DELETE FROM ebitda_adjustments WHERE id=? AND company_id=?",
        (adj_id, company_id)
    )
    await db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Documents — upload & ingest
# ---------------------------------------------------------------------------

@app.get("/documents")
async def list_documents(
    company_id: Optional[int] = None,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
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


def _extract_company_name_from_pdf_sync(filepath: str) -> str:
    """Extract company name from page 1 of a PDF via Claude. Returns empty string on failure."""
    try:
        import pdfplumber
        import anthropic
        with pdfplumber.open(filepath) as pdf:
            if not pdf.pages:
                return ""
            page1_text = pdf.pages[0].extract_text(x_tolerance=2, y_tolerance=3) or ""
        if not page1_text.strip():
            return ""
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=64,
            messages=[{
                "role": "user",
                "content": (
                    "Extract the company or entity name from this financial document cover page. "
                    "Reply with ONLY the company name — no explanation, no punctuation.\n\n"
                    f"{page1_text[:2000]}"
                )
            }]
        )
        name = msg.content[0].text.strip() if msg.content else ""
        return name[:200] if name else ""
    except Exception:
        return ""


async def _resolve_or_create_company(db, name: str, user_id: int) -> tuple[int, str]:
    """Find existing company by name (case-insensitive) or create a new one. Returns (id, name)."""
    async with db.execute(
        "SELECT id, name FROM companies WHERE lower(name)=lower(?) AND user_id=?",
        (name, user_id)
    ) as cur:
        existing = await cur.fetchone()
    if existing:
        return existing["id"], existing["name"]
    async with db.execute(
        "INSERT INTO companies (name, exchange, user_id) VALUES (?, 'Private', ?)",
        (name, user_id)
    ) as cur:
        company_id = cur.lastrowid
    await db.commit()
    return company_id, name


@app.post("/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file:            UploadFile = File(...),
    company_id:      Optional[int] = Form(None),
    company_name:    Optional[str] = Form(None),
    report_type:     str  = Form("annual_report"),
    entity_type:     str  = Form("listed"),
    fiscal_year_end: str  = Form(""),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    suffix = Path(file.filename).suffix.lower()
    allowed = {".pdf", ".xlsx", ".xls", ".xlsm", ".docx"}
    if suffix not in allowed:
        raise HTTPException(400, f"Only PDF, Excel, and Word files are accepted. Got: {suffix}")

    is_excel = suffix in {".xlsx", ".xls", ".xlsm"}
    exchange = "Private"

    if company_id is not None:
        # Explicit company supplied — verify ownership (existing behaviour)
        async with db.execute(
            "SELECT id, exchange FROM companies WHERE id=? AND user_id=?",
            (company_id, current_user["id"])
        ) as cur:
            company = await cur.fetchone()
        if not company:
            raise HTTPException(404, f"Company {company_id} not found.")
        exchange = company["exchange"] or "Private"
        resolved_name = None
    else:
        # Auto-resolve: use provided name (Excel) or extract from PDF
        if is_excel:
            if not company_name or not company_name.strip():
                raise HTTPException(400, "Company name is required for Excel uploads.")
            resolved_name = company_name.strip()
        else:
            # Save to a temp location first so we can read it for name extraction
            tmp_dir = PDF_DIR / "_tmp"
            tmp_dir.mkdir(exist_ok=True)
            tmp_path = tmp_dir / Path(file.filename).name
            contents = await file.read()
            with open(tmp_path, "wb") as f:
                f.write(contents)
            # Extract company name from PDF page 1 via Claude
            loop = asyncio.get_running_loop()
            extracted = await loop.run_in_executor(
                None, _extract_company_name_from_pdf_sync, str(tmp_path)
            )
            resolved_name = extracted.strip() if extracted.strip() else Path(file.filename).stem
            # Rewind file-like object by wrapping the bytes we already read
            import io
            file.file = io.BytesIO(contents)

        company_id, resolved_name = await _resolve_or_create_company(
            db, resolved_name, current_user["id"]
        )

    # Save file into company directory
    company_dir = PDF_DIR / str(company_id)
    company_dir.mkdir(exist_ok=True)
    safe_name = Path(file.filename).name
    dest = company_dir / safe_name

    # Clean up tmp file if it was written there
    tmp_candidate = PDF_DIR / "_tmp" / safe_name
    if tmp_candidate.exists():
        import shutil as _shutil
        _shutil.move(str(tmp_candidate), str(dest))
    else:
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)

    async with db.execute("""
        INSERT INTO documents
            (company_id, filename, filepath, report_type, entity_type, fiscal_year_end, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (company_id, safe_name, str(dest),
          report_type, entity_type, fiscal_year_end, current_user["id"])) as cur:
        document_id = cur.lastrowid
    await db.commit()

    background_tasks.add_task(
        _run_ingestion, document_id, company_id, str(dest),
        entity_type, exchange, fiscal_year_end
    )

    return {
        "document_id": document_id,
        "company_id": company_id,
        "company_name": resolved_name,
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
    current_user: dict = Depends(require_admin),
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
    current_user: dict = Depends(require_admin),
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
    current_user: dict = Depends(require_admin),
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
    current_user: dict = Depends(require_admin),
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
    current_user: dict = Depends(require_admin),
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
    current_user: dict = Depends(require_admin),
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
    current_user: dict = Depends(require_admin),
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
async def get_settings(current_user: dict = Depends(require_admin)):
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
    current_user: dict = Depends(require_admin),
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
    current_user: dict = Depends(require_admin),
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
# Wizard — authenticated non-admin upload path (Phase 3.5, D-05, D-06)
# ---------------------------------------------------------------------------

@app.post("/wizard/upload", status_code=201)
async def wizard_upload(
    background_tasks: BackgroundTasks,
    business_name: str = Form(...),
    file: UploadFile = File(...),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),   # NOT require_admin — per D-05
):
    """Create company + upload document for non-admin users. Reuses _run_ingestion."""
    name = business_name.strip()
    if not name:
        raise HTTPException(400, "Business name is required")

    suffix = Path(file.filename).suffix.lower()
    allowed = {".pdf", ".xlsx", ".xls", ".xlsm", ".docx"}
    if suffix not in allowed:
        raise HTTPException(400, f"Only PDF, Excel, and Word files are accepted. Got: {suffix}")

    # Idempotent company creation — reuses existing helper (D-06)
    company_id, _ = await _resolve_or_create_company(db, name, current_user["id"])

    # Save file into company directory (project security rule: Path(file.filename).name)
    company_dir = PDF_DIR / str(company_id)
    company_dir.mkdir(exist_ok=True)
    safe_name = Path(file.filename).name
    dest = company_dir / safe_name
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Insert document record
    async with db.execute("""
        INSERT INTO documents
            (company_id, filename, filepath, report_type, entity_type, fiscal_year_end, user_id)
        VALUES (?, ?, ?, 'compilation', 'sme', '', ?)
    """, (company_id, safe_name, str(dest), current_user["id"])) as cur:
        document_id = cur.lastrowid
    await db.commit()

    # Kick off background ingestion — same task as admin upload (D-06)
    background_tasks.add_task(
        _run_ingestion, document_id, company_id, str(dest), "sme", "Private", ""
    )

    return {"company_id": company_id, "document_id": document_id, "status": "processing"}


# ---------------------------------------------------------------------------
# Wizard — report generation (Phase 5)
# ---------------------------------------------------------------------------

# Valid report types (match REPORT_TYPE_LABELS keys in report_email.py)
_VALID_REPORT_TYPES = frozenset(REPORT_TYPE_LABELS.keys())


@app.post("/wizard/report/generate", status_code=201)
async def wizard_report_generate(
    request: Request,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),   # non-admin users can generate
):
    """
    Create a report job and immediately queue generation.

    Body (JSON):
      {
        "company_id": int,
        "report_type": str,          // one of VALID_REPORT_TYPES
        "intake_answers": { ... }    // report-type-specific answers dict
      }

    Phase 5 bypasses pending_payment (D-04). Phase 6 inserts the payment gate
    before this endpoint without touching the generation logic.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Request body must be valid JSON")

    company_id = body.get("company_id")
    report_type = body.get("report_type")
    intake_answers = body.get("intake_answers", {})

    if not company_id:
        raise HTTPException(400, "company_id is required")
    if not report_type or report_type not in _VALID_REPORT_TYPES:
        raise HTTPException(
            400,
            f"report_type must be one of: {', '.join(sorted(_VALID_REPORT_TYPES))}"
        )
    if not isinstance(intake_answers, dict):
        raise HTTPException(400, "intake_answers must be a JSON object")

    # Verify the company belongs to this user
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")

    # Create report row (status = queued per D-04)
    async with db.execute("""
        INSERT INTO reports (company_id, user_id, report_type, status)
        VALUES (?, ?, ?, 'queued')
    """, (company_id, current_user["id"], report_type)) as cur:
        report_id = cur.lastrowid

    # Store intake answers
    await db.execute("""
        INSERT INTO report_intake (report_id, answers) VALUES (?, ?)
    """, (report_id, json.dumps(intake_answers)))
    await db.commit()

    # Queue background generation task
    background_tasks.add_task(
        _generate_report,
        report_id,
        company_id,
        current_user["id"],
        report_type,
        intake_answers,
    )

    return {"report_id": report_id, "status": "queued"}


@app.get("/wizard/report/{report_id}/status")
async def wizard_report_status(
    report_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return current status of a report generation job."""
    async with db.execute("""
        SELECT id, report_type, status, error_message, created_at, completed_at
        FROM reports
        WHERE id=? AND user_id=?
    """, (report_id, current_user["id"])) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Report not found")
    return dict(row)


@app.post("/wizard/report/{report_id}/retry")
async def wizard_report_retry(
    report_id: int,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Reset a failed report to queued and re-queue the generation task (D-06).
    Only callable when status is 'failed'.
    """
    async with db.execute("""
        SELECT id, company_id, report_type, status
        FROM reports WHERE id=? AND user_id=?
    """, (report_id, current_user["id"])) as cur:
        report = await cur.fetchone()
    if not report:
        raise HTTPException(404, "Report not found")
    if report["status"] != "failed":
        raise HTTPException(409, f"Report is not in failed state (current: {report['status']})")

    # Fetch the original intake answers for re-use
    async with db.execute(
        "SELECT answers FROM report_intake WHERE report_id=? ORDER BY id DESC LIMIT 1",
        (report_id,)
    ) as cur:
        intake_row = await cur.fetchone()
    intake_answers = json.loads(intake_row["answers"]) if intake_row else {}

    # Reset status
    await db.execute("""
        UPDATE reports
        SET status='queued', error_message=NULL, completed_at=NULL
        WHERE id=? AND user_id=?
    """, (report_id, current_user["id"]))
    await db.commit()

    background_tasks.add_task(
        _generate_report,
        report_id,
        report["company_id"],
        current_user["id"],
        report["report_type"],
        intake_answers,
    )
    return {"report_id": report_id, "status": "queued"}


# ---------------------------------------------------------------------------
# Report generation background task (Phase 5)
# ---------------------------------------------------------------------------

# Section schemas per report type — used by prompt builder and Phase 7 template registry
REPORT_SECTIONS: dict[str, list[str]] = {
    "valuation": [
        "executive_summary",
        "business_overview",
        "financial_analysis",
        "valuation_methodology",
        "dcf_analysis",
        "multiples_analysis",
        "concluded_value",
        "disclaimer",
    ],
    "bank_credit": [
        "executive_summary",
        "borrower_overview",
        "financial_analysis",
        "dscr_analysis",
        "sensitivity_analysis",
        "security_collateral",
        "recommendation",
        "disclaimer",
    ],
    "forecast": [
        "executive_summary",
        "business_overview",
        "assumptions",
        "revenue_forecast",
        "ebitda_forecast",
        "cashflow_forecast",
        "scenario_analysis",
        "disclaimer",
    ],
    "capital_raising": [
        "executive_summary",
        "company_overview",
        "investment_highlights",
        "use_of_funds",
        "financial_summary",
        "management_team",
        "transaction_structure",
        "disclaimer",
    ],
    "im": [
        "executive_summary",
        "business_overview",
        "products_services",
        "market_position",
        "management_team",
        "financial_performance",
        "growth_opportunities",
        "transaction_details",
        "risk_factors",
        "disclaimer",
    ],
}


async def _generate_report(
    report_id: int,
    company_id: int,
    user_id: int,
    report_type: str,
    intake_answers: dict,
) -> None:
    """
    Background task: read financial data + profile, run Python algorithms
    (Valuation Advisory only), call Claude for narrative, store JSON content,
    send email on completion.

    Opens its own DB connection (same pattern as _run_ingestion).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("PRAGMA journal_mode=WAL")

        try:
            # Mark as generating
            await db.execute(
                "UPDATE reports SET status='generating' WHERE id=?",
                (report_id,)
            )
            await db.commit()

            # --- Load company profile ---
            async with db.execute("""
                SELECT c.name, c.sector, c.description
                FROM companies c WHERE c.id=?
            """, (company_id,)) as cur:
                company = await cur.fetchone()
            if not company:
                raise RuntimeError(f"Company {company_id} not found")

            company_name = company["name"]
            company_sector = company["sector"] or ""
            company_description = company["description"] or ""

            # Management team
            async with db.execute("""
                SELECT name, title, bio FROM management_team
                WHERE company_id=? ORDER BY id ASC
            """, (company_id,)) as cur:
                mgmt_team = [dict(r) for r in await cur.fetchall()]

            # EBITDA adjustments (add-backs from Phase 3)
            async with db.execute("""
                SELECT label, amount, rationale FROM ebitda_adjustments
                WHERE company_id=? ORDER BY id ASC
            """, (company_id,)) as cur:
                ebitda_adjustments = [dict(r) for r in await cur.fetchall()]

            # Financial rows — most recent 3 periods for each statement type
            async with db.execute("""
                SELECT statement, row_key, row_label, period, value, currency, unit
                FROM financial_rows
                WHERE company_id=?
                ORDER BY statement, row_key, period DESC
            """, (company_id,)) as cur:
                fin_rows = [dict(r) for r in await cur.fetchall()]

            # --- Prepare context dict for prompt builder ---
            context = {
                "company_name": company_name,
                "company_sector": company_sector,
                "company_description": company_description,
                "management_team": mgmt_team,
                "ebitda_adjustments": ebitda_adjustments,
                "financial_rows": fin_rows,
                "intake_answers": intake_answers,
            }

            # --- Run Python algorithm for Valuation Advisory (D-08) ---
            algorithm_outputs = None
            if report_type == "valuation":
                algorithm_outputs = await _run_valuation_algorithm(
                    db, company_id, intake_answers, ebitda_adjustments, fin_rows
                )
                context["algorithm_outputs"] = algorithm_outputs

            # --- Build prompt and call Claude ---
            sections = REPORT_SECTIONS.get(report_type, ["content"])
            system_prompt, user_message = _build_report_prompt(
                report_type, sections, context
            )

            content_json = await _call_claude_for_report(
                system_prompt, user_message, sections
            )

            # --- Mark done, store content ---
            await db.execute("""
                UPDATE reports
                SET status='done', content=?, completed_at=datetime('now')
                WHERE id=?
            """, (json.dumps(content_json), report_id))
            await db.commit()
            print(f"[REPORT] report_id={report_id} done ({report_type})")

            # --- Send email notification ---
            async with db.execute(
                "SELECT email FROM users WHERE id=?", (user_id,)
            ) as cur:
                user_row = await cur.fetchone()
            if user_row:
                user_email = user_row["email"]
                # Use email as display name (name not stored separately in this schema)
                user_name = user_email.split("@")[0]
                await send_report_ready_email(
                    user_email, user_name, report_type, report_id
                )

        except Exception as exc:
            err_msg = str(exc)[:1000]
            print(f"[REPORT ERROR] report_id={report_id}: {err_msg}")
            try:
                await db.execute("""
                    UPDATE reports
                    SET status='failed', error_message=?
                    WHERE id=?
                """, (err_msg, report_id))
                await db.commit()
            except Exception as db_exc:
                print(f"[REPORT ERROR] Failed to mark report failed: {db_exc}")


async def _run_valuation_algorithm(
    db, company_id: int, intake_answers: dict,
    ebitda_adjustments: list[dict], fin_rows: list[dict]
) -> dict:
    """
    Run the Python valuation algorithm (D-08). Returns the outputs dict
    that will be passed to Claude's prompt.

    Imports backend/valuation.py which is created in Plan 03 of Phase 5.
    Returns a stub dict if valuation.py is not yet available.
    """
    try:
        import valuation as val_module
        return await asyncio.get_running_loop().run_in_executor(
            None,
            val_module.compute_valuation,
            intake_answers,
            fin_rows,
            ebitda_adjustments,
        )
    except ImportError:
        # valuation.py not yet available (created in Plan 05-03)
        print(f"[REPORT] valuation.py not available — using stub outputs for company {company_id}")
        return {
            "method_used": "both",
            "normalised_ebitda": None,
            "note": "Valuation algorithm not yet available — narrative only",
        }
    except Exception as exc:
        print(f"[REPORT] Valuation algorithm error for company {company_id}: {exc}")
        return {
            "method_used": "both",
            "normalised_ebitda": None,
            "note": f"Valuation algorithm error: {exc}",
        }


def _build_report_prompt(
    report_type: str,
    sections: list[str],
    context: dict,
) -> tuple[str, str]:
    """
    Build the Claude system prompt and user message for a given report type.
    Returns (system_prompt, user_message).
    """
    company_name = context.get("company_name", "the company")
    company_sector = context.get("company_sector", "")
    company_description = context.get("company_description", "")
    mgmt_team = context.get("management_team", [])
    ebitda_adjustments = context.get("ebitda_adjustments", [])
    fin_rows = context.get("financial_rows", [])
    intake_answers = context.get("intake_answers", {})
    algorithm_outputs = context.get("algorithm_outputs")

    # Format financial rows as a condensed table
    fin_summary = _format_financial_rows(fin_rows)

    # Format management team
    mgmt_summary = ""
    if mgmt_team:
        lines = [f"- {m['name']}, {m.get('title','')}{ ': ' + m['bio'] if m.get('bio') else ''}"
                 for m in mgmt_team]
        mgmt_summary = "Management Team:\n" + "\n".join(lines)

    # Format EBITDA add-backs
    ebitda_summary = ""
    if ebitda_adjustments:
        lines = [f"- {a['label']}: {a['amount']:,.0f}" + (f" ({a['rationale']})" if a.get('rationale') else "")
                 for a in ebitda_adjustments]
        ebitda_summary = "EBITDA Add-backs:\n" + "\n".join(lines)

    # Section list for Claude
    sections_str = "\n".join(f'  "{s}": "<section content>"' for s in sections)

    system_prompt = """You are an expert financial report writer for AccountIQ, a professional financial analysis platform.

Your role is to write first-draft quality professional financial reports for SME business owners.
Reports must be accurate, factual, and based ONLY on the data provided — do not invent numbers or make assumptions not supported by the data.

CRITICAL REQUIREMENTS:
1. Every report section must include appropriate "indicative only" disclaimer language where relevant
2. The final section (disclaimer) must clearly state the report is indicative only and does not constitute financial advice
3. Base all analysis on the financial data and intake answers provided — do not fabricate metrics
4. Output MUST be valid JSON matching the required section schema exactly

OUTPUT FORMAT:
Return a single JSON object with exactly these keys:
{
""" + sections_str + """
}

Do not include any text outside the JSON object. Do not include markdown code fences."""

    # Report-type-specific instructions
    type_instructions = {
        "valuation": _valuation_prompt_instructions(algorithm_outputs, intake_answers),
        "bank_credit": _bank_credit_prompt_instructions(intake_answers, fin_rows),
        "forecast": _forecast_prompt_instructions(intake_answers),
        "capital_raising": _capital_raising_prompt_instructions(intake_answers),
        "im": _im_prompt_instructions(intake_answers),
    }
    specific_instructions = type_instructions.get(report_type, "")

    user_message = f"""Generate a {REPORT_TYPE_LABELS.get(report_type, report_type)} for {company_name}.

COMPANY INFORMATION:
- Name: {company_name}
- Sector: {company_sector or 'Not specified'}
- Description: {company_description or 'Not provided'}

{mgmt_summary}

{ebitda_summary}

FINANCIAL DATA:
{fin_summary}

INTAKE QUESTIONNAIRE ANSWERS:
{json.dumps(intake_answers, indent=2)}

{specific_instructions}

Generate the complete report as JSON matching the required section schema."""

    return system_prompt, user_message


def _valuation_prompt_instructions(algorithm_outputs: dict | None, intake_answers: dict) -> str:
    if not algorithm_outputs or algorithm_outputs.get("normalised_ebitda") is None:
        return (
            "NOTE: Valuation algorithm outputs are not available. "
            "Write a qualitative narrative-only valuation section acknowledging that "
            "quantitative analysis requires complete financial data. "
            "Do not fabricate any numbers or multiples."
        )
    return f"""PYTHON-COMPUTED VALUATION OUTPUTS (use these exact numbers — do not modify):
{json.dumps(algorithm_outputs, indent=2)}

Instructions:
- Use the concluded_range values (low/mid/high) as the valuation conclusion
- Explain the DCF and EV/EBITDA methodologies in plain language
- Reference the key risk factors identified in the questionnaire scoring
- The valuation is indicative only — state this clearly in executive_summary and disclaimer"""


def _bank_credit_prompt_instructions(intake_answers: dict, fin_rows: list[dict]) -> str:
    return """Instructions for Bank Credit Paper:
- Include DSCR calculation based on extracted EBITDA, interest expense, and the proposed facility repayment schedule from intake
- Include a 3-year financial trend table summarising revenue, EBITDA, and net profit
- Include sensitivity analysis showing DSCR at -10% and -20% revenue scenarios
- All computed figures must be derived from the financial data provided — label clearly as estimated where data is incomplete
- The recommendation section should be objective and reference the financial metrics"""


def _forecast_prompt_instructions(intake_answers: dict) -> str:
    return """Instructions for Financial Forecast:
- The assumptions section must list every assumption drawn from the intake questionnaire answers
- Include 3-year projections for revenue, EBITDA, and net profit based on stated growth rates
- Include base, bull, and bear scenarios (base = stated growth rate, bull = +50% of growth rate, bear = -50%)
- Label all projections clearly as forward-looking estimates"""


def _capital_raising_prompt_instructions(intake_answers: dict) -> str:
    return """Instructions for Capital Raising Document:
- Use-of-funds section must itemise every use of proceeds from the intake answers
- Management team section must be populated from the company profile management team data
- Include the instrument type and transaction structure from intake answers
- All financial projections must be clearly labelled as forward-looking estimates"""


def _im_prompt_instructions(intake_answers: dict) -> str:
    return """Instructions for Information Memorandum:
- All 10 sections must contain company-specific content — no generic placeholders
- Sale rationale must reflect the user-provided rationale from intake answers
- Growth opportunities section must reference the specific opportunities identified in intake
- Target buyer type and transaction structure must align with intake answers
- Risk factors must be balanced — identify both genuine risks and mitigating factors"""


def _format_financial_rows(fin_rows: list[dict]) -> str:
    """Format financial_rows into a readable summary for the Claude prompt."""
    if not fin_rows:
        return "No financial data available."

    # Group by statement type and collect periods
    from collections import defaultdict
    by_stmt: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    periods_set: set[str] = set()
    for row in fin_rows:
        stmt = row.get("statement", "")
        key = row.get("row_key", "")
        period = row.get("period", "")
        value = row.get("value")
        if stmt and key and period and value is not None:
            by_stmt[stmt][key][period] = value
            periods_set.add(period)

    periods = sorted(periods_set, reverse=True)[:3]  # Most recent 3 periods

    lines = []
    for stmt in ["pnl", "bs", "cf", "eq"]:
        if stmt not in by_stmt:
            continue
        stmt_labels = {"pnl": "P&L", "bs": "Balance Sheet", "cf": "Cash Flow", "eq": "Equity"}
        lines.append(f"\n{stmt_labels.get(stmt, stmt.upper())}:")
        header = "  {:<35}".format("") + "".join(f"  {p:>12}" for p in periods)
        lines.append(header)
        for key, period_vals in sorted(by_stmt[stmt].items()):
            row_line = f"  {key:<35}"
            for p in periods:
                val = period_vals.get(p)
                row_line += f"  {val:>12,.0f}" if val is not None else f"  {'—':>12}"
            lines.append(row_line)

    return "\n".join(lines) if lines else "No financial data available."


async def _call_claude_for_report(
    system_prompt: str,
    user_message: str,
    sections: list[str],
) -> dict:
    """
    Call Claude claude-sonnet-4-6 for report generation (plain JSON, no tool-use).
    Returns parsed dict with section keys.
    """
    import anthropic as _anthropic
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set — cannot generate report")

    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    client = _anthropic.Anthropic(api_key=key)

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, lambda: client.messages.create(
        model=model,
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    ))

    raw_text = response.content[0].text if response.content else ""

    # Parse JSON from Claude's response
    content_json = _parse_json_from_response(raw_text, sections)
    return content_json


def _parse_json_from_response(raw_text: str, sections: list[str]) -> dict:
    """
    Extract JSON from Claude's response text.
    Handles cases where Claude wraps JSON in markdown code fences.
    Falls back to a stub dict if parsing fails.
    """
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            # Ensure all expected sections are present
            for s in sections:
                if s not in parsed:
                    parsed[s] = f"[Section '{s}' not generated — please retry]"
            return parsed
    except json.JSONDecodeError:
        pass

    # Last resort: try to find a JSON object in the text
    import re as _re
    match = _re.search(r'\{[\s\S]+\}', text)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                for s in sections:
                    if s not in parsed:
                        parsed[s] = f"[Section '{s}' not generated — please retry]"
                return parsed
        except json.JSONDecodeError:
            pass

    # Fallback stub
    print(f"[REPORT] Failed to parse JSON from Claude response, using stub. Raw: {raw_text[:200]}")
    return {s: f"[Generation error — section '{s}' could not be parsed]" for s in sections}


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "AccountIQ Learning Agent API. UI at /app"}
