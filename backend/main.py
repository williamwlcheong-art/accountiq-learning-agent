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
from auth import auth_router, get_current_user, require_admin

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
# Root redirect
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "AccountIQ Learning Agent API. UI at /app"}
