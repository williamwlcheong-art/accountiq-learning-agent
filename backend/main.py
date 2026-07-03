"""
AccountIQ Learning Agent — FastAPI backend
Run with: uvicorn main:app --reload --port 8765
"""
import os
import json
import shutil
import asyncio
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, HTMLResponse
import aiosqlite

# Load .env from project root (one level up from backend/)
from dotenv import load_dotenv, set_key
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH, override=False)

from db import init_db, get_db, get_pattern_library, DB_PATH
from ingestion import ingest_document
from auth import auth_router, get_current_user, require_admin
from payments import (
    checkout_config,
    construct_webhook_event,
    create_checkout_session,
    stripe_enabled,
)
from report_email import send_report_ready_email, REPORT_TYPE_LABELS
from report_prompts import build_prompt, SECTION_SCHEMAS, compute_bank_credit_figures
from research_loop import run_valuation_research
from valuation import (
    compute_wacc_scenarios, compute_dcf, compute_illiquidity_discount,
    compute_risk_score, compute_multiples_ev,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    print("[STARTUP] AccountIQ Learning Agent ready.")
    yield


app = FastAPI(
    title="AccountIQ Learning Agent",
    version="0.1.0",
    description="Ingest financial PDFs, learn patterns, improve over time.",
    lifespan=lifespan,
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

E2E_MODE = os.environ.get("ACCOUNTIQ_E2E_MODE", "false").lower() == "true"


def _e2e_financial_rows() -> list[tuple[str, str, str, str, float, float]]:
    return [
        ("pnl", "revenue", "Revenue", "2025", 1_250_000.0, 0.99),
        ("pnl", "ebitda", "EBITDA", "2025", 240_000.0, 0.98),
        ("pnl", "net_profit", "Net Profit", "2025", 150_000.0, 0.97),
        ("bs", "cash_and_bank", "Cash & bank", "2025", 95_000.0, 0.98),
        ("bs", "total_assets", "Total Assets", "2025", 850_000.0, 0.98),
    ]


def _e2e_report_content(report_type: str) -> dict:
    sections = SECTION_SCHEMAS.get(report_type, ["executive_summary", "disclaimer"])
    content = {}
    for section in sections:
        title = section.replace("_", " ").title()
        if section == "disclaimer":
            content[section] = (
                "This report is indicative only, is not financial advice, "
                "is not regulated advice under the FMCA, and should not be relied "
                "on without independent professional advice."
            )
        elif section.endswith("summary") or section in {"valuation_summary", "financial_summary"}:
            content[section] = {
                "narrative": f"E2E generated {title} with <script>escaped text</script> for safety checks.",
                "table": {
                    "headers": ["Metric", "Value"],
                    "rows": [["Revenue", "$1,250,000"], ["EBITDA", "$240,000"]],
                },
            }
        else:
            content[section] = f"E2E generated {title} for {report_type}."
    return content

# Serve the legacy vanilla frontend only when explicitly requested.
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
SERVE_LEGACY_FRONTEND = os.environ.get("ACCOUNTIQ_SERVE_LEGACY_FRONTEND", "false").lower() == "true"
if SERVE_LEGACY_FRONTEND and FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="legacy_frontend")


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
            if E2E_MODE:
                await db.execute(
                    "UPDATE documents SET extraction_status='processing', updated_at=datetime('now') WHERE id=?",
                    (document_id,),
                )
                await db.execute(
                    "INSERT INTO extraction_log (document_id, level, message) VALUES (?, 'info', ?)",
                    (document_id, "E2E ingestion shortcut started"),
                )
                for statement, row_key, row_label, period, value, confidence in _e2e_financial_rows():
                    await db.execute(
                        """
                        INSERT INTO financial_rows
                            (document_id, company_id, statement, row_key, row_label, period, value, confidence)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (document_id, company_id, statement, row_key, row_label, period, value, confidence),
                    )
                await db.execute(
                    """
                    UPDATE documents
                    SET extraction_status='done',
                        page_count=1,
                        has_ocr=0,
                        confidence_score=0.99,
                        narrative='E2E generated narrative with <script>escaped text</script>.',
                        reporting_standard='E2E',
                        updated_at=datetime('now')
                    WHERE id=?
                    """,
                    (document_id,),
                )
                await db.execute(
                    "INSERT INTO extraction_log (document_id, level, message) VALUES (?, 'info', ?)",
                    (document_id, "E2E ingestion shortcut completed"),
                )
                await db.commit()
                return

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
    """Export patterns as JSON for backup, review, or migration."""
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

    # Insert document record — handle re-upload of same filename gracefully
    try:
        async with db.execute("""
            INSERT INTO documents
                (company_id, filename, filepath, report_type, entity_type, fiscal_year_end, user_id)
            VALUES (?, ?, ?, 'compilation', 'sme', '', ?)
        """, (company_id, safe_name, str(dest), current_user["id"])) as cur:
            document_id = cur.lastrowid
        await db.commit()
    except sqlite3.IntegrityError:
        # Same file uploaded again — reset existing record and re-run ingestion
        await db.execute(
            "UPDATE documents SET extraction_status='pending' WHERE filepath=?",
            (str(dest),)
        )
        await db.commit()
        async with db.execute(
            "SELECT id FROM documents WHERE filepath=?", (str(dest),)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(500, "Failed to locate existing document record")
        document_id = row[0]

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


async def _read_report_payload(request: Request) -> tuple[int, str, dict]:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Request body must be valid JSON")

    company_id = body.get("company_id")
    report_type = body.get("report_type")
    intake_answers = body.get("intake_answers", {})

    if not isinstance(company_id, int) or company_id <= 0:
        raise HTTPException(400, "company_id must be a positive integer")
    if not report_type or report_type not in _VALID_REPORT_TYPES:
        raise HTTPException(
            400,
            f"report_type must be one of: {', '.join(sorted(_VALID_REPORT_TYPES))}"
        )
    if not isinstance(intake_answers, dict):
        raise HTTPException(400, "intake_answers must be a JSON object")

    return company_id, report_type, intake_answers


async def _ensure_user_company(
    db: aiosqlite.Connection,
    company_id: int,
    user_id: int,
) -> None:
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, user_id)
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")


async def _insert_report_job(
    db: aiosqlite.Connection,
    *,
    company_id: int,
    user_id: int,
    report_type: str,
    status: str,
    intake_answers: dict,
) -> int:
    async with db.execute("""
        INSERT INTO reports (company_id, user_id, report_type, status)
        VALUES (?, ?, ?, ?)
    """, (company_id, user_id, report_type, status)) as cur:
        report_id = cur.lastrowid

    await db.execute("""
        INSERT INTO report_intake (report_id, answers) VALUES (?, ?)
    """, (report_id, json.dumps(intake_answers)))
    return report_id


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

    Non-valuation report generation remains available for internal/advisor flows.
    Self-serve Valuation Advisory must use /wizard/report/checkout.
    """
    company_id, report_type, intake_answers = await _read_report_payload(request)
    if report_type == "valuation_advisory":
        raise HTTPException(409, "Valuation Advisory reports must be started through checkout.")

    # Verify the company belongs to this user
    await _ensure_user_company(db, company_id, current_user["id"])

    # Create report row (status = queued per D-04)
    report_id = await _insert_report_job(
        db,
        company_id=company_id,
        user_id=current_user["id"],
        report_type=report_type,
        status="queued",
        intake_answers=intake_answers,
    )
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


@app.post("/wizard/report/checkout", status_code=201)
async def wizard_report_checkout(
    request: Request,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a pending paid valuation and return a Stripe Checkout URL."""
    company_id, report_type, intake_answers = await _read_report_payload(request)
    if report_type != "valuation_advisory":
        raise HTTPException(400, "Checkout is currently only available for valuation_advisory.")

    await _ensure_user_company(db, company_id, current_user["id"])

    config = checkout_config()
    if not E2E_MODE and not stripe_enabled():
        raise HTTPException(503, "Stripe checkout is not configured.")

    report_id = await _insert_report_job(
        db,
        company_id=company_id,
        user_id=current_user["id"],
        report_type=report_type,
        status="pending_payment",
        intake_answers=intake_answers,
    )
    async with db.execute("""
        INSERT INTO purchases (report_id, user_id, amount_cents, currency, status)
        VALUES (?, ?, ?, ?, 'pending')
    """, (report_id, current_user["id"], config.price_cents, config.currency)) as cur:
        purchase_id = cur.lastrowid

    status = "pending_payment"
    checkout_url = None

    if E2E_MODE:
        await db.execute("""
            UPDATE purchases
            SET status='paid', paid_at=datetime('now')
            WHERE id=?
        """, (purchase_id,))
        await db.execute(
            "UPDATE reports SET status='queued' WHERE id=?",
            (report_id,),
        )
        status = "queued"
        background_tasks.add_task(
            _generate_report,
            report_id,
            company_id,
            current_user["id"],
            report_type,
            intake_answers,
        )
    else:
        session = create_checkout_session(
            report_id=report_id,
            purchase_id=purchase_id,
            user_email=current_user["email"],
            config=config,
        )
        await db.execute("""
            UPDATE purchases
            SET stripe_checkout_session_id=?
            WHERE id=?
        """, (session.session_id, purchase_id))
        checkout_url = session.url

    await db.commit()
    return {
        "report_id": report_id,
        "status": status,
        "checkout_url": checkout_url,
    }


@app.post("/payments/stripe/webhook")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    payload = await request.body()
    try:
        event = construct_webhook_event(
            payload,
            request.headers.get("stripe-signature"),
        )
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    except Exception:
        raise HTTPException(400, "Invalid Stripe webhook payload or signature")

    event_type = _object_get(event, "type")
    if event_type != "checkout.session.completed":
        return {"received": True, "ignored": True}

    session = _object_get(_object_get(event, "data") or {}, "object") or {}
    session_id = _object_get(session, "id")
    payment_intent_id = _object_get(session, "payment_intent")
    if not session_id:
        raise HTTPException(400, "Stripe checkout session id missing")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute("""
            SELECT
                p.id AS purchase_id,
                p.report_id,
                p.user_id,
                p.status AS purchase_status,
                r.company_id,
                r.report_type,
                r.status AS report_status,
                ri.answers
            FROM purchases p
            JOIN reports r ON r.id = p.report_id
            LEFT JOIN report_intake ri ON ri.report_id = r.id
            WHERE p.stripe_checkout_session_id=?
            ORDER BY ri.id DESC
            LIMIT 1
        """, (session_id,)) as cur:
            row = await cur.fetchone()

        if not row:
            raise HTTPException(404, "Purchase not found")

        await db.execute("""
            UPDATE purchases
            SET status='paid',
                stripe_payment_intent_id=?,
                paid_at=COALESCE(paid_at, datetime('now'))
            WHERE id=?
        """, (payment_intent_id, row["purchase_id"]))

        should_queue = row["report_status"] == "pending_payment"
        if should_queue:
            await db.execute(
                "UPDATE reports SET status='queued' WHERE id=?",
                (row["report_id"],),
            )
        await db.commit()

    if should_queue:
        intake_answers = json.loads(row["answers"]) if row["answers"] else {}
        background_tasks.add_task(
            _generate_report,
            row["report_id"],
            row["company_id"],
            row["user_id"],
            row["report_type"],
            intake_answers,
        )

    return {"received": True}


def _object_get(obj, key: str):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


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


@app.get("/wizard/company/{company_id}/profile-status")
async def wizard_profile_status(
    company_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Wizard-scoped profile status for user-owned companies."""
    async with db.execute(
        "SELECT sector, description FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"]),
    ) as cur:
        company = await cur.fetchone()
    if not company:
        raise HTTPException(404, "Company not found")

    sector_complete = bool(company["sector"])
    description_complete = len((company["description"] or "").strip()) >= 50

    async with db.execute(
        "SELECT COUNT(*) as n FROM management_team WHERE company_id=?",
        (company_id,),
    ) as cur:
        management_complete = (await cur.fetchone())["n"] > 0

    async with db.execute(
        "SELECT COUNT(*) as n FROM ebitda_adjustments WHERE company_id=?",
        (company_id,),
    ) as cur:
        ebitda_complete = (await cur.fetchone())["n"] > 0

    sections_complete = sum([sector_complete, description_complete, management_complete, ebitda_complete])
    return {
        "sections_complete": sections_complete,
        "total": 4,
        "sector_complete": sector_complete,
        "description_complete": description_complete,
        "management_complete": management_complete,
        "ebitda_complete": ebitda_complete,
        "can_generate": sector_complete and ebitda_complete,
    }


@app.get("/wizard/company/{company_id}/ebitda-adjustments")
async def wizard_get_ebitda_adjustments(
    company_id: int,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    """Wizard-scoped variant of GET /companies/{company_id}/ebitda-adjustments.

    Phase 3.5 placed the /companies/* routes behind Depends(require_admin);
    non-admin wizard users cannot use that endpoint. This route authorises via
    ownership instead of admin-only.

    Authorisation: caller must own the company OR be an admin. Otherwise 403.
    Response: list of {id, label, amount, rationale}, ordered by id ASC.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT user_id FROM companies WHERE id = ?",
            (company_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Company not found")
        owner_id = row["user_id"]
        is_admin = bool(current_user.get("is_admin"))
        if owner_id != current_user.get("id") and not is_admin:
            raise HTTPException(status_code=403, detail="Forbidden")

        async with db.execute(
            "SELECT id, label, amount, rationale FROM ebitda_adjustments "
            "WHERE company_id = ? ORDER BY id ASC",
            (company_id,),
        ) as cur:
            rows = await cur.fetchall()

    return [
        {
            "id": r["id"],
            "label": r["label"],
            "amount": r["amount"],
            "rationale": r["rationale"],
        }
        for r in rows
    ]


import html as _html_lib
import re as _re


def _narrative_to_html(text: str) -> str:
    """Convert lightly-markdown narrative text to safe HTML.

    Handles: ## subsection headings, - / * bullet lists, **bold**, paragraph grouping.
    All text is HTML-escaped before inline substitutions so no user content can inject tags.
    Public for testability.
    """
    lines = text.split("\n")
    chunks: list[str] = []
    bullet_buffer: list[str] = []

    def flush_bullets() -> None:
        if bullet_buffer:
            items = "".join(f"<li>{item}</li>" for item in bullet_buffer)
            chunks.append(f"<ul>{items}</ul>")
            bullet_buffer.clear()

    def apply_inline(s: str) -> str:
        # **bold** → <strong>bold</strong>; applied on already-escaped text so ** is safe
        return _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_bullets()
            continue

        if stripped.startswith("## "):
            flush_bullets()
            heading_text = apply_inline(_html_lib.escape(stripped[3:].strip()))
            chunks.append(f"<h3>{heading_text}</h3>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            item_text = apply_inline(_html_lib.escape(stripped[2:].strip()))
            bullet_buffer.append(item_text)
        else:
            flush_bullets()
            para_text = apply_inline(_html_lib.escape(stripped))
            chunks.append(f"<p>{para_text}</p>")

    flush_bullets()
    return "".join(chunks)


def _render_report_sections_html(sections: dict, section_order: list) -> str:
    """Render report sections as HTML, handling both plain-string and dict (narrative+table) sections.

    Public for testability — used by wizard_report_view.
    """
    section_html = ""
    for key in section_order:
        content = sections.get(key, "")
        heading = key.replace("_", " ").title()

        if isinstance(content, dict):
            narrative = str(content.get("narrative", "") or "")
            table_data = content.get("table") if isinstance(content.get("table"), dict) else None
        else:
            narrative = str(content) if content is not None else ""
            table_data = None

        paragraphs = _narrative_to_html(narrative)

        table_html = ""
        if table_data:
            headers = table_data.get("headers", []) or []
            rows = table_data.get("rows", []) or []
            if isinstance(headers, list) and isinstance(rows, list):
                th_cells = "".join(
                    f"<th>{_html_lib.escape(str(h))}</th>" for h in headers
                )
                tr_rows = "".join(
                    "<tr>" + "".join(f"<td>{_html_lib.escape(str(c))}</td>" for c in row) + "</tr>"
                    for row in rows if isinstance(row, list)
                )
                if th_cells or tr_rows:
                    table_html = (
                        f"<table class='report-table'>"
                        f"<thead><tr>{th_cells}</tr></thead>"
                        f"<tbody>{tr_rows}</tbody>"
                        f"</table>"
                    )

        section_class = " class='disclaimer'" if key == "disclaimer" else ""
        section_html += f"""
        <section{section_class}>
            <h2>{_html_lib.escape(heading)}</h2>
            {paragraphs}
            {table_html}
        </section>"""

    return section_html


@app.get("/wizard/report/{report_id}/view", response_class=HTMLResponse)
async def wizard_report_view(
    report_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Render a completed report as readable HTML (temporary viewer until Phase 7)."""
    async with db.execute("""
        SELECT r.id, r.report_type, r.status, r.content, r.completed_at,
               c.name
        FROM reports r
        JOIN companies c ON c.id = r.company_id
        WHERE r.id=? AND r.user_id=?
    """, (report_id, current_user["id"])) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Report not found")
    if row["status"] != "done":
        raise HTTPException(400, f"Report is not ready yet (status: {row['status']})")

    import json as _json
    try:
        sections = _json.loads(row["content"])
    except Exception:
        raise HTTPException(500, "Report content could not be parsed")

    section_order = SECTION_SCHEMAS.get(row["report_type"], list(sections.keys()))
    label = row["report_type"].replace("_", " ").title()
    back_url = f"{os.getenv('APP_BASE_URL', 'http://localhost:3000').rstrip('/')}/wizard"

    section_html = _render_report_sections_html(sections, section_order)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_html_lib.escape(label)} — {_html_lib.escape(row['name'])}</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 820px; margin: 40px auto; padding: 0 24px;
          color: #1a1a2e; line-height: 1.7; }}
  header {{ border-bottom: 2px solid #1a1a2e; padding-bottom: 16px; margin-bottom: 32px; }}
  header h1 {{ font-size: 1.6rem; margin: 0 0 4px; }}
  header p {{ margin: 0; color: #555; font-size: .9rem; }}
  section {{ margin-bottom: 2.5rem; }}
  h2 {{ font-size: 1.1rem; font-weight: 700; border-left: 4px solid #2563eb;
        padding-left: 12px; margin-bottom: 12px; color: #1a1a2e; }}
  h3 {{ font-size: 1rem; font-weight: 600; margin: 1.2rem 0 .4rem; color: #1a1a2e; }}
  p {{ margin: 0 0 .9rem; font-size: .95rem; }}
  ul {{ margin: .2rem 0 .9rem 1.4rem; padding: 0; }}
  li {{ font-size: .95rem; margin-bottom: .3rem; line-height: 1.6; }}
  .disclaimer {{ background: #fff8e1; border: 1px solid #f59e0b; border-radius: 6px;
                 padding: 12px 16px; }}
  .disclaimer p {{ font-size: .85rem; line-height: 1.6; color: #92400e; }}
  .disclaimer li {{ font-size: .85rem; color: #92400e; }}
  .back {{ display:inline-block; margin-bottom:24px; font-size:.875rem;
           color:#2563eb; text-decoration:none; font-family:sans-serif; }}
  .meta {{ font-family:sans-serif; font-size:.8rem; color:#777; margin-top:4px; }}
  table.report-table {{ width: 100%; border-collapse: collapse; margin: 12px 0 24px; font-size: .9rem; overflow-x: auto; display: block; }}
  table.report-table th, table.report-table td {{ padding: 8px 12px; border-bottom: 1px solid #e2e8f0; text-align: left; white-space: nowrap; }}
  table.report-table thead th {{ background: #f0f4f8; font-weight: 600; }}
  table.report-table tbody tr:nth-child(even) {{ background: #fafbfc; }}
  table.report-table td:not(:first-child) {{ text-align: right; }}
</style>
</head>
<body>
<a class="back" href="{_html_lib.escape(back_url, quote=True)}">&#x2190; Back</a>
<header>
  <h1>{_html_lib.escape(label)}</h1>
  <p>{_html_lib.escape(row['name'])}</p>
  <p class="meta">Report #{row['id']} &nbsp;·&nbsp; Generated {row['completed_at']}</p>
</header>
{section_html}
</body>
</html>"""
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Report generation background task (Phase 5)
# ---------------------------------------------------------------------------

# REPORT_SECTIONS is kept for backward compatibility but SECTION_SCHEMAS
# (from report_prompts) is the canonical source used by generate_report and Phase 7.
# Both use the same full report-type keys (e.g. 'valuation_advisory').
REPORT_SECTIONS = SECTION_SCHEMAS  # alias — do not remove


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

    Uses build_prompt() from report_prompts and SECTION_SCHEMAS for validation.
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
            print(f"[REPORT] Generating report_id={report_id} type={report_type}")

            if E2E_MODE:
                await asyncio.sleep(0.05)
                content_json = _e2e_report_content(report_type)
                await db.execute(
                    """
                    UPDATE reports
                    SET status='done', content=?, completed_at=datetime('now')
                    WHERE id=?
                    """,
                    (json.dumps(content_json), report_id),
                )
                await db.commit()
                print(f"[REPORT] E2E report_id={report_id} done ({report_type})")
                return

            # --- 1. Load company profile ---
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

            # --- 2. Management team ---
            async with db.execute("""
                SELECT name, title, bio FROM management_team
                WHERE company_id=? ORDER BY id ASC
            """, (company_id,)) as cur:
                mgmt_team = [dict(r) for r in await cur.fetchall()]

            # --- 3. EBITDA adjustments (add-backs from Phase 3) ---
            async with db.execute("""
                SELECT label, amount, rationale FROM ebitda_adjustments
                WHERE company_id=? ORDER BY id ASC
            """, (company_id,)) as cur:
                ebitda_adjustments = [dict(r) for r in await cur.fetchall()]

            # --- 4. Financial rows — all periods for all statement types ---
            async with db.execute("""
                SELECT statement, row_key, row_label, period, value
                FROM financial_rows
                WHERE company_id=?
                ORDER BY statement, row_key, period DESC
            """, (company_id,)) as cur:
                raw_fin_rows = [dict(r) for r in await cur.fetchall()]

            # Transform flat (statement, row_key, period, value) rows into the
            # grouped format expected by build_prompt(): each row has
            # {canonical_key, statement, values: {period: value}}
            from collections import defaultdict as _dd
            _grouped: dict[str, dict[str, dict]] = _dd(lambda: _dd(dict))
            for r in raw_fin_rows:
                stmt = r["statement"]
                key = r["row_key"]
                period = r["period"]
                value = r["value"]
                if value is not None:
                    _grouped[stmt][key][period] = value

            financial_rows_for_prompt: list[dict] = []
            for stmt, keys_map in _grouped.items():
                for key, vals in keys_map.items():
                    financial_rows_for_prompt.append({
                        "canonical_key": key,
                        "statement": stmt,
                        "values": vals,
                    })

            # --- 5. Run Python algorithm for Valuation Advisory (D-08) ---
            valuation_result = None
            bank_credit_figs = None

            if report_type == "valuation_advisory":
                # 5a. Update status so the wizard can show 'researching' in real time
                await db.execute(
                    "UPDATE reports SET status='researching' WHERE id=?", (report_id,)
                )
                await db.commit()

                # 5b. Run agentic web research loop (Plan 02)
                company_location = (intake_answers.get("company_location") or "New Zealand") if isinstance(intake_answers, dict) else "New Zealand"
                industry_sector_for_research = company_sector or "General SME"
                brief = await run_valuation_research(
                    company_name=company_name,
                    company_location=company_location,
                    industry_sector=industry_sector_for_research,
                )

                # 5c. Compute WACC scenarios (percent), then 3x DCF (decimal), then illiquidity discount
                wacc_pct = compute_wacc_scenarios(
                    risk_free_rate=brief.risk_free_rate,
                    industry_beta=brief.industry_beta,
                    erp=brief.erp,
                )

                # Extract financial inputs from raw_fin_rows
                pnl_by_key: dict = {}
                bs_by_key: dict = {}
                for r in raw_fin_rows:
                    key = r.get("row_key", "")
                    period = r.get("period", "")
                    value = r.get("value")
                    if value is None:
                        continue
                    if r.get("statement") == "pnl":
                        pnl_by_key.setdefault(key, []).append((period, float(value)))
                    elif r.get("statement") == "bs":
                        bs_by_key.setdefault(key, []).append((period, float(value)))

                def _latest_value(rows_by_key: dict, key: str) -> float:
                    entries = rows_by_key.get(key, [])
                    if not entries:
                        return 0.0
                    return sorted(entries, key=lambda x: x[0], reverse=True)[0][1]

                extracted_ebitda = _latest_value(pnl_by_key, "ebitda")
                if extracted_ebitda == 0.0:
                    net_p = _latest_value(pnl_by_key, "net_profit")
                    da = _latest_value(pnl_by_key, "depreciation_amortisation") or _latest_value(pnl_by_key, "depreciation")
                    extracted_ebitda = net_p + abs(da)

                revenues_val = _latest_value(pnl_by_key, "revenue")
                net_profit_latest = _latest_value(pnl_by_key, "net_profit")
                cash_val = abs(
                    _latest_value(bs_by_key, "cash_and_equivalents") or
                    _latest_value(bs_by_key, "cash_and_bank") or
                    _latest_value(bs_by_key, "cash")
                )

                # Use new intake normalisations array as authoritative add-back source;
                # fall back to Phase 3 ebitda_adjustments if not provided.
                intake_norms = intake_answers.get("normalisations") if isinstance(intake_answers, dict) else None
                if isinstance(intake_norms, list) and len(intake_norms) > 0:
                    addbacks_total = sum(float(n.get("amount", 0) or 0) for n in intake_norms)
                else:
                    addbacks_total = sum(float(a.get("amount", 0) or 0) for a in ebitda_adjustments)
                normalised_ebitda = extracted_ebitda + addbacks_total

                forecast_years = int(intake_answers.get("forecast_horizon", 5)) if isinstance(intake_answers, dict) else 5
                revenue_growth_pct = float(intake_answers.get("revenue_growth_cagr", 5.0) or 5.0) if isinstance(intake_answers, dict) else 5.0
                terminal_growth_pct = float(intake_answers.get("terminal_growth_rate", 2.5) or 2.5) if isinstance(intake_answers, dict) else 2.5
                tax_rate = 0.28  # NZ corporate tax rate

                loop = asyncio.get_running_loop()

                def _run_dcf_for_scenario(wacc_percent: float) -> dict:
                    return compute_dcf(
                        ebitda=normalised_ebitda,
                        wacc=wacc_percent / 100.0,
                        growth_rate=revenue_growth_pct / 100.0,
                        tax_rate=tax_rate,
                        years=forecast_years,
                        terminal_growth=terminal_growth_pct / 100.0,
                    )

                dcf_high = await loop.run_in_executor(None, _run_dcf_for_scenario, wacc_pct["high"])
                dcf_mid  = await loop.run_in_executor(None, _run_dcf_for_scenario, wacc_pct["mid"])
                dcf_low  = await loop.run_in_executor(None, _run_dcf_for_scenario, wacc_pct["low"])

                def _ev_from_dcf(d: dict) -> float:
                    return float(d.get("enterprise_value_dcf") or d.get("enterprise_value") or d.get("ev") or 0.0)

                ev_mid = _ev_from_dcf(dcf_mid)
                illiq_rate = await loop.run_in_executor(
                    None,
                    compute_illiquidity_discount,
                    revenues_val,
                    (net_profit_latest > 0),
                    cash_val,
                    ev_mid,
                )
                ev_adjusted = {
                    "high": _ev_from_dcf(dcf_high) * (1.0 - illiq_rate),
                    "mid":  ev_mid * (1.0 - illiq_rate),
                    "low":  _ev_from_dcf(dcf_low) * (1.0 - illiq_rate),
                }

                # Comparable multiples method — risk-score positions within market range
                risk_answers = {k: v for k, v in (intake_answers or {}).items()
                                if k.startswith("rq_")}
                risk_score = compute_risk_score(risk_answers)
                multiples_result = compute_multiples_ev(
                    normalised_ebitda=normalised_ebitda,
                    risk_score=risk_score,
                    ev_ebitda_low=brief.ev_ebitda_low,
                    ev_ebitda_high=brief.ev_ebitda_high,
                )

                valuation_result = {
                    "research_brief": brief.model_dump(),
                    "wacc_scenarios_pct": wacc_pct,
                    "dcf_scenarios": {"high": dcf_high, "mid": dcf_mid, "low": dcf_low},
                    "illiquidity_discount": {"rate": illiq_rate, "ev_adjusted": ev_adjusted},
                    "normalised_ebitda": normalised_ebitda,
                    "revenues": revenues_val,
                    "net_debt": 0.0,
                    "cash": cash_val,
                    "multiples_result": multiples_result,
                }
            elif report_type == "bank_credit_paper":
                bank_credit_figs = compute_bank_credit_figures(
                    financial_rows_for_prompt, intake_answers
                )

            # --- 6. Build Claude prompt via report_prompts.build_prompt() ---
            system_prompt, user_message = build_prompt(
                report_type=report_type,
                company_name=company_name,
                industry=company_sector,
                description=company_description,
                financial_rows=financial_rows_for_prompt,
                intake_answers=intake_answers,
                management_team=mgmt_team,
                ebitda_adjustments=ebitda_adjustments,
                valuation_result=valuation_result,
                bank_credit_figures=bank_credit_figs,
            )

            # --- 7. Call Claude API (non-tool-use, plain JSON response) ---
            content_json = await _call_claude_for_report(
                system_prompt, user_message,
                sections=SECTION_SCHEMAS[report_type],
            )

            # --- 8. Validate JSON: all expected sections must be present ---
            expected_sections = SECTION_SCHEMAS[report_type]
            missing = [s for s in expected_sections if s not in content_json]
            if missing:
                raise ValueError(
                    f"Claude response missing required sections: {missing}. "
                    "Report marked failed — please retry."
                )

            # --- 8b. FMCA disclaimer compliance gate (REPT-06 + AI-SPEC guardrail) ---
            if report_type == "valuation_advisory":
                disclaimer_section = content_json.get("disclaimer", "")
                if isinstance(disclaimer_section, dict):
                    disclaimer_text = str(disclaimer_section.get("narrative", ""))
                else:
                    disclaimer_text = str(disclaimer_section)
                lowered = disclaimer_text.lower()
                required_phrases = [
                    ("indicative", ("indicative",)),
                    ("financial advice", ("financial advice",)),
                    ("FMCA or FMCA name", ("fmca", "financial markets conduct")),
                    ("not relied", ("not relied", "should not be relied")),
                ]
                missing_phrases = []
                for label, needles in required_phrases:
                    if not any(n in lowered for n in needles):
                        missing_phrases.append(label)
                if missing_phrases:
                    err = f"Disclaimer compliance check failed — missing required phrases: {missing_phrases}"
                    print(f"[REPORT ERROR] report_id={report_id} disclaimer_incomplete: {missing_phrases}")
                    await db.execute(
                        "UPDATE reports SET status='failed', error_message=? WHERE id=?",
                        (err, report_id),
                    )
                    await db.commit()
                    return

            # --- 9. Mark done, store content ---
            await db.execute("""
                UPDATE reports
                SET status='done', content=?, completed_at=datetime('now')
                WHERE id=?
            """, (json.dumps(content_json), report_id))
            await db.commit()
            print(f"[REPORT] report_id={report_id} done ({report_type})")

            # --- 10. Load user email and send notification ---
            async with db.execute(
                "SELECT email FROM users WHERE id=?", (user_id,)
            ) as cur:
                user_row = await cur.fetchone()
            if user_row:
                user_email_addr = user_row["email"]
                user_name = user_email_addr.split("@")[0]
                await send_report_ready_email(
                    user_email_addr, user_name, report_type, report_id
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
    return {
        "name": "AccountIQ API",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
        "ui": "Run the Next.js app from web/ at http://localhost:3000",
        "legacy_ui": "/app when ACCOUNTIQ_SERVE_LEGACY_FRONTEND=true",
    }
