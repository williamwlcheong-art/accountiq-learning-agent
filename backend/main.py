"""
AccountIQ Learning Agent — FastAPI backend
Run with: uvicorn main:app --reload --port 8765
"""
import os
import json
import shutil
import asyncio
import hashlib
import uuid
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, HTMLResponse, FileResponse
import aiosqlite

# Load .env from project root (one level up from backend/)
from dotenv import load_dotenv, set_key
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH, override=False)

from db import init_db, get_db, get_pattern_library, DB_PATH
from financial_authority import (
    AuthorityConflictError,
    authoritative_financial_rows,
    claim_document_retry,
    complete_document_authority,
    promote_document_authority,
)
from ingestion import ingest_document
from auth import auth_router, get_current_user, require_admin
from payments import (
    checkout_config,
    construct_webhook_event,
    create_checkout_session,
    stripe_enabled,
)
from report_email import send_report_ready_email, REPORT_TYPE_LABELS
from report_rendering import render_report_html, report_pdf_path, write_pdf
from report_snapshots import (
    LegacySnapshotRestartRequired,
    SnapshotIntegrityError,
    build_report_input_snapshot_candidate,
    create_report_input_snapshot,
    load_report_input_snapshot,
    persist_report_input_snapshot,
    snapshot_requires_restart,
)
from report_validation import validate_generated_report
from report_prompts import (
    build_prompt,
    SECTION_SCHEMAS,
    TABLE_SECTIONS_VALUATION,
    compute_bank_credit_figures,
)
from research_loop import run_valuation_research
from fcff_engine import calculate_fcff, report_prompt_payload
from valuation import compute_multiples_crosscheck
from valuation_inputs import (
    ValuationInputError,
    build_valuation_inputs,
    derive_fcff_assumption_readiness,
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
        ("pnl", "depreciation", "Depreciation and amortisation", "2025", -35_000.0, 0.98),
        ("pnl", "net_profit", "Net Profit", "2025", 150_000.0, 0.97),
        ("bs", "cash_and_bank", "Cash & bank", "2025", 95_000.0, 0.98),
        ("bs", "trade_debtors", "Trade debtors", "2025", 180_000.0, 0.98),
        ("bs", "inventory", "Inventory", "2025", 85_000.0, 0.98),
        ("bs", "trade_creditors", "Trade creditors", "2025", 110_000.0, 0.98),
        ("bs", "short_term_debt", "Bank overdraft", "2025", 0.0, 0.98),
        ("bs", "long_term_debt", "Bank loan", "2025", 120_000.0, 0.98),
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
        elif section in TABLE_SECTIONS_VALUATION or section.endswith("summary"):
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

    # EBITDA bridge: most recent authoritative period with profit and depreciation rows
    reported_ebitda = None
    authoritative_rows = await authoritative_financial_rows(db, company_id, "pnl")
    bridge_rows = [
        row for row in authoritative_rows
        if row["row_key"] in {
            "net_profit", "depreciation_amortisation", "depreciation"
        }
    ]
    has_financials = bool(bridge_rows)
    max_period = max((row["period"] for row in bridge_rows), default=None)
    if max_period:
        fin_rows = {
            row["row_key"]: row["value"]
            for row in bridge_rows
            if row["period"] == max_period
        }
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


def _revision_path(company_dir: Path, original_name: str) -> Path:
    """Build a non-reusable path while retaining the safe original filename."""
    safe_name = Path(original_name).name
    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix
    return company_dir / f"{stem}-{uuid.uuid4().hex}{suffix}"


async def _previous_revision(db, company_id: int, filename: str):
    async with db.execute(
        """
        SELECT id FROM documents
        WHERE company_id=? AND filename=?
        ORDER BY id DESC LIMIT 1
        """,
        (company_id, filename),
    ) as cur:
        return await cur.fetchone()


def _write_upload_revision(file, destination: Path) -> str:
    digest = hashlib.sha256()
    with open(destination, "xb") as output:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
            output.write(chunk)
    return digest.hexdigest()


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
            tmp_path = _revision_path(tmp_dir, file.filename)
            contents = await file.read()
            with open(tmp_path, "xb") as f:
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
    previous = await _previous_revision(db, company_id, safe_name)
    dest = _revision_path(company_dir, safe_name)

    if "tmp_path" in locals() and tmp_path.exists():
        shutil.move(str(tmp_path), str(dest))
        file_hash = hashlib.sha256(contents).hexdigest()
    else:
        file_hash = _write_upload_revision(file.file, dest)

    async with db.execute("""
        INSERT INTO documents
            (company_id, filename, filepath, report_type, entity_type,
             fiscal_year_end, user_id, file_hash, supersedes_document_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (company_id, safe_name, str(dest),
          report_type, entity_type, fiscal_year_end, current_user["id"],
          file_hash, previous["id"] if previous else None)) as cur:
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
                    SET page_count=1,
                        has_ocr=0,
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
                try:
                    await complete_document_authority(db, document_id, 0.99)
                except AuthorityConflictError as authority_error:
                    await db.execute("BEGIN IMMEDIATE")
                    try:
                        await db.execute(
                            """
                            UPDATE documents SET extraction_status='done',
                                extraction_completed_at=datetime('now'),
                                confidence_score=0.99, updated_at=datetime('now')
                            WHERE id=? AND extraction_status='processing'
                            """,
                            (document_id,),
                        )
                        await db.execute(
                            "INSERT INTO extraction_log (document_id, level, message) VALUES (?, 'warn', ?)",
                            (document_id, f"Authority conflict: {authority_error.conflicts}"),
                        )
                        await db.commit()
                    except Exception:
                        await db.rollback()
                        raise
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


@app.get("/wizard/company/{company_id}/fcff-assumptions")
async def wizard_fcff_assumption_readiness(
    company_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _ensure_user_company(db, company_id, current_user["id"])
    rows = await authoritative_financial_rows(db, company_id)
    if not rows:
        return {
            "state": "needs_adviser_assistance",
            "message": "We need an adviser to confirm the investment assumptions from your statements.",
            "depreciation": {"rate": None, "status": "missing", "source_period": None, "provenance": None},
            "operating_nwc": {"rate": None, "status": "missing", "source_period": None, "provenance": None},
        }
    try:
        derived = derive_fcff_assumption_readiness(rows)
    except ValuationInputError:
        derived = {"depreciation": None, "operating_nwc": None}

    def result(name: str) -> dict:
        item = derived[name]
        if item is None:
            return {
                "rate": None,
                "status": "missing",
                "source_period": None,
                "provenance": None,
            }
        return {
            "rate": float(item["rate"]),
            "status": "available",
            "source_period": item["source_period"],
            "provenance": item["provenance"],
        }

    depreciation_result = result("depreciation")
    nwc_result = result("operating_nwc")
    state = "ready" if depreciation_result["status"] == "available" and nwc_result["status"] == "available" else "needs_adviser_assistance"
    message = (
        "Safe same-period ratios are available for confirmation."
        if state == "ready"
        else "We need an adviser to confirm the investment assumptions from your statements."
    )
    return {
        "state": state,
        "message": message,
        "depreciation": depreciation_result,
        "operating_nwc": nwc_result,
    }


# ---------------------------------------------------------------------------
# Approved WACC assumption sets
# ---------------------------------------------------------------------------

_WACC_DECIMAL_FIELDS = (
    "risk_free_rate",
    "equity_risk_premium",
    "beta",
    "cost_of_debt",
    "target_debt_weight",
    "target_equity_weight",
)
_WACC_OPTIONAL_DECIMAL_FIELDS = ("additional_premium", "scenario_spread")


def _wacc_decimal(body: dict, field: str, *, optional: bool = False) -> Decimal | None:
    value = body.get(field)
    if optional and value is None:
        return None
    if value is None or isinstance(value, bool):
        raise HTTPException(400, f"{field} must be a valid number.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(400, f"{field} must be a valid number.")
    if not result.is_finite() or result < 0:
        raise HTTPException(400, f"{field} must be a non-negative finite number.")
    return result


def _validate_wacc_payload(body: dict) -> dict:
    required_text = {
        "name": "WACC assumption-set name is required.",
        "beta_type": "WACC beta type is required.",
        "source_references": "WACC source references are required.",
        "publisher": "WACC publisher is required.",
        "rationale": "WACC rationale is required.",
    }
    cleaned = {}
    for field, message in required_text.items():
        value = str(body.get(field) or "").strip()
        if not value:
            raise HTTPException(400, message)
        cleaned[field] = value
    as_of_date = str(body.get("as_of_date") or "").strip()
    try:
        date.fromisoformat(as_of_date)
    except ValueError:
        raise HTTPException(400, "WACC as-of date must be a valid ISO date.")
    cleaned["as_of_date"] = as_of_date
    for field in _WACC_DECIMAL_FIELDS:
        cleaned[field] = _wacc_decimal(body, field)
    for field in _WACC_OPTIONAL_DECIMAL_FIELDS:
        cleaned[field] = _wacc_decimal(body, field, optional=True)
    if cleaned["target_debt_weight"] + cleaned["target_equity_weight"] != Decimal("100"):
        raise HTTPException(400, "Target debt and equity weights must total 100%.")
    return cleaned


def _serialise_wacc_set(row) -> dict:
    item = dict(row)
    for field in _WACC_DECIMAL_FIELDS + _WACC_OPTIONAL_DECIMAL_FIELDS:
        item[field] = float(item[field]) if item[field] is not None else None
    item["active"] = bool(item["active"])
    item["approved_by"] = item.pop("approved_by") if "approved_by" in item else None
    item.pop("approved_by_user_id", None)
    return item


async def _get_wacc_set(db, assumption_set_id: int):
    async with db.execute(
        """
        SELECT ws.*, u.email AS approved_by
        FROM wacc_assumption_sets ws
        LEFT JOIN users u ON u.id=ws.approved_by_user_id
        WHERE ws.id=?
        """,
        (assumption_set_id,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "WACC assumption set not found")
    return row


@app.get("/admin/wacc-assumption-sets")
async def list_wacc_assumption_sets(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    async with db.execute(
        """
        SELECT ws.*, u.email AS approved_by
        FROM wacc_assumption_sets ws
        LEFT JOIN users u ON u.id=ws.approved_by_user_id
        ORDER BY ws.name, ws.version DESC
        """
    ) as cur:
        rows = await cur.fetchall()
    return [_serialise_wacc_set(row) for row in rows]


@app.post("/admin/wacc-assumption-sets", status_code=201)
async def create_wacc_assumption_set(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    values = _validate_wacc_payload(await request.json())
    await db.execute("BEGIN IMMEDIATE")
    try:
        async with db.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM wacc_assumption_sets WHERE name=?",
            (values["name"],),
        ) as cur:
            version = (await cur.fetchone())[0]
        fields = [
            "name", "version", *_WACC_DECIMAL_FIELDS[:3], "beta_type",
            *_WACC_DECIMAL_FIELDS[3:], *_WACC_OPTIONAL_DECIMAL_FIELDS,
            "source_references", "publisher", "as_of_date", "rationale",
        ]
        params = [values["name"], version] + [values.get(field) for field in fields[2:]]
        async with db.execute(
            f"INSERT INTO wacc_assumption_sets ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
            [str(value) if isinstance(value, Decimal) else value for value in params],
        ) as cur:
            assumption_set_id = cur.lastrowid
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _serialise_wacc_set(await _get_wacc_set(db, assumption_set_id))


@app.put("/admin/wacc-assumption-sets/{assumption_set_id}")
async def update_wacc_assumption_set(
    assumption_set_id: int,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    values = _validate_wacc_payload(await request.json())
    fields = [
        "name", *_WACC_DECIMAL_FIELDS[:3], "beta_type",
        *_WACC_DECIMAL_FIELDS[3:], *_WACC_OPTIONAL_DECIMAL_FIELDS,
        "source_references", "publisher", "as_of_date", "rationale",
    ]
    params = [
        str(values.get(field)) if isinstance(values.get(field), Decimal) else values.get(field)
        for field in fields
    ]
    await db.execute("BEGIN IMMEDIATE")
    try:
        async with db.execute(
            f"UPDATE wacc_assumption_sets SET {', '.join(f'{field}=?' for field in fields)} WHERE id=? AND status='draft'",
            [*params, assumption_set_id],
        ) as cur:
            updated = cur.rowcount
        if updated != 1:
            async with db.execute(
                "SELECT status FROM wacc_assumption_sets WHERE id=?",
                (assumption_set_id,),
            ) as cur:
                row = await cur.fetchone()
            await db.rollback()
            if not row:
                raise HTTPException(404, "WACC assumption set not found")
            raise HTTPException(
                409,
                "Approved WACC assumption sets are immutable. Create a new version instead.",
            )
        await db.commit()
    except Exception:
        if db.in_transaction:
            await db.rollback()
        raise
    return _serialise_wacc_set(await _get_wacc_set(db, assumption_set_id))


@app.post("/admin/wacc-assumption-sets/{assumption_set_id}/approve")
async def approve_wacc_assumption_set(
    assumption_set_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    await db.execute("BEGIN IMMEDIATE")
    try:
        async with db.execute(
            """
            UPDATE wacc_assumption_sets
            SET status='approved', approved_at=datetime('now'),
                approved_by_user_id=?
            WHERE id=? AND status='draft'
            """,
            (current_user["id"], assumption_set_id),
        ) as cur:
            approved = cur.rowcount
        if approved != 1:
            async with db.execute(
                "SELECT status FROM wacc_assumption_sets WHERE id=?",
                (assumption_set_id,),
            ) as cur:
                row = await cur.fetchone()
            await db.rollback()
            if not row:
                raise HTTPException(404, "WACC assumption set not found")
            raise HTTPException(409, "Only a draft WACC assumption set can be approved.")
        await db.commit()
    except Exception:
        if db.in_transaction:
            await db.rollback()
        raise
    return _serialise_wacc_set(await _get_wacc_set(db, assumption_set_id))


@app.post("/admin/wacc-assumption-sets/{assumption_set_id}/activate")
async def activate_wacc_assumption_set(
    assumption_set_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    await db.execute("BEGIN IMMEDIATE")
    try:
        await db.execute("UPDATE wacc_assumption_sets SET active=0 WHERE active=1")
        async with db.execute(
            "UPDATE wacc_assumption_sets SET active=1 WHERE id=? AND status='approved'",
            (assumption_set_id,),
        ) as cur:
            activated = cur.rowcount
        if activated != 1:
            await db.rollback()
            raise HTTPException(409, "Only an approved WACC assumption set can be activated.")
        await db.commit()
    except Exception:
        if db.in_transaction:
            await db.rollback()
        raise
    return _serialise_wacc_set(await _get_wacc_set(db, assumption_set_id))


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
    """Return authoritative financial rows for a company."""
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"]),
    ) as cur:
        if not await cur.fetchone():
            return []
    rows = await authoritative_financial_rows(db, company_id, statement)
    return [
        {
            **row,
            "source_count": 1,
        }
        for row in rows
    ]


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

    if doc["extraction_status"] not in {"pending", "failed"}:
        raise HTTPException(409, "Only pending or failed documents can be retried")
    async with db.execute(
        "SELECT 1 FROM document_authority WHERE document_id=? LIMIT 1",
        (document_id,),
    ) as cur:
        if await cur.fetchone():
            raise HTTPException(409, "Authoritative document revisions cannot be retried in place")

    if not await claim_document_retry(db, document_id, current_user["id"]):
        raise HTTPException(409, "Document retry was already claimed or is no longer eligible")

    # Clear partial data only after this request has atomically claimed the retry.
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

    # Save an immutable file revision; the original safe name remains metadata.
    company_dir = PDF_DIR / str(company_id)
    company_dir.mkdir(exist_ok=True)
    safe_name = Path(file.filename).name
    previous = await _previous_revision(db, company_id, safe_name)
    dest = _revision_path(company_dir, safe_name)
    file_hash = _write_upload_revision(file.file, dest)

    async with db.execute("""
        INSERT INTO documents
            (company_id, filename, filepath, report_type, entity_type,
             fiscal_year_end, user_id, file_hash, supersedes_document_id)
        VALUES (?, ?, ?, 'compilation', 'sme', '', ?, ?, ?)
    """, (
        company_id,
        safe_name,
        str(dest),
        current_user["id"],
        file_hash,
        previous["id"] if previous else None,
    )) as cur:
        document_id = cur.lastrowid
    await db.commit()

    # Kick off background ingestion — same task as admin upload (D-06)
    background_tasks.add_task(
        _run_ingestion, document_id, company_id, str(dest), "sme", "Private", ""
    )

    return {"company_id": company_id, "document_id": document_id, "status": "processing"}


async def _wizard_readiness(
    db: aiosqlite.Connection,
    company_id: int,
    document_id: int | None,
    user_id: int,
) -> dict:
    document_filter = "d.id=? AND" if document_id is not None else ""
    params = (
        (document_id, company_id, user_id, user_id)
        if document_id is not None
        else (company_id, user_id, user_id)
    )
    async with db.execute(
        f"""
        SELECT d.id, d.filename, d.extraction_status
        FROM documents d
        JOIN companies c ON c.id=d.company_id
        WHERE {document_filter} d.company_id=? AND d.user_id=? AND c.user_id=?
        ORDER BY d.id DESC
        LIMIT 1
        """,
        params,
    ) as cur:
        document = await cur.fetchone()
    if not document:
        raise HTTPException(404, "Company or document not found")

    status = document["extraction_status"]
    state = "processing"
    code = "extraction_processing"
    message = "We are extracting and checking your financial statements."
    if status == "failed":
        state = "failed"
        code = "extraction_failed"
        message = "We could not extract this document. Upload a clearer financial statement to continue."
    elif status == "done":
        try:
            rows = await authoritative_financial_rows(db, company_id)
            if rows and any(row["document_id"] == document["id"] for row in rows):
                state = "ready"
                code = "ready"
                message = "Your financial statements are ready for valuation intake."
            elif rows:
                state = "failed"
                code = "document_not_selected"
                message = "This upload did not contribute usable authoritative financial rows."
            else:
                state = "failed"
                code = "no_financial_rows"
                message = "No usable financial rows were found in this document."
        except AuthorityConflictError:
            state = "conflict"
            code = "authority_conflict"
            message = "More than one source covers the same statement period. An adviser must resolve the source before checkout."

    async with db.execute(
        """
        SELECT da.statement, da.period, da.document_id, d.filename
        FROM document_authority da
        JOIN documents d ON d.id=da.document_id AND d.extraction_status='done'
        WHERE da.company_id=?
        ORDER BY da.period DESC, da.statement, da.document_id
        """,
        (company_id,),
    ) as cur:
        source_periods = [dict(row) for row in await cur.fetchall()]
    async with db.execute(
        """
        SELECT c.name, c.sector, c.description, c.country, c.exchange,
               (SELECT COUNT(*) FROM management_team mt WHERE mt.company_id=c.id)
                   AS management_team_count,
               (SELECT COUNT(*) FROM ebitda_adjustments ea WHERE ea.company_id=c.id)
                   AS ebitda_adjustment_count
        FROM companies c
        WHERE c.id=? AND c.user_id=?
        """,
        (company_id, user_id),
    ) as cur:
        profile = dict(await cur.fetchone())
    config = checkout_config()
    return {
        "state": state,
        "code": code,
        "message": message,
        "document": dict(document),
        "source_periods": source_periods,
        "profile": profile,
        "checkout": {
            "report_type": "valuation_advisory",
            "amount_cents": config.price_cents,
            "currency": config.currency,
        },
    }


@app.get("/wizard/company/{company_id}/readiness")
async def wizard_company_readiness(
    company_id: int,
    document_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return owner-scoped extraction and authority readiness for checkout."""
    return await _wizard_readiness(db, company_id, document_id, current_user["id"])


# ---------------------------------------------------------------------------
# Wizard — report generation (Phase 5)
# ---------------------------------------------------------------------------

# Valid report types (match REPORT_TYPE_LABELS keys in report_email.py)
_VALID_REPORT_TYPES = frozenset(REPORT_TYPE_LABELS.keys())


def _requires_admin_review(report_type: str) -> bool:
    if report_type != "valuation_advisory":
        return False
    flag = os.environ.get("ACCOUNTIQ_REQUIRE_ADMIN_REVIEW", "true").strip().lower()
    return flag not in {"0", "false", "no", "off"}


async def _store_generated_report(
    db: aiosqlite.Connection,
    *,
    report_id: int,
    report_type: str,
    content_json: dict,
    valuation_result: dict | None = None,
) -> str:
    validate_generated_report(content_json, report_type, valuation_result)
    next_status = "awaiting_review" if _requires_admin_review(report_type) else "done"
    if next_status == "done":
        cursor = await db.execute("""
            UPDATE reports
            SET status='done', content=?, completed_at=datetime('now')
            WHERE id=? AND status IN ('generating', 'researching')
        """, (json.dumps(content_json), report_id))
    else:
        cursor = await db.execute("""
            UPDATE reports
            SET status='awaiting_review', content=?, completed_at=NULL
            WHERE id=? AND status IN ('generating', 'researching')
        """, (json.dumps(content_json), report_id))
    if cursor.rowcount == 0:
        async with db.execute("SELECT status FROM reports WHERE id=?", (report_id,)) as cur:
            row = await cur.fetchone()
        return row["status"] if row else "missing"
    if next_status == "awaiting_review":
        await db.execute("""
            INSERT INTO reviews (report_id, status)
            VALUES (?, 'awaiting_review')
            ON CONFLICT(report_id) DO UPDATE SET
                reviewer_user_id=NULL,
                status='awaiting_review',
                updated_at=datetime('now'),
                approved_at=NULL
        """, (report_id,))
    return next_status


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

    # Create the report and its immutable generation inputs together.
    await db.execute("BEGIN IMMEDIATE")
    try:
        report_id = await _insert_report_job(
            db,
            company_id=company_id,
            user_id=current_user["id"],
            report_type=report_type,
            status="queued",
            intake_answers=intake_answers,
        )
        await create_report_input_snapshot(
            db, report_id, company_id, current_user["id"]
        )
        await db.commit()
    except (AuthorityConflictError, ValueError) as exc:
        await db.rollback()
        detail = (
            "Financial document authority must be resolved before generation."
            if isinstance(exc, AuthorityConflictError)
            else str(exc)
        )
        raise HTTPException(409, detail)
    except Exception:
        await db.rollback()
        raise

    # Queue background generation task
    background_tasks.add_task(_generate_report, report_id)

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
    body = await request.json()
    idempotency_key = body.get("idempotency_key")
    document_id = body.get("document_id")
    if report_type != "valuation_advisory":
        raise HTTPException(400, "Checkout is currently only available for valuation_advisory.")
    if not isinstance(idempotency_key, str) or not 8 <= len(idempotency_key) <= 128:
        raise HTTPException(400, "idempotency_key must be 8-128 characters")
    if document_id is not None and (not isinstance(document_id, int) or document_id <= 0):
        raise HTTPException(400, "document_id must be a positive integer")

    await _ensure_user_company(db, company_id, current_user["id"])
    request_digest = hashlib.sha256(json.dumps(
        {
            "user_id": current_user["id"],
            "company_id": company_id,
            "document_id": document_id,
            "report_type": report_type,
            "intake_answers": intake_answers,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()

    config = checkout_config()
    if not E2E_MODE and not stripe_enabled():
        raise HTTPException(503, "Stripe checkout is not configured.")

    await db.execute("BEGIN IMMEDIATE")
    try:
        # Reconfirm ownership and readiness while holding the short persistence transaction.
        await _ensure_user_company(db, company_id, current_user["id"])
        readiness = await _wizard_readiness(
            db, company_id, document_id, current_user["id"]
        )
        if readiness["state"] != "ready":
            raise HTTPException(
                409,
                {
                    "state": readiness["state"],
                    "code": readiness["code"],
                    "message": readiness["message"],
                },
            )
        async with db.execute(
            """
            SELECT p.id AS purchase_id, p.report_id, p.status, p.stripe_checkout_session_id,
                   p.stripe_checkout_url, p.checkout_request_digest,
                   ris.canonical_digest AS snapshot_digest, ris.schema_version,
                   ris.valuation_engine_version, r.status AS report_status
            FROM purchases p JOIN reports r ON r.id=p.report_id
            LEFT JOIN report_input_snapshots ris ON ris.report_id=r.id
            WHERE p.user_id=? AND p.checkout_idempotency_key=?
            """,
            (current_user["id"], idempotency_key),
        ) as cur:
            existing_order = await cur.fetchone()
        if existing_order:
            stored_digest = existing_order["checkout_request_digest"]
            if stored_digest is None:
                # Older pending purchases predate the request digest. Their frozen
                # snapshot cannot prove document selector equivalence, so fail closed.
                raise HTTPException(
                    409,
                    {
                        "state": "conflict",
                        "code": "idempotency_key_reused",
                        "message": "This checkout key is already bound to another request.",
                    },
                )
            if stored_digest != request_digest:
                raise HTTPException(
                    409,
                    {
                        "state": "conflict",
                        "code": "idempotency_key_reused",
                        "message": "This checkout key is already bound to another request.",
                    },
                )
            if snapshot_requires_restart(
                existing_order["schema_version"],
                existing_order["valuation_engine_version"],
                existing_order["report_status"],
            ):
                raise HTTPException(
                    409,
                    {
                        "code": "legacy_snapshot_restart_required",
                        "message": _LEGACY_SNAPSHOT_RESTART_MESSAGE,
                    },
                )
            await db.commit()
            report_id = existing_order["report_id"]
            purchase_id = existing_order["purchase_id"]
        else:
            snapshot_candidate = await build_report_input_snapshot_candidate(
                db,
                company_id=company_id,
                user_id=current_user["id"],
                report_type=report_type,
                intake_answers=intake_answers,
            )
            build_valuation_inputs(
                snapshot_candidate["financial_rows"], snapshot_candidate,
                require_fcff=True,
            )
            report_id = await _insert_report_job(
                db,
                company_id=company_id,
                user_id=current_user["id"],
                report_type=report_type,
                status="pending_payment",
                intake_answers=intake_answers,
            )
            await persist_report_input_snapshot(db, report_id, snapshot_candidate)
            async with db.execute("""
                INSERT INTO purchases
                    (report_id, user_id, amount_cents, currency, status,
                     checkout_idempotency_key, checkout_request_digest)
                VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """, (
                report_id, current_user["id"], config.price_cents, config.currency,
                idempotency_key, request_digest,
            )) as cur:
                purchase_id = cur.lastrowid
            await db.commit()
    except ValuationInputError as exc:
        await db.rollback()
        raise HTTPException(
            409,
            {
                "state": "needs_clarification",
                "code": "needs_clarification",
                "reason_code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except (AuthorityConflictError, ValueError) as exc:
        await db.rollback()
        if isinstance(exc, AuthorityConflictError):
            detail = {
                "state": "conflict",
                "code": "authority_conflict",
                "message": "Financial document authority must be resolved before checkout.",
            }
        else:
            message = str(exc)
            detail = {
                "state": "conflict",
                "code": (
                    "source_file_unavailable"
                    if "retained file is missing" in message
                    else "snapshot_unavailable"
                ),
                "message": message,
            }
        raise HTTPException(409, detail)
    except Exception:
        await db.rollback()
        raise

    status = "pending_payment"
    checkout_url = None

    if E2E_MODE:
        await db.execute("""
            UPDATE purchases
            SET status='paid', paid_at=COALESCE(paid_at, datetime('now'))
            WHERE id=?
        """, (purchase_id,))
        queue_cursor = await db.execute(
            "UPDATE reports SET status='queued' WHERE id=? AND status='pending_payment'",
            (report_id,),
        )
        if queue_cursor.rowcount == 1:
            background_tasks.add_task(_generate_report, report_id)
        async with db.execute("SELECT status FROM reports WHERE id=?", (report_id,)) as cur:
            status = (await cur.fetchone())["status"]
    else:
        if existing_order and existing_order["stripe_checkout_url"]:
            checkout_url = existing_order["stripe_checkout_url"]
        else:
            session = create_checkout_session(
                report_id=report_id,
                purchase_id=purchase_id,
                user_email=current_user["email"],
                config=config,
            )
            await db.execute("""
                UPDATE purchases
                SET stripe_checkout_session_id=?, stripe_checkout_url=?
                WHERE id=?
            """, (session.session_id, session.url, purchase_id))
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
    payable_event_types = {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }
    if event_type not in payable_event_types:
        return {"received": True, "ignored": True}

    session = _object_get(_object_get(event, "data") or {}, "object") or {}
    if _object_get(session, "payment_status") != "paid":
        return {"received": True, "ignored": True}
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
            metadata = _object_get(session, "metadata") or {}
            purchase_id = _object_get(metadata, "purchase_id")
            if purchase_id and str(purchase_id).isdigit():
                async with db.execute(
                    """
                    SELECT p.id AS purchase_id, p.report_id
                    FROM purchases p
                    JOIN reports r ON r.id=p.report_id
                    WHERE p.id=? AND p.status='pending' AND r.status='pending_payment'
                    """,
                    (int(purchase_id),),
                ) as cur:
                    row = await cur.fetchone()
                if row:
                    cursor = await db.execute(
                        """
                        UPDATE purchases
                        SET stripe_checkout_session_id=?
                        WHERE id=? AND stripe_checkout_session_id IS NULL
                        """,
                        (session_id, row["purchase_id"]),
                    )
                    if cursor.rowcount != 1:
                        await db.rollback()
                        raise HTTPException(409, "Checkout session could not be reconciled")
            if not row:
                raise HTTPException(404, "Purchase not found")

        await db.execute("""
            UPDATE purchases
            SET status='paid',
                stripe_payment_intent_id=?,
                paid_at=COALESCE(paid_at, datetime('now'))
            WHERE id=?
        """, (payment_intent_id, row["purchase_id"]))

        queue_cursor = await db.execute(
            "UPDATE reports SET status='queued' WHERE id=? AND status='pending_payment'",
            (row["report_id"],),
        )
        should_queue = queue_cursor.rowcount == 1
        await db.commit()

    if should_queue:
        background_tasks.add_task(_generate_report, row["report_id"])

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


_LEGACY_SNAPSHOT_RESTART_MESSAGE = (
    "This paid valuation needs updated FCFF inputs before it can be generated."
)


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

    # Verify the original immutable snapshot before requeueing.
    try:
        await load_report_input_snapshot(db, report_id)
    except LegacySnapshotRestartRequired:
        raise HTTPException(
            409,
            {
                "code": "legacy_snapshot_restart_required",
                "message": _LEGACY_SNAPSHOT_RESTART_MESSAGE,
            },
        )
    except SnapshotIntegrityError:
        raise HTTPException(409, "Report input snapshot failed integrity verification")

    # Reset status conditionally so duplicate retries cannot queue twice.
    cursor = await db.execute("""
        UPDATE reports
        SET status='queued', error_message=NULL, completed_at=NULL
        WHERE id=? AND user_id=? AND status='failed'
    """, (report_id, current_user["id"]))
    await db.commit()
    if cursor.rowcount != 1:
        raise HTTPException(409, "Report retry was already claimed")

    background_tasks.add_task(_generate_report, report_id)
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
                        f"<div class='table-scroll' tabindex='0' role='region' "
                        f"aria-label='{_html_lib.escape(heading)} table'><table class='report-table'>"
                        f"<thead><tr>{th_cells}</tr></thead>"
                        f"<tbody>{tr_rows}</tbody>"
                        f"</table></div>"
                    )

        section_class = " class='disclaimer'" if key == "disclaimer" else ""
        section_html += f"""
        <section{section_class}>
            <h2>{_html_lib.escape(heading)}</h2>
            {paragraphs}
            {table_html}
        </section>"""

    return section_html


def _render_report_html(row, sections: dict, back_url: str) -> str:
    section_order = SECTION_SCHEMAS.get(row["report_type"], list(sections.keys()))
    label = row["report_type"].replace("_", " ").title()
    section_html = _render_report_sections_html(sections, section_order)
    generated_label = row["completed_at"] or (
        "Draft awaiting review" if row["status"] == "awaiting_review" else row["status"]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_html_lib.escape(label)} | {_html_lib.escape(row['name'])} | AccountIQ</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #f5f7fa; color: #172033; font-family: "Segoe UI", system-ui, sans-serif; line-height: 1.65; }}
  .report-shell {{ width: min(980px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 56px; }}
  .report-topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 24px; }}
  .wordmark {{ color: #0d1b2a; font-weight: 800; font-size: 1.1rem; letter-spacing: -0.02em; text-decoration: none; }}
  .back {{ display: inline-flex; min-height: 40px; align-items: center; color: #1565c0; font-size: .875rem; font-weight: 700; text-decoration: none; }}
  .back:focus-visible {{ outline: 3px solid #2196f3; outline-offset: 3px; }}
  .report-card {{ padding: clamp(24px, 5vw, 48px); border: 1px solid #e0e4ea; border-radius: 12px; background: #fff; box-shadow: 0 12px 32px rgba(13, 27, 42, .08); }}
  header {{ border-bottom: 2px solid #0d1b2a; padding-bottom: 22px; margin-bottom: 32px; }}
  header h1 {{ margin: 0 0 6px; color: #0d1b2a; font-size: clamp(1.6rem, 4vw, 2.25rem); line-height: 1.15; letter-spacing: -.03em; }}
  header p {{ margin: 0; color: #607080; font-size: .95rem; }}
  .meta {{ margin-top: 10px; font-size: .82rem; }}
  section {{ margin-bottom: 2.5rem; }}
  h2 {{ margin: 0 0 14px; border-left: 4px solid #1565c0; padding-left: 12px; color: #0d1b2a; font-size: 1.15rem; line-height: 1.3; }}
  h3 {{ margin: 1.4rem 0 .5rem; color: #0d1b2a; font-size: 1rem; }}
  p {{ margin: 0 0 1rem; font-size: .95rem; }}
  ul {{ margin: .2rem 0 1rem 1.4rem; padding: 0; }}
  li {{ margin-bottom: .35rem; font-size: .95rem; }}
  .disclaimer {{ padding: 14px 16px; border: 1px solid #f0c36d; border-radius: 8px; background: #fffbeb; }}
  .disclaimer p, .disclaimer li {{ color: #92400e; font-size: .86rem; }}
  .table-scroll {{ width: 100%; margin: 12px 0 24px; overflow-x: auto; border: 1px solid #e0e4ea; border-radius: 8px; }}
  .table-scroll:focus-visible {{ outline: 3px solid #2196f3; outline-offset: 3px; }}
  table.report-table {{ width: 100%; min-width: 620px; border-collapse: collapse; font-size: .88rem; }}
  table.report-table th, table.report-table td {{ padding: 10px 12px; border-bottom: 1px solid #e0e4ea; text-align: left; white-space: nowrap; }}
  table.report-table thead th {{ background: #f0f4f8; color: #607080; font-size: .75rem; font-weight: 700; }}
  table.report-table tbody tr:nth-child(even) {{ background: #fafbfc; }}
  table.report-table td:not(:first-child) {{ text-align: right; }}
  @media (max-width: 560px) {{ .report-shell {{ width: min(100% - 24px, 980px); padding-top: 20px; }} .report-topbar {{ align-items: flex-start; flex-direction: column-reverse; gap: 8px; }} .report-card {{ padding: 22px 18px; }} }}
  @media print {{ body {{ background: #fff; }} .report-shell {{ width: 100%; padding: 0; }} .report-topbar {{ display: none; }} .report-card {{ border: 0; border-radius: 0; box-shadow: none; padding: 0; }} .table-scroll {{ overflow: visible; }} table.report-table {{ min-width: 0; }} }}
</style>
</head>
<body>
<div class="report-shell">
  <div class="report-topbar">
    <a class="wordmark" href="{_html_lib.escape(back_url, quote=True)}">AccountIQ</a>
    <a class="back" href="{_html_lib.escape(back_url, quote=True)}">Back to valuations</a>
  </div>
  <main class="report-card">
    <header>
      <h1>{_html_lib.escape(label)}</h1>
      <p>{_html_lib.escape(row['name'])}</p>
      <p class="meta">Report #{row['id']} &middot; Generated {_html_lib.escape(str(generated_label))}</p>
    </header>
    {section_html}
  </main>
</div>
</body>
</html>"""


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

    back_url = f"{os.getenv('APP_BASE_URL', 'http://localhost:3000').rstrip('/')}/wizard"
    html = _render_report_html(row, sections, back_url)
    return HTMLResponse(content=html)


@app.get("/wizard/report/{report_id}/pdf", response_class=FileResponse)
async def wizard_report_pdf(
    report_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return a cached professional PDF for an approved, user-owned report."""
    async with db.execute("""
        SELECT r.id, r.report_type, r.status, r.content, r.completed_at,
               c.name AS company_name
        FROM reports r
        JOIN companies c ON c.id = r.company_id
        WHERE r.id=? AND r.user_id=?
    """, (report_id, current_user["id"])) as cursor:
        report = await cursor.fetchone()
    if not report:
        raise HTTPException(404, "Report not found")
    if report["status"] != "done":
        raise HTTPException(400, f"Report is not ready yet (status: {report['status']})")

    try:
        sections = json.loads(report["content"])
    except Exception:
        raise HTTPException(500, "Report content could not be parsed")
    if not isinstance(sections, dict):
        raise HTTPException(500, "Report content has an invalid structure")

    output_path = report_pdf_path(EXPORT_DIR, report_id)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        html_text = render_report_html(
            report["company_name"],
            report["report_type"],
            sections,
            report["completed_at"],
            SECTION_SCHEMAS.get(report["report_type"]),
        )
        await asyncio.get_running_loop().run_in_executor(
            None,
            write_pdf,
            html_text,
            output_path,
        )

    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=output_path.name,
    )


@app.get("/account/purchases")
async def account_purchases(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List the authenticated customer's purchases and delivery states."""
    async with db.execute("""
        SELECT
            p.id AS purchase_id,
            p.report_id,
            c.name AS company_name,
            r.report_type,
            p.status AS purchase_status,
            r.status AS report_status,
            p.amount_cents,
            p.currency,
            p.paid_at,
            p.created_at
        FROM purchases p
        JOIN reports r ON r.id = p.report_id
        JOIN companies c ON c.id = r.company_id
        WHERE p.user_id=? AND r.user_id=? AND c.user_id=?
        ORDER BY p.created_at DESC, p.id DESC
    """, (current_user["id"], current_user["id"], current_user["id"])) as cursor:
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@app.get("/admin/reports/pending")
async def admin_reports_pending(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    async with db.execute("""
        SELECT
            r.id,
            r.company_id,
            c.name AS company_name,
            u.email AS user_email,
            r.report_type,
            r.status,
            r.created_at,
            r.completed_at,
            p.amount_cents,
            p.currency,
            p.paid_at
        FROM reports r
        JOIN companies c ON c.id = r.company_id
        JOIN users u ON u.id = r.user_id
        LEFT JOIN purchases p ON p.report_id = r.id
        WHERE r.status='awaiting_review'
        ORDER BY r.created_at ASC, r.id ASC
    """) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/admin/reports/{report_id}/view", response_class=HTMLResponse)
async def admin_report_view(
    report_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    async with db.execute("""
        SELECT r.id, r.report_type, r.status, r.content, r.completed_at,
               c.name
        FROM reports r
        JOIN companies c ON c.id = r.company_id
        WHERE r.id=?
    """, (report_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Report not found")
    if row["status"] not in {"awaiting_review", "done"}:
        raise HTTPException(400, f"Report is not reviewable yet (status: {row['status']})")

    import json as _json
    try:
        sections = _json.loads(row["content"])
    except Exception:
        raise HTTPException(500, "Report content could not be parsed")

    back_url = f"{os.getenv('APP_BASE_URL', 'http://localhost:3000').rstrip('/')}/admin/reports"
    return HTMLResponse(content=_render_report_html(row, sections, back_url))


@app.post("/admin/reports/{report_id}/approve")
async def admin_report_approve(
    report_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    async with db.execute("""
        SELECT
            r.id,
            r.report_type,
            r.status,
            u.email AS user_email,
            EXISTS (
                SELECT 1
                FROM purchases p
                WHERE p.report_id = r.id
                  AND p.status = 'paid'
                  AND p.paid_at IS NOT NULL
            ) AS is_paid
        FROM reports r
        JOIN users u ON u.id = r.user_id
        WHERE r.id=?
    """, (report_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Report not found")
    if row["status"] != "awaiting_review":
        raise HTTPException(409, f"Report is not awaiting review (current: {row['status']})")
    if not row["is_paid"]:
        raise HTTPException(409, "Report cannot be approved until payment is confirmed")

    cursor = await db.execute("""
        UPDATE reports
        SET status='done', completed_at=datetime('now')
        WHERE id=? AND status='awaiting_review'
    """, (report_id,))
    if cursor.rowcount == 0:
        await db.commit()
        raise HTTPException(409, "Report is no longer awaiting review")
    await db.execute("""
        INSERT INTO reviews (
            report_id,
            reviewer_user_id,
            status,
            approved_at
        )
        VALUES (?, ?, 'approved', datetime('now'))
        ON CONFLICT(report_id) DO UPDATE SET
            reviewer_user_id=excluded.reviewer_user_id,
            status='approved',
            updated_at=datetime('now'),
            approved_at=datetime('now')
    """, (report_id, current_user["id"]))
    await db.commit()

    user_email_addr = row["user_email"]
    await send_report_ready_email(
        user_email_addr,
        user_email_addr.split("@")[0],
        row["report_type"],
        report_id,
    )
    return {"id": report_id, "status": "done"}


# ---------------------------------------------------------------------------
# Report generation background task (Phase 5)
# ---------------------------------------------------------------------------

# REPORT_SECTIONS is kept for backward compatibility but SECTION_SCHEMAS
# (from report_prompts) is the canonical source used by generate_report and Phase 7.
# Both use the same full report-type keys (e.g. 'valuation_advisory').
REPORT_SECTIONS = SECTION_SCHEMAS  # alias — do not remove

_SAFE_REPORT_GENERATION_ERROR = (
    "We couldn't generate a complete report. Please retry, or contact support if the problem continues."
)


async def _generate_report(report_id: int) -> None:
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
            # Claim the queued job. A duplicate/late background task must not
            # move an approved or in-review report back into generation.
            cursor = await db.execute(
                "UPDATE reports SET status='generating' WHERE id=? AND status='queued'",
                (report_id,)
            )
            await db.commit()
            if cursor.rowcount == 0:
                async with db.execute("SELECT status FROM reports WHERE id=?", (report_id,)) as cur:
                    row = await cur.fetchone()
                current_status = row["status"] if row else "missing"
                print(f"[REPORT] Skipping report_id={report_id}; status={current_status}")
                return
            print(f"[REPORT] Generating report_id={report_id}")

            async with db.execute(
                "SELECT user_id FROM reports WHERE id=?", (report_id,)
            ) as cur:
                report_owner = await cur.fetchone()
            if not report_owner:
                raise SnapshotIntegrityError("Report is missing")
            snapshot = await load_report_input_snapshot(db, report_id)
            user_id = report_owner["user_id"]
            company = snapshot["company"]
            company_name = company["name"]
            company_sector = company.get("sector") or ""
            company_description = company.get("description") or ""
            mgmt_team = snapshot["management_team"]
            ebitda_adjustments = snapshot["ebitda_adjustments"]
            raw_fin_rows = snapshot["financial_rows"]
            intake_answers = snapshot["intake_answers"]
            report_type = snapshot["report_type"]

            if E2E_MODE:
                await asyncio.sleep(0.05)
                content_json = _e2e_report_content(report_type)
                next_status = await _store_generated_report(
                    db,
                    report_id=report_id,
                    report_type=report_type,
                    content_json=content_json,
                )
                await db.commit()
                print(f"[REPORT] E2E report_id={report_id} {next_status} ({report_type})")
                return

            # Transform frozen financial rows into the grouped format expected by
            # build_prompt(): each row has {canonical_key, statement, values}.
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

                # Frozen inputs and deterministic arithmetic are validated before
                # research or report writing begins.
                typed_inputs = build_valuation_inputs(
                    raw_fin_rows, snapshot, require_fcff=True
                )
                fcff_result = calculate_fcff(typed_inputs)
                deterministic_fcff = report_prompt_payload(fcff_result)

                # Research supplies narrative and market-multiple context only.
                company_location = (intake_answers.get("company_location") or "New Zealand") if isinstance(intake_answers, dict) else "New Zealand"
                industry_sector_for_research = company_sector or "General SME"
                brief = await run_valuation_research(
                    company_name=company_name,
                    company_location=company_location,
                    industry_sector=industry_sector_for_research,
                )

                normalised_ebitda = float(typed_inputs.normalised_ebitda.value)
                multiples_result = compute_multiples_crosscheck(
                    normalised_ebitda=normalised_ebitda,
                    ev_ebitda_low=brief.ev_ebitda_low,
                    ev_ebitda_high=brief.ev_ebitda_high,
                )
                scenario_bridges = {
                    scenario.name: {
                        "enterprise_value": scenario.enterprise_value,
                        "interest_bearing_debt": fcff_result.interest_bearing_debt,
                        "unrestricted_cash": fcff_result.unrestricted_cash,
                        "net_debt": scenario.net_debt,
                        "approved_surplus_assets": scenario.approved_surplus_assets,
                        "pre_dlom_equity_value": scenario.pre_dlom_equity_value,
                        "dlom_rate": scenario.dlom_rate,
                        "dlom_amount": scenario.dlom_amount,
                        "equity_value": scenario.equity_value,
                    }
                    for scenario in fcff_result.scenarios
                }

                valuation_result = {
                    "research_brief": brief.model_dump(),
                    "deterministic_fcff": deterministic_fcff,
                    "normalised_ebitda": normalised_ebitda,
                    "normalisations": [
                        {
                            "label": item.label,
                            "amount": str(item.amount),
                            "rationale": item.rationale,
                        }
                        for item in typed_inputs.normalisations
                    ],
                    "scenario_bridges": scenario_bridges,
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
            content_json = await _call_claude_for_report(system_prompt, user_message)

            # --- 8. Store validated content; paid valuations wait for reviewer approval ---
            next_status = await _store_generated_report(
                db,
                report_id=report_id,
                report_type=report_type,
                content_json=content_json,
                valuation_result=valuation_result,
            )
            await db.commit()
            print(f"[REPORT] report_id={report_id} {next_status} ({report_type})")

            # --- 10. Load user email and send notification ---
            if next_status == "done":
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
            customer_error = (
                _LEGACY_SNAPSHOT_RESTART_MESSAGE
                if isinstance(exc, LegacySnapshotRestartRequired)
                else _SAFE_REPORT_GENERATION_ERROR
            )
            try:
                await db.execute("""
                    UPDATE reports
                    SET status='failed', content=NULL, error_message=?
                    WHERE id=?
                """, (customer_error, report_id))
                await db.commit()
            except Exception as db_exc:
                print(f"[REPORT ERROR] Failed to mark report failed: {db_exc}")


async def _call_claude_for_report(
    system_prompt: str,
    user_message: str,
) -> dict:
    """Call Claude for report generation and return its parsed JSON object."""
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
    content_json = _parse_json_from_response(raw_text)
    return content_json


def _parse_json_from_response(raw_text: str) -> dict:
    """
    Extract a JSON object from Claude's response text.

    Markdown fences and surrounding prose are tolerated, but malformed JSON and
    non-object JSON fail closed. Content completeness is validated separately.
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
                return parsed
        except json.JSONDecodeError:
            pass

    raise ValueError("Claude response must contain a valid JSON object")


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
