"""
AccountIQ Learning Agent — FastAPI backend
Run with: uvicorn main:app --reload --port 8765
"""
import os
import json
import shutil
import asyncio
import sqlite3
import math
import re
import time
import ipaddress
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from urllib.parse import urlparse

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
from financial_reconciliation import reconcile_financial_rows
from ingestion import ingest_document
from auth import auth_router, get_current_user, require_admin
from report_email import send_report_ready_email, REPORT_TYPE_LABELS
from report_prompts import (
    BANK_CREDIT_COVENANT_DEFINITIONS,
    BANK_CREDIT_COVENANT_PACKAGE_DEFAULTS,
    build_prompt,
    SECTION_SCHEMAS,
    TABLE_SECTIONS_BANK_CREDIT,
    TABLE_SECTIONS_VALUATION,
    compute_bank_credit_figures,
)
from report_rendering import (
    FINANCIAL_TREND_VISUAL_SUBTITLE,
    SENSITIVITY_SPREAD_VISUAL_SUBTITLE,
    VALUATION_RANGE_VISUAL_SUBTITLE,
    _right_aligned_pdf_columns as _right_aligned_report_table_columns,
    dcf_value_build_visual,
    equity_bridge_visual,
    executive_valuation_highlights,
    financial_trend_visual,
    implied_multiple_reconciliation,
    normalised_ebitda_bridge_visual,
    report_display_date,
    report_pdf_path,
    report_reference_code,
    sensitivity_spread_visual,
    valuation_method_selection,
    valuation_reader_guidance,
    valuation_range_visual,
    valuation_basis_of_preparation,
    wacc_build_visual,
    write_report_pdf,
)
from report_quality import (
    UNFINISHED_FOLLOWUP_MARKERS,
    audit_valuation_report_content,
    audit_valuation_report_html,
    audit_valuation_report_pdf,
    audit_bank_credit_report_html,
    audit_bank_credit_report_pdf,
)
from evidence_research import collect_evidence_research, evidence_sources_table
from research_loop import WEB_SEARCH_TOOL, run_valuation_research
from sector_library import (
    enrich_research_brief,
    match_sector_report,
    sector_prompt_context,
)
from market_intelligence import apply_market_intelligence_to_report_content
from report_readiness import (
    assess_credit_financial_readiness,
    credit_readiness_message,
    report_follow_up_items,
)
from valuation import (
    compute_wacc_scenarios, compute_dcf, compute_illiquidity_discount,
    compute_multiples_range, select_revenue_growth_assumption,
    derive_reinvestment_assumptions, compute_dcf_sensitivity_matrix,
    assess_valuation_financial_readiness, build_forecast_cash_flow_schedule,
    build_balance_sheet_summary_table,
    build_dcf_analysis_table, build_multiples_crosscheck_table,
    build_comparable_evidence_table,
    build_executive_summary_table, build_valuation_summary_table,
    build_wacc_assumptions_table,
    build_financial_performance_table, build_financial_ratio_table,
    build_normalisation_schedule_table,
    build_assumption_source_trail, build_sources_table,
    build_sensitivity_analysis_table, build_specific_risk_factor_table,
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

ALLOWED_FINANCIAL_UPLOAD_SUFFIXES = {".pdf", ".xlsx", ".xls", ".xlsm", ".docx"}
MAX_WIZARD_UPLOAD_FILES = 8
_TRUE_ENV_VALUES = {"1", "true", "yes", "on"}


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE_ENV_VALUES


E2E_MODE = _env_flag("ACCOUNTIQ_E2E_MODE")


def _demo_mode_enabled() -> bool:
    """Return whether deterministic sample extraction/reporting is active.

    E2E mode always implies demo mode, but local/demo usage should be enabled
    explicitly with ACCOUNTIQ_DEMO_MODE=true so live deployments do not silently
    deliver simulated valuation work when a provider key is missing.
    """
    return E2E_MODE or _env_flag("ACCOUNTIQ_DEMO_MODE")


def _report_generation_mode() -> str:
    """Select the report engine without silently labelling a live report as demo.

    ``auto`` is the default: use the OpenAI workflow when a valid
    key is configured and otherwise use the deterministic evidence workflow.
    The evidence workflow only fetches user-approved public URLs and writes
    reports from templates plus calculated financial schedules; it never calls
    OpenAI or another commercial AI provider.
    """
    if _demo_mode_enabled():
        return "demo"
    requested = os.environ.get("ACCOUNTIQ_REPORT_GENERATION_MODE", "auto").strip().lower()
    if requested not in {"auto", "provider", "evidence"}:
        requested = "auto"
    if requested == "evidence":
        return "evidence"
    if requested == "provider":
        return "provider" if _live_openai_key_configured() else "unavailable"
    return "provider" if _live_openai_key_configured() else "evidence"


def _row_value(row, key: str, default=None):
    """Return a value from sqlite row-like objects without assuming the column exists."""
    if row is None:
        return default
    try:
        if hasattr(row, "keys") and key not in row.keys():
            return default
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def _content_looks_like_demo_report(content: object) -> bool:
    """Detect older demo reports created before report.demo_mode was persisted."""
    lowered = str(content or "").lower()
    demo_markers = (
        "demo figures and simulated research",
        "sample public-source research",
        "sample report",
        "simulated research",
    )
    return any(marker in lowered for marker in demo_markers)


def _report_demo_mode_from_row(row) -> bool:
    """Use the report's stored mode so old demo reports stay labelled correctly."""
    raw_demo_mode = _row_value(row, "demo_mode")
    try:
        if raw_demo_mode is not None and int(raw_demo_mode) == 1:
            return True
    except (TypeError, ValueError):
        pass
    return _content_looks_like_demo_report(_row_value(row, "content", ""))


def _report_generation_mode_from_row(row) -> str:
    """Use persisted generation mode so a retry/review stays auditable."""
    if _report_demo_mode_from_row(row):
        return "demo"
    mode = str(_row_value(row, "generation_mode", "") or "").strip().lower()
    if mode in {"provider", "evidence", "demo"}:
        return mode
    return "provider"


def _live_openai_key_configured() -> bool:
    key = os.environ.get("OPENAI_API_KEY", "")
    return bool(
        key
        and not key.startswith("sk-YOUR")
        and key != "sk-e2e-placeholder"
    )


_LIVE_RESEARCH_PREFLIGHT_TTL_SECONDS = 300
_LIVE_RESEARCH_PREFLIGHT_TIMEOUT_SECONDS = 8
_live_research_preflight_cache: dict[str, float] = {}


def _live_research_connection_error_detail(current_user: dict) -> str:
    """Return a safe setup-error message for the current user type."""
    if current_user.get("is_admin"):
        return (
            "Provider-only report generation is selected, but the live AI research connection is not configured. "
            "Switch AccountIQ to evidence mode to generate source-scoped reports without a commercial AI key, "
            "or add and verify an OpenAI API key for provider research."
        )
    return (
        "Report preparation is temporarily unavailable. "
        "Please contact the AccountIQ administrator."
    )


def _openai_key_cache_signature(key: str) -> str:
    """Return a non-secret cache signature for a provider key."""
    if len(key) <= 12:
        return f"len:{len(key)}"
    return f"{key[:8]}:{key[-4:]}:{len(key)}"


def _openai_live_research_preflight_sync(api_key: str, model: str) -> None:
    """Verify the selected OpenAI model accepts AccountIQ's web-search setup."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The OpenAI SDK is not installed.") from exc

    client = OpenAI(api_key=api_key)
    client.responses.create(
        model=model,
        max_output_tokens=16,
        input=(
            "AccountIQ connection check. Reply OK only. "
            "Do not use web search or any other tool."
        ),
        tools=[WEB_SEARCH_TOOL],
    )


def _live_research_preflight_cache_key(api_key: str, model: str) -> str:
    return f"{_openai_key_cache_signature(api_key)}:{model}"


async def _run_live_research_preflight(api_key: str, model: str) -> bool:
    """Run the live-research preflight and return whether a fresh call was made."""
    cache_key = _live_research_preflight_cache_key(api_key, model)
    now = time.monotonic()
    if now - _live_research_preflight_cache.get(cache_key, 0) < _LIVE_RESEARCH_PREFLIGHT_TTL_SECONDS:
        return False

    await asyncio.wait_for(
        asyncio.to_thread(_openai_live_research_preflight_sync, api_key, model),
        timeout=_LIVE_RESEARCH_PREFLIGHT_TIMEOUT_SECONDS,
    )
    _live_research_preflight_cache[cache_key] = time.monotonic()
    return True


async def _ensure_live_research_connection(current_user: dict) -> None:
    """Fail before queueing when the live AI research connection cannot run."""
    if _demo_mode_enabled():
        return
    if not _live_openai_key_configured():
        raise HTTPException(503, _live_research_connection_error_detail(current_user))

    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")

    try:
        await _run_live_research_preflight(api_key, model)
    except Exception as exc:
        print(f"[REPORT] Live research preflight failed: {type(exc).__name__}: {exc}")
        raise HTTPException(503, _live_research_connection_error_detail(current_user))


def _e2e_financial_rows() -> list[tuple[str, str, str, str, float, float]]:
    return [
        ("pnl", "revenue", "Revenue", "2025", 1_250_000.0, 0.99),
        ("pnl", "cogs", "Direct costs", "2025", 462_500.0, 0.97),
        ("pnl", "gross_profit", "Gross profit", "2025", 787_500.0, 0.98),
        ("pnl", "wages_salaries", "Wages and salaries", "2025", 310_000.0, 0.96),
        ("pnl", "rent_occupancy", "Rent and occupancy", "2025", 96_000.0, 0.96),
        ("pnl", "advertising_marketing", "Advertising and marketing", "2025", 42_000.0, 0.94),
        ("pnl", "insurance", "Insurance", "2025", 18_000.0, 0.94),
        ("pnl", "other_operating_expenses", "Other operating expenses", "2025", 81_500.0, 0.92),
        ("pnl", "operating_expenses", "Operating expenses", "2025", 547_500.0, 0.96),
        ("pnl", "ebitda", "EBITDA", "2025", 240_000.0, 0.98),
        ("pnl", "depreciation_amortisation", "Depreciation and amortisation", "2025", 25_000.0, 0.96),
        ("pnl", "ebit", "EBIT", "2025", 215_000.0, 0.96),
        ("pnl", "net_profit", "Net Profit", "2025", 150_000.0, 0.97),
        ("bs", "cash_and_bank", "Cash & bank", "2025", 95_000.0, 0.98),
        ("bs", "trade_debtors", "Accounts receivable", "2025", 210_000.0, 0.96),
        ("bs", "inventory", "Stock on hand", "2025", 65_000.0, 0.95),
        ("bs", "total_current_assets", "Total current assets", "2025", 370_000.0, 0.96),
        ("bs", "trade_creditors", "Accounts payable", "2025", 155_000.0, 0.96),
        ("bs", "other_current_liab", "Other current liabilities", "2025", 45_000.0, 0.94),
        ("bs", "short_term_debt", "Current portion of loans", "2025", 60_000.0, 0.95),
        ("bs", "total_current_liab", "Total current liabilities", "2025", 260_000.0, 0.96),
        ("bs", "fixed_assets_net", "Fixed assets", "2025", 185_000.0, 0.96),
        ("bs", "other_noncurrent_assets", "Other non-current assets", "2025", 295_000.0, 0.92),
        ("bs", "total_assets", "Total Assets", "2025", 850_000.0, 0.98),
        ("bs", "long_term_debt", "Term loans", "2025", 100_000.0, 0.95),
        ("bs", "other_noncurrent_liab", "Other non-current liabilities", "2025", 60_000.0, 0.92),
        ("bs", "total_liabilities", "Total liabilities", "2025", 420_000.0, 0.96),
        ("bs", "shareholders_equity", "Shareholders equity", "2025", 430_000.0, 0.96),
    ]


def _e2e_report_content(report_type: str, *, demo_mode: bool = True) -> dict:
    sections = SECTION_SCHEMAS.get(report_type, ["executive_summary", "disclaimer"])
    if report_type == "bank_credit_paper":
        demo_note = (
            " Public research and financial figures are simulated only to demonstrate the AccountIQ "
            "credit-paper experience."
            if demo_mode
            else " Public-source context is retained separately from uploaded financials and lender inputs."
        )
        section_narratives = {
            "executive_summary": (
                "This screening-only bank credit paper reviews a requested facility of $1,000,000. "
                "Uploaded financials and lender inputs support the initial DSCR, ICR, LVR, NTOA and "
                "supportable debt view. The request remains subject to conditions precedent before committee."
                + demo_note
            ),
            "transaction_summary": "The transaction summary records the proposed purpose, amount, term, funding cost, security and repayment profile.",
            "sources_and_uses": "Sources and uses show the requested facility and identify any funds-flow evidence still required.",
            "borrower_and_sponsor_profile": "The borrower profile is limited to supplied company context and identifies the repayment source and guarantor evidence required.",
            "facilities_requested": "The facilities requested section sets out the proposed lender structure used throughout the credit calculations.",
            "security_package": "The security package section tests the proposed security, LVR and lien-priority evidence before credit committee.",
            "financial_performance_forecast": "Uploaded trading history is the credit anchor; no unsupported forecast is substituted for missing financial evidence.",
            "coverage_and_sensitivity": "Coverage ratios show base DSCR and ICR, rate stress, EBITDA downside and the scheduled deleveraging profile.",
            "balance_sheet_debt_capacity": "The balance-sheet section explains cash, debt, working capital and NTOA as a debt-capacity proxy rather than a formal collateral valuation.",
            "industry_and_competitive_landscape": "Industry context is illustrative in demo mode and must be checked against approved public sources before lender reliance.",
            "proposed_covenants": "The proposed lender controls are not agreed terms and must be tested against final bank policy and the agreed EBITDA definition.",
            "key_risks_and_mitigants": "Key risks include trading variance, interest-rate pressure, collateral value, liquidity, management dependence and documentation gaps.",
            "conditions_precedent": "Conditions precedent identify the management accounts, debt schedule, security evidence, ownership information and lender terms required before committee.",
            "recommendation": "The recommendation is screening-only: confirm the conditions precedent and revise structure if the supportable debt or coverage limits are not met.",
            "disclaimer": "This bank credit paper is indicative only, does not constitute financial advice, credit approval or a bank commitment, and should not be relied on without independent professional advice. The paper is prepared with regard to the FMCA context.",
        }
        table_sections = set(TABLE_SECTIONS_BANK_CREDIT)
        content: dict = {}
        for section in sections:
            if section not in table_sections:
                content[section] = section_narratives[section]
                continue
            content[section] = {
                "narrative": section_narratives.get(section, "The credit paper section records the lender-screening position."),
                "table": {
                    "headers": ["Credit item", "Position", "Credit treatment"],
                    "rows": [["Uploaded financials", "Available for screening", "Confirm source documents before committee."]],
                },
            }
            if section == "coverage_and_sensitivity":
                content[section]["amortisation_profile_table"] = {
                    "headers": ["Period", "Opening debt", "Closing debt"],
                    "rows": [["Year 1", "$1,000,000", "$850,000"]],
                }
            if section == "balance_sheet_debt_capacity":
                content[section]["debt_capacity_table"] = {
                    "headers": ["Constraint", "Supportable debt", "Basis"],
                    "rows": [["Illustrative leverage limit", "$900,000", "Latest uploaded EBITDA"]],
                }
        return content
    if report_type == "valuation_advisory":
        demo_disclaimer = (
            " Demo figures and simulated research are included only to demonstrate the AccountIQ "
            "report experience."
            if demo_mode
            else ""
        )
        comparable_context = (
            "illustrative public-market and benchmark context for the sample report"
            if demo_mode
            else "public-market and benchmark context for this report"
        )
        sources_context = (
            "the sample report's market, WACC, inflation and public-profile context. "
            "In a live report, each source is retained"
            if demo_mode
            else "the report's market, WACC, inflation and public-profile context. "
            "Each source is retained"
        )
        sample = {
            "introduction": (
                "## Client and report purpose\n"
                "This indicative valuation has been prepared to provide management and shareholders "
                "with an informed view of the fair-market value of 100% of the operating business. "
                "The stated purpose is to understand what the business may be worth before any sale, "
                "finance or shareholder discussion.\n\n"
                "## Valuation date and basis of value\n"
                "The valuation is expressed as at the prepared date shown on the cover page. Value "
                "is considered on a going-concern fair-market basis for the operating business, "
                "before buyer-specific synergies, transaction structure, warranties or completion "
                "adjustments.\n\n"
                "## Sources of information\n"
                "The report draws on uploaded financial information, management-confirmed private inputs, "
                "public-source research and AccountIQ valuation calculations. "
                "Public source URLs are retained in the sources section so a "
                "reader can inspect the evidence trail behind the valuation assumptions.\n\n"
                "## Liability, confidentiality and compliance\n"
                "This report is indicative only and is prepared for the stated purpose. It is not "
                "an independent business valuation report, does not constitute financial advice and "
                "should not be relied on as a substitute for independent professional advice."
                f"{demo_disclaimer}"
            ),
            "executive_summary": {
                "narrative": (
                    "The primary discounted cash flow analysis indicates an enterprise value range "
                    "of $1.90 million to $2.83 million after the private-company illiquidity adjustment, "
                    "with a midpoint of $2.31 million. The result "
                    "is most sensitive to maintainable EBITDA, customer retention and the selected "
                    "cost of capital."
                ),
                "table": {
                    "headers": ["Indicative valuation", "High", "Mid", "Low"],
                    "rows": [
                        ["Enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"],
                        ["Less: net debt", "$65,000", "$65,000", "$65,000"],
                        ["Indicative equity value", "$2,766,000", "$2,249,000", "$1,833,000"],
                    ],
                },
            },
            "business_overview": (
                "The subject company provides recurring business services to New Zealand SMEs. "
                "Public-source research indicates a stable market position supported by repeat "
                "customers, while management has confirmed that responsibility is shared across "
                "the operating team."
            ),
            "market_position": {
                "narrative": (
                    "The relevant New Zealand services market remains fragmented. Competitive advantage "
                    "depends on customer retention, delivery quality and trusted relationships. Public "
                    "market evidence was cross-checked against the company's private operating context."
                ),
                "table": {
                    "headers": ["Market consideration", "Current context", "Valuation relevance"],
                    "rows": [[
                        "Competitive structure",
                        "Fragmented private-SME market",
                        "Customer retention and delivery quality affect maintainable earnings and risk.",
                    ]],
                },
            },
            "about_business_valuations": (
                "## What the valuation represents\n"
                "A business valuation estimates what a willing, informed buyer might pay and a willing, "
                "informed seller might accept in an arm's-length transaction at the valuation date. It is "
                "not the same as a guaranteed sale price. It assumes a going-concern operating business "
                "and focuses on maintainable earnings rather than a one-off result. The final "
                "consideration may also reflect buyer synergies, deal structure, warranties, "
                "working-capital adjustments and market conditions.\n\n"
                "## Enterprise value and equity value\n"
                "Enterprise value is the value of the operating business before its financing position. "
                "Equity value is derived by deducting interest-bearing debt and adding available cash and "
                "separately identified surplus assets. This report therefore presents both measures.\n\n"
                "## Why a range is used\n"
                "Private-company value is sensitive to forecasts, customer retention and the return required "
                "by a market participant or investor. High, midpoint and low cases communicate that uncertainty "
                "more honestly than a single point estimate."
            ),
            "valuation_methodology": (
                "## Primary method - discounted cash flow\n"
                "Discounted cash flow is the primary method because it directly reflects the company's "
                "maintainable future cash-generating capacity. Expected free cash flows are forecast over "
                "five years and discounted to present value using a private-company cost of capital.\n\n"
                "## Independent cross-check - market multiples\n"
                "Researched EV/EBITDA evidence provides an independent reasonableness cross-check. It is not "
                "used mechanically because disclosed transactions differ in scale, growth, customer mix, "
                "contract security and strategic value."
            ),
            "financial_performance": {
                "narrative": (
                    "Revenue increased from $980,000 in FY23 to $1.25 million in FY25, while the forecast "
                    "year uses a more measured $1.35 million revenue base rather than assuming an aggressive "
                    "step-change. Direct costs are shown separately so the reader can see the bridge from "
                    "revenue to gross profit, and operating expenses are then deducted to arrive at EBITDA. "
                    "The key expense breakdown highlights the main controllable overheads: wages and salaries are "
                    "the largest cost category, rent and occupancy is the next major recurring overhead, and "
                    "marketing, insurance and other operating expenses are shown where they are material.\n\n"
                    "Gross profit improved from $588,000 to $787,500 over the historical period, while EBITDA "
                    "increased from $165,000 to $240,000. The forecast keeps EBITDA margin broadly stable at "
                    "19.2%, which is deliberately conservative: it recognises recent operating leverage without "
                    "assuming every efficiency gain repeats indefinitely. FY25 reported EBITDA of $240,000 is "
                    "then adjusted separately in the normalisation schedule to reach the maintainable earnings "
                    "base used for valuation."
                ),
                "table": {
                    "headers": ["Year ending March", "FY23 Actual", "FY24 Actual", "FY25 Actual", "FY26 Forecast"],
                    "rows": [
                        ["Revenue", "$980,000", "$1,110,000", "$1,250,000", "$1,350,000"],
                        ["Less: direct costs / cost of sales", "($392,000)", "($427,400)", "($462,500)", "($499,500)"],
                        ["Gross profit", "$588,000", "$682,600", "$787,500", "$850,500"],
                        ["Less: operating expenses before EBITDA", "($423,000)", "($477,600)", "($547,500)", "($591,500)"],
                        ["Key expense breakdown - wages and salaries", "($240,000)", "($272,000)", "($310,000)", "($335,000)"],
                        ["Key expense breakdown - rent and occupancy", "($84,000)", "($90,000)", "($96,000)", "($102,000)"],
                        ["Key expense breakdown - advertising and marketing", "($30,000)", "($36,000)", "($42,000)", "($45,000)"],
                        ["Key expense breakdown - insurance", "($15,000)", "($16,600)", "($18,000)", "($20,000)"],
                        ["Key expense breakdown - other operating expenses", "($54,000)", "($63,000)", "($81,500)", "($89,500)"],
                        ["EBITDA", "$165,000", "$205,000", "$240,000", "$259,000"],
                        ["EBITDA margin", "16.8%", "18.5%", "19.2%", "19.2%"],
                        ["Less: depreciation and amortisation", "($20,000)", "($22,000)", "($25,000)", "($27,000)"],
                        ["EBIT", "$145,000", "$183,000", "$215,000", "$232,000"],
                        ["Net profit after tax", "$105,000", "$128,000", "$150,000", "$163,000"],
                    ],
                },
            },
            "financial_ratio_analysis": {
                "narrative": (
                    "Historical ratios show improving scale and operating leverage. The forecast deliberately "
                    "holds EBITDA margin broadly flat rather than assuming that the recent expansion continues "
                    "indefinitely."
                ),
                "table": {
                    "headers": ["Ratio", "FY23 Actual", "FY24 Actual", "FY25 Actual", "FY26 Forecast"],
                    "rows": [
                        ["Revenue growth", "Not available", "13.3%", "12.6%", "8.0%"],
                        ["Gross margin", "60.0%", "61.5%", "63.0%", "63.0%"],
                        ["EBITDA margin", "16.8%", "18.5%", "19.2%", "19.2%"],
                        ["Net profit margin", "10.7%", "11.5%", "12.0%", "12.1%"],
                    ],
                },
            },
            "normalisations_schedule": {
                "narrative": (
                    "Normalisations isolate maintainable operating earnings from owner-specific and "
                    "one-off expenditure."
                ),
                "table": {
                    "headers": ["Adjustment", "Amount", "Rationale"],
                    "rows": [
                        ["Owner remuneration above market", "$35,000", "Replace with an arm's-length management cost"],
                        ["One-off legal costs", "$12,000", "Non-recurring legal expenditure"],
                        ["Normalised FY25 EBITDA", "$287,000", "Reported EBITDA plus confirmed adjustments"],
                    ],
                },
            },
            "balance_sheet_summary": {
                "narrative": (
                    "The balance sheet is shown for two reasons. First, it gives the reader context on the "
                    "reported asset, liability and net-asset position of the business. Secondly, it explains "
                    "how AccountIQ converts enterprise value, which values the operating business before "
                    "financing, into equity value, which is the value attributable to shareholders.\n\n"
                    "The sample business has $370,000 of current assets and $260,000 of current liabilities, "
                    "which supports the working-capital assumption used in the DCF. The operating asset base "
                    "is mainly accounts receivable, stock and fixed assets, while the main operating liability "
                    "is accounts payable. Net tangible operating assets are shown separately so the reader can "
                    "see the operating asset position before cash and interest-bearing loans are considered.\n\n"
                    "Reported net assets of $430,000 are materially below the $2.249 million midpoint equity "
                    "value because the valuation is based on maintainable cash flow rather than book value. "
                    "Net debt of $65,000 is deducted from enterprise value and no separately identified surplus "
                    "assets are added."
                ),
                "table": {
                    "headers": ["Balance sheet item", "Value", "Commentary / treatment"],
                    "rows": [
                        ["Cash and bank", "$95,000", "Available cash shown separately from operating assets and included in the equity bridge."],
                        ["Accounts receivable / trade debtors", "$210,000", "Customer receivables included in operating asset and NTOA context."],
                        ["Inventory / stock", "$65,000", "Stock on hand included in operating asset and NTOA context."],
                        ["Total current assets", "$370,000", "Uploaded balance sheet current-asset total; supports the working-capital context."],
                        ["Operating fixed assets", "$185,000", "Operating asset base shown for context; not used as a standalone asset valuation."],
                        ["Other non-current assets", "$295,000", "Other long-term assets shown for balance-sheet completeness."],
                        ["Total assets", "$850,000", "Reported asset base shown as financial-position context."],
                        ["Accounts payable / trade creditors", "$155,000", "Trade payables included in operating liability and NTOA context."],
                        ["Other current liabilities", "$45,000", "Other operating current liabilities included in NTOA context where extracted."],
                        ["Short-term loans / current borrowings", "$60,000", "Current interest-bearing borrowings included in the debt bridge."],
                        ["Total current liabilities", "$260,000", "Uploaded balance sheet current-liability total; supports the working-capital context."],
                        ["Long-term loans / borrowings", "$100,000", "Non-current interest-bearing borrowings included in the debt bridge."],
                        ["Other non-current liabilities", "$60,000", "Other long-term liabilities shown for balance-sheet completeness."],
                        ["Total liabilities", "$420,000", "Reported liability base shown as solvency and leverage context."],
                        ["Shareholders' equity / net assets", "$430,000", "Book equity is shown for context and reconciled separately from going-concern enterprise value."],
                        ["Net tangible operating assets (NTOA)", "$260,000", "Receivables, stock and fixed assets less accounts payable and other operating current liabilities, excluding cash and interest-bearing debt."],
                        ["Operating working capital", "$75,000", "Accounts receivable and stock less accounts payable and other operating current liabilities."],
                        ["Interest-bearing debt", "$160,000", "Borrowings deducted through the net-debt bridge."],
                        ["Net debt", "$65,000", "Interest-bearing debt less cash and bank."],
                        ["Surplus assets", "$0", "No separately identified surplus or non-operating assets in the sample case."],
                        ["Midpoint enterprise value", "$2,314,000", "Central DCF operating-business value after illiquidity adjustment."],
                        ["Less: net debt", "($65,000)", "Deducted to move from enterprise value to shareholder value."],
                        ["Add: surplus assets", "$0", "No surplus assets added in the sample case."],
                        ["Midpoint equity value", "$2,249,000", "Central shareholder-value indication after the bridge."],
                    ],
                },
            },
            "valuation_assumptions": {
                "narrative": (
                "## Earnings and forecast period\n"
                "The model uses normalised FY25 EBITDA of $287,000 and a five-year explicit forecast "
                "period. Revenue and maintainable earnings grow at 8.0% a year, derived from uploaded "
                "revenue history because management did not provide a specific short-term forecast.\n\n"
                    "## Long-term and reinvestment assumptions\n"
                    "A 2.5% terminal growth rate is anchored to long-run New Zealand inflation and remains "
                    "below every WACC scenario. The model applies the 28% New Zealand corporate tax rate. "
                    "Base depreciation of $25,000 is assumed to equal maintenance capital expenditure. "
                    "Operating working capital is modelled at 5.0% of revenue, so growth requires a corresponding "
                    "incremental cash investment.\n\n"
                    "## Ownership and customer context\n"
                    "Management has indicated that operational responsibility is shared, no single customer "
                    "represents more than 20% of revenue, and income is a mix of recurring and project work."
                ),
                "table": {
                    "headers": ["Assumption / input", "Value used", "Primary source", "Why it matters"],
                    "rows": [
                        ["Normalised EBITDA", "$287,000", "Uploaded financial statements plus management-confirmed earnings adjustments", "Sets the maintainable earnings base for DCF and multiples cross-checks."],
                        ["Explicit forecast period", "5 years", "AccountIQ valuation model convention", "Defines the period over which cash flows are forecast before terminal value."],
                        ["Revenue and earnings growth", "8.0%", "Uploaded revenue history: CAGR capped between -5% and 12%", "Drives the forecast cash-flow build and sensitivity matrix."],
                        ["Terminal growth", "2.5%", "Public research: New Zealand inflation input", "Anchors long-term growth and must remain below the discount rate."],
                        ["WACC scenarios: high / mid / low valuation", "9.9% / 11.5% / 13.4%", "Public research: RBNZ risk-free rate and Damodaran ERP/beta", "Discounts forecast cash flows and creates the valuation range."],
                        ["Maintenance capital expenditure", "$25,000", "Uploaded financial statements: depreciation proxy", "Converts EBITDA into free cash flow by allowing for asset reinvestment."],
                        ["Operating working capital ratio", "5.0%", "Uploaded balance sheet: operating working-capital line items", "Captures the cash investment required to support revenue growth."],
                        ["Debt, cash and surplus assets", "Debt $160,000; cash $95,000; surplus assets $0", "Debt: uploaded balance sheet borrowings where extracted; cash: uploaded balance sheet cash balance; surplus assets: no management-supplied amount identified", "Bridges enterprise value to indicative equity value."],
                        ["Owner or key-person dependency", "Responsibility is shared across leadership and team", "Management-confirmed private input", "Informs transition risk, key-person exposure and continuity planning."],
                        ["Largest-customer concentration", "10% to 25%", "Management-confirmed private input", "Highlights concentration risk that is not usually visible online."],
                        ["Revenue predictability", "A mix of recurring and one-off revenue", "Management-confirmed private input", "Distinguishes contracted revenue from transactional or project income."],
                        ["Revenue outlook", "No specific forecast provided; growth derived from uploaded financial history", "Management-confirmed private input", "Documents the short-term outlook used to support or derive the growth assumption."],
                    ],
                },
            },
            "wacc_assumptions": {
                "narrative": (
                    "The cost of capital was developed from current public data and adjusted for the "
                    "risk and illiquidity of a privately held New Zealand SME. The high valuation uses "
                    "the lowest WACC; the low valuation uses the highest WACC."
                ),
                "table": {
                    "headers": ["Component", "High valuation", "Mid valuation", "Low valuation"],
                    "rows": [
                        ["Risk-free rate", "4.4%", "4.4%", "4.4%"],
                        ["Equity risk premium", "5.6%", "5.9%", "6.2%"],
                        ["Industry total beta", "1.05", "1.20", "1.35"],
                        ["WACC", "9.9%", "11.5%", "13.4%"],
                        ["Illiquidity discount", "11.8%", "11.8%", "11.8%"],
                    ],
                },
            },
            "dcf_analysis": {
                "narrative": (
                    "Forecast free cash flows are discounted at the three WACC scenarios. Terminal value "
                    "uses the Gordon growth model and the 2.5% terminal growth rate remains below every "
                    "discount-rate scenario. FCFF is EBIT after tax plus depreciation, less maintenance "
                    "capital expenditure and change in operating working capital. The private-company "
                    "illiquidity adjustment is shown explicitly rather than embedded in an opaque final multiple."
                ),
                "table": {
                    "headers": ["DCF item", "High valuation", "Mid valuation", "Low valuation"],
                    "rows": [
                        ["WACC", "9.9%", "11.5%", "13.4%"],
                        ["Terminal growth", "2.5%", "2.5%", "2.5%"],
                        ["Base revenue", "$1,250,000", "$1,250,000", "$1,250,000"],
                        ["Normalised EBITDA", "$287,000", "$287,000", "$287,000"],
                        ["Base depreciation", "$25,000", "$25,000", "$25,000"],
                        ["Maintenance capex", "$25,000", "$25,000", "$25,000"],
                        ["Operating working capital / revenue", "5.0%", "5.0%", "5.0%"],
                        ["Enterprise value before illiquidity", "$3,209,000", "$2,624,000", "$2,152,000"],
                        ["Illiquidity discount", "11.8%", "11.8%", "11.8%"],
                        ["Adjusted enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"],
                    ],
                },
                "cash_flow_schedule": {
                    "headers": ["Mid-case forecast", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5"],
                    "rows": [
                        ["Revenue", "$1,350,000", "$1,458,000", "$1,574,640", "$1,700,611", "$1,836,660"],
                        ["EBITDA", "$309,960", "$334,757", "$361,537", "$390,460", "$421,697"],
                        ["EBIT", "$282,960", "$305,597", "$330,045", "$356,448", "$384,964"],
                        ["Tax", "$79,229", "$85,567", "$92,412", "$99,805", "$107,790"],
                        ["Maintenance capex", "$27,000", "$29,160", "$31,493", "$34,012", "$36,733"],
                        ["Change in operating working capital", "$5,000", "$5,400", "$5,832", "$6,299", "$6,802"],
                        ["Free cash flow to firm", "$198,731", "$214,630", "$231,800", "$250,344", "$270,372"],
                        ["Discounted free cash flow", "$178,234", "$172,639", "$167,220", "$161,971", "$156,887"],
                    ],
                },
            },
            "valuation_summary": {
                "narrative": (
                    "The low DCF case overlaps the upper end of the market cross-check, while the midpoint "
                    "DCF conclusion is higher at $2.31 million. This difference is driven by the assumed "
                    "cash-flow growth and should be considered explicitly rather than averaged away. The DCF "
                    "remains the primary conclusion and the multiple range is an independent check."
                ),
                "table": {
                    "headers": ["Method / scenario", "Input", "Enterprise value", "Adjusted EV", "Equity value"],
                    "rows": [
                        ["DCF - high valuation", "9.9% WACC", "$3,209,000", "$2,831,000", "$2,766,000"],
                        ["DCF - midpoint", "11.5% WACC", "$2,624,000", "$2,314,000", "$2,249,000"],
                        ["DCF - low valuation", "13.4% WACC", "$2,152,000", "$1,898,000", "$1,833,000"],
                        ["Multiples - low", "5.0x EBITDA", "$1,435,000", "$1,435,000", "$1,370,000"],
                        ["Multiples - midpoint", "6.0x EBITDA", "$1,722,000", "$1,722,000", "$1,657,000"],
                        ["Multiples - high", "7.0x EBITDA", "$2,009,000", "$2,009,000", "$1,944,000"],
                    ],
                },
            },
            "multiples_crosscheck": (
                {
                    "narrative": (
                        "Public benchmark evidence supports an indicative range of 5.0x to 7.0x normalised "
                        "EBITDA. The DCF midpoint implies a higher multiple than the 6.0x market midpoint, "
                        "so the cross-check is shown as a reasonableness tension rather than averaged into "
                        "the conclusion. The range is not a direct pricing promise because observed businesses "
                        "differ in scale, growth, customer mix, contract security and strategic value."
                    ),
                    "table": {
                        "headers": ["Input", "Low", "Mid", "High"],
                        "rows": [
                            ["EV/EBITDA multiple", "5.0x", "6.0x", "7.0x"],
                            ["Normalised EBITDA", "$287,000", "$287,000", "$287,000"],
                            ["Indicated enterprise value", "$1,435,000", "$1,722,000", "$2,009,000"],
                        ],
                    },
                }
            ),
            "sensitivity_and_risks": {
                "narrative": (
                    "## Quantified sensitivity\n"
                    "The 8.0% growth and 11.5% WACC midpoint is the base case. Across the matrix, adjusted "
                    "enterprise value ranges from $1.77 million at 6.0% growth and 13.4% WACC to $3.05 "
                    "million at 10.0% growth and 9.9% WACC.\n\n"
                    "## Business-specific matters\n"
                    "- Customer retention: although no single customer exceeds 20% of revenue, the aggregate "
                    "retention of repeat customers remains important.\n"
                    "- Revenue quality: mixed recurring and project income provides diversity but less certainty "
                    "than fully contracted revenue.\n"
                    "- Transition: shared management reduces key-person exposure, subject to confirming retention "
                    "and handover arrangements.\n"
                    "- Pipeline: unsigned opportunities have not been treated as contracted revenue.\n\n"
                    "The matrix quantifies WACC and growth only. The business-specific matters remain unquantified "
                    "and should be revisited if circumstances change before reliance or use."
                ),
                "table": {
                    "headers": [
                        "Growth assumption",
                        "High valuation / 9.9% WACC",
                        "Mid valuation / 11.5% WACC",
                        "Low valuation / 13.4% WACC",
                    ],
                    "rows": [
                        ["6.0%", "$2,621,000", "$2,147,000", "$1,765,000"],
                        ["8.0% - base", "$2,831,000", "$2,314,000", "$1,898,000"],
                        ["10.0%", "$3,054,000", "$2,492,000", "$2,040,000"],
                    ],
                },
                "specific_risk_factors": {
                    "headers": ["Specific risk factor", "Management input", "Valuation relevance", "Report treatment"],
                    "rows": [
                        ["Owner or key-person transition", "Responsibility is shared across leadership and team", "Affects operating continuity, handover depth and confidence in maintainable earnings.", "Moderate transition risk; diligence should confirm responsibilities and handover depth."],
                        ["Customer concentration", "10% to 25%", "Large customer exposure can increase earnings volatility and diligence risk.", "Moderate concentration risk; review top-customer retention and contract terms."],
                        ["Revenue predictability", "A mix of recurring and one-off revenue", "Contracted or recurring revenue usually supports more reliable cash-flow forecasts.", "Mixed recurring and project revenue creates moderate earnings visibility."],
                        ["Revenue outlook and pipeline", "No specific forecast provided; growth derived from uploaded financial history", "Growth expectations affect forecast cash flows and sensitivity cases.", "Growth is derived from uploaded history rather than a management forecast; review pipeline evidence before reliance."],
                        ["Other private context", "A key contract renews next year.", "Captures risks or opportunities not normally visible in public research.", "Management-supplied context should be confirmed and reflected in diligence, forecast cases or reliance limitations."],
                    ],
                },
            },
            "comparable_evidence": {
                "narrative": (
                    f"The evidence below is {comparable_context}. It is broad-sector evidence rather than a set of directly comparable private "
                    "transactions, so the observed range is used only as a reasonableness check."
                ),
                "table": {
                    "headers": ["Evidence", "Date", "Metric / multiple", "Relevance and limitation", "Source"],
                    "rows": [
                        [
                            "Business services sector dataset",
                            "Current dataset",
                            "EV/EBITDA benchmark",
                            "Broad listed-company evidence; larger and more liquid than the subject",
                            "Damodaran Online - https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
                        ],
                        [
                            "NZ private-company valuation context",
                            "Valuation date",
                            "Risk-free and inflation inputs",
                            "Supports discount-rate inputs, not a transaction multiple",
                            "Reserve Bank of New Zealand - https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
                        ],
                        [
                            "Subject company public profile",
                            "Valuation date",
                            "Operating and market context",
                            "Public profile information retained for company-fact corroboration",
                            "NZ Companies Office - https://companies-register.companiesoffice.govt.nz/",
                        ],
                    ],
                },
            },
            "sources": {
                "narrative": (
                    f"The following public sources support {sources_context} so the reader "
                    "can review the evidence trail behind the valuation assumptions."
                ),
                "table": {
                    "headers": ["Source", "URL", "Supports / used for"],
                    "rows": [
                        [
                            "Reserve Bank of New Zealand, interest rates",
                            "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
                            "Risk-free-rate and discount-rate context",
                        ],
                        [
                            "Reserve Bank of New Zealand, inflation",
                            "https://www.rbnz.govt.nz/monetary-policy/about-monetary-policy/inflation",
                            "Long-term inflation and terminal-growth context",
                        ],
                        [
                            "Damodaran Online, data resources",
                            "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
                            "Equity risk premium, beta and private-company valuation inputs",
                        ],
                        [
                            "NZ Companies Office",
                            "https://companies-register.companiesoffice.govt.nz/",
                            "Company public-profile corroboration",
                        ],
                    ],
                },
            },
            "disclaimer": (
                "## Indicative purpose and reliance\n"
                "This report is indicative only and has been prepared solely for the stated valuation "
                "purpose. It does not constitute financial advice and should not be relied upon as a "
                "substitute for independent professional, legal, tax or accounting advice. No responsibility "
                "is accepted to any third party who obtains or relies on this report.\n\n"
                "## Information and valuation date\n"
                "The analysis relies on management-supplied information, extracted financial records and "
                "identified public sources. Those inputs have not been independently audited. Conclusions "
                "may change if information is incomplete, inaccurate or circumstances change after the "
                "valuation date.\n\n"
                "## Regulatory context\n"
                "The report is prepared with regard to the Financial Markets Conduct Act (FMCA) context but "
                "is not a regulated product-disclosure statement, fairness opinion or assurance engagement."
            ),
            "general_principles": (
                "## Basis of value\n"
                "- A willing but not anxious buyer and a willing but not anxious seller.\n"
                "- An arm's-length transaction after proper marketing.\n"
                "- Both parties act knowledgeably, prudently and without compulsion.\n"
                "- The business continues as a going concern with assets used in their current operations.\n\n"
                "## Timing and information\n"
                "- Value is assessed at the stated valuation date and may change as markets, trading or "
                "capital costs change.\n"
                "- Forecasts are estimates, not guarantees, and depend on stated assumptions.\n"
                "- Buyer-specific synergies and unusual strategic premiums are excluded unless explicitly stated."
            ),
            "glossary": (
                "## Core valuation terms\n"
                "- DCF: Discounted cash flow. This method estimates value by forecasting the future cash flows the business is expected to generate and discounting those cash flows back to today's dollars. It is useful where the business is expected to continue trading and value is driven by future maintainable performance.\n"
                "- Enterprise value: The value of the operating business before allowing for its financing position. It excludes the effect of surplus cash, interest-bearing debt and separately identified non-operating assets so readers can assess the value of the business operations themselves.\n"
                "- Equity value: The value attributable to shareholders after the enterprise-value bridge. It starts with enterprise value, deducts interest-bearing debt, adds available cash and adds any separately identified surplus or non-operating assets.\n"
                "- EBITDA: Earnings before interest, tax, depreciation and amortisation. It is a common proxy for operating earnings before financing, tax and non-cash depreciation charges, but it is not the same as cash flow because it excludes capital expenditure and working-capital movements.\n"
                "- Maintainable earnings: The level of earnings considered sustainable for valuation purposes after removing unusual, one-off, owner-specific or non-operating items. Maintainable earnings should represent the earnings a market participant could reasonably expect from normal operations.\n"
                "- Normalisation: A valuation adjustment that converts reported earnings into maintainable earnings. Examples include adding back genuine one-off legal costs or adjusting owner remuneration to an arm's-length management cost.\n"
                "- Terminal value: The value attributed to cash flows beyond the explicit forecast period. In a DCF, it often represents a large portion of value, so the terminal growth assumption must be supportable and lower than the discount rate.\n"
                "- WACC: Weighted average cost of capital. It is the discount rate used to convert forecast cash flows into present value and reflects the return a market participant would require for the risk of investing in the business.\n"
                "- Illiquidity discount: An adjustment for the reduced marketability of a private-company interest compared with a listed security. It recognises that selling a private business interest can take longer, involve more diligence and attract a smaller buyer pool.\n"
                "- FMCA: The Financial Markets Conduct Act 2013. The report refers to this regulatory context to make clear that the output is indicative valuation support, not a regulated product-disclosure statement, fairness opinion or substitute for independent professional advice."
            ),
        }
        return {section: sample.get(section, "") for section in sections}

    content = {}
    for section in sections:
        title = section.replace("_", " ").title()
        if section == "disclaimer":
            content[section] = (
                "This report is indicative only, is not financial advice, "
                "is not regulated advice under the FMCA, and should not be relied "
                "on without independent professional advice."
            )
        elif section in set(TABLE_SECTIONS_VALUATION + TABLE_SECTIONS_BANK_CREDIT):
            content[section] = {
                "narrative": f"E2E generated {title} with <script>escaped text</script> for safety checks.",
                "table": {
                    "headers": ["Metric", "Value"],
                    "rows": [["Revenue", "$1,250,000"], ["EBITDA", "$240,000"]],
                },
            }
            if report_type == "bank_credit_paper" and section == "coverage_and_sensitivity":
                content[section]["amortisation_profile_table"] = {
                    "headers": ["Year", "Opening debt", "Closing debt"],
                    "rows": [["Year 1", "$250,000", "$200,000"]],
                }
            if report_type == "bank_credit_paper" and section == "balance_sheet_debt_capacity":
                content[section]["debt_capacity_table"] = {
                    "headers": ["Constraint", "Supportable debt", "Basis"],
                    "rows": [["Illustrative coverage constraint", "$250,000", "E2E test data"]],
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
    """Extract company name from page 1 of a PDF via OpenAI. Returns empty string on failure."""
    try:
        import pdfplumber
        from openai import OpenAI
        with pdfplumber.open(filepath) as pdf:
            if not pdf.pages:
                return ""
            page1_text = pdf.pages[0].extract_text(x_tolerance=2, y_tolerance=3) or ""
        if not page1_text.strip():
            return ""
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return ""
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-5.4-mini"),
            max_output_tokens=64,
            input=(
                "Extract the company or entity name from this financial document cover page. "
                "Reply with ONLY the company name — no explanation, no punctuation.\n\n"
                f"{page1_text[:2000]}"
            ),
        )
        name = str(getattr(response, "output_text", "") or "").strip()
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
            # Extract company name from PDF page 1 via OpenAI when configured.
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
                    (document_id, "Demo ingestion shortcut started"),
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
                        narrative='Demo-mode sample extraction completed. Figures are simulated and not for reliance.',
                        reporting_standard='Demo',
                        updated_at=datetime('now')
                    WHERE id=?
                    """,
                    (document_id,),
                )
                await db.execute(
                    "INSERT INTO extraction_log (document_id, level, message) VALUES (?, 'info', ?)",
                    (document_id, "Demo ingestion shortcut completed"),
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
    key = os.environ.get("OPENAI_API_KEY", "")
    live_key_configured = _live_openai_key_configured()
    import ingestion as ing
    return {
        "demo_mode": _demo_mode_enabled(),
        "demo_mode_configured": _env_flag("ACCOUNTIQ_DEMO_MODE"),
        "demo_mode_forced": E2E_MODE,
        "api_key_set": live_key_configured,
        "report_generation_mode": _report_generation_mode(),
        "evidence_mode_available": True,
        "api_key_preview": (
            (key[:12] + "…" + key[-4:]) if len(key) > 20 else "set"
        ) if live_key_configured else "",
        "openai_model": os.environ.get("OPENAI_MODEL") or ing.OPENAI_MODEL,
        "env_file": str(ENV_PATH),
    }


@app.post("/settings")
async def update_settings(
    api_key:      str = Form(None),
    openai_model: str = Form(None),
    demo_mode: Optional[str] = Form(None),
    current_user: dict = Depends(require_admin),
):
    """Persist settings to .env and reload into the running process."""
    import ingestion as ing

    msg_parts: list[str] = []

    if demo_mode is not None:
        demo_enabled = str(demo_mode).strip().lower() in _TRUE_ENV_VALUES
        demo_value = "true" if demo_enabled else "false"
        set_key(str(ENV_PATH), "ACCOUNTIQ_DEMO_MODE", demo_value)
        os.environ["ACCOUNTIQ_DEMO_MODE"] = demo_value
        msg_parts.append(f"Demo mode {'enabled' if demo_enabled else 'disabled'}.")

    if api_key and api_key.startswith("sk-"):
        set_key(str(ENV_PATH), "OPENAI_API_KEY", api_key)
        os.environ["OPENAI_API_KEY"] = api_key
        ing.OPENAI_API_KEY = api_key
        msg_parts.append("API key saved.")
    elif api_key:
        raise HTTPException(400, "Key must start with sk-")

    if openai_model:
        set_key(str(ENV_PATH), "OPENAI_MODEL", openai_model)
        os.environ["OPENAI_MODEL"] = openai_model
        ing.OPENAI_MODEL = openai_model
        msg_parts.append(f"Model set to {openai_model}.")

    return {"ok": True, "message": " ".join(msg_parts) if msg_parts else "No settings changed."}


@app.post("/settings/ai-connection/check")
async def check_ai_connection(current_user: dict = Depends(require_admin)):
    """Verify whether AccountIQ can use the configured live AI research connection."""
    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")

    if _demo_mode_enabled():
        return {
            "ok": True,
            "status": "demo_mode",
            "message": (
                "Demo mode is active, so live AI research was not checked. "
                "You can continue testing the valuation journey without an OpenAI key."
            ),
            "model": model,
            "demo_mode": True,
            "api_key_set": _live_openai_key_configured(),
        }

    if not _live_openai_key_configured():
        return {
            "ok": True,
            "status": "evidence_mode",
            "message": (
                "Live AI research is not configured. AccountIQ can still extract uploaded accounts with the "
                "rule-based reader and generate evidence-mode reports from approved public URLs without an OpenAI key."
            ),
            "model": model,
            "demo_mode": False,
            "api_key_set": False,
        }

    api_key = os.environ.get("OPENAI_API_KEY", "")
    try:
        fresh_check = await _run_live_research_preflight(api_key, model)
    except Exception as exc:
        print(f"[REPORT] Admin AI connection check failed: {type(exc).__name__}: {exc}")
        return {
            "ok": False,
            "status": "failed",
            "message": (
                "Live AI research could not be verified. Check the OpenAI key, selected model "
                "and whether the account has access to the required web-search tools."
            ),
            "model": model,
            "demo_mode": False,
            "api_key_set": True,
        }

    return {
        "ok": True,
        "status": "verified",
        "message": (
            "Live AI research is verified. Valuation reports can use online market evidence "
            "with the configured model."
        ),
        "model": model,
        "demo_mode": False,
        "api_key_set": True,
        "cached": not fresh_check,
    }


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
    files: Optional[list[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),   # NOT require_admin — per D-05
):
    """Create company + upload one or more documents for non-admin users."""
    name = business_name.strip()
    if not name:
        raise HTTPException(400, "Business name is required")

    upload_files: list[UploadFile] = []
    if file is not None:
        upload_files.append(file)
    if files:
        upload_files.extend(files)
    upload_files = [upload for upload in upload_files if upload and upload.filename]
    if not upload_files:
        raise HTTPException(400, "Please upload at least one financial statement file.")
    if len(upload_files) > MAX_WIZARD_UPLOAD_FILES:
        raise HTTPException(
            400,
            f"You can upload up to {MAX_WIZARD_UPLOAD_FILES} financial statement files at a time.",
        )

    # Idempotent company creation — reuses existing helper (D-06)
    company_id, _ = await _resolve_or_create_company(db, name, current_user["id"])

    # Save file into company directory (project security rule: Path(file.filename).name)
    company_dir = PDF_DIR / str(company_id)
    company_dir.mkdir(exist_ok=True)

    document_ids: list[int] = []
    filenames: list[str] = []
    used_names: set[str] = set()
    for upload in upload_files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in ALLOWED_FINANCIAL_UPLOAD_SUFFIXES:
            raise HTTPException(
                400,
                f"Only PDF, Excel, and Word files are accepted. Got: {suffix or 'unknown'}",
            )

        base_name = Path(upload.filename or "financial-statement").name
        safe_name = base_name
        if safe_name in used_names:
            stem = Path(base_name).stem
            ext = Path(base_name).suffix
            copy_index = 2
            while safe_name in used_names:
                safe_name = f"{stem}-{copy_index}{ext}"
                copy_index += 1
        used_names.add(safe_name)
        dest = company_dir / safe_name
        with open(dest, "wb") as f:
            shutil.copyfileobj(upload.file, f)

        # Insert document record — handle re-upload of same filename gracefully.
        try:
            async with db.execute("""
                INSERT INTO documents
                    (company_id, filename, filepath, report_type, entity_type, fiscal_year_end, user_id)
                VALUES (?, ?, ?, 'compilation', 'sme', '', ?)
            """, (company_id, safe_name, str(dest), current_user["id"])) as cur:
                document_id = cur.lastrowid
            await db.commit()
        except sqlite3.IntegrityError:
            async with db.execute(
                "SELECT id FROM documents WHERE filepath=? AND user_id=?",
                (str(dest), current_user["id"]),
            ) as cur:
                row = await cur.fetchone()
            if row is None:
                raise HTTPException(500, "Failed to locate existing document record")
            document_id = int(row[0])
            await db.execute(
                """
                UPDATE documents
                SET extraction_status='pending',
                    confidence_score=NULL,
                    raw_provider_response=NULL,
                    narrative=NULL,
                    updated_at=datetime('now')
                WHERE id=? AND user_id=?
                """,
                (document_id, current_user["id"]),
            )
            await db.execute("DELETE FROM financial_rows WHERE document_id=?", (document_id,))
            await db.execute("DELETE FROM extraction_log WHERE document_id=?", (document_id,))
            await db.commit()

        document_ids.append(document_id)
        filenames.append(safe_name)

        # Kick off background ingestion — same task as admin upload (D-06)
        background_tasks.add_task(
            _run_ingestion, document_id, company_id, str(dest), "sme", "Private", ""
        )

    return {
        "company_id": company_id,
        "document_id": document_ids[-1],
        "document_ids": document_ids,
        "filenames": filenames,
        "status": "processing",
        "demo_mode": _demo_mode_enabled(),
    }


@app.get("/wizard/document/{document_id}/status")
async def wizard_document_status(
    document_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return a customer-safe ingestion status for a wizard upload."""
    async with db.execute(
        """
        SELECT id, company_id, filename, extraction_status, confidence_score, updated_at
        FROM documents
        WHERE id=? AND user_id=?
        """,
        (document_id, current_user["id"]),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Document not found")

    status = row["extraction_status"] or "pending"
    messages = {
        "pending": "Your file is waiting to be processed.",
        "processing": "We are reading the financial statements and checking the extracted figures.",
        "done": "Your financial statements are ready.",
        "failed": "We could not read this file reliably. Please upload a clearer or complete copy.",
    }
    return {
        **dict(row),
        "extraction_status": status,
        "message": messages.get(status, "Your financial statements are being processed."),
        "demo_mode": _demo_mode_enabled(),
    }


@app.post("/wizard/financial-review")
async def wizard_financial_review(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return the selected-file reconciliation before report questions begin."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Request body must be valid JSON")

    company_id = body.get("company_id")
    source_document_ids = _normalise_source_document_ids(body.get("source_document_ids"))
    overrides = _normalise_financial_reconciliation_overrides(
        body.get("financial_reconciliation_overrides")
    )
    if not isinstance(company_id, int) or company_id <= 0:
        raise HTTPException(400, "company_id must be a positive integer")
    if not source_document_ids:
        raise HTTPException(400, "source_document_ids must include at least one financial statement")

    resolved_document_ids, _ = await _generation_source_documents(
        db,
        company_id=company_id,
        user_id=current_user["id"],
        source_document_ids=source_document_ids,
    )
    reconciliation = await _reconcile_selected_financials(
        db,
        company_id=company_id,
        user_id=current_user["id"],
        source_document_ids=resolved_document_ids,
        overrides=overrides,
    )
    valuation_readiness = assess_valuation_financial_readiness(reconciliation["rows"])
    credit_readiness = assess_credit_financial_readiness(reconciliation["rows"])
    return {
        "document_ids": resolved_document_ids,
        **reconciliation,
        "readiness": {
            "valuation_advisory": {
                **valuation_readiness,
                "follow_up_items": report_follow_up_items(
                    valuation_readiness,
                    credit_readiness,
                )["valuation_advisory"],
            },
            "bank_credit_paper": credit_readiness,
        },
    }


# ---------------------------------------------------------------------------
# Wizard — report generation (Phase 5)
# ---------------------------------------------------------------------------

# Valid report types (match REPORT_TYPE_LABELS keys in report_email.py)
_VALID_REPORT_TYPES = frozenset(REPORT_TYPE_LABELS.keys())
_SELF_SERVE_REPORT_TYPES = frozenset({"valuation_advisory", "bank_credit_paper"})

_VALUATION_REQUIRED_OPTIONS = {
    "valuation_purpose": {
        "understand_value",
        "sale_or_transaction",
        "shareholder_or_employee_scheme",
        "succession_planning",
        "finance_or_investment",
        "other",
    },
    "owner_dependency": {"independent", "shared", "important", "critical", "unknown"},
    "customer_concentration": {
        "under_10",
        "10_to_25",
        "over_25",
        "consumer_or_diversified",
        "unknown",
    },
    "revenue_quality": {"mostly_contract", "mixed", "mostly_one_off", "unknown"},
    "revenue_outlook": {"lower", "steady", "modest_growth", "strong_growth", "not_sure"},
}
_VALUATION_OPTIONAL_INTAKE_FIELDS = frozenset(
    {
        "company_website",
        "company_location",
        "public_source_urls",
        "private_context",
        "business_address",
        "instructing_party",
        "valuation_date",
        "source_information",
        "operations_and_services",
        "forecast_pipeline_evidence",
        "premises_and_lease",
        "management_continuity",
        "normalisations",
        "replacement_manager_cost",
        "debt_override",
        "surplus_assets",
        "custom_growth_rate",
    }
)
_VALUATION_REQUIRED_FIELD_LABELS = {
    "valuation_purpose": "Purpose",
    "owner_dependency": "Owner or key-person dependency",
    "customer_concentration": "Largest customer",
    "revenue_quality": "Revenue predictability",
    "revenue_outlook": "Revenue outlook",
}
_VALUATION_OPTIONAL_FIELD_LABELS = {
    "replacement_manager_cost": "Replacement manager cost",
    "debt_override": "Interest-bearing debt at valuation date",
    "surplus_assets": "Surplus or non-operating assets",
    "custom_growth_rate": "Specific supported annual revenue growth",
    "business_address": "Business / premises address",
    "instructing_party": "Instructing party / intended recipient",
    "valuation_date": "Preferred valuation date",
    "source_information": "Source inventory",
    "operations_and_services": "Operations and services",
    "forecast_pipeline_evidence": "Forecast / pipeline support",
    "premises_and_lease": "Premises / lease context",
    "management_continuity": "Management continuity",
}

_BANK_CREDIT_SECURITY_OPTIONS = {
    "general_security",
    "fleet",
    "property",
    "fleet_and_property",
    "general_security_and_guarantee",
    "unsecured",
    "other",
}
_BANK_CREDIT_REPAYMENT_PROFILES = {
    "principal_and_interest",
    "interest_only",
    "interest_only_then_amortising",
}
_BANK_CREDIT_REQUIRED_FIELD_LABELS = {
    "loan_purpose": "loan purpose",
    "amount_requested": "facility amount requested",
    "proposed_term_years": "term of debt",
    "conservative_funding_cost_pct": "conservative funding cost",
    "lvr_percent": "LVR or advance-rate assumption",
    "security_package": "security package",
    "repayment_profile": "repayment profile",
}
_BANK_CREDIT_OPTIONAL_FIELDS = frozenset(
    {
        "company_website",
        "company_location",
        "public_source_urls",
        "borrower_structure",
        "transaction_structure",
        "ownership_and_sponsor",
        "acquisition_rationale",
        "refinance_context",
        "facility_type",
        "facility_structure",
        "private_credit_context",
        "security_value",
        "security_notes",
        "source_of_repayment",
        "transaction_value",
        "transaction_costs",
        "equity_contribution",
        "working_capital_buffer",
        "sponsor_bridge_amount",
        "sponsor_bridge_term_months",
        "sponsor_bridge_repayment_source",
        "security_structure",
        "sponsor_bridge_security",
        "refinance_amount",
        "transaction_fees",
        "existing_debt_to_refinance",
        "minimum_dscr",
        "minimum_interest_cover",
        "maximum_senior_leverage",
        "covenant_package_level",
        "selected_covenants",
        "covenant_package_notes",
    }
)


def _valuation_intake_field_label(field: str) -> str:
    """Return a user-facing label for valuation intake validation messages."""
    return (
        _VALUATION_REQUIRED_FIELD_LABELS.get(field)
        or _VALUATION_OPTIONAL_FIELD_LABELS.get(field)
        or field.replace("_", " ")
    )


def _valuation_intake_value_supplied(value: object) -> bool:
    """Return whether an intake value was meaningfully supplied by the caller."""
    if value in (None, ""):
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _normalise_optional_public_url(value: object, field_label: str) -> str:
    """Accept friendly URL entry while keeping research hints bounded and safe."""
    if value in (None, ""):
        return ""
    url = str(value).strip()
    if not url:
        return ""
    if len(url) > 2048:
        raise HTTPException(422, f"{field_label} is too long")
    if "://" not in url:
        url = f"https://{url}"
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or any(ch.isspace() for ch in url)
        or not parsed.hostname
    ):
        raise HTTPException(422, f"{field_label} must be a valid http or https URL")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise HTTPException(422, f"{field_label} must be a public http or https URL")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        ip = None
    if ip and (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise HTTPException(422, f"{field_label} must be a public http or https URL")
    if "." not in host:
        raise HTTPException(422, f"{field_label} must be a valid http or https URL")
    return url.rstrip("/")


def _normalise_public_source_urls(value: object) -> list[str]:
    """Normalise optional pasted source links into a short de-duplicated URL list."""
    if value in (None, ""):
        return []
    if isinstance(value, str):
        candidates = re.split(r"[\n,]+", value)
    elif isinstance(value, list):
        candidates = [str(item) for item in value]
    else:
        raise HTTPException(422, "public source URLs must be text or a list of URLs")

    urls: list[str] = []
    seen: set[str] = set()
    for index, candidate in enumerate(candidates, start=1):
        normalised = _normalise_optional_public_url(candidate, f"public source URL {index}")
        if not normalised or normalised in seen:
            continue
        urls.append(normalised)
        seen.add(normalised)

    if len(urls) > 10:
        raise HTTPException(422, "public source URLs cannot contain more than 10 links")
    return urls


def _require_evidence_mode_source_hints(intake_answers: dict) -> None:
    """Require a bounded public-source scope for no-provider business research.

    Evidence mode is deliberately not an unrestricted crawler.  Requiring one
    approved company website or public URL gives the user control over what is
    fetched, keeps the report's source trail reviewable, and prevents a report
    from claiming it researched a business when it had no public source at all.
    """
    website = str(intake_answers.get("company_website") or "").strip()
    source_urls = intake_answers.get("public_source_urls") or []
    if website or source_urls:
        return
    raise HTTPException(
        422,
        "Add the business website or at least one public source URL so AccountIQ can collect source-backed business context without an AI provider.",
    )


def _normalise_optional_company_location(value: object) -> str:
    """Normalise the optional location hint used for public-source matching."""
    if value in (None, ""):
        return ""
    location = re.sub(r"\s+", " ", str(value)).strip()
    if not location:
        return ""
    if len(location) > 120:
        raise HTTPException(422, "company location is too long")
    if any(ord(char) < 32 for char in location):
        raise HTTPException(422, "company location contains invalid characters")
    return location


def _normalise_optional_private_context(value: object) -> str:
    """Keep optional private valuation context concise, safe and report-ready."""
    if value in (None, ""):
        return ""
    raw = str(value)
    if any(ord(char) < 32 and not char.isspace() for char in raw):
        raise HTTPException(422, "private context contains invalid characters")
    context = re.sub(r"\s+", " ", raw).strip()
    if not context:
        return ""
    if len(context) > 1200:
        raise HTTPException(422, "private context is too long")
    return context


def _normalise_optional_credit_context(
    value: object,
    field_label: str,
    *,
    max_chars: int,
) -> str:
    """Keep optional credit-paper text concise, safe and report-ready."""
    if value in (None, ""):
        return ""
    raw = str(value)
    if any(ord(char) < 32 and not char.isspace() for char in raw):
        raise HTTPException(422, f"{field_label} contains invalid characters")
    text = re.sub(r"\s+", " ", raw).strip()
    if not text:
        return ""
    if len(text) > max_chars:
        raise HTTPException(422, f"{field_label} is too long")
    return text


def _normalise_bank_credit_covenant_intake(answers: dict) -> None:
    """Normalise covenant package selections in-place."""
    package_level = str(answers.get("covenant_package_level") or "balanced").strip() or "balanced"
    if package_level not in BANK_CREDIT_COVENANT_PACKAGE_DEFAULTS:
        raise HTTPException(422, "Please choose one of the available covenant-package options.")
    answers["covenant_package_level"] = package_level

    raw_selection = answers.get("selected_covenants")
    if raw_selection in (None, ""):
        answers["selected_covenants"] = list(BANK_CREDIT_COVENANT_PACKAGE_DEFAULTS[package_level])
    elif isinstance(raw_selection, str):
        answers["selected_covenants"] = [
            item.strip()
            for item in re.split(r"[\n,]+", raw_selection)
            if item.strip()
        ]
    elif isinstance(raw_selection, list):
        answers["selected_covenants"] = [str(item).strip() for item in raw_selection if str(item).strip()]
    else:
        raise HTTPException(422, "selected covenants must be a list or comma-separated text")

    if not answers["selected_covenants"]:
        raise HTTPException(422, "Please choose at least one covenant or lender control.")
    if len(answers["selected_covenants"]) > len(BANK_CREDIT_COVENANT_DEFINITIONS):
        raise HTTPException(422, "Too many covenant selections were supplied.")

    unknown = [
        key
        for key in answers["selected_covenants"]
        if key not in BANK_CREDIT_COVENANT_DEFINITIONS
    ]
    if unknown:
        raise HTTPException(422, "Unknown covenant selection: " + ", ".join(sorted(set(unknown))))

    deduped: list[str] = []
    seen: set[str] = set()
    for key in answers["selected_covenants"]:
        if key in seen:
            continue
        deduped.append(key)
        seen.add(key)
    answers["selected_covenants"] = deduped

    notes = _normalise_optional_credit_context(
        answers.get("covenant_package_notes"),
        "covenant notes",
        max_chars=500,
    )
    if notes:
        answers["covenant_package_notes"] = notes
    elif "covenant_package_notes" in answers:
        answers["covenant_package_notes"] = ""


def _normalise_positive_credit_number(
    answers: dict,
    field: str,
    label: str,
    *,
    min_value: float = 0.0,
    max_value: float | None = None,
    required: bool = True,
) -> None:
    """Normalise numeric credit intake fields in-place."""
    value = answers.get(field)
    if value in (None, ""):
        if required:
            raise HTTPException(422, f"Please provide {label}.")
        return
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise HTTPException(422, f"{label} must be a number")
    if not math.isfinite(number) or number <= min_value:
        if min_value == 0:
            raise HTTPException(422, f"{label} must be greater than zero")
        raise HTTPException(422, f"{label} must be greater than {min_value:g}")
    if max_value is not None and number > max_value:
        raise HTTPException(422, f"{label} must be no more than {max_value:g}")
    answers[field] = number


def _validate_bank_credit_intake_answers(answers: dict) -> None:
    """Validate the focused lender questions required for Bank Credit Paper."""
    missing = [
        label
        for field, label in _BANK_CREDIT_REQUIRED_FIELD_LABELS.items()
        if not str(answers.get(field, "")).strip()
    ]
    if missing:
        raise HTTPException(
            422,
            "Please complete the required credit-paper questions. Missing: " + ", ".join(missing),
        )

    loan_purpose = _normalise_optional_credit_context(
        answers.get("loan_purpose"),
        "loan purpose",
        max_chars=300,
    )
    if not loan_purpose:
        raise HTTPException(422, "Please provide a loan purpose.")
    answers["loan_purpose"] = loan_purpose

    _normalise_positive_credit_number(
        answers,
        "amount_requested",
        "facility amount requested",
        max_value=1_000_000_000,
    )
    _normalise_positive_credit_number(
        answers,
        "proposed_term_years",
        "term of debt",
        max_value=30,
    )
    _normalise_positive_credit_number(
        answers,
        "conservative_funding_cost_pct",
        "conservative funding cost",
        max_value=30,
    )
    _normalise_positive_credit_number(
        answers,
        "lvr_percent",
        "LVR or advance-rate assumption",
        max_value=100,
    )

    security_package = str(answers.get("security_package") or "").strip()
    if security_package not in _BANK_CREDIT_SECURITY_OPTIONS:
        raise HTTPException(422, "Please choose one of the available security-package answers.")
    answers["security_package"] = security_package

    repayment_profile = str(answers.get("repayment_profile") or "").strip()
    if repayment_profile not in _BANK_CREDIT_REPAYMENT_PROFILES:
        raise HTTPException(422, "Please choose one of the available repayment-profile answers.")
    answers["repayment_profile"] = repayment_profile
    _normalise_bank_credit_covenant_intake(answers)

    for field, label, max_value in (
        ("security_value", "security value", 1_000_000_000),
        ("transaction_value", "purchase price or asset value", 1_000_000_000),
        ("transaction_costs", "transaction costs", 100_000_000),
        ("equity_contribution", "equity contribution", 1_000_000_000),
        ("working_capital_buffer", "working-capital buffer", 100_000_000),
        ("sponsor_bridge_amount", "additional bridge amount", 1_000_000_000),
        ("sponsor_bridge_term_months", "bridge term", 60),
        ("refinance_amount", "refinance amount", 1_000_000_000),
        ("transaction_fees", "transaction fees", 100_000_000),
        ("existing_debt_to_refinance", "existing debt to refinance", 1_000_000_000),
        ("minimum_dscr", "minimum DSCR", 10),
        ("minimum_interest_cover", "minimum interest cover", 20),
        ("maximum_senior_leverage", "maximum senior leverage", 20),
    ):
        _normalise_positive_credit_number(
            answers,
            field,
            label,
            max_value=max_value,
            required=False,
        )

    company_website = _normalise_optional_public_url(
        answers.get("company_website"),
        "company website",
    )
    if company_website:
        answers["company_website"] = company_website
    elif "company_website" in answers:
        answers["company_website"] = ""
    answers["public_source_urls"] = _normalise_public_source_urls(
        answers.get("public_source_urls")
    )
    company_location = _normalise_optional_company_location(
        answers.get("company_location")
    )
    if company_location:
        answers["company_location"] = company_location
    elif "company_location" in answers:
        answers["company_location"] = ""

    for field, label, max_chars in (
        ("borrower_structure", "borrower structure", 300),
        ("facility_type", "facility type", 160),
        ("private_credit_context", "credit context", 1200),
        ("security_notes", "security notes", 600),
        ("source_of_repayment", "source of repayment", 500),
        ("sponsor_bridge_repayment_source", "bridge repayment source", 500),
        ("transaction_structure", "transaction / group structure", 1000),
        ("ownership_and_sponsor", "ownership and sponsor context", 800),
        ("acquisition_rationale", "acquisition rationale", 1000),
        ("refinance_context", "existing debt / refinance context", 800),
        ("facility_structure", "facility structure", 800),
        ("security_structure", "security and guarantee structure", 800),
        ("sponsor_bridge_security", "sponsor bridge security", 600),
    ):
        text = _normalise_optional_credit_context(
            answers.get(field),
            label,
            max_chars=max_chars,
        )
        if text:
            answers[field] = text
        elif field in answers:
            answers[field] = ""

    allowed_fields = set(_BANK_CREDIT_REQUIRED_FIELD_LABELS) | set(_BANK_CREDIT_OPTIONAL_FIELDS)
    unsupported_fields = sorted(
        field
        for field, value in answers.items()
        if field not in allowed_fields and _valuation_intake_value_supplied(value)
    )
    if unsupported_fields:
        raise HTTPException(
            422,
            "AccountIQ uses a focused credit-paper intake: public-source hints, loan purpose, "
            "facility amount, LVR, term, funding cost and security. Remove unsupported credit fields: "
            + ", ".join(unsupported_fields),
        )


def _normalise_normalisation_text(
    value: object,
    *,
    field_label: str,
    max_chars: int,
    required: bool = False,
) -> str:
    """Keep earnings-review text concise before it is stored or used in reports."""
    raw = str(value or "")
    if any(ord(char) < 32 and not char.isspace() for char in raw):
        raise HTTPException(422, f"{field_label} contains invalid characters")
    text = re.sub(r"\s+", " ", raw).strip()
    if required and not text:
        raise HTTPException(422, f"{field_label} is required")
    if len(text) > max_chars:
        raise HTTPException(422, f"{field_label} is too long")
    return text


def _blank_normalisation_row(item: dict) -> bool:
    """Return whether an earnings-review row contains no user-supplied adjustment."""
    label = str(item.get("label", "") or "").strip()
    rationale = str(item.get("rationale", "") or "").strip()
    amount = item.get("amount", "")
    amount_blank = amount is None or (isinstance(amount, str) and not amount.strip())
    return not label and not rationale and amount_blank


def _validate_valuation_intake_answers(answers: dict) -> None:
    """Enforce the same short, material valuation intake at the API boundary."""
    missing = [
        _valuation_intake_field_label(field)
        for field in _VALUATION_REQUIRED_OPTIONS
        if not str(answers.get(field, "")).strip()
    ]
    if missing:
        raise HTTPException(
            422,
            "Please complete the five required valuation answers. Missing: " + ", ".join(missing),
        )

    invalid = [
        _valuation_intake_field_label(field)
        for field, allowed in _VALUATION_REQUIRED_OPTIONS.items()
        if answers.get(field) not in allowed
    ]
    if invalid:
        raise HTTPException(422, "Please choose one of the available answers for: " + ", ".join(invalid))

    legacy_questionnaire_fields = sorted(
        field for field, value in answers.items()
        if field.startswith("rq_") and value not in (None, "")
    )
    if legacy_questionnaire_fields:
        raise HTTPException(
            422,
            "AccountIQ uses five private valuation answers plus the earnings review; "
            "older detailed scoring fields are not used in this short valuation intake. "
            "Please refresh the wizard answers or remove: "
            + ", ".join(legacy_questionnaire_fields),
        )

    for field in ("replacement_manager_cost", "debt_override", "surplus_assets"):
        value = answers.get(field)
        if value in (None, ""):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise HTTPException(422, f"{_valuation_intake_field_label(field)} must be a number")
        if not math.isfinite(number) or number < 0:
            raise HTTPException(422, f"{_valuation_intake_field_label(field)} must be zero or greater")

    custom_growth = answers.get("custom_growth_rate")
    if custom_growth not in (None, ""):
        try:
            growth_number = float(custom_growth)
        except (TypeError, ValueError):
            raise HTTPException(422, "supported revenue-growth view must be a number")
        if not math.isfinite(growth_number) or not -50 <= growth_number <= 100:
            raise HTTPException(422, "supported revenue-growth view must be between -50 and 100")

    derived_assumption_fields = {
        "forecast_horizon": "forecast horizon",
        "forecast_period": "forecast period",
        "explicit_forecast_period": "explicit forecast period",
        "terminal_growth_rate": "terminal growth rate",
        "terminal_growth": "terminal growth",
        "terminal_growth_pct": "terminal growth",
        "terminal_growth_percent": "terminal growth",
        "wacc": "WACC",
        "wacc_pct": "WACC",
        "wacc_rate": "WACC",
        "wacc_assumption": "WACC",
        "discount_rate": "discount rate",
        "discount_rate_pct": "discount rate",
        "discount_rate_percent": "discount rate",
        "cost_of_capital": "cost of capital",
        "cost_of_equity": "cost of equity",
        "risk_free_rate": "risk-free rate",
        "risk_free_rate_pct": "risk-free rate",
        "equity_risk_premium": "equity risk premium",
        "erp": "equity risk premium",
        "beta": "industry beta",
        "industry_beta": "industry beta",
        "illiquidity_discount": "illiquidity discount",
        "illiquidity_discount_rate": "illiquidity discount",
        "revenue_growth_rate": "revenue growth rate",
        "revenue_growth_rate_pct": "revenue growth rate",
        "forecast_years": "forecast years",
    }

    def _derived_assumption_label(field: str) -> Optional[str]:
        if field in derived_assumption_fields:
            return derived_assumption_fields[field]

        normalised_field = re.sub(r"[^a-z0-9]+", "_", str(field).lower()).strip("_")
        tokens = {token for token in normalised_field.split("_") if token}

        if "wacc" in tokens:
            return "WACC"
        if {"discount", "rate"}.issubset(tokens):
            return "discount rate"
        if {"terminal", "growth"}.issubset(tokens):
            return "terminal growth"
        if {"forecast", "horizon"}.issubset(tokens):
            return "forecast horizon"
        if "forecast" in tokens and ({"period"} & tokens or {"years"} & tokens):
            return "forecast period"
        if "riskfree" in tokens or {"risk", "free"}.issubset(tokens):
            return "risk-free rate"
        if "erp" in tokens or {"equity", "risk", "premium"}.issubset(tokens):
            return "equity risk premium"
        if "beta" in tokens:
            return "industry beta"
        if {"illiquidity", "discount"}.issubset(tokens):
            return "illiquidity discount"
        if {"cost", "capital"}.issubset(tokens):
            return "cost of capital"
        if {"cost", "equity"}.issubset(tokens):
            return "cost of equity"
        if {"revenue", "growth", "rate"}.issubset(tokens):
            return "revenue growth rate"
        return None

    supplied_derived_fields = list(
        dict.fromkeys(
            label
            for field, value in answers.items()
            if value not in (None, "") and (label := _derived_assumption_label(field))
        )
    )
    if supplied_derived_fields:
        raise HTTPException(
            422,
            "AccountIQ derives technical valuation assumptions instead of asking the user "
            "to choose them. Remove: " + ", ".join(supplied_derived_fields),
        )

    allowed_fields = (
        set(_VALUATION_REQUIRED_OPTIONS)
        | set(_VALUATION_OPTIONAL_INTAKE_FIELDS)
        | set(derived_assumption_fields)
    )
    unsupported_fields = sorted(
        field
        for field, value in answers.items()
        if field not in allowed_fields and _valuation_intake_value_supplied(value)
    )
    if unsupported_fields:
        raise HTTPException(
            422,
            "AccountIQ uses a short valuation intake: five private answers, optional source "
            "hints, optional private context and the earnings review. Remove unsupported "
            "valuation fields: "
            + ", ".join(unsupported_fields),
        )

    company_website = _normalise_optional_public_url(
        answers.get("company_website"),
        "company website",
    )
    if company_website:
        answers["company_website"] = company_website
    elif "company_website" in answers:
        answers["company_website"] = ""
    answers["public_source_urls"] = _normalise_public_source_urls(
        answers.get("public_source_urls")
    )
    company_location = _normalise_optional_company_location(
        answers.get("company_location")
    )
    if company_location:
        answers["company_location"] = company_location
    elif "company_location" in answers:
        answers["company_location"] = ""
    private_context = _normalise_optional_private_context(
        answers.get("private_context")
    )
    if private_context:
        answers["private_context"] = private_context
    elif "private_context" in answers:
        answers["private_context"] = ""

    for field, label, max_chars in (
        ("business_address", "business / premises address", 240),
        ("instructing_party", "instructing party / intended recipient", 240),
        ("valuation_date", "preferred valuation date", 40),
        ("source_information", "source inventory", 1000),
        ("operations_and_services", "operations and services", 1200),
        ("forecast_pipeline_evidence", "forecast / pipeline support", 1200),
        ("premises_and_lease", "premises / lease context", 800),
        ("management_continuity", "management continuity", 800),
    ):
        text = _normalise_optional_credit_context(
            answers.get(field),
            label,
            max_chars=max_chars,
        )
        if text:
            answers[field] = text
        elif field in answers:
            answers[field] = ""

    normalisations = answers.get("normalisations", [])
    if not isinstance(normalisations, list):
        raise HTTPException(422, "Earnings adjustments must be sent as a list")
    if len(normalisations) > 50:
        raise HTTPException(422, "The earnings review can include up to 50 adjustments")
    normalised_normalisations = []
    for index, item in enumerate(normalisations, start=1):
        if not isinstance(item, dict):
            raise HTTPException(422, f"Adjustment {index} must include a label, amount and rationale")
        if _blank_normalisation_row(item):
            continue
        label = _normalise_normalisation_text(
            item.get("label", ""),
            field_label=f"Adjustment {index} label",
            max_chars=120,
            required=True,
        )
        rationale = _normalise_normalisation_text(
            item.get("rationale", ""),
            field_label=f"Adjustment {index} rationale",
            max_chars=300,
            required=True,
        )
        try:
            amount = float(item.get("amount", 0))
        except (TypeError, ValueError):
            raise HTTPException(422, f"Adjustment {index} amount must be a number")
        if not math.isfinite(amount):
            raise HTTPException(422, f"Adjustment {index} amount must be finite")
        if amount == 0:
            raise HTTPException(
                422,
                f"Adjustment {index} needs a non-zero amount, or remove the row",
            )
        normalised_normalisations.append(
            {"label": label, "amount": amount, "rationale": rationale}
        )
    answers["normalisations"] = normalised_normalisations


def _valuation_financial_readiness_message(issues: list[str]) -> str:
    missing = ", ".join(issues)
    return (
        "We could not extract the key valuation figures from the uploaded financial statements "
        f"({missing}). Please upload clearer financial statements showing revenue and EBITDA or profit."
    )


def _valuation_earnings_review_normalisations(
    intake_answers: dict | None,
    legacy_ebitda_adjustments: list[dict],
) -> list[dict]:
    """Return the authoritative earnings-review rows used for valuation calculations."""
    intake_norms = (
        intake_answers.get("normalisations")
        if isinstance(intake_answers, dict)
        else None
    )
    if isinstance(intake_norms, list):
        normalisations = [dict(item) for item in intake_norms if isinstance(item, dict)]
    else:
        normalisations = [
            dict(item)
            for item in legacy_ebitda_adjustments
            if isinstance(item, dict)
        ]

    replacement_manager_cost = (
        intake_answers.get("replacement_manager_cost")
        if isinstance(intake_answers, dict)
        else None
    )
    if replacement_manager_cost not in (None, ""):
        cost = abs(float(replacement_manager_cost or 0))
        if cost > 0:
            normalisations.append(
                {
                    "label": "Replacement manager cost",
                    "amount": -cost,
                    "rationale": (
                        "Management-supplied replacement manager cost deducted to reflect "
                        "maintainable earnings after replacing owner involvement."
                    ),
                }
            )

    return normalisations


_CUSTOMER_SAFE_REPORT_FAILURE_MESSAGES = {
    "valuation_advisory": (
        "We could not complete the valuation report quality checks. Please retry. "
        "If this keeps happening, contact the AccountIQ administrator."
    ),
    "default": (
        "We could not complete the report quality checks. Please retry. "
        "If this keeps happening, contact the AccountIQ administrator."
    ),
}


def _customer_safe_report_failure_message(exc: Exception, report_type: str) -> str:
    """Return a customer-facing report failure message without provider/internal details."""
    raw_message = str(exc).strip()

    # Preserve deliberately customer-actionable upload/readiness guidance. The
    # background generator can still encounter this if a report is queued by an
    # older caller or if financial rows change after preflight.
    if raw_message.startswith("We could not extract the key valuation figures"):
        return raw_message[:1000]

    return _CUSTOMER_SAFE_REPORT_FAILURE_MESSAGES.get(
        report_type,
        _CUSTOMER_SAFE_REPORT_FAILURE_MESSAGES["default"],
    )


def _normalise_source_document_ids(value: object) -> list[int] | None:
    """Return a validated source-document list from an int/list/JSON-like value."""
    if value in (None, ""):
        return None
    if isinstance(value, int):
        ids = [value]
    elif isinstance(value, list):
        ids = value
    else:
        raise HTTPException(400, "source_document_ids must be a list of positive integers")

    normalised: list[int] = []
    for raw_id in ids:
        if not isinstance(raw_id, int) or raw_id <= 0:
            raise HTTPException(400, "source_document_ids must contain positive integers")
        if raw_id not in normalised:
            normalised.append(raw_id)
    if not normalised:
        raise HTTPException(400, "source_document_ids must include at least one document")
    if len(normalised) > MAX_WIZARD_UPLOAD_FILES:
        raise HTTPException(
            400,
            f"source_document_ids can include up to {MAX_WIZARD_UPLOAD_FILES} documents",
        )
    return normalised


def _normalise_financial_reconciliation_overrides(value: object) -> dict[str, int]:
    """Validate a user's source-file selections for overlapping financial rows."""
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise HTTPException(400, "financial_reconciliation_overrides must be a map of conflict IDs to document IDs")
    if len(value) > 100:
        raise HTTPException(400, "Too many financial reconciliation selections were supplied")

    normalised: dict[str, int] = {}
    for raw_conflict_id, raw_document_id in value.items():
        conflict_id = str(raw_conflict_id or "").strip()
        if not conflict_id or len(conflict_id) > 200:
            raise HTTPException(400, "Financial reconciliation selections include an invalid conflict ID")
        if not isinstance(raw_document_id, int) or raw_document_id <= 0:
            raise HTTPException(400, "Financial reconciliation selections must use positive document IDs")
        normalised[conflict_id] = raw_document_id
    return normalised


async def _reconcile_selected_financials(
    db: aiosqlite.Connection,
    *,
    company_id: int,
    user_id: int,
    source_document_ids: list[int],
    overrides: dict[str, int] | None = None,
) -> dict:
    """Load selected source rows with provenance and reconcile overlapping years."""
    placeholders = ",".join("?" for _ in source_document_ids)
    async with db.execute(
        f"""
        SELECT fr.document_id, fr.statement, fr.row_key, fr.row_label, fr.period,
               fr.value, fr.currency, fr.unit, fr.confidence, d.filename
        FROM financial_rows fr
        JOIN documents d ON d.id = fr.document_id
        WHERE fr.company_id=? AND fr.document_id IN ({placeholders})
          AND d.user_id=?
        ORDER BY fr.statement, fr.row_key, fr.period DESC, fr.document_id ASC
        """,
        (company_id, *source_document_ids, user_id),
    ) as cur:
        rows = [dict(row) for row in await cur.fetchall()]
    return reconcile_financial_rows(rows, overrides=overrides)


def _source_document_ids_from_intake_row(row: aiosqlite.Row | None) -> list[int] | None:
    if not row:
        return None
    try:
        raw_ids = row["source_document_ids"]
    except (KeyError, IndexError):
        raw_ids = None
    if raw_ids:
        try:
            parsed = json.loads(raw_ids)
        except Exception:
            parsed = None
        ids = _normalise_source_document_ids(parsed)
        if ids:
            return ids
    single = row["source_document_id"] if row["source_document_id"] is not None else None
    return _normalise_source_document_ids(single)


async def _generation_source_documents(
    db: aiosqlite.Connection,
    *,
    company_id: int,
    user_id: int,
    source_document_ids: list[int] | None,
) -> tuple[list[int], list[str]]:
    """Return selected completed-upload context, or raise a customer-safe error."""
    if source_document_ids:
        placeholders = ",".join("?" for _ in source_document_ids)
        document_query = f"""
            SELECT id, extraction_status
            FROM documents
            WHERE id IN ({placeholders}) AND company_id=? AND user_id=?
        """
        document_params = (*source_document_ids, company_id, user_id)
    else:
        document_query = """
            SELECT id, extraction_status
            FROM documents
            WHERE company_id=? AND user_id=?
            ORDER BY id DESC
            LIMIT 1
        """
        document_params = (company_id, user_id)

    async with db.execute(document_query, document_params) as cur:
        rows = [dict(row) for row in await cur.fetchall()]
    if not rows:
        raise HTTPException(422, "Please upload financial statements before preparing a report.")

    rows_by_id = {int(row["id"]): row for row in rows}
    if source_document_ids:
        missing = [doc_id for doc_id in source_document_ids if doc_id not in rows_by_id]
        if missing:
            raise HTTPException(404, "One or more uploaded financial statements could not be found.")
        resolved_document_ids = source_document_ids
    else:
        resolved_document_ids = [int(rows[0]["id"])]

    statuses = [
        str(rows_by_id[document_id].get("extraction_status") or "pending")
        for document_id in resolved_document_ids
    ]
    if any(status in {"pending", "processing"} for status in statuses):
        raise HTTPException(
            409,
            "Your financial statements are still being processed. Please wait a moment and try again.",
        )
    if any(status != "done" for status in statuses):
        raise HTTPException(
            422,
            "We could not read the uploaded financial statements reliably. Please upload a clearer or complete copy.",
        )
    return resolved_document_ids, statuses


async def _ensure_report_generation_ready(
    db: aiosqlite.Connection,
    *,
    company_id: int,
    user_id: int,
    report_type: str,
    source_document_ids: list[int] | None,
    reconciliation_overrides: dict[str, int] | None,
    current_user: dict,
) -> list[int]:
    """Validate that a report job can be generated before queueing work."""
    resolved_document_ids, _ = await _generation_source_documents(
        db,
        company_id=company_id,
        user_id=user_id,
        source_document_ids=source_document_ids,
    )

    reconciliation = await _reconcile_selected_financials(
        db,
        company_id=company_id,
        user_id=user_id,
        source_document_ids=resolved_document_ids,
        overrides=reconciliation_overrides,
    )
    if reconciliation["invalid_override_ids"]:
        raise HTTPException(
            422,
            "One or more selected financial-statement sources are no longer available for reconciliation. "
            "Please review the uploaded financial statements again.",
        )
    if reconciliation["unresolved_conflict_ids"]:
        raise HTTPException(
            409,
            "We found different values for the same financial year across the uploaded statements. "
            "Review the financial-statement sources and choose the figure to use before preparing a report.",
        )

    generation_mode = _report_generation_mode()
    if generation_mode == "unavailable":
        raise HTTPException(503, _live_research_connection_error_detail(current_user))

    if report_type == "valuation_advisory" and not _demo_mode_enabled():
        readiness = assess_valuation_financial_readiness(reconciliation["rows"])
        if not readiness["ready"]:
            raise HTTPException(
                422,
                _valuation_financial_readiness_message(readiness["issues"]),
            )
    if report_type == "bank_credit_paper" and not _demo_mode_enabled():
        readiness = assess_credit_financial_readiness(reconciliation["rows"])
        if not readiness["ready"]:
            raise HTTPException(422, credit_readiness_message(readiness["issues"]))

    if generation_mode == "provider":
        await _ensure_live_research_connection(current_user)

    return resolved_document_ids


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
        "report_type": str,          // one of active self-serve report types
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
    source_document_id = body.get("source_document_id")
    source_document_ids = _normalise_source_document_ids(body.get("source_document_ids"))
    reconciliation_overrides = _normalise_financial_reconciliation_overrides(
        body.get("financial_reconciliation_overrides")
    )

    if not isinstance(company_id, int) or company_id <= 0:
        raise HTTPException(400, "company_id must be a positive integer")
    if not report_type or report_type not in _VALID_REPORT_TYPES:
        raise HTTPException(
            400,
            f"report_type must be one of: {', '.join(sorted(_VALID_REPORT_TYPES))}"
        )
    if report_type not in _SELF_SERVE_REPORT_TYPES:
        raise HTTPException(
            422,
            "Only Valuation Advisory and Bank Credit Paper are available in the self-serve wizard. "
            "Other report types are coming soon.",
        )
    if not isinstance(intake_answers, dict):
        raise HTTPException(400, "intake_answers must be a JSON object")
    if source_document_id is not None and (
        not isinstance(source_document_id, int) or source_document_id <= 0
    ):
        raise HTTPException(400, "source_document_id must be a positive integer")
    if source_document_ids is None:
        source_document_ids = _normalise_source_document_ids(source_document_id)
    if report_type == "valuation_advisory":
        _validate_valuation_intake_answers(intake_answers)
    elif report_type == "bank_credit_paper":
        _validate_bank_credit_intake_answers(intake_answers)

    generation_mode = _report_generation_mode()
    if generation_mode == "evidence":
        _require_evidence_mode_source_hints(intake_answers)

    # Store the selected source document for each material overlap with the
    # report intake. It is deliberately excluded from the short business/lender
    # questionnaire validation above.
    intake_answers["_financial_reconciliation_overrides"] = reconciliation_overrides

    # Verify the company belongs to this user
    async with db.execute(
        "SELECT id FROM companies WHERE id=? AND user_id=?",
        (company_id, current_user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Company not found")

    # The report must not start until the wizard's financial upload is fully
    # extracted and live dependencies are ready. When older API clients omit
    # source_document_id/source_document_ids, use the latest document for the
    # owned company as a backward-compatible fallback.
    source_document_ids_for_generation = await _ensure_report_generation_ready(
        db,
        company_id=company_id,
        user_id=current_user["id"],
        report_type=report_type,
        source_document_ids=source_document_ids,
        reconciliation_overrides=reconciliation_overrides,
        current_user=current_user,
    )
    report_demo_mode = generation_mode == "demo"
    primary_source_document_id = source_document_ids_for_generation[-1]
    generation_source_arg: int | list[int] = (
        source_document_ids_for_generation[0]
        if len(source_document_ids_for_generation) == 1
        else source_document_ids_for_generation
    )

    # Create report row (status = queued per D-04)
    async with db.execute("""
        INSERT INTO reports (company_id, user_id, report_type, status, demo_mode, generation_mode)
        VALUES (?, ?, ?, 'queued', ?, ?)
    """, (
        company_id,
        current_user["id"],
        report_type,
        int(report_demo_mode),
        generation_mode,
    )) as cur:
        report_id = cur.lastrowid

    # Store intake answers
    await db.execute("""
        INSERT INTO report_intake (report_id, source_document_id, source_document_ids, answers)
        VALUES (?, ?, ?, ?)
    """, (
        report_id,
        primary_source_document_id,
        json.dumps(source_document_ids_for_generation),
        json.dumps(intake_answers),
    ))
    await db.commit()

    # Queue background generation task
    background_tasks.add_task(
        _generate_report,
        report_id,
        company_id,
        current_user["id"],
        report_type,
        intake_answers,
        generation_source_arg,
    )

    return {
        "report_id": report_id,
        "status": "queued",
        "demo_mode": report_demo_mode,
        "generation_mode": generation_mode,
    }


@app.get("/wizard/report/{report_id}/status")
async def wizard_report_status(
    report_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return current status of a report generation job."""
    async with db.execute("""
        SELECT id, report_type, status, error_message, created_at, completed_at, demo_mode, generation_mode, content
        FROM reports
        WHERE id=? AND user_id=?
    """, (report_id, current_user["id"])) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Report not found")
    payload = dict(row)
    payload["demo_mode"] = _report_demo_mode_from_row(row)
    payload["generation_mode"] = _report_generation_mode_from_row(row)
    payload.pop("content", None)
    return payload


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
        """
        SELECT id, answers, source_document_id, source_document_ids
        FROM report_intake
        WHERE report_id=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (report_id,)
    ) as cur:
        intake_row = await cur.fetchone()
    try:
        intake_answers = json.loads(intake_row["answers"]) if intake_row else {}
    except json.JSONDecodeError:
        raise HTTPException(
            422,
            "Stored intake answers are invalid. Please start a new valuation report.",
        )
    if not isinstance(intake_answers, dict):
        raise HTTPException(
            422,
            "Stored intake answers are invalid. Please start a new valuation report.",
        )
    stored_reconciliation_overrides = intake_answers.pop(
        "_financial_reconciliation_overrides", None
    )
    if report["report_type"] == "valuation_advisory":
        _validate_valuation_intake_answers(intake_answers)
    elif report["report_type"] == "bank_credit_paper":
        _validate_bank_credit_intake_answers(intake_answers)
    generation_mode = _report_generation_mode()
    if generation_mode == "evidence":
        _require_evidence_mode_source_hints(intake_answers)
    source_document_ids = _source_document_ids_from_intake_row(intake_row)
    reconciliation_overrides = _normalise_financial_reconciliation_overrides(
        stored_reconciliation_overrides
    )
    intake_answers["_financial_reconciliation_overrides"] = reconciliation_overrides
    source_document_ids_for_generation = await _ensure_report_generation_ready(
        db,
        company_id=report["company_id"],
        user_id=current_user["id"],
        report_type=report["report_type"],
        source_document_ids=source_document_ids,
        reconciliation_overrides=reconciliation_overrides,
        current_user=current_user,
    )
    report_demo_mode = generation_mode == "demo"
    generation_source_arg: int | list[int] = (
        source_document_ids_for_generation[0]
        if len(source_document_ids_for_generation) == 1
        else source_document_ids_for_generation
    )

    # Reset status
    await db.execute("""
        UPDATE reports
        SET status='queued', error_message=NULL, completed_at=NULL, demo_mode=?, generation_mode=?, research_evidence=NULL
        WHERE id=? AND user_id=?
    """, (int(report_demo_mode), generation_mode, report_id, current_user["id"]))
    if intake_row:
        await db.execute(
            "UPDATE report_intake SET answers=?, source_document_ids=? WHERE id=?",
            (
                json.dumps(intake_answers),
                json.dumps(source_document_ids_for_generation),
                intake_row["id"],
            ),
        )
    await db.commit()

    background_tasks.add_task(
        _generate_report,
        report_id,
        report["company_id"],
        current_user["id"],
        report["report_type"],
        intake_answers,
        generation_source_arg,
    )
    return {
        "report_id": report_id,
        "status": "queued",
        "demo_mode": report_demo_mode,
        "generation_mode": generation_mode,
    }


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

_REPORT_SECTION_TITLES = {
    "introduction": "Introduction",
    "executive_summary": "Executive Summary",
    "business_overview": "Overview",
    "market_position": "Market Position",
    "about_business_valuations": "About Business Valuations",
    "valuation_methodology": "Valuation Methodology Adopted",
    "financial_performance": "Financial Performance",
    "financial_ratio_analysis": "Historical Ratio Analysis",
    "normalisations_schedule": "Normalisations",
    "balance_sheet_summary": "Balance Sheet Summary",
    "valuation_assumptions": "Valuation Approach and Assumptions",
    "wacc_assumptions": "Weighted Average Cost of Capital",
    "dcf_analysis": "Discounted Cash Flow Analysis",
    "valuation_summary": "Indicative Valuation Summary",
    "multiples_crosscheck": "Multiples Cross-check",
    "sensitivity_and_risks": "Sensitivity and Specific Risks",
    "comparable_evidence": "Comparable Evidence Appendix",
    "sources": "Sources and References",
    "disclaimer": "Disclaimer",
    "general_principles": "General Principles",
    "glossary": "Glossary",
    "transaction_summary": "Transaction Summary",
    "sources_and_uses": "Sources & Uses",
    "borrower_and_sponsor_profile": "Borrower & Sponsor Profile",
    "facilities_requested": "Facilities Requested",
    "security_package": "Security Package",
    "financial_performance_forecast": "Financial Performance & Forecast",
    "coverage_and_sensitivity": "Coverage Ratios & Sensitivity",
    "balance_sheet_debt_capacity": "Balance Sheet & Debt Capacity",
    "industry_and_competitive_landscape": "Industry & Competitive Landscape",
    "proposed_covenants": "Proposed Covenants",
    "key_risks_and_mitigants": "Key Risks & Mitigants",
    "conditions_precedent": "Conditions Precedent",
    "recommendation": "Recommendation",
}

_VALUATION_PURPOSE_LABELS = {
    "understand_value": "Understand what the business may be worth",
    "sale_or_transaction": "Prepare for a sale or transaction",
    "shareholder_or_employee_scheme": "Shareholder or employee share scheme",
    "succession_planning": "Succession or estate planning",
    "finance_or_investment": "Finance or investment discussions",
    "other": "Another valuation purpose",
}


def _valuation_purpose_label(raw_value: object) -> str:
    """Return a reader-facing label for the short valuation-purpose answer."""
    key = str(raw_value or "").strip()
    return _VALUATION_PURPOSE_LABELS.get(key, key.replace("_", " ").title() if key else "")


async def _latest_report_intake_answers(db: aiosqlite.Connection, report_id: int) -> dict:
    """Fetch the latest stored intake answers for report front-matter."""
    async with db.execute(
        "SELECT answers FROM report_intake WHERE report_id=? ORDER BY id DESC LIMIT 1",
        (report_id,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return {}
    try:
        answers = json.loads(row["answers"])
    except Exception:
        return {}
    return answers if isinstance(answers, dict) else {}


def _inline_report_html(text: object) -> str:
    """Escape report text, convert safe URLs to links, then apply light inline markup."""
    raw = str(text)
    chunks: list[str] = []
    cursor = 0
    for match in _re.finditer(r"https?://[^\s<>\"]+", raw):
        start, end = match.span()
        url = match.group(0).rstrip(").,;]")
        if not url:
            continue
        url_end = start + len(url)
        chunks.append(_html_lib.escape(raw[cursor:start]))
        escaped_url = _html_lib.escape(url, quote=True)
        chunks.append(
            f'<a href="{escaped_url}" target="_blank" rel="noopener noreferrer">{escaped_url}</a>'
        )
        cursor = url_end
    chunks.append(_html_lib.escape(raw[cursor:]))
    escaped_with_links = "".join(chunks)
    return _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped_with_links)


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

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_bullets()
            continue

        if stripped.startswith("## "):
            flush_bullets()
            heading_text = _inline_report_html(stripped[3:].strip())
            chunks.append(f"<h3>{heading_text}</h3>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            item_text = _inline_report_html(stripped[2:].strip())
            bullet_buffer.append(item_text)
        else:
            flush_bullets()
            para_text = _inline_report_html(stripped)
            chunks.append(f"<p>{para_text}</p>")

    flush_bullets()
    return "".join(chunks)


def _render_executive_valuation_highlights_html(sections: dict) -> str:
    """Render an executive-summary conclusion panel from computed valuation rows."""
    highlights = executive_valuation_highlights(sections)
    if not highlights:
        return ""
    cards = "".join(
        "<div>"
        f"<dt>{_html_lib.escape(label)}</dt>"
        f"<dd>{_html_lib.escape(value)}</dd>"
        f"<p>{_html_lib.escape(note)}</p>"
        "</div>"
        for label, value, note in highlights
    )
    return f"""
    <aside class="executive-highlights" aria-label="Valuation conclusion at a glance">
      <h3>Valuation conclusion at a glance</h3>
      <dl>{cards}</dl>
    </aside>
    """


def _render_valuation_range_visual_html(sections: dict) -> str:
    """Render a compact range-band visual from computed valuation rows."""
    visual = valuation_range_visual(sections)
    if visual is None:
        return ""
    title, rows = visual
    numeric_values = [
        float(row[key])
        for row in rows
        for key in ("low_value", "mid_value", "high_value")
        if row.get(key) is not None
    ]
    if not numeric_values:
        return ""
    scale_min = min(numeric_values)
    scale_max = max(numeric_values)
    if scale_min == scale_max:
        scale_min *= 0.95
        scale_max *= 1.05
    padding = (scale_max - scale_min) * 0.08
    scale_min -= padding
    scale_max += padding
    scale_span = scale_max - scale_min or 1

    def position(value: object) -> float:
        return max(0.0, min(100.0, ((float(value) - scale_min) / scale_span) * 100))

    row_html = ""
    for row in rows:
        low_position = position(row["low_value"])
        high_position = position(row["high_value"])
        mid_position = position(row["mid_value"])
        bar_left = min(low_position, high_position)
        bar_width = abs(high_position - low_position)
        row_html += f"""
        <div class="range-visual-row">
          <div class="range-visual-label">
            <strong>{_html_lib.escape(str(row.get("label", "")))}</strong>
            <span>{_html_lib.escape(str(row.get("note", "")))}</span>
          </div>
          <div class="range-visual-track" aria-label="{_html_lib.escape(str(row.get("label", "")), quote=True)} range">
            <span class="range-visual-axis"></span>
            <span class="range-visual-band" style="left:{bar_left:.2f}%; width:{bar_width:.2f}%"></span>
            <span class="range-visual-mid" style="left:{mid_position:.2f}%"></span>
            <span class="range-visual-low" style="left:{low_position:.2f}%">{_html_lib.escape(str(row.get("low_label", "")))}</span>
            <span class="range-visual-high" style="left:{high_position:.2f}%">{_html_lib.escape(str(row.get("high_label", "")))}</span>
            <span class="range-visual-mid-label" style="left:{mid_position:.2f}%">Mid {_html_lib.escape(str(row.get("mid_label", "")))}</span>
          </div>
        </div>
        """

    return f"""
    <aside class="valuation-range-visual" aria-label="{_html_lib.escape(title, quote=True)}">
      <h3>{_html_lib.escape(title)}</h3>
      <p>{_html_lib.escape(VALUATION_RANGE_VISUAL_SUBTITLE)}</p>
      <div>{row_html}</div>
    </aside>
    """


def _render_financial_trend_visual_html(sections: dict) -> str:
    """Render a compact revenue and EBITDA trend visual from computed table rows."""
    visual = financial_trend_visual(sections)
    if visual is None:
        return ""
    title, rows = visual
    max_value = max(
        float(row[key])
        for row in rows
        for key in ("revenue_value", "ebitda_value")
        if row.get(key) is not None
    )
    if max_value <= 0:
        return ""

    row_html = ""
    for row in rows:
        revenue_width = max(0.0, min(100.0, (float(row["revenue_value"]) / max_value) * 100))
        ebitda_width = max(0.0, min(100.0, (float(row["ebitda_value"]) / max_value) * 100))
        margin_label = str(row.get("margin_label", "") or "")
        margin_text = f"EBITDA margin {margin_label}" if margin_label else ""
        row_html += f"""
        <div class="financial-trend-row">
          <div class="financial-trend-period">
            <strong>{_html_lib.escape(str(row.get("period", "")))}</strong>
            <span>{_html_lib.escape(margin_text)}</span>
          </div>
          <div class="financial-trend-bars">
            <div class="financial-trend-bar revenue">
              <span style="width:{revenue_width:.2f}%"></span>
              <strong>{_html_lib.escape(str(row.get("revenue_label", "")))}</strong>
            </div>
            <div class="financial-trend-bar ebitda">
              <span style="width:{ebitda_width:.2f}%"></span>
              <strong>{_html_lib.escape(str(row.get("ebitda_label", "")))}</strong>
            </div>
          </div>
        </div>
        """

    return f"""
    <aside class="financial-trend-visual" aria-label="{_html_lib.escape(title, quote=True)}">
      <div class="financial-trend-header">
        <div>
          <h3>{_html_lib.escape(title)}</h3>
          <p>{_html_lib.escape(FINANCIAL_TREND_VISUAL_SUBTITLE)}</p>
        </div>
        <dl aria-label="Financial trend legend">
          <div><dt>Revenue</dt><dd></dd></div>
          <div><dt>EBITDA</dt><dd></dd></div>
        </dl>
      </div>
      <div>{row_html}</div>
    </aside>
    """


def _render_normalised_ebitda_bridge_visual_html(sections: dict) -> str:
    """Render the bridge from uploaded EBITDA to normalised EBITDA."""
    visual = normalised_ebitda_bridge_visual(sections)
    if visual is None:
        return ""
    title, row = visual
    steps = [
        (
            "Uploaded EBITDA basis",
            row.get("uploaded_ebitda_label", ""),
            "Starting earnings base from the uploaded financial statements.",
        ),
        "+",
        (
            "Net normalisation",
            row.get("net_adjustment_label", ""),
            row.get("adjustment_note", ""),
        ),
        "=",
        (
            "Normalised EBITDA",
            row.get("normalised_ebitda_label", ""),
            "Maintainable earnings base carried into DCF and market-multiple checks.",
        ),
        "",
        (
            "Owner review",
            row.get("adjustment_count_label", ""),
            "The earnings bridge comes from the earnings-adjustment review and uploaded accounts.",
        ),
        "",
        (
            "Source basis",
            "Accounts + review",
            "The bridge is calculated from uploaded accounts and confirmed adjustment rows.",
        ),
        "",
        (
            "Valuation use",
            "DCF and multiples",
            "The same normalised EBITDA is used consistently across valuation methods.",
        ),
    ]
    step_html = ""
    for step in steps:
        if isinstance(step, str):
            step_html += f'<span class="normalised-ebitda-bridge-operator">{_html_lib.escape(step)}</span>'
            continue
        label, value, note = step
        step_html += f"""
        <div class="normalised-ebitda-bridge-card">
          <strong>{_html_lib.escape(str(label))}</strong>
          <span>{_html_lib.escape(str(value))}</span>
          <p>{_html_lib.escape(str(note))}</p>
        </div>
        """
    return f"""
    <aside class="normalised-ebitda-bridge-visual" aria-label="{_html_lib.escape(title, quote=True)}">
      <h3>{_html_lib.escape(title)}</h3>
      <p>{_html_lib.escape(str(row.get("note", "")))}</p>
      <div class="normalised-ebitda-bridge-steps">{step_html}</div>
    </aside>
    """


def _render_equity_bridge_visual_html(sections: dict) -> str:
    """Render a compact enterprise-to-equity bridge visual from computed balance-sheet rows."""
    visual = equity_bridge_visual(sections)
    if visual is None:
        return ""
    title, row = visual
    steps = [
        (
            "Midpoint enterprise value",
            row.get("enterprise_label", ""),
            "Operating-business value before debt, cash and surplus assets.",
        ),
        (
            "Less net debt",
            row.get("net_debt_label", ""),
            "Interest-bearing debt less available cash.",
        ),
        (
            "Surplus assets",
            row.get("surplus_label", ""),
            "Separately identified non-operating assets added back.",
        ),
        (
            "Midpoint equity value",
            row.get("equity_label", ""),
            "Indicative shareholder value after the balance-sheet bridge.",
        ),
    ]
    step_html = ""
    for index, (label, value, note) in enumerate(steps):
        if index:
            operator = ["-", "+", "="][index - 1]
            step_html += f'<span class="equity-bridge-operator">{operator}</span>'
        step_html += f"""
        <div class="equity-bridge-card">
          <strong>{_html_lib.escape(label)}</strong>
          <span>{_html_lib.escape(str(value))}</span>
          <p>{_html_lib.escape(note)}</p>
        </div>
        """

    return f"""
    <aside class="equity-bridge-visual" aria-label="{_html_lib.escape(title, quote=True)}">
      <h3>{_html_lib.escape(title)}</h3>
      <p>{_html_lib.escape(str(row.get("note", "")))}</p>
      <div class="equity-bridge-steps">{step_html}</div>
    </aside>
    """


def _render_wacc_build_visual_html(sections: dict) -> str:
    """Render a compact mid-case WACC build visual from computed WACC rows."""
    visual = wacc_build_visual(sections)
    if visual is None:
        return ""
    title, row = visual
    rows = [
        [
            (
                "Risk-free rate",
                row.get("risk_free_label", ""),
                "Public market base return before company and sector risk.",
            ),
            "+",
            (
                "Beta-adjusted risk premium",
                row.get("beta_adjusted_premium_label", ""),
                row.get("premium_note", ""),
            ),
            "=",
            (
                "Mid WACC",
                row.get("wacc_label", ""),
                "Discount rate applied to the mid-case forecast cash flows.",
            ),
        ],
        [
            (
                "Illiquidity discount",
                row.get("illiquidity_label", ""),
                "Separate private-company marketability adjustment applied after DCF value.",
            ),
            "",
            (
                "Source inputs",
                f"ERP {row.get('erp_label', '')} / beta {row.get('beta_label', '')}",
                "Public research inputs are disclosed as part of the valuation evidence trail.",
            ),
            "",
            (
                "Technical inputs",
                "Derived",
                "WACC, beta and equity-risk-premium assumptions are derived and disclosed as valuation-model inputs.",
            ),
        ],
    ]

    row_html = ""
    for equation in rows:
        cells = ""
        for item in equation:
            if isinstance(item, str):
                cells += f'<span class="wacc-build-operator">{_html_lib.escape(item)}</span>'
                continue
            label, value, note = item
            cells += f"""
            <div class="wacc-build-card">
              <strong>{_html_lib.escape(label)}</strong>
              <span>{_html_lib.escape(str(value))}</span>
              <p>{_html_lib.escape(str(note))}</p>
            </div>
            """
        row_html += f'<div class="wacc-build-row">{cells}</div>'

    return f"""
    <aside class="wacc-build-visual" aria-label="{_html_lib.escape(title, quote=True)}">
      <h3>{_html_lib.escape(title)}</h3>
      <p>{_html_lib.escape(str(row.get("note", "")))}</p>
      <div class="wacc-build-rows">{row_html}</div>
    </aside>
    """


def _render_dcf_value_build_visual_html(sections: dict) -> str:
    """Render a compact mid-case DCF value-build visual from computed DCF rows."""
    visual = dcf_value_build_visual(sections)
    if visual is None:
        return ""
    title, row = visual
    equations = [
        [
            (
                "PV explicit FCFF",
                row.get("explicit_fcff_label", ""),
                "Present value of the five-year forecast cash flows.",
            ),
            "+",
            (
                "PV terminal value",
                row.get("terminal_value_label", ""),
                "Implied continuing value after the explicit forecast period.",
            ),
            "=",
            (
                "EV before illiquidity",
                row.get("ev_before_illiquidity_label", ""),
                "Mid-case DCF enterprise value before the private-company discount.",
            ),
        ],
        [
            (
                "EV before illiquidity",
                row.get("ev_before_illiquidity_label", ""),
                "Starting point for the marketability adjustment.",
            ),
            "-",
            (
                "Illiquidity discount",
                row.get("illiquidity_discount_label", ""),
                "Explicit private-company marketability adjustment.",
            ),
            "=",
            (
                "Adjusted enterprise value",
                row.get("adjusted_ev_label", ""),
                "Mid-case operating-business value used in the valuation summary.",
            ),
        ],
    ]

    equation_html = ""
    for equation in equations:
        row_html = ""
        for item in equation:
            if isinstance(item, str):
                row_html += f'<span class="dcf-value-build-operator">{_html_lib.escape(item)}</span>'
                continue
            label, value, note = item
            row_html += f"""
            <div class="dcf-value-build-card">
              <strong>{_html_lib.escape(label)}</strong>
              <span>{_html_lib.escape(str(value))}</span>
              <p>{_html_lib.escape(note)}</p>
            </div>
            """
        equation_html += f'<div class="dcf-value-build-row">{row_html}</div>'

    return f"""
    <aside class="dcf-value-build-visual" aria-label="{_html_lib.escape(title, quote=True)}">
      <h3>{_html_lib.escape(title)}</h3>
      <p>{_html_lib.escape(str(row.get("note", "")))}</p>
      <div class="dcf-value-build-rows">{equation_html}</div>
    </aside>
    """


def _render_implied_multiple_reconciliation_html(sections: dict) -> str:
    """Render DCF-implied EV/EBITDA multiples against the researched market range."""
    visual = implied_multiple_reconciliation(sections)
    if visual is None:
        return ""
    title, row = visual
    cards = [
        (
            "Normalised EBITDA",
            row.get("normalised_ebitda_label", ""),
            "Maintainable earnings base used for the market and DCF implied multiple checks.",
        ),
        (
            "Market EV/EBITDA range",
            row.get("market_range_label", ""),
            "Researched market range used as a reasonableness cross-check.",
        ),
        (
            "DCF post-illiquidity range",
            row.get("dcf_post_range_label", ""),
            "Primary DCF adjusted enterprise-value range expressed as an EV/EBITDA multiple.",
        ),
        (
            "DCF pre-illiquidity range",
            row.get("dcf_pre_range_label", ""),
            "DCF enterprise-value range before the private-company marketability discount.",
        ),
        (
            "DCF midpoint multiple",
            row.get("dcf_post_mid_label", ""),
            "Midpoint adjusted DCF enterprise value divided by normalised EBITDA.",
        ),
        (
            "Cross-check tension",
            row.get("midpoint_gap_label") or "In range",
            "Shows whether the selected DCF midpoint sits above or below the market midpoint.",
        ),
    ]
    card_html = "".join(
        f"""
        <div class="implied-multiple-card">
          <strong>{_html_lib.escape(label)}</strong>
          <span>{_html_lib.escape(str(value))}</span>
          <p>{_html_lib.escape(note)}</p>
        </div>
        """
        for label, value, note in cards
    )
    return f"""
    <aside class="implied-multiple-visual" aria-label="{_html_lib.escape(title, quote=True)}">
      <h3>{_html_lib.escape(title)}</h3>
      <p>{_html_lib.escape(str(row.get("note", "")))}</p>
      <div class="implied-multiple-grid">{card_html}</div>
    </aside>
    """


def _render_sensitivity_spread_visual_html(sections: dict) -> str:
    """Render a compact sensitivity spread visual from the computed matrix."""
    visual = sensitivity_spread_visual(sections)
    if visual is None:
        return ""
    title, rows = visual
    numeric_values = [
        float(row[key])
        for row in rows
        for key in ("low_value", "mid_value", "high_value")
        if row.get(key) is not None
    ]
    if not numeric_values:
        return ""
    scale_min = min(numeric_values)
    scale_max = max(numeric_values)
    if scale_min == scale_max:
        scale_min *= 0.95
        scale_max *= 1.05
    padding = (scale_max - scale_min) * 0.08
    scale_min -= padding
    scale_max += padding
    scale_span = scale_max - scale_min or 1

    def position(value: object) -> float:
        return max(0.0, min(100.0, ((float(value) - scale_min) / scale_span) * 100))

    row_html = ""
    for row in rows:
        low_position = position(row["low_value"])
        high_position = position(row["high_value"])
        mid_position = position(row["mid_value"])
        bar_left = min(low_position, high_position)
        bar_width = abs(high_position - low_position)
        row_html += f"""
        <div class="range-visual-row">
          <div class="range-visual-label">
            <strong>{_html_lib.escape(str(row.get("label", "")))}</strong>
            <span>{_html_lib.escape(str(row.get("note", "")))}</span>
          </div>
          <div class="range-visual-track" aria-label="{_html_lib.escape(str(row.get("label", "")), quote=True)} range">
            <span class="range-visual-axis"></span>
            <span class="range-visual-band" style="left:{bar_left:.2f}%; width:{bar_width:.2f}%"></span>
            <span class="range-visual-mid" style="left:{mid_position:.2f}%"></span>
            <span class="range-visual-low" style="left:{low_position:.2f}%">{_html_lib.escape(str(row.get("low_label", "")))}</span>
            <span class="range-visual-high" style="left:{high_position:.2f}%">{_html_lib.escape(str(row.get("high_label", "")))}</span>
            <span class="range-visual-mid-label" style="left:{mid_position:.2f}%">Base {_html_lib.escape(str(row.get("mid_label", "")))}</span>
          </div>
        </div>
        """

    return f"""
    <aside class="sensitivity-spread-visual" aria-label="{_html_lib.escape(title, quote=True)}">
      <h3>{_html_lib.escape(title)}</h3>
      <p>{_html_lib.escape(SENSITIVITY_SPREAD_VISUAL_SUBTITLE)}</p>
      <div>{row_html}</div>
    </aside>
    """


def _render_valuation_reader_guidance_html(sections: dict, section_key: str) -> str:
    """Render a valuation table interpretation panel from computed table rows."""
    guidance = valuation_reader_guidance(sections, section_key)
    if guidance is None:
        return ""
    title, rows = guidance
    cards = "".join(
        "<div>"
        f"<dt>{_html_lib.escape(label)}</dt>"
        f"<dd>{_html_lib.escape(value)}</dd>"
        f"<p>{_html_lib.escape(note)}</p>"
        "</div>"
        for label, value, note in rows
    )
    return f"""
    <aside class="reader-guidance" aria-label="{_html_lib.escape(title, quote=True)}">
      <h3>{_html_lib.escape(title)}</h3>
      <dl>{cards}</dl>
    </aside>
    """


def _render_valuation_method_selection_html(sections: dict) -> str:
    """Render the valuation-method selection rationale from computed report sections."""
    visual = valuation_method_selection(sections)
    if visual is None:
        return ""
    title, rows = visual
    if not rows:
        return ""
    row_html = "".join(
        "<tr>"
        f"<td>{_html_lib.escape(str(row.get('approach', '')))}</td>"
        f"<td>{_html_lib.escape(str(row.get('role', '')))}</td>"
        f"<td>{_html_lib.escape(str(row.get('rationale', '')))}</td>"
        f"<td>{_html_lib.escape(str(row.get('report_treatment', '')))}</td>"
        "</tr>"
        for row in rows
    )
    return f"""
    <aside class="method-selection-visual" aria-label="{_html_lib.escape(title, quote=True)}">
      <h3>{_html_lib.escape(title)}</h3>
      <p>Explains why the report adopts DCF, uses market multiples as a cross-check and does not rely on a net-asset method.</p>
      <table>
        <thead>
          <tr>
            <th>Approach</th>
            <th>Role</th>
            <th>Why this treatment is appropriate</th>
            <th>Report treatment</th>
          </tr>
        </thead>
        <tbody>{row_html}</tbody>
      </table>
    </aside>
    """


def _report_table_caption(key: str) -> str:
    return key.replace("_", " ").title()


def _render_market_line_chart_html(chart: dict) -> str:
    """Render a deterministic, accessible inline SVG market chart."""
    series_list = [
        item
        for item in (chart.get("series") or [])
        if isinstance(item, dict) and isinstance(item.get("values"), list)
    ]
    numeric_values: list[float] = []
    for series in series_list:
        for point in series.get("values") or []:
            try:
                numeric_values.append(float(point.get("value")))
            except (AttributeError, TypeError, ValueError):
                continue
    if not series_list or len(numeric_values) < 2:
        return ""

    width, height = 720.0, 286.0
    left, right, top, bottom = 70.0, 24.0, 24.0, 54.0
    plot_width = width - left - right
    plot_height = height - top - bottom
    minimum = min(numeric_values)
    maximum = max(numeric_values)
    all_nonnegative = minimum >= 0
    all_nonpositive = maximum <= 0
    if all_nonnegative:
        minimum = 0.0
    if all_nonpositive:
        maximum = 0.0
    if math.isclose(minimum, maximum):
        maximum = minimum + 1.0
    padding = (maximum - minimum) * 0.08
    if not all_nonnegative:
        minimum -= padding
    if not all_nonpositive:
        maximum += padding
    span = maximum - minimum
    palette = ("#1769aa", "#d97706", "#2e7d32", "#7c3aed")

    def point_xy(index: int, count: int, value: float) -> tuple[float, float]:
        x_value = left + (plot_width * index / max(count - 1, 1))
        y_value = top + ((maximum - value) / span) * plot_height
        return x_value, y_value

    grid_lines = []
    for index in range(5):
        ratio = index / 4
        y_value = top + ratio * plot_height
        label_value = maximum - ratio * span
        if abs(label_value) >= 1000:
            label = f"{label_value / 1000:,.0f}k"
        elif abs(label_value) >= 100:
            label = f"{label_value:,.0f}"
        else:
            label = f"{label_value:,.1f}"
        grid_lines.append(
            f'<line x1="{left:.1f}" y1="{y_value:.1f}" x2="{width-right:.1f}" '
            f'y2="{y_value:.1f}" stroke="#dfe5ec" stroke-width="1"/>'
            f'<text x="{left-9:.1f}" y="{y_value+4:.1f}" text-anchor="end" '
            f'fill="#637083" font-size="11">{_html_lib.escape(label)}</text>'
        )

    paths = []
    legends = []
    period_labels: list[str] = []
    for series_index, series in enumerate(series_list):
        valid_points: list[tuple[str, float]] = []
        for point in series.get("values") or []:
            try:
                valid_points.append((str(point.get("period") or ""), float(point.get("value"))))
            except (AttributeError, TypeError, ValueError):
                continue
        if len(valid_points) < 2:
            continue
        if not period_labels:
            period_labels = [label for label, _value in valid_points]
        colour = palette[series_index % len(palette)]
        coordinates = [
            point_xy(index, len(valid_points), value)
            for index, (_period, value) in enumerate(valid_points)
        ]
        path_points = " ".join(f"{x_value:.1f},{y_value:.1f}" for x_value, y_value in coordinates)
        circles = "".join(
            f'<circle cx="{x_value:.1f}" cy="{y_value:.1f}" r="3.2" '
            f'fill="{colour}" stroke="white" stroke-width="1.4"/>'
            for x_value, y_value in coordinates
        )
        paths.append(
            f'<polyline points="{path_points}" fill="none" stroke="{colour}" '
            f'stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>{circles}'
        )
        legends.append(
            f'<span><i style="background:{colour}"></i>'
            f'{_html_lib.escape(str(series.get("name") or "Series"))}</span>'
        )

    if not paths:
        return ""
    x_labels = []
    for index, label in enumerate(period_labels):
        if len(period_labels) > 8 and index not in {0, len(period_labels) - 1} and index % 2:
            continue
        x_value, _ = point_xy(index, len(period_labels), 0)
        x_labels.append(
            f'<text x="{x_value:.1f}" y="{height-bottom+22:.1f}" text-anchor="middle" '
            f'fill="#637083" font-size="10">{_html_lib.escape(label)}</text>'
        )

    source_names = {
        "stats_nz_cpi": "Stats NZ",
        "stats_nz_gdp": "Stats NZ",
        "stats_nz_migration": "Stats NZ",
        "stats_nz_bfd": "Stats NZ Business Financial Data",
        "rbnz_ocr": "Reserve Bank of New Zealand",
    }
    sources = list(
        dict.fromkeys(
            source_names.get(str(source_id), str(source_id))
            for source_id in chart.get("source_ids") or []
        )
    )
    note = str(chart.get("note") or "").strip()
    caption = " · ".join(
        value
        for value in (
            f"Source: {', '.join(sources)}" if sources else "",
            note,
        )
        if value
    )
    return f"""
    <figure class="market-line-chart">
      <figcaption>
        <strong>{_html_lib.escape(str(chart.get("title") or "Market trend"))}</strong>
        <span>{_html_lib.escape(str(chart.get("subtitle") or ""))}</span>
      </figcaption>
      <div class="market-chart-legend">{"".join(legends)}</div>
      <svg viewBox="0 0 {width:.0f} {height:.0f}" role="img"
           aria-label="{_html_lib.escape(str(chart.get('title') or 'Market trend'), quote=True)}">
        {"".join(grid_lines)}
        <line x1="{left:.1f}" y1="{top:.1f}" x2="{left:.1f}" y2="{height-bottom:.1f}" stroke="#9aa8b8"/>
        <line x1="{left:.1f}" y1="{height-bottom:.1f}" x2="{width-right:.1f}" y2="{height-bottom:.1f}" stroke="#9aa8b8"/>
        {"".join(paths)}
        {"".join(x_labels)}
        <text x="15" y="{top + plot_height / 2:.1f}" text-anchor="middle"
              transform="rotate(-90 15 {top + plot_height / 2:.1f})"
              fill="#637083" font-size="11">{_html_lib.escape(str(chart.get("unit") or ""))}</text>
      </svg>
      <p class="market-chart-source">{_html_lib.escape(caption)}</p>
    </figure>
    """


def _render_report_sections_html(
    sections: dict,
    section_order: list,
    report_type: str | None = None,
) -> str:
    """Render report sections as HTML, handling both plain-string and dict (narrative+table) sections.

    Public for testability — used by wizard_report_view.
    """
    section_html = ""

    def render_table(table_data: dict, caption: str = "") -> str:
        headers = table_data.get("headers", []) or []
        rows = table_data.get("rows", []) or []
        if not isinstance(headers, list) or not isinstance(rows, list):
            return ""
        valid_rows = [row for row in rows if isinstance(row, list)]
        column_count = max(
            len(headers),
            max((len(row) for row in valid_rows), default=0),
        )
        right_aligned_columns = _right_aligned_report_table_columns(
            headers,
            valid_rows,
            column_count,
        )

        def numeric_class(index: int) -> str:
            return ' class="numeric-cell"' if index in right_aligned_columns else ""

        th_cells = "".join(
            f"<th{numeric_class(index)}>{_inline_report_html(h)}</th>"
            for index, h in enumerate(headers)
        )
        tr_rows = "".join(
            "<tr>"
            + "".join(
                f"<td{numeric_class(index)}>{_inline_report_html(c)}</td>"
                for index, c in enumerate(row)
            )
            + "</tr>"
            for row in valid_rows
        )
        if not th_cells and not tr_rows:
            return ""
        caption_html = f"<caption>{_html_lib.escape(caption)}</caption>" if caption else ""
        return (
            f"<table class='report-table'>"
            f"{caption_html}"
            f"<thead><tr>{th_cells}</tr></thead>"
            f"<tbody>{tr_rows}</tbody>"
            f"</table>"
        )

    visible_sections = [key for key in section_order if key in sections]
    is_valuation_report = report_type in {None, "valuation_advisory"}
    for section_number, key in enumerate(visible_sections, start=1):
        content = sections.get(key, "")
        heading = _REPORT_SECTION_TITLES.get(key, key.replace("_", " ").title())

        if isinstance(content, dict):
            narrative = str(content.get("narrative", "") or "")
            table_data = content.get("table") if isinstance(content.get("table"), dict) else None
            market_charts = (
                content.get("market_charts")
                if isinstance(content.get("market_charts"), list)
                else []
            )
            extra_tables = {
                sub_key: sub_value
                for sub_key, sub_value in content.items()
                if sub_key not in {"narrative", "table"}
                and isinstance(sub_value, dict)
                and isinstance(sub_value.get("headers"), list)
                and isinstance(sub_value.get("rows"), list)
            }
        else:
            narrative = str(content) if content is not None else ""
            table_data = None
            market_charts = []
            extra_tables = {}

        paragraphs = _narrative_to_html(narrative)
        market_charts_html = "".join(
            _render_market_line_chart_html(chart)
            for chart in market_charts
            if isinstance(chart, dict)
        )
        executive_highlights_html = (
            _render_executive_valuation_highlights_html(sections)
            if is_valuation_report and key == "executive_summary"
            else ""
        )
        valuation_range_visual_html = (
            _render_valuation_range_visual_html(sections)
            if is_valuation_report and key == "executive_summary"
            else ""
        )
        valuation_method_selection_html = (
            _render_valuation_method_selection_html(sections)
            if is_valuation_report and key == "valuation_methodology"
            else ""
        )
        financial_trend_visual_html = (
            _render_financial_trend_visual_html(sections)
            if is_valuation_report and key == "financial_performance"
            else ""
        )
        normalised_ebitda_bridge_visual_html = (
            _render_normalised_ebitda_bridge_visual_html(sections)
            if is_valuation_report and key == "normalisations_schedule"
            else ""
        )
        equity_bridge_visual_html = (
            _render_equity_bridge_visual_html(sections)
            if is_valuation_report and key == "balance_sheet_summary"
            else ""
        )
        wacc_build_visual_html = (
            _render_wacc_build_visual_html(sections)
            if is_valuation_report and key == "wacc_assumptions"
            else ""
        )
        dcf_value_build_visual_html = (
            _render_dcf_value_build_visual_html(sections)
            if is_valuation_report and key == "dcf_analysis"
            else ""
        )
        implied_multiple_reconciliation_html = (
            _render_implied_multiple_reconciliation_html(sections)
            if is_valuation_report and key == "multiples_crosscheck"
            else ""
        )
        sensitivity_spread_visual_html = (
            _render_sensitivity_spread_visual_html(sections)
            if is_valuation_report and key == "sensitivity_and_risks"
            else ""
        )

        table_html = ""
        if table_data:
            table_html = render_table(table_data, f"{heading} detailed schedule")
        guidance_html = (
            _render_valuation_reader_guidance_html(sections, key)
            if is_valuation_report
            else ""
        )
        pre_narrative_guidance_html = guidance_html if key == "disclaimer" else ""
        pre_table_guidance_html = (
            guidance_html
            if key in {"valuation_methodology", "financial_performance", "financial_ratio_analysis", "normalisations_schedule", "balance_sheet_summary", "valuation_assumptions", "wacc_assumptions", "dcf_analysis", "multiples_crosscheck", "valuation_summary", "sensitivity_and_risks", "comparable_evidence", "sources"}
            else ""
        )
        post_table_guidance_html = (
            ""
            if key in {"valuation_methodology", "financial_performance", "financial_ratio_analysis", "normalisations_schedule", "balance_sheet_summary", "valuation_assumptions", "wacc_assumptions", "dcf_analysis", "multiples_crosscheck", "valuation_summary", "sensitivity_and_risks", "comparable_evidence", "sources", "disclaimer"}
            else guidance_html
        )
        for sub_key, subtable in extra_tables.items():
            subheading = {
                "cash_flow_schedule": "Mid-case forecast cash-flow schedule",
                "specific_risk_factors": "Specific risk factors",
                "debt_capacity_table": "Debt-capacity constraints",
                "amortisation_profile_table": "P&I leverage profile",
                "sector_scale_table": "Sector scale and boundary",
                "market_sources_table": "Market data sources",
            }.get(sub_key, _report_table_caption(sub_key))
            subtable_html = render_table(subtable, subheading)
            if subtable_html:
                table_html += (
                    f"<h3>{_html_lib.escape(subheading)}</h3>"
                    f"{subtable_html}"
                )

        section_classes = ["report-section"]
        if key == "executive_summary":
            section_classes.append("executive-summary")
        if key == "disclaimer":
            section_classes.append("disclaimer")
        section_classes.append(f"section-{key.replace('_', '-')}")
        section_class = " ".join(section_classes)
        section_kicker = (
            "AccountIQ bank credit paper"
            if report_type == "bank_credit_paper"
            else "AccountIQ indicative valuation"
        )
        section_html += f"""
        <section id="{_html_lib.escape(key, quote=True)}" class="{section_class}">
            <span class="section-kicker">{_html_lib.escape(section_kicker)}</span>
            <h2><span class="section-number">{section_number:02d}</span> {_html_lib.escape(heading)}</h2>
            {pre_narrative_guidance_html}
            {paragraphs}
            {market_charts_html}
            {executive_highlights_html}
            {valuation_range_visual_html}
            {pre_table_guidance_html}
            {valuation_method_selection_html}
            {financial_trend_visual_html}
            {normalised_ebitda_bridge_visual_html}
            {equity_bridge_visual_html}
            {wacc_build_visual_html}
            {dcf_value_build_visual_html}
            {implied_multiple_reconciliation_html}
            {sensitivity_spread_visual_html}
            {table_html}
            {post_table_guidance_html}
        </section>"""

    return section_html


def _render_cover_valuation_snapshot_html(sections: dict) -> str:
    """Render a compact cover snapshot from the report's own valuation table."""
    priority_terms = (
        "enterprise value",
        "net debt",
        "equity value",
        "indicative equity",
    )

    for section_key in ("executive_summary", "valuation_summary"):
        content = sections.get(section_key)
        if not isinstance(content, dict):
            continue
        table = content.get("table")
        if not isinstance(table, dict):
            continue
        headers = table.get("headers")
        rows = table.get("rows")
        if not isinstance(headers, list) or len(headers) < 2 or not isinstance(rows, list):
            continue

        scenario_headers = [str(header) for header in headers[1:4]]
        snapshot_rows: list[list[str]] = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 2:
                continue
            label = str(row[0])
            if not any(term in label.lower() for term in priority_terms):
                continue
            snapshot_rows.append([label, *[str(value) for value in row[1:4]]])

        if not scenario_headers or not snapshot_rows:
            continue

        header_cells = "".join(f"<th>{_html_lib.escape(value)}</th>" for value in ["Output", *scenario_headers])
        row_cells = "".join(
            "<tr>"
            + "".join(f"<td>{_html_lib.escape(value)}</td>" for value in row)
            + "</tr>"
            for row in snapshot_rows[:3]
        )
        return f"""
        <aside class="cover-snapshot" aria-label="Valuation snapshot">
          <span>Valuation snapshot</span>
          <table>
            <thead><tr>{header_cells}</tr></thead>
            <tbody>{row_cells}</tbody>
          </table>
          <p>Computed from the same valuation table used in the body of this report.</p>
        </aside>
        """

    return ""


def _render_cover_report_brief_html(
    *,
    company_name: str,
    report_label: str,
    report_id: int,
    report_type: str = "valuation_advisory",
    generated_at: str = "",
    valuation_purpose: str = "",
    demo_mode: bool = False,
) -> str:
    """Render professional cover metadata without adding more owner questions."""
    if report_type == "bank_credit_paper":
        reliance = (
            "Demo credit paper only - not for reliance."
            if demo_mode
            else "Indicative lender screening only; not credit approval or a lender commitment."
        )
        rows = [
            ("Prepared for", company_name),
            ("Prepared by", "AccountIQ"),
            ("Report type", report_label),
            ("Reference", report_reference_code(report_id, report_type)),
            ("Prepared date", report_display_date(generated_at)),
            ("Purpose", "Credit paper / lender screening"),
            ("Credit posture", "Screening-only until diligence and bank approval"),
            ("Reliance", reliance),
        ]
    else:
        purpose = valuation_purpose.strip() or "Not specified"
        reliance = (
            "Demo data only - not for reliance."
            if demo_mode
            else "Indicative valuation support only; obtain independent professional advice before reliance."
        )
        rows = [
            ("Prepared for", company_name),
            ("Prepared by", "AccountIQ"),
            ("Report type", report_label),
            ("Reference", report_reference_code(report_id, report_type)),
            ("Valuation date", report_display_date(generated_at)),
            ("Purpose", purpose),
            ("Basis of value", "Indicative fair-market value, going-concern basis"),
            ("Reliance", reliance),
        ]
    row_html = "".join(
        "<div>"
        f"<dt>{_html_lib.escape(label)}</dt>"
        f"<dd>{_html_lib.escape(str(value))}</dd>"
        "</div>"
        for label, value in rows
    )
    return f"""
    <aside class="cover-brief" aria-label="Report cover details">
      <dl>{row_html}</dl>
    </aside>
    """


def _render_cover_report_basis_html(report_type: str = "valuation_advisory") -> str:
    """Render the evidence basis on the cover without asking more questions."""
    rows = (
        [
            ("Uploaded financials", "Revenue, EBITDA and balance sheet"),
            ("Lender inputs", "Facility, LVR, funding cost and security"),
            ("Public client context", "Business and sector research"),
            ("Credit model", "DSCR, ICR, leverage and NTOA"),
        ]
        if report_type == "bank_credit_paper"
        else [
            ("Uploaded financials", "Revenue, earnings and balance sheet"),
            ("Five private inputs", "Only facts management can confirm"),
            ("Public-source trail", "Research URLs retained for review"),
            ("AccountIQ model", "DCF, WACC, multiples and sensitivity"),
        ]
    )
    row_html = "".join(
        "<div>"
        f"<dt>{_html_lib.escape(label)}</dt>"
        f"<dd>{_html_lib.escape(note)}</dd>"
        "</div>"
        for label, note in rows
    )
    return f"""
    <aside class="cover-report-basis" aria-label="Report basis">
      <span>Report basis</span>
      <dl>{row_html}</dl>
    </aside>
    """


def _render_report_contents_html(sections: dict, section_order: list) -> str:
    """Render the report contents list with real, accessible section numbers."""
    contents_html = ""
    section_number = 0
    for key in section_order:
        if key not in sections:
            continue
        section_number += 1
        title = _REPORT_SECTION_TITLES.get(key, str(key).replace("_", " ").title())
        accessible_title = f"{section_number:02d} {title}"
        contents_html += (
            f"<li><a href='#{_html_lib.escape(str(key), quote=True)}' "
            f"aria-label='{_html_lib.escape(accessible_title, quote=True)}'>"
            f"<span class='contents-number'>{section_number:02d}</span>"
            f"<span>{_html_lib.escape(title)}</span>"
            "</a></li>"
        )
    return contents_html


def _render_valuation_basis_html(
    *,
    company_name: str = "",
    report_label: str = "",
    report_id: int | str | None = None,
    demo_mode: bool,
    valuation_purpose: str = "",
    generated_at: str = "",
    intake_answers: dict | None = None,
) -> str:
    """Render unnumbered valuation front-matter that explains evidence basis."""
    basis = valuation_basis_of_preparation(
        company_name=company_name,
        report_label=report_label,
        report_id=report_id,
        demo_mode=demo_mode,
        valuation_purpose=valuation_purpose,
        generated_at=generated_at,
        intake_answers=intake_answers,
    )

    def render_basis_table(table_data: dict, class_name: str) -> str:
        headers = table_data.get("headers", []) if isinstance(table_data, dict) else []
        rows = table_data.get("rows", []) if isinstance(table_data, dict) else []
        header_html = "".join(f"<th>{_inline_report_html(value)}</th>" for value in headers)
        row_html = "".join(
            "<tr>"
            + "".join(f"<td>{_inline_report_html(cell)}</td>" for cell in row)
            + "</tr>"
            for row in rows
            if isinstance(row, list)
        )
        return (
            f"<table class='report-table {class_name}'>"
            f"<thead><tr>{header_html}</tr></thead>"
            f"<tbody>{row_html}</tbody>"
            "</table>"
            if header_html or row_html
            else ""
        )

    report_letter = basis.get("report_letter") if isinstance(basis.get("report_letter"), dict) else {}
    report_letter_table = (
        report_letter.get("table")
        if isinstance(report_letter.get("table"), dict)
        else {}
    )
    report_letter_html = ""
    if report_letter:
        report_letter_html = (
            '<div class="basis-report-letter">'
            f"<h3>{_inline_report_html(str(report_letter.get('title') or 'Report letter'))}</h3>"
            f"{_narrative_to_html(str(report_letter.get('narrative') or ''))}"
            f"{render_basis_table(report_letter_table, 'report-letter-table')}"
            "</div>"
        )
    scope_table_html = render_basis_table(basis["scope_table"], "scope-table")
    management_input_table = (
        basis.get("management_input_table")
        if isinstance(basis.get("management_input_table"), dict)
        else {}
    )
    management_input_table_html = (
        render_basis_table(management_input_table, "management-input-table")
        if management_input_table.get("rows")
        else ""
    )
    basis_table_html = render_basis_table(basis["table"], "basis-table")
    return f"""
    <section id="basis-of-preparation" class="report-page basis-page" aria-labelledby="basis-of-preparation-title">
      <span class="section-kicker">Basis of preparation</span>
      <h2 id="basis-of-preparation-title">Basis of preparation</h2>
      {report_letter_html}
      {_narrative_to_html(str(basis["narrative"]))}
      {scope_table_html}
      {"<h3>Management input trail</h3>" if management_input_table_html else ""}
      {management_input_table_html}
      <h3>Evidence and model basis</h3>
      {basis_table_html}
    </section>
    """


@app.get("/wizard/report/{report_id}/view", response_class=HTMLResponse)
async def wizard_report_view(
    report_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Render a completed report as the browser review surface for the report pack."""
    async with db.execute("""
        SELECT r.id, r.report_type, r.status, r.content, r.completed_at, r.demo_mode, r.generation_mode,
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

    intake_answers = await _latest_report_intake_answers(db, report_id)
    valuation_purpose = _valuation_purpose_label(intake_answers.get("valuation_purpose"))
    section_order = SECTION_SCHEMAS.get(row["report_type"], list(sections.keys()))
    demo_mode = _report_demo_mode_from_row(row)
    generation_mode = _report_generation_mode_from_row(row)
    if row["report_type"] == "valuation_advisory":
        label = (
            "Demo Indicative Valuation Report"
            if demo_mode
            else "Evidence-Mode Indicative Valuation Report"
            if generation_mode == "evidence"
            else "Indicative Valuation Report"
        )
    else:
        label = row["report_type"].replace("_", " ").title()
    back_url = f"{os.getenv('APP_BASE_URL', 'http://localhost:3000').rstrip('/')}/wizard"

    section_html = _render_report_sections_html(sections, section_order, row["report_type"])
    cover_snapshot_html = (
        _render_cover_valuation_snapshot_html(sections)
        if row["report_type"] == "valuation_advisory"
        else ""
    )
    cover_report_basis_html = (
        _render_cover_report_basis_html(row["report_type"])
        if row["report_type"] in {"valuation_advisory", "bank_credit_paper"}
        else ""
    )
    cover_brief_html = (
        _render_cover_report_brief_html(
            company_name=row["name"],
            report_label=label,
            report_type=row["report_type"],
            report_id=row["id"],
            generated_at=row["completed_at"] or "",
            valuation_purpose=valuation_purpose,
            demo_mode=demo_mode,
        )
        if row["report_type"] in {"valuation_advisory", "bank_credit_paper"}
        else ""
    )
    basis_html = (
        _render_valuation_basis_html(
            company_name=row["name"],
            report_label=label,
            report_id=row["id"],
            demo_mode=demo_mode,
            valuation_purpose=valuation_purpose,
            generated_at=row["completed_at"] or "",
            intake_answers=intake_answers,
        )
        if row["report_type"] == "valuation_advisory"
        else ""
    )
    contents_html = _render_report_contents_html(sections, section_order)
    basis_contents_html = (
        """
        <div class="contents-frontmatter">
          <a href="#basis-of-preparation"><span>Front matter</span>Report letter and basis of preparation</a>
        </div>
        """
        if row["report_type"] == "valuation_advisory"
        else ""
    )
    demo_banner = (
        """
        <aside class="demo-banner" role="note">
          <strong>Demo data - not for reliance.</strong>
          Research, financial figures and valuation conclusions in this report are simulated
          to demonstrate the AccountIQ experience.
        </aside>
        """
        if demo_mode
        else ""
    )
    cover_kicker = (
        "Demo data - not for reliance"
        if demo_mode
        else "Confidential - indicative only"
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_html_lib.escape(label)} - {_html_lib.escape(row['name'])}</title>
<style>
  :root {{ --navy:#082b4c; --blue:#1769aa; --ink:#172033; --muted:#667085; --line:#d7dee8; }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{ margin:0; background:#edf1f5; color:var(--ink); font-family:"Aptos","Segoe UI",Arial,sans-serif; line-height:1.58; }}
  .viewer-toolbar {{ position:sticky; top:0; z-index:10; display:flex; justify-content:space-between;
                     align-items:center; min-height:52px; padding:8px max(20px, calc((100vw - 900px)/2));
                     background:rgba(8,43,76,.96); color:white; box-shadow:0 2px 10px rgba(8,43,76,.18); }}
  .viewer-toolbar a {{ color:white; text-decoration:none; font-size:.875rem; font-weight:700; }}
  .viewer-toolbar span {{ font-size:.78rem; opacity:.8; }}
  .viewer-toolbar-actions {{ display:flex; align-items:center; gap:14px; }}
  .viewer-download {{ display:inline-flex; align-items:center; justify-content:center; min-height:34px; padding:7px 12px;
                      border:1px solid rgba(255,255,255,.56); border-radius:999px; background:rgba(255,255,255,.12); }}
  .viewer-download:hover {{ background:rgba(255,255,255,.2); text-decoration:none; }}
  .report {{ width:min(900px, calc(100% - 32px)); margin:28px auto 64px; }}
  .demo-banner {{ margin:0 0 18px; padding:14px 18px; border:1px solid #e3ad55; border-radius:8px;
                  background:#fff8e8; color:#70450a; font-size:.88rem; }}
  .demo-banner strong {{ display:block; margin-bottom:2px; }}
  .report-page {{ min-height:1120px; padding:78px 74px; background:white; box-shadow:0 12px 30px rgba(15,23,42,.10); }}
  .cover {{ position:relative; display:flex; flex-direction:column; justify-content:flex-end; overflow:hidden;
            min-height:1120px; padding:84px 76px; background:linear-gradient(150deg, #f8fbff 0 52%, #dceafb 52% 64%, #082b4c 64%); color:white; }}
  .cover::before {{ content:""; position:absolute; top:72px; left:76px; width:86px; height:7px; background:#2f80c5; }}
  .brand {{ position:absolute; top:98px; left:76px; color:var(--navy); font-size:1.05rem; font-weight:900; letter-spacing:.04em; }}
  .cover-copy {{ position:relative; max-width:760px; padding:28px 32px 30px; border:1px solid rgba(207,226,243,.28);
                 border-radius:22px; background:rgba(8,43,76,.92); box-shadow:0 20px 42px rgba(8,43,76,.24); }}
  .cover-snapshot {{ position:relative; width:100%; margin:0 0 78px; padding:20px 24px 18px; border:1px solid #c8d6e5;
                     border-radius:18px; background:white; color:var(--ink); box-shadow:0 16px 35px rgba(8,43,76,.12); }}
  .cover-snapshot span {{ display:block; margin:-20px -24px 16px; padding:10px 24px; border-radius:18px 18px 0 0;
                          background:var(--blue); color:white; font-size:.82rem; font-weight:850; letter-spacing:.06em;
                          text-transform:uppercase; }}
  .cover-snapshot table {{ width:100%; border-collapse:collapse; font-size:.9rem; }}
  .cover-snapshot th, .cover-snapshot td {{ padding:10px 0; border-bottom:1px solid var(--line); text-align:right; }}
  .cover-snapshot th:first-child, .cover-snapshot td:first-child {{ text-align:left; }}
  .cover-snapshot tbody td:not(:first-child) {{ font-weight:800; font-variant-numeric:tabular-nums; }}
  .cover-snapshot p {{ margin:10px 0 0; color:var(--muted); font-size:.76rem; }}
  .cover-report-basis {{ position:relative; width:100%; margin:58px 0 34px; padding:18px 22px; border:1px solid #d7dee8;
                         border-radius:18px; background:rgba(255,255,255,.92); color:var(--ink);
                         box-shadow:0 12px 28px rgba(8,43,76,.10); }}
  .cover-report-basis span {{ display:block; margin:0 0 13px; color:var(--blue); font-size:.72rem; font-weight:850;
                              letter-spacing:.08em; text-transform:uppercase; }}
  .cover-report-basis dl {{ display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:0; margin:0; }}
  .cover-report-basis div {{ min-width:0; padding:0 18px; border-left:1px solid var(--line); }}
  .cover-report-basis div:first-child {{ padding-left:0; border-left:0; }}
  .cover-report-basis dt {{ margin:0 0 5px; color:var(--navy); font-size:.78rem; font-weight:850; }}
  .cover-report-basis dd {{ margin:0; color:var(--muted); font-size:.7rem; line-height:1.35; }}
  .cover-kicker {{ display:block; margin-bottom:12px; color:#b9d8f2; font-size:.78rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }}
  .cover h1 {{ max-width:650px; margin:0 0 18px; font-size:3.3rem; line-height:1.05; letter-spacing:-.035em; }}
  .cover .company {{ margin:0; font-size:1.45rem; font-weight:600; }}
  .cover-brief {{ margin:30px 0 0; padding:18px 20px; border:1px solid rgba(207,226,243,.36);
                  border-radius:16px; background:rgba(255,255,255,.08); backdrop-filter:blur(6px); }}
  .cover-brief dl {{ display:grid; grid-template-columns:1fr 1fr; gap:14px 28px; margin:0; }}
  .cover-brief div {{ min-width:0; }}
  .cover-brief dt {{ margin:0 0 3px; color:#b9d8f2; font-size:.67rem; font-weight:850; letter-spacing:.11em; text-transform:uppercase; }}
  .cover-brief dd {{ margin:0; color:white; font-size:.86rem; font-weight:700; line-height:1.35; overflow-wrap:anywhere; }}
  .cover .cover-meta {{ margin:32px 0 0; color:#cfe2f3; font-size:.86rem; }}
  .contents {{ margin-top:28px; min-height:auto; }}
  .contents h2 {{ margin:0 0 34px; color:var(--navy); font-size:2.45rem; font-weight:400; letter-spacing:-.03em; }}
  .contents-frontmatter {{ margin:0 0 18px; border-top:1px solid var(--line); border-bottom:1px solid var(--line); }}
  .contents-frontmatter a {{ display:flex; gap:12px; padding:13px 0; color:var(--ink); text-decoration:none; font-size:.92rem; font-weight:700; }}
  .contents-frontmatter span {{ min-width:5.2rem; color:var(--blue); font-size:.72rem; font-weight:850; letter-spacing:.04em; text-transform:uppercase; }}
  .contents ol {{ display:grid; grid-template-columns:1fr 1fr; gap:0 38px; margin:0; padding:0; list-style:none; }}
  .contents li {{ border-bottom:1px solid var(--line); }}
  .contents a {{ display:flex; gap:12px; padding:13px 0; color:var(--ink); text-decoration:none; font-size:.92rem; font-weight:700; }}
  .contents-number {{ min-width:2ch; color:var(--blue); font-size:.72rem; letter-spacing:.04em; }}
  .report-section {{ min-height:760px; margin-top:28px; padding:70px 74px 80px; background:white; box-shadow:0 12px 30px rgba(15,23,42,.10); }}
  .section-kicker {{ display:block; margin-bottom:8px; color:var(--blue); font-size:.68rem; font-weight:850; letter-spacing:.12em; text-transform:uppercase; }}
  h2 {{ margin:0 0 28px; padding-bottom:16px; border-bottom:1px solid var(--navy); color:var(--navy);
        font-size:2.2rem; font-weight:400; line-height:1.1; letter-spacing:-.025em; }}
  .section-number {{ display:inline-block; min-width:2.6rem; margin-right:.75rem; color:var(--blue); font-size:1rem; font-weight:850; letter-spacing:.06em; vertical-align:.35rem; }}
  h3 {{ margin:1.7rem 0 .55rem; color:var(--navy); font-size:1.02rem; font-weight:800; }}
  .basis-report-letter {{ margin:0 0 26px; padding:18px 20px; border:1px solid #dbeafe; border-radius:14px;
                          background:linear-gradient(135deg, #f8fbff, #ffffff); }}
  .basis-report-letter h3 {{ margin-top:0; }}
  p {{ margin:0 0 .9rem; font-size:.93rem; }}
  a {{ color:var(--blue); text-decoration:none; overflow-wrap:anywhere; }}
  a:hover {{ text-decoration:underline; }}
  ul {{ margin:.25rem 0 1rem 1.25rem; padding:0; }}
  li {{ margin-bottom:.35rem; font-size:.93rem; line-height:1.55; }}
  .executive-summary {{ border-top:8px solid var(--navy); }}
  .executive-highlights {{ margin:22px 0 24px; padding:18px 20px; border:1px solid #bfdbfe; border-radius:14px;
                          background:linear-gradient(135deg, #eff6ff, #ffffff); }}
  .executive-highlights h3 {{ margin:0 0 14px; color:var(--navy); font-size:1rem; }}
  .executive-highlights dl {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:12px; margin:0; }}
  .executive-highlights div {{ padding:12px; border:1px solid #dbeafe; border-radius:10px; background:white; }}
  .executive-highlights dt {{ margin:0 0 5px; color:var(--blue); font-size:.72rem; font-weight:850; letter-spacing:.05em; text-transform:uppercase; }}
  .executive-highlights dd {{ margin:0; color:var(--navy); font-size:1.08rem; font-weight:850; font-variant-numeric:tabular-nums; }}
  .executive-highlights p {{ margin:6px 0 0; color:var(--muted); font-size:.78rem; line-height:1.35; }}
  .valuation-range-visual,
  .sensitivity-spread-visual {{ margin:0 0 28px; padding:18px 20px; border:1px solid #dbeafe; border-radius:14px;
                                background:linear-gradient(135deg, #f8fbff, #ffffff); }}
  .valuation-range-visual h3,
  .sensitivity-spread-visual h3 {{ margin:0 0 6px; color:var(--navy); font-size:1rem; }}
  .valuation-range-visual > p,
  .sensitivity-spread-visual > p {{ margin:0 0 16px; color:var(--muted); font-size:.78rem; }}
  .range-visual-row {{ display:grid; grid-template-columns:minmax(150px, .34fr) minmax(0, 1fr); gap:18px;
                       align-items:center; margin:0 0 18px; }}
  .range-visual-row:last-child {{ margin-bottom:0; }}
  .range-visual-label strong {{ display:block; color:var(--navy); font-size:.86rem; }}
  .range-visual-label span {{ display:block; margin-top:4px; color:var(--muted); font-size:.72rem; line-height:1.35; }}
  .range-visual-track {{ position:relative; height:48px; }}
  .range-visual-axis {{ position:absolute; left:0; right:0; top:22px; height:2px; background:#d7dee8; }}
  .range-visual-band {{ position:absolute; top:18px; height:10px; border-radius:999px; background:var(--blue); }}
  .range-visual-mid {{ position:absolute; top:15px; width:16px; height:16px; margin-left:-8px; border:3px solid var(--navy);
                       border-radius:999px; background:white; box-shadow:0 2px 8px rgba(8,43,76,.16); }}
  .range-visual-low,
  .range-visual-high,
  .range-visual-mid-label {{ position:absolute; transform:translateX(-50%); white-space:nowrap; font-variant-numeric:tabular-nums; }}
  .range-visual-low,
  .range-visual-high {{ top:33px; color:var(--muted); font-size:.68rem; }}
  .range-visual-mid-label {{ top:0; color:var(--navy); font-size:.72rem; font-weight:850; }}
  .normalised-ebitda-bridge-visual {{ margin:0 0 28px; padding:18px 20px; border:1px solid #dbeafe; border-radius:14px;
                                      background:linear-gradient(135deg, #f8fbff, #ffffff); }}
  .normalised-ebitda-bridge-visual h3 {{ margin:0 0 6px; color:var(--navy); font-size:1rem; }}
  .normalised-ebitda-bridge-visual > p {{ margin:0 0 16px; color:var(--muted); font-size:.78rem; }}
  .normalised-ebitda-bridge-steps {{ display:grid; grid-template-columns:minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1fr);
                                     gap:9px; align-items:stretch; }}
  .normalised-ebitda-bridge-card {{ padding:11px 12px; border:1px solid #dbeafe; border-radius:11px; background:white; }}
  .normalised-ebitda-bridge-card strong {{ display:block; margin:0 0 5px; color:var(--blue); font-size:.68rem; font-weight:850; letter-spacing:.04em; text-transform:uppercase; }}
  .normalised-ebitda-bridge-card span {{ display:block; margin:0; color:var(--navy); font-size:1rem; font-weight:850; font-variant-numeric:tabular-nums; }}
  .normalised-ebitda-bridge-card p {{ margin:6px 0 0; color:var(--muted); font-size:.72rem; line-height:1.35; }}
  .normalised-ebitda-bridge-operator {{ display:flex; align-items:center; justify-content:center; color:var(--navy);
                                        font-size:1.05rem; font-weight:850; }}
  .equity-bridge-visual {{ margin:0 0 28px; padding:18px 20px; border:1px solid #dbeafe; border-radius:14px;
                           background:linear-gradient(135deg, #f8fbff, #ffffff); }}
  .equity-bridge-visual h3 {{ margin:0 0 6px; color:var(--navy); font-size:1rem; }}
  .equity-bridge-visual > p {{ margin:0 0 16px; color:var(--muted); font-size:.78rem; }}
  .equity-bridge-steps {{ display:grid; grid-template-columns:minmax(0, 1.1fr) auto minmax(0, .9fr) auto minmax(0, .9fr) auto minmax(0, 1.2fr);
                          gap:9px; align-items:stretch; margin:0; }}
  .equity-bridge-card {{ padding:11px 12px; border:1px solid #dbeafe; border-radius:11px; background:white; }}
  .equity-bridge-card strong {{ display:block; margin:0 0 5px; color:var(--blue); font-size:.68rem; font-weight:850; letter-spacing:.04em; text-transform:uppercase; }}
  .equity-bridge-card span {{ display:block; margin:0; color:var(--navy); font-size:1rem; font-weight:850; font-variant-numeric:tabular-nums; }}
  .equity-bridge-card p {{ margin:6px 0 0; color:var(--muted); font-size:.72rem; line-height:1.35; }}
  .equity-bridge-operator {{ display:flex; align-items:center; justify-content:center; color:var(--navy);
                             font-size:1.05rem; font-weight:850; }}
  .wacc-build-visual {{ margin:0 0 28px; padding:18px 20px; border:1px solid #dbeafe; border-radius:14px;
                        background:linear-gradient(135deg, #f8fbff, #ffffff); }}
  .wacc-build-visual h3 {{ margin:0 0 6px; color:var(--navy); font-size:1rem; }}
  .wacc-build-visual > p {{ margin:0 0 16px; color:var(--muted); font-size:.78rem; }}
  .wacc-build-rows {{ display:grid; gap:10px; }}
  .wacc-build-row {{ display:grid; grid-template-columns:minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1fr);
                     gap:9px; align-items:stretch; }}
  .wacc-build-card {{ padding:11px 12px; border:1px solid #dbeafe; border-radius:11px; background:white; }}
  .wacc-build-card strong {{ display:block; margin:0 0 5px; color:var(--blue); font-size:.68rem; font-weight:850; letter-spacing:.04em; text-transform:uppercase; }}
  .wacc-build-card span {{ display:block; margin:0; color:var(--navy); font-size:1rem; font-weight:850; font-variant-numeric:tabular-nums; }}
  .wacc-build-card p {{ margin:6px 0 0; color:var(--muted); font-size:.72rem; line-height:1.35; }}
  .wacc-build-operator {{ display:flex; align-items:center; justify-content:center; color:var(--navy);
                          font-size:1.05rem; font-weight:850; }}
  .dcf-value-build-visual {{ margin:0 0 28px; padding:18px 20px; border:1px solid #dbeafe; border-radius:14px;
                             background:linear-gradient(135deg, #f8fbff, #ffffff); }}
  .dcf-value-build-visual h3 {{ margin:0 0 6px; color:var(--navy); font-size:1rem; }}
  .dcf-value-build-visual > p {{ margin:0 0 16px; color:var(--muted); font-size:.78rem; }}
  .dcf-value-build-rows {{ display:grid; gap:10px; }}
  .dcf-value-build-row {{ display:grid; grid-template-columns:minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1.08fr);
                          gap:9px; align-items:stretch; }}
  .dcf-value-build-card {{ padding:11px 12px; border:1px solid #dbeafe; border-radius:11px; background:white; }}
  .dcf-value-build-card strong {{ display:block; margin:0 0 5px; color:var(--blue); font-size:.68rem; font-weight:850; letter-spacing:.04em; text-transform:uppercase; }}
  .dcf-value-build-card span {{ display:block; margin:0; color:var(--navy); font-size:1rem; font-weight:850; font-variant-numeric:tabular-nums; }}
  .dcf-value-build-card p {{ margin:6px 0 0; color:var(--muted); font-size:.72rem; line-height:1.35; }}
  .dcf-value-build-operator {{ display:flex; align-items:center; justify-content:center; color:var(--navy);
                               font-size:1.05rem; font-weight:850; }}
  .implied-multiple-visual {{ margin:0 0 28px; padding:18px 20px; border:1px solid #dbeafe; border-radius:14px;
                              background:linear-gradient(135deg, #f8fbff, #ffffff); }}
  .implied-multiple-visual h3 {{ margin:0 0 6px; color:var(--navy); font-size:1rem; }}
  .implied-multiple-visual > p {{ margin:0 0 16px; color:var(--muted); font-size:.78rem; }}
  .implied-multiple-grid {{ display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:10px; }}
  .implied-multiple-card {{ padding:11px 12px; border:1px solid #dbeafe; border-radius:11px; background:white; }}
  .implied-multiple-card strong {{ display:block; margin:0 0 5px; color:var(--blue); font-size:.68rem; font-weight:850; letter-spacing:.04em; text-transform:uppercase; }}
  .implied-multiple-card span {{ display:block; margin:0; color:var(--navy); font-size:1rem; font-weight:850; font-variant-numeric:tabular-nums; }}
  .implied-multiple-card p {{ margin:6px 0 0; color:var(--muted); font-size:.72rem; line-height:1.35; }}
  .method-selection-visual {{ margin:0 0 28px; padding:18px 20px; border:1px solid #dbeafe; border-radius:14px;
                              background:linear-gradient(135deg, #f8fbff, #ffffff); }}
  .method-selection-visual h3 {{ margin:0 0 6px; color:var(--navy); font-size:1rem; }}
  .method-selection-visual > p {{ margin:0 0 16px; color:var(--muted); font-size:.78rem; }}
  .method-selection-visual table {{ width:100%; border-collapse:collapse; font-size:.76rem; }}
  .method-selection-visual th {{ padding:9px 10px; background:var(--navy); color:white; text-align:left; font-weight:800; }}
  .method-selection-visual td {{ padding:10px; border:1px solid #dbeafe; color:var(--ink); vertical-align:top; line-height:1.35; }}
  .method-selection-visual tbody tr:nth-child(even) {{ background:#f8fbff; }}
  .executive-summary table.report-table {{ margin-top:28px; }}
  .reader-guidance {{ margin:0 0 28px; padding:16px 18px; border:1px solid var(--line); border-radius:14px;
                     background:linear-gradient(135deg, #f8fbff, #ffffff); }}
  .reader-guidance h3 {{ margin:0 0 13px; color:var(--navy); font-size:.98rem; }}
  .reader-guidance dl {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:11px; margin:0; }}
  .reader-guidance div {{ padding:11px 12px; border:1px solid #e4eaf2; border-radius:10px; background:white; }}
  .reader-guidance dt {{ margin:0 0 4px; color:var(--blue); font-size:.7rem; font-weight:850; letter-spacing:.05em; text-transform:uppercase; }}
  .reader-guidance dd {{ margin:0; color:var(--navy); font-size:1rem; font-weight:850; font-variant-numeric:tabular-nums; }}
  .reader-guidance p {{ margin:6px 0 0; color:var(--muted); font-size:.77rem; line-height:1.35; }}
  .market-line-chart {{ margin:24px 0; padding:18px 20px 14px; border:1px solid #dbe5ef; border-radius:14px;
                        background:linear-gradient(145deg, #f8fbff, #fff); break-inside:avoid; }}
  .market-line-chart figcaption strong {{ display:block; color:var(--navy); font-size:.98rem; }}
  .market-line-chart figcaption span {{ display:block; margin-top:3px; color:var(--muted); font-size:.77rem; }}
  .market-line-chart svg {{ display:block; width:100%; height:auto; margin-top:8px; overflow:visible; }}
  .market-chart-legend {{ display:flex; flex-wrap:wrap; gap:14px; margin:12px 0 0; color:var(--muted); font-size:.72rem; }}
  .market-chart-legend span {{ display:inline-flex; align-items:center; gap:6px; }}
  .market-chart-legend i {{ width:18px; height:3px; border-radius:999px; }}
  .market-chart-source {{ margin:4px 0 0; color:var(--muted); font-size:.67rem; line-height:1.4; }}
  .financial-trend-visual {{ margin:0 0 28px; padding:18px 20px; border:1px solid #dbeafe; border-radius:14px;
                             background:linear-gradient(135deg, #f8fbff, #ffffff); }}
  .financial-trend-header {{ display:flex; align-items:flex-start; justify-content:space-between; gap:18px; margin-bottom:14px; }}
  .financial-trend-header h3 {{ margin:0 0 6px; color:var(--navy); font-size:1rem; }}
  .financial-trend-header p {{ margin:0; color:var(--muted); font-size:.78rem; }}
  .financial-trend-header dl {{ display:flex; gap:12px; margin:0; }}
  .financial-trend-header dl div {{ display:flex; align-items:center; gap:5px; }}
  .financial-trend-header dt {{ color:var(--muted); font-size:.68rem; font-weight:850; letter-spacing:.05em; text-transform:uppercase; }}
  .financial-trend-header dd {{ width:22px; height:7px; margin:0; border-radius:999px; background:var(--blue); }}
  .financial-trend-header dl div:nth-child(2) dd {{ background:#2e7d32; }}
  .financial-trend-row {{ display:grid; grid-template-columns:minmax(120px, .22fr) minmax(0, 1fr); gap:16px; align-items:center; margin-bottom:11px; }}
  .financial-trend-row:last-child {{ margin-bottom:0; }}
  .financial-trend-period strong {{ display:block; color:var(--navy); font-size:.82rem; }}
  .financial-trend-period span {{ display:block; margin-top:3px; color:var(--muted); font-size:.7rem; }}
  .financial-trend-bars {{ display:grid; gap:5px; }}
  .financial-trend-bar {{ position:relative; height:18px; border-radius:999px; background:#e6ecf3; overflow:hidden; }}
  .financial-trend-bar span {{ position:absolute; left:0; top:0; bottom:0; border-radius:999px; background:var(--blue); }}
  .financial-trend-bar.ebitda span {{ background:#2e7d32; }}
  .financial-trend-bar strong {{ position:absolute; right:8px; top:50%; transform:translateY(-50%); color:var(--navy);
                                 font-size:.66rem; font-weight:850; font-variant-numeric:tabular-nums; }}
  .disclaimer {{ min-height:auto; border-top:8px solid #c9932f; background:#fffdf8; }}
  .disclaimer p, .disclaimer li {{ color:#5f4b22; font-size:.84rem; }}
  .meta {{ font-size:.8rem; color:var(--muted); }}
  table.report-table {{ width:100%; margin:20px 0 28px; border-collapse:collapse; font-size:.82rem; }}
  table.report-table caption {{ caption-side:top; margin:0 0 8px; color:var(--muted); font-size:.72rem; font-weight:850; letter-spacing:.08em; text-align:left; text-transform:uppercase; }}
  table.report-table th, table.report-table td {{ padding:10px 11px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
  table.report-table thead th {{ border-bottom:2px solid var(--navy); background:var(--navy); color:white; font-weight:750; }}
  table.report-table tbody tr:nth-child(even) {{ background:#f6f8fb; }}
  table.report-table .numeric-cell {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .section-sources table.report-table td,
  .section-comparable-evidence table.report-table td {{ text-align:left; overflow-wrap:anywhere; font-variant-numeric:normal; }}
  .basis-page {{ min-height:auto; }}
  .basis-page h2 {{ margin-bottom:20px; }}
  .basis-table td,
  .scope-table td {{ text-align:left !important; font-variant-numeric:normal !important; }}
  @media (max-width:720px) {{
    .report {{ width:100%; margin:0; }}
    .cover, .report-page, .report-section {{ min-height:auto; margin:0; padding:48px 24px; box-shadow:none; }}
    .cover {{ min-height:80vh; }}
    .cover h1 {{ font-size:2.35rem; }}
    .brand, .cover::before {{ left:24px; }}
    .cover-report-basis {{ margin:96px 0 28px; padding:16px; }}
    .cover-report-basis dl {{ grid-template-columns:1fr 1fr; gap:12px; }}
    .cover-report-basis div {{ padding:0; border-left:0; }}
    .cover-snapshot {{ margin:0 0 40px; padding:16px; }}
    .cover-snapshot span {{ margin:-16px -16px 12px; padding:9px 16px; }}
    .cover-snapshot table {{ display:block; overflow-x:auto; }}
    .cover-copy {{ padding:24px; }}
    .cover-brief dl {{ grid-template-columns:1fr; }}
    .executive-highlights dl {{ grid-template-columns:1fr; }}
    .range-visual-row {{ grid-template-columns:1fr; gap:10px; }}
    .normalised-ebitda-bridge-steps {{ grid-template-columns:1fr; }}
    .normalised-ebitda-bridge-operator {{ min-height:20px; }}
    .equity-bridge-steps {{ grid-template-columns:1fr; }}
    .equity-bridge-operator {{ min-height:20px; }}
    .wacc-build-row {{ grid-template-columns:1fr; }}
    .wacc-build-operator {{ min-height:20px; }}
    .dcf-value-build-row {{ grid-template-columns:1fr; }}
    .dcf-value-build-operator {{ min-height:20px; }}
    .implied-multiple-grid {{ grid-template-columns:1fr; }}
    .method-selection-visual {{ overflow-x:auto; }}
    .method-selection-visual table {{ min-width:680px; }}
    .reader-guidance dl {{ grid-template-columns:1fr; }}
    .financial-trend-header {{ display:grid; }}
    .financial-trend-row {{ grid-template-columns:1fr; gap:8px; }}
    .contents ol {{ grid-template-columns:1fr; }}
    table.report-table {{ display:block; overflow-x:auto; }}
    .viewer-toolbar {{ flex-wrap:wrap; gap:8px; padding:10px 18px; }}
    .viewer-toolbar-actions {{ width:100%; justify-content:space-between; }}
  }}
  @media print {{
    @page {{ size:A4; margin:0; }}
    body {{ background:white; }}
    .viewer-toolbar {{ display:none; }}
    .report {{ width:100%; margin:0; }}
    .cover, .report-page, .report-section {{ width:210mm; min-height:297mm; margin:0; padding:20mm 18mm; box-shadow:none; break-after:page; page-break-after:always; }}
    .contents {{ min-height:297mm; }}
    .report-section:last-child {{ break-after:auto; page-break-after:auto; }}
    h2, h3, table {{ break-after:avoid; page-break-after:avoid; }}
    tr, p, li {{ break-inside:avoid; page-break-inside:avoid; }}
  }}
</style>
</head>
<body>
<nav class="viewer-toolbar">
  <a href="{_html_lib.escape(back_url, quote=True)}">&#x2190; Back to AccountIQ</a>
  <div class="viewer-toolbar-actions">
    <span>PDF download ready</span>
    <a class="viewer-download" href="./pdf" download>Download PDF</a>
  </div>
</nav>
<main class="report">
  {demo_banner}
  <section class="cover">
    <div class="brand">AccountIQ</div>
    {cover_report_basis_html}
    {cover_snapshot_html}
    <div class="cover-copy">
      <span class="cover-kicker">{_html_lib.escape(cover_kicker)}</span>
      <h1>{_html_lib.escape(label)}</h1>
      <p class="company">{_html_lib.escape(row['name'])}</p>
      {cover_brief_html}
      <p class="cover-meta">{_html_lib.escape(report_reference_code(row['id'], row['report_type']))} &nbsp; | &nbsp; Prepared {_html_lib.escape(report_display_date(row['completed_at']))}</p>
    </div>
  </section>
  <section class="report-page contents">
    <span class="section-kicker">Report navigation</span>
    <h2>Contents</h2>
    {basis_contents_html}
    <ol>{contents_html}</ol>
  </section>
  {basis_html}
  {section_html}
</main>
</body>
</html>"""
    if row["report_type"] == "valuation_advisory" and not demo_mode:
        audit = audit_valuation_report_html(html, demo_mode=demo_mode)
        if not audit.passed:
            issue_details = ", ".join(
                issue.get("code", "quality_issue")
                for issue in (audit.as_dict().get("issues") or [])
                if isinstance(issue, dict)
            )
            raise HTTPException(
                500,
                "Generated valuation browser report failed professional artifact quality checks"
                + (f": {issue_details}" if issue_details else "."),
            )
    elif row["report_type"] == "bank_credit_paper":
        audit = audit_bank_credit_report_html(html, demo_mode=demo_mode)
        if not audit.passed:
            issue_details = ", ".join(
                issue.get("code", "quality_issue")
                for issue in (audit.as_dict().get("issues") or [])
                if isinstance(issue, dict)
            )
            raise HTTPException(
                500,
                "Generated bank credit browser report failed professional artifact quality checks"
                + (f": {issue_details}" if issue_details else "."),
            )
    return HTMLResponse(content=html)


@app.get("/wizard/report/{report_id}/pdf", response_class=FileResponse)
async def wizard_report_pdf(
    report_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Render the authenticated report view to a downloadable A4 PDF."""
    async with db.execute(
        """
        SELECT r.id, r.report_type, r.status, r.content, r.completed_at, r.demo_mode, r.generation_mode, c.name
        FROM reports r
        JOIN companies c ON c.id = r.company_id
        WHERE r.id=? AND r.user_id=?
        """,
        (report_id, current_user["id"]),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Report not found")
    if row["status"] != "done":
        raise HTTPException(400, f"Report is not ready yet (status: {row['status']})")
    try:
        sections = json.loads(row["content"])
    except Exception:
        raise HTTPException(500, "Report content could not be parsed")

    intake_answers = await _latest_report_intake_answers(db, report_id)
    valuation_purpose = _valuation_purpose_label(intake_answers.get("valuation_purpose"))
    company_name = row["name"]
    demo_mode = _report_demo_mode_from_row(row)
    generation_mode = _report_generation_mode_from_row(row)
    if row["report_type"] == "valuation_advisory":
        report_label = (
            "Demo Indicative Valuation Report"
            if demo_mode
            else "Evidence-Mode Indicative Valuation Report"
            if generation_mode == "evidence"
            else "Indicative Valuation Report"
        )
    else:
        report_label = row["report_type"].replace("_", " ").title()
    section_order = SECTION_SCHEMAS.get(row["report_type"], list(sections.keys()))
    output_path = report_pdf_path(EXPORT_DIR, report_id)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: write_report_pdf(
            output_path,
            company_name=company_name,
            report_label=report_label,
            report_type=row["report_type"],
            valuation_purpose=valuation_purpose,
            intake_answers=intake_answers,
            sections=sections,
            section_order=section_order,
            section_titles=_REPORT_SECTION_TITLES,
            report_id=report_id,
            generated_at=row["completed_at"] or "",
            demo_mode=demo_mode,
        ),
    )

    if row["report_type"] == "valuation_advisory" and not demo_mode:
        audit = await loop.run_in_executor(
            None,
            lambda: audit_valuation_report_pdf(output_path, demo_mode=demo_mode),
        )
        if not audit.passed:
            issue_details = ", ".join(
                issue.get("code", "quality_issue")
                for issue in (audit.as_dict().get("issues") or [])
                if isinstance(issue, dict)
            )
            raise HTTPException(
                500,
                "Generated valuation PDF failed professional artifact quality checks"
                + (f": {issue_details}" if issue_details else "."),
            )
    elif row["report_type"] == "bank_credit_paper":
        audit = await loop.run_in_executor(
            None,
            lambda: audit_bank_credit_report_pdf(output_path, demo_mode=demo_mode),
        )
        if not audit.passed:
            issue_details = ", ".join(
                issue.get("code", "quality_issue")
                for issue in (audit.as_dict().get("issues") or [])
                if isinstance(issue, dict)
            )
            raise HTTPException(
                500,
                "Generated bank credit PDF failed professional artifact quality checks"
                + (f": {issue_details}" if issue_details else "."),
            )

    safe_name = _re.sub(r"[^A-Za-z0-9._-]+", "-", company_name).strip("-") or f"report-{report_id}"
    reference_code = report_reference_code(report_id, row["report_type"])

    if row["report_type"] == "bank_credit_paper":
        download_suffix = "demo-bank-credit-paper" if demo_mode else "bank-credit-paper"
    else:
        download_suffix = "demo-indicative-valuation" if demo_mode else "indicative-valuation"

    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=f"{safe_name}-{reference_code}-{download_suffix}.pdf",
    )


# ---------------------------------------------------------------------------
# Report generation background task (Phase 5)
# ---------------------------------------------------------------------------

# REPORT_SECTIONS is kept for backward compatibility but SECTION_SCHEMAS
# (from report_prompts) is the canonical source used by generate_report and Phase 7.
# Both use the same full report-type keys (e.g. 'valuation_advisory').
REPORT_SECTIONS = SECTION_SCHEMAS  # alias — do not remove


class _DemoResearchBrief(SimpleNamespace):
    """Small pydantic-like object for no-key local demo report generation."""

    def model_dump(self) -> dict:
        return dict(self.__dict__)


def _demo_research_brief(
    *,
    company_name: str,
    company_location: str,
    industry_sector: str,
) -> _DemoResearchBrief:
    """Return conservative deterministic research inputs for local demo mode."""
    return _DemoResearchBrief(
        company_summary=(
            f"Demo-mode public research is not connected. The report therefore treats "
            f"{company_name} as a private SME operating in {company_location} and relies "
            "on uploaded financials plus user-supplied context for business-specific facts."
        ),
        sector_summary=(
            f"Demo-mode sector context for {industry_sector or 'General SME'} is illustrative. "
            "Use a live AI key before relying on public-source market commentary."
        ),
        industry_category=industry_sector or "General SME",
        risk_free_rate=4.0,
        industry_beta=1.0,
        erp=5.5,
        inflation_rate=2.5,
        ev_ebitda_low=3.5,
        ev_ebitda_high=5.0,
        comparable_transactions=[],
        sources=[],
    )


def _section_with_table(narrative: str, table: dict, **extra) -> dict:
    section = {
        "narrative": narrative,
        "table": table if isinstance(table, dict) else {"headers": [], "rows": []},
    }
    section.update(extra)
    return section


def _records_to_table(records: list[dict], headers: list[tuple[str, str]]) -> dict:
    return {
        "headers": [label for _key, label in headers],
        "rows": [
            [str(record.get(key, "")) for key, _label in headers]
            for record in records
        ],
    }


def _format_report_intake_context(intake_answers: dict | None, fields: tuple[str, ...]) -> str:
    """Format supplied context for deterministic report narratives without inventing missing facts."""
    answers = intake_answers or {}
    lines: list[str] = []
    for field in fields:
        value = answers.get(field)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, (list, tuple, set)):
            display = "; ".join(str(item).strip() for item in value if str(item).strip())
        else:
            display = str(value).strip()
        if display:
            lines.append(f"- {field.replace('_', ' ').title()}: {display}")
    return "\n".join(lines) or "- No additional context supplied."


def _demo_report_content_from_inputs(
    *,
    report_type: str,
    company_name: str,
    financial_rows: list[dict],
    valuation_result: dict | None,
    bank_credit_figures: dict | None,
    credit_research_brief: dict | None,
    intake_answers: dict | None = None,
) -> dict:
    """Build a no-key demo report draft that preserves uploaded financial figures."""
    content = _e2e_report_content(report_type, demo_mode=True)
    valuation_context = _format_report_intake_context(
        intake_answers,
        (
            "business_address",
            "instructing_party",
            "valuation_date",
            "source_information",
            "operations_and_services",
            "forecast_pipeline_evidence",
            "premises_and_lease",
            "management_continuity",
        ),
    )
    credit_context = _format_report_intake_context(
        intake_answers,
        (
            "transaction_structure",
            "borrower_structure",
            "ownership_and_sponsor",
            "acquisition_rationale",
            "refinance_context",
            "facility_structure",
            "security_structure",
            "sponsor_bridge_security",
        ),
    )
    if report_type == "valuation_advisory" and valuation_result:
        content.update({
            "introduction": (
                f"## Client and report purpose\nThis local demo indicative valuation draft for {company_name} "
                "uses the figures extracted from the uploaded financial statements. Public research and "
                "narrative drafting are simulated because demo mode is active.\n\n"
                f"## Supplied report context\n{valuation_context}\n\n"
                "## Reliance limitation\nThis is a test draft only and should not be relied on for lending, "
                "sale, investment or tax decisions."
            ),
            "executive_summary": _section_with_table(
                "This demo draft uses the uploaded accounts for the valuation schedules. Review the extracted "
                "figures first; public-market inputs are conservative demo assumptions until a live AI key is configured.",
                valuation_result.get("executive_summary_table") or {},
            ),
            "business_overview": (
                "Demo mode has not run live web research. Use the uploaded financials and any user-supplied "
                f"context as the business-specific evidence for this test draft.\n\n## Business-specific context\n{valuation_context}"
            ),
            "market_position": _section_with_table(
                "Market-position commentary is illustrative in demo mode. Configure live research before relying "
                "on sector positioning or comparable evidence.",
                {
                    "headers": ["Market evidence", "Status", "Use in report"],
                    "rows": [[
                        "Sector and macro context",
                        "Illustrative demo context",
                        "Do not use as a company-specific conclusion.",
                    ]],
                },
            ),
            "about_business_valuations": (
                "A business valuation distinguishes enterprise value from equity value. Enterprise value is the "
                "value of the operating business before debt and surplus cash; equity value is the amount left for "
                "shareholders after the debt/cash bridge."
            ),
            "valuation_methodology": (
                "The demo draft applies a DCF as the primary method and an EV/EBITDA range as a cross-check. "
                "The calculation uses uploaded EBITDA, working-capital inputs where extracted, and conservative "
                "demo discount-rate assumptions."
            ),
            "financial_performance": _section_with_table(
                "Summary P&L extracted from the uploaded financial statements. This table should reconcile to "
                "the source accounts before the draft is relied on.",
                valuation_result.get("financial_performance_table") or {},
            ),
            "financial_ratio_analysis": _section_with_table(
                "Ratio analysis is calculated from the extracted revenue, gross profit, EBITDA and net profit rows.",
                valuation_result.get("financial_ratio_table") or {},
            ),
            "normalisations_schedule": _section_with_table(
                "Normalisations are taken from the earnings review. If none are confirmed, maintainable earnings "
                "equal the uploaded EBITDA basis.",
                valuation_result.get("normalisation_schedule") or {},
            ),
            "balance_sheet_summary": _section_with_table(
                "Balance-sheet rows are shown where uploaded statements include them. NTOA means net tangible "
                "operating assets before cash and interest-bearing debt.",
                valuation_result.get("balance_sheet_summary_table") or {},
            ),
            "valuation_assumptions": _section_with_table(
                "The assumptions trail shows which values came from uploaded accounts, management inputs, demo "
                f"market assumptions or AccountIQ model conventions.\n\n## Management and forecast context\n{valuation_context}",
                valuation_result.get("assumption_source_trail") or {},
            ),
            "wacc_assumptions": _section_with_table(
                "WACC assumptions are deterministic demo values in this no-key test run.",
                valuation_result.get("wacc_assumptions_table") or {},
            ),
            "dcf_analysis": _section_with_table(
                "DCF outputs are calculated from the uploaded earnings base and demo discount-rate assumptions.",
                valuation_result.get("dcf_analysis_table") or {},
                cash_flow_schedule=valuation_result.get("forecast_cash_flow_schedule") or {},
            ),
            "valuation_summary": _section_with_table(
                "Indicative valuation range from the AccountIQ model using uploaded financial rows.",
                valuation_result.get("valuation_summary_table") or {},
            ),
            "multiples_crosscheck": _section_with_table(
                "The multiples cross-check uses a conservative demo EV/EBITDA range until live comparable evidence is configured.",
                valuation_result.get("multiples_crosscheck_table") or {},
            ),
            "sensitivity_and_risks": _section_with_table(
                "Sensitivity analysis shows how the valuation changes under discount-rate and growth cases.",
                valuation_result.get("sensitivity_table") or {},
                specific_risk_factors=valuation_result.get("specific_risk_factors") or {},
            ),
            "comparable_evidence": _section_with_table(
                "No live comparable evidence was researched in demo mode. Treat this section as a placeholder until live research is enabled.",
                valuation_result.get("comparable_evidence_table") or {},
            ),
            "sources": _section_with_table(
                "No live public sources were queried in this demo run. Uploaded financial statements are the source for the financial schedules.\n\n"
                f"## Source inventory supplied by management\n{valuation_context}",
                valuation_result.get("sources_table") or {},
            ),
            "disclaimer": (
                "This demo indicative valuation does not constitute financial advice under the FMCA or "
                "Financial Markets Conduct regime and should not be relied on for any transaction, lending "
                "or investment decision."
            ),
            "general_principles": (
                "The valuation assumes a willing buyer and willing seller, an arm's-length transaction, "
                "reasonable knowledge, no compulsion and going-concern operation at the valuation date."
            ),
            "glossary": (
                "DCF means discounted cash flow: a method that estimates business value from future cash flows. "
                "Enterprise value is operating-business value before debt and surplus cash. Equity value is the "
                "shareholder value after the debt and cash bridge. EBITDA is earnings before interest, tax, "
                "depreciation and amortisation. Maintainable earnings are the earnings expected to continue after "
                "normal one-off or owner-specific adjustments. WACC is the discount rate used to convert future "
                "cash flows into today's value. Terminal value captures value beyond the explicit forecast period. "
                "Illiquidity discount reflects reduced marketability for a private SME. Normalisation means an "
                "earnings adjustment for non-recurring, non-operating or owner-specific items. FMCA refers to New "
                "Zealand's Financial Markets Conduct framework."
            ),
        })
        return {section: content.get(section, "") for section in SECTION_SCHEMAS[report_type]}

    if report_type == "bank_credit_paper" and bank_credit_figures:
        summary = bank_credit_figures.get("requested_facility_summary") or {}
        capacity_headroom = bank_credit_figures.get("capacity_headroom")
        requested_amount = str(summary.get("amount_requested") or "Not provided")
        binding_constraint = str(summary.get("binding_constraint") or "Not available")
        if isinstance(capacity_headroom, (int, float)):
            recommendation_posture = (
                "appears supportable on the available screening calculations"
                if capacity_headroom >= 0
                else "requires revised structure or additional support before committee"
            )
            headroom_text = f"${capacity_headroom:,.0f}"
        else:
            recommendation_posture = "is not committee-ready until the missing evidence is supplied"
            headroom_text = "Not available"
        company_summary = str(
            (credit_research_brief or {}).get("company_summary")
            or f"{company_name} is the borrower reviewed in this local demo credit paper."
        )
        sector_summary = str(
            (credit_research_brief or {}).get("sector_summary")
            or "Live public-source sector research has not been run in demo mode."
        )
        covenant_package = bank_credit_figures.get("covenant_package") or {}
        covenant_label = str(covenant_package.get("label") or "Balanced")
        covenant_notes = str(covenant_package.get("notes") or "").strip()
        selected_covenant_labels = covenant_package.get("selected_labels") or []
        selected_covenants_text = (
            ", ".join(str(label) for label in selected_covenant_labels)
            if selected_covenant_labels
            else "the controls shown in the table"
        )

        coverage_table = _records_to_table(bank_credit_figures.get("coverage_table") or [], [
            ("case", "Case"),
            ("ebitda", "EBITDA"),
            ("funding_cost", "Funding cost"),
            ("cash_interest", "Cash interest"),
            ("annual_principal", "Annual principal"),
            ("dscr", "DSCR"),
            ("icr", "ICR"),
        ])
        debt_capacity_table = _records_to_table(bank_credit_figures.get("debt_capacity_table") or [], [
            ("constraint", "Constraint"),
            ("supportable_debt", "Supportable debt"),
            ("basis", "Basis"),
            ("binding", "Binding"),
            ("caveat", "Caveat"),
        ])
        content.update({
            "executive_summary": _section_with_table(
                (
                    f"## Indicative terms request\n"
                    f"This demo bank credit paper for {company_name} is drafted in the same practical style as a "
                    "lender credit paper: requested facility, source of repayment, security, coverage, balance-sheet "
                    "support, covenants, conditions and recommendation. Uploaded financials drive the tables; public "
                    "research is simulated in demo mode until a live AI key is configured.\n\n"
                    f"## Screening conclusion\n"
                    f"The requested facility of {requested_amount} {recommendation_posture}. The calculated "
                    f"supportable debt is {summary.get('supportable_debt', 'Not available')}, headroom / shortfall is "
                    f"{headroom_text}, and the binding constraint is {binding_constraint}. This remains screening-only "
                    "until source documents, collateral values, debt schedules and lender terms are confirmed."
                ),
                bank_credit_figures.get("credit_metrics_table") or {},
            ),
            "transaction_summary": _section_with_table(
                (
                    "The transaction summary sets out the borrower structure, amount requested, debt purpose, term, "
                    "repayment profile, funding cost and source of repayment. This mirrors the front half of a bank "
                    f"paper where the credit team needs to understand the ask before reading the detailed analysis.\n\n"
                    f"## Transaction context supplied\n{credit_context}"
                ),
                bank_credit_figures.get("facility_terms_table") or {},
            ),
            "sources_and_uses": _section_with_table(
                (
                    "Sources and uses are built from the supplied facility amount and any optional refinance, costs, "
                    "working-capital, equity or bridge details. Where detail is not provided, the table deliberately "
                    "flags the missing funds-flow evidence rather than inventing a balanced transaction schedule."
                ),
                bank_credit_figures.get("sources_and_uses_table") or {},
            ),
            "borrower_and_sponsor_profile": (
                f"## Borrower profile\n{company_summary}\n\n"
                "## Sponsor / ownership context\n"
                "Demo mode has not completed live borrower research. Use the borrower / ownership structure supplied "
                f"in the intake, Companies Office extracts, guarantor information and management background before "
                f"presenting this as committee-ready.\n\n## Supplied transaction and sponsor context\n{credit_context}\n\n"
                "## Repayment source\n"
                "Primary repayment is expected to come from operating cash flow shown in the uploaded financials. "
                "Any sponsor bridge, guarantee, property support or shareholder contribution should be documented "
                "separately and tested against its own repayment source."
            ),
            "facilities_requested": _section_with_table(
                (
                    "The facility terms below are the lender-screening structure used throughout the paper. The same "
                    "amount, term, funding cost and repayment profile flow through the DSCR, ICR, LVR and debt-capacity "
                    f"calculations.\n\n## Facility structure supplied\n{credit_context}"
                ),
                bank_credit_figures.get("facility_terms_table") or {},
            ),
            "security_package": _section_with_table(
                (
                    "Security is assessed by type, supplied value, target LVR, calculated LVR and the implied security "
                    "value required where no appraisal is supplied. Fleet, property, GSA, guarantee and unsecured "
                    f"positions should each be confirmed with lender-form documents before committee.\n\n## Security structure supplied\n{credit_context}"
                ),
                bank_credit_figures.get("security_analysis_table") or {},
            ),
            "financial_performance_forecast": _section_with_table(
                (
                    "The uploaded trading history is the primary source for repayment capacity. The latest uploaded "
                    "EBITDA is used as the credit anchor unless the user later supplies a lender-supported normalisation "
                    "or QoE bridge."
                ),
                bank_credit_figures.get("financial_trend_table") or {},
            ),
            "coverage_and_sensitivity": _section_with_table(
                (
                    "Coverage and sensitivity are calculated from uploaded EBITDA and the requested funding terms. "
                    "The table shows base coverage, rate stress and EBITDA downside. The amortisation profile then "
                    "shows how leverage reduces through the proposed term where principal is scheduled."
                ),
                coverage_table,
                amortisation_profile_table=bank_credit_figures.get("amortisation_profile_table") or {},
            ),
            "balance_sheet_debt_capacity": _section_with_table(
                (
                    "The balance-sheet section shows the main operating assets and liabilities a lender needs to see: "
                    "accounts receivable, stock, fixed assets, accounts payable, short-term debt, long-term debt, "
                    "operating working capital and NTOA. NTOA is used here as a tangible operating asset proxy, not "
                    "as a formal collateral valuation. Where the uploaded pack does not include a balance sheet, the "
                    "section remains visible and the missing schedules become committee conditions."
                ),
                bank_credit_figures.get("balance_sheet_strength_table") or {},
                debt_capacity_table=debt_capacity_table,
            ),
            "industry_and_competitive_landscape": _section_with_table(
                f"## Sector context\n{sector_summary}\n\n"
                "## Credit relevance\n"
                "In a live run this section should be supported by public-source research into the borrower, sector, "
                "competitors, regulation, contracts, cyclicality and local operating footprint. In demo mode, treat "
                "the sector narrative as illustrative and rely on the uploaded financials for quantitative conclusions.",
                {
                    "headers": ["Market evidence", "Status", "Credit use"],
                    "rows": [[
                        "Sector and macro context",
                        "Illustrative demo context",
                        "Test demand, pricing and cost sensitivities before credit reliance.",
                    ]],
                },
            ),
            "proposed_covenants": _section_with_table(
                (
                    "The covenants below are proposed lender controls only. They are not agreed terms and should be "
                    "checked against the bank's credit policy, facility type, borrower size and final EBITDA definition. "
                    f"The selected package is {covenant_label}, covering {selected_covenants_text}."
                    + (f" User notes: {covenant_notes}" if covenant_notes else "")
                ),
                bank_credit_figures.get("proposed_covenants_table") or {},
            ),
            "key_risks_and_mitigants": _section_with_table(
                (
                    "The key risks and mitigants are framed for credit committee: what could impair repayment, what "
                    "protects the lender, and which conditions are required before reliance."
                ),
                bank_credit_figures.get("key_risks_mitigants_table") or {},
            ),
            "conditions_precedent": _section_with_table(
                (
                    "These items are required before the paper could move from screening-only to bank credit committee. "
                    "They are deliberately specific so the user can see what evidence is missing."
                ),
                bank_credit_figures.get("conditions_precedent_table") or {},
            ),
            "recommendation": _section_with_table(
                (
                    f"We recommend treating this as a screening-only credit paper until the conditions precedent are "
                    f"cleared. On the uploaded financials and supplied facility assumptions, the requested facility of "
                    f"{requested_amount} {recommendation_posture}; calculated supportable debt is "
                    f"{summary.get('supportable_debt', 'Not available')} with headroom / shortfall of {headroom_text}. "
                    f"The binding constraint is {binding_constraint}. The lender should proceed only if collateral, "
                    "debt schedules, covenant definitions, tax status, management accounts and security documents "
                    "support the structure."
                ),
                bank_credit_figures.get("credit_metrics_table") or {},
            ),
            "disclaimer": (
                "This demo bank credit paper is indicative only and has been prepared for testing the AccountIQ "
                "workflow. It does not constitute financial advice, credit approval, a bank commitment, legal advice "
                "or tax advice, should not be relied on as a substitute for independent professional advice, and is "
                "subject to the Financial Markets Conduct Act / FMCA context. A lender should complete its own "
                "credit assessment, due diligence, security review and approval process."
            ),
        })
        return {section: content.get(section, "") for section in SECTION_SCHEMAS[report_type]}

    return content


def _replace_demo_copy_with_evidence_copy(value: object) -> object:
    """Remove demo wording when reusing deterministic report schedules in evidence mode."""
    if isinstance(value, dict):
        return {key: _replace_demo_copy_with_evidence_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_demo_copy_with_evidence_copy(item) for item in value]
    if not isinstance(value, str):
        return value
    replacements = (
        ("Demo-mode", "Evidence-mode"),
        ("demo-mode", "evidence-mode"),
        ("Demo mode", "Evidence mode"),
        ("demo mode", "evidence mode"),
        ("This local demo", "This evidence-mode"),
        ("This demo", "This evidence-mode"),
        ("demo report", "evidence-mode report"),
        ("demo draft", "evidence-mode draft"),
        ("demo figures", "documented model conventions"),
        ("demo market", "documented model-convention"),
        ("demo discount-rate", "documented model-convention"),
        ("demo EV/EBITDA", "documented EV/EBITDA"),
        ("simulated public research", "approved public-source evidence"),
        ("simulated research", "approved public-source evidence"),
        ("simulated market evidence", "approved public-source evidence"),
        ("sample professional valuation assumptions", "documented valuation assumptions"),
        ("sample valuation evidence", "documented valuation evidence"),
        ("labelled demo source URLs", "retained public source URLs"),
        ("sample public-source research", "approved public-source evidence"),
        ("live AI key", "independent market evidence"),
        ("live research", "independent external research"),
        ("live web research", "independent external research"),
        ("No live", "No independent"),
        ("Demo ", "Documented "),
        ("demo ", "documented "),
    )
    text = value
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _evidence_mode_assumption_source_trail(table: object) -> dict:
    """Keep market-assumption provenance accurate when no public market feed ran."""
    if not isinstance(table, dict):
        return {"headers": [], "rows": []}
    result = json.loads(json.dumps(table))
    for row in result.get("rows", []):
        if not isinstance(row, list):
            continue
        for index, cell in enumerate(row):
            if isinstance(cell, str) and "public research" in cell.lower():
                row[index] = re.sub(
                    r"public research[^;:.]*[:;]?",
                    "Public research not retrieved; documented model convention:",
                    cell,
                    flags=re.IGNORECASE,
                )
    return result


def _evidence_mode_report_content_from_inputs(
    *,
    report_type: str,
    company_name: str,
    financial_rows: list[dict],
    valuation_result: dict | None,
    bank_credit_figures: dict | None,
    research_brief: dict | None,
    intake_answers: dict | None = None,
) -> dict:
    """Build a source-scoped report without invoking a commercial AI provider.

    Financial schedules remain the existing deterministic calculations.  This
    function replaces only the old demo framing with explicit public-evidence
    limits, rather than trying to imitate a model-written research narrative.
    """
    content = _demo_report_content_from_inputs(
        report_type=report_type,
        company_name=company_name,
        financial_rows=financial_rows,
        valuation_result=valuation_result,
        bank_credit_figures=bank_credit_figures,
        credit_research_brief=research_brief,
        intake_answers=intake_answers,
    )
    content = _replace_demo_copy_with_evidence_copy(content)
    brief = research_brief or {}
    source_records = brief.get("evidence_sources") if isinstance(brief, dict) else []
    source_urls = [str(item) for item in (brief.get("sources") or [])] if isinstance(brief, dict) else []
    limitations = [str(item) for item in (brief.get("limitations") or [])] if isinstance(brief, dict) else []
    evidence_summary = str(brief.get("company_summary") or "No public-source evidence was retained.")
    sector_summary = str(brief.get("sector_summary") or "No sector evidence was retained.")
    limitation_text = " ".join(limitations) or (
        "Only approved public sources were considered; the report does not perform open-web discovery."
    )
    source_scope = ", ".join(source_urls[:3]) or "the public URLs supplied in the intake"

    if report_type == "valuation_advisory" and valuation_result:
        sources_table = evidence_sources_table(source_records)
        if not sources_table.get("rows") and source_urls:
            sources_table = {
                "headers": ["Source", "URL", "Supports / used for"],
                "rows": [[
                    "Management-supplied public source",
                    source_urls[0],
                    "Source scope supplied for evidence-mode research; no factual claim is made unless readable content was retrieved.",
                ]],
            }
        comparable_source = source_urls[0] if source_urls else "https://www.rbnz.govt.nz/"
        valuation_result["sources_table"] = sources_table
        valuation_result["assumption_source_trail"] = _evidence_mode_assumption_source_trail(
            valuation_result.get("assumption_source_trail")
        )
        content["introduction"] = (
            f"## Client and report purpose\nThis indicative valuation for {company_name} is prepared from uploaded "
            "financial information, management-confirmed private inputs and the approved public-source evidence trail. "
            "It is prepared for the client or intended user to assess a preliminary going-concern value. The valuation date is the report preparation date unless an alternative valuation date is expressly agreed.\n\n"
            "## Sources of information and evidence boundary\nFinancial schedules use the uploaded financial statements. "
            f"Public context is limited to {source_scope}; {limitation_text}\n\n"
            "## Evidence-mode generation\nThis report was prepared without a commercial AI provider. "
            "It uses deterministic financial calculations and the retained public-source evidence trail.\n\n"
            "## Reliance limitation\nThis is an indicative analysis, not an independent business valuation, financial advice, tax advice or legal advice. "
            "It is confidential to the intended user and should not be relied on without independent professional advice."
        )
        content["executive_summary"] = _section_with_table(
            "The valuation schedules use the uploaded accounts and transparent model conventions. Public company context is limited to the retained evidence trail; "
            "no commercial AI provider, open-web search or paid market database was used.",
            valuation_result.get("executive_summary_table") or {},
        )
        content["business_overview"] = (
            f"## Public information reviewed\n{evidence_summary}\n\n"
            "## Evidence boundary\nThe report retains the reviewed URLs and retrieval status. Published website content is context only and is not independent verification of management representations."
        )
        content["market_position"] = _section_with_table(
            f"## Sector context\n{sector_summary}\n\n"
            "## Valuation relevance\nNo automated open-web discovery, paid data source or transaction database was used. Sector growth, competitor, regulatory and comparable-transaction conclusions are therefore not asserted unless the retained public evidence directly supports them.",
            {
                "headers": ["Evidence boundary", "Evidence available", "Valuation use"],
                "rows": [[
                    "Approved public-source scope",
                    source_scope,
                    "Use only for corroborated market context; do not infer company market share.",
                ]],
            },
        )
        content["about_business_valuations"] = (
            "A business valuation estimates a range of value for a going concern, recognising that a willing buyer and willing seller may place different values on the same future cash flows. "
            "Enterprise value measures the operating business before debt and surplus cash, while equity value is the amount remaining for shareholders after the debt and cash bridge. "
            "Maintainable earnings are the recurring earnings a market participant expects the business to sustain after normalising one-off, non-operating or owner-specific items. "
            "The valuation range reflects uncertainty in future performance, funding costs, growth, customer retention and other risk factors rather than a single guaranteed outcome."
        )
        content["general_principles"] = (
            "This analysis assumes a willing buyer and a willing seller dealing at arm's length, each acting with reasonable knowledge and without compulsion. "
            "It assumes the business continues as a going concern at the valuation date and that the financial information fairly represents the operating business. "
            "The conclusion is date-sensitive: changes in trading, finance costs, management continuity, assets, liabilities or market conditions may change the indicated valuation range."
        )
        content["valuation_methodology"] = (
            "Discounted cash flow (DCF) is the primary method because it converts the business's expected future cash-generating capacity into enterprise value using a documented discount rate. "
            "The EV/EBITDA multiple range is a reasonableness cross-check only. In evidence mode, the multiple and WACC inputs are transparent model conventions rather than independently researched market data. "
            "Any market multiple comparison remains sensitive to scale, growth, margins, customer concentration, contract security and other comparability factors."
        )
        content["valuation_assumptions"] = _section_with_table(
            "The source trail distinguishes uploaded financial data, management-confirmed private inputs and public research not retrieved in evidence mode. "
            "Where independent market evidence is unavailable, AccountIQ labels the documented model convention rather than presenting it as a market fact.",
            valuation_result.get("assumption_source_trail") or {},
        )
        content["multiples_crosscheck"] = _section_with_table(
            "The EV/EBITDA range is a transparent model convention for a private-SME cross-check. It is not a conclusion drawn from comparable transactions because no independent transaction evidence was retrieved in this run.",
            valuation_result.get("multiples_crosscheck_table") or {},
        )
        content["comparable_evidence"] = _section_with_table(
            "No independent comparable-transaction evidence was retrieved. The table records this limitation rather than manufacturing a market-data conclusion.",
            {
                "headers": ["Evidence / transaction", "Date", "Metric or multiple", "Relevance and limitations", "Source"],
                "rows": [[
                    "No comparable transaction evidence retrieved",
                    "Not available",
                    "Not available",
                    "The EV/EBITDA range is a documented model convention only; it is not independently corroborated market evidence.",
                    f"Approved public-source scope - {comparable_source}",
                ]],
            },
        )
        content["sources"] = _section_with_table(
            "This source ledger records the public URLs approved for this run, when they were retrieved, and the limited purpose for which they were considered. Uploaded financial statements remain the source for all financial schedules.",
            sources_table,
        )
        content["disclaimer"] = (
            "This evidence-mode indicative valuation does not constitute financial advice under the Financial Markets Conduct Act / FMCA context and should not be relied on for lending, sale, investment, tax or legal decisions. "
            "It is not an independent business valuation. Users should obtain independent professional financial, legal, tax and accounting advice and complete appropriate due diligence before acting."
        )
        return {section: content.get(section, "") for section in SECTION_SCHEMAS[report_type]}

    if report_type == "bank_credit_paper" and bank_credit_figures:
        evidence_note = (
            f"\n\n## Public-source evidence boundary\n{limitation_text} "
            "The retained source list is used for borrower context only; uploaded financials and lender-provided terms drive the quantitative credit analysis."
        )
        content["borrower_and_sponsor_profile"] = (
            f"## Borrower profile\n{evidence_summary}\n\n"
            "## Sponsor / ownership context\nConfirm borrower structure, ownership, guarantees and management capability with Companies Office extracts and lender due diligence before committee.\n\n"
            "## Repayment source\nPrimary repayment is expected to come from operating cash flow in the uploaded financial statements. Any sponsor support, guarantee or property support must be documented and assessed separately."
            + evidence_note
        )
        content["industry_and_competitive_landscape"] = _section_with_table(
            f"## Sector context\n{sector_summary}\n\n"
            "## Credit relevance\nThe report does not make unsupported statements about competitors, contracts, regulation or sector growth. Those points should be added only when supported by a retained source or lender diligence."
            + evidence_note,
            {
                "headers": ["Evidence boundary", "Evidence available", "Credit use"],
                "rows": [[
                    "Approved public-source scope",
                    source_scope,
                    "Use for borrower context only; financials and lender terms drive debt capacity.",
                ]],
            },
        )
        content["executive_summary"] = _section_with_table(
            "This indicative credit paper uses uploaded financials, lender-supplied facility terms and approved public-source context. No commercial AI provider, open-web search or paid market database was used.",
            bank_credit_figures.get("credit_metrics_table") or {},
        )
        content["disclaimer"] = (
            "This evidence-mode bank credit paper is indicative only. It is not financial advice, a credit approval, a bank commitment, legal advice or tax advice and should not be relied on instead of independent professional advice. "
            "A lender must complete its own credit assessment, due diligence, security review and approval process."
        )
        return {section: content.get(section, "") for section in SECTION_SCHEMAS[report_type]}

    return content


async def _generate_report(
    report_id: int,
    company_id: int,
    user_id: int,
    report_type: str,
    intake_answers: dict,
    source_document_id: int | list[int] | None = None,
) -> None:
    """
    Background task: read financial data + profile, run Python algorithms
    (Valuation Advisory only), call OpenAI for narrative, store JSON content,
    send email on completion.

    Uses build_prompt() from report_prompts and SECTION_SCHEMAS for validation.
    Opens its own DB connection (same pattern as _run_ingestion).
    """
    source_document_ids = _normalise_source_document_ids(source_document_id)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("PRAGMA journal_mode=WAL")

        try:
            async with db.execute(
                "SELECT demo_mode, generation_mode, content FROM reports WHERE id=?",
                (report_id,),
            ) as cur:
                report_mode_row = await cur.fetchone()
            report_demo_mode = _report_demo_mode_from_row(report_mode_row)
            generation_mode = _report_generation_mode_from_row(report_mode_row)

            # Mark as generating
            await db.execute(
                "UPDATE reports SET status='generating' WHERE id=?",
                (report_id,)
            )
            await db.commit()
            print(f"[REPORT] Generating report_id={report_id} type={report_type}")

            if generation_mode == "demo" and (E2E_MODE or not source_document_ids):
                await asyncio.sleep(0.05)
                content_json = _e2e_report_content(report_type, demo_mode=True)
                if report_type in {"valuation_advisory", "bank_credit_paper"}:
                    content_json = apply_market_intelligence_to_report_content(
                        content_json,
                        None,
                        report_type,
                    )
                await db.execute(
                    """
                    UPDATE reports
                    SET status='done', content=?, completed_at=datetime('now')
                    WHERE id=?
                    """,
                    (json.dumps(content_json), report_id),
                )
                await db.commit()
                print(f"[REPORT] Demo report_id={report_id} done ({report_type})")
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
            sector_match = None
            if report_type in {"valuation_advisory", "bank_credit_paper"}:
                try:
                    sector_match = match_sector_report(
                        company_sector,
                        company_description,
                    )
                except Exception as exc:
                    # A missing optional pack must not hide an otherwise valid
                    # financial report. The report evidence records that no
                    # sector match was available.
                    print(f"[WARN] Sector library unavailable for report {report_id}: {exc}")
            sector_context = sector_prompt_context(
                sector_match,
                report_type,
            )

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

            # --- 4. Financial rows — all periods for the selected wizard upload ---
            # New wizard reports should be anchored to the file the user just
            # uploaded. Older internal callers may omit source_document_id, in
            # which case we retain the historical company-level behaviour.
            if source_document_ids:
                placeholders = ",".join("?" for _ in source_document_ids)
                financial_rows_query = """
                    SELECT fr.document_id, fr.statement, fr.row_key, fr.row_label, fr.period,
                           fr.value, fr.currency, fr.unit, fr.confidence, d.filename
                    FROM financial_rows fr
                    JOIN documents d ON d.id = fr.document_id
                    WHERE fr.company_id=? AND fr.document_id IN ({placeholders})
                    ORDER BY fr.statement, fr.row_key, fr.period DESC, fr.document_id ASC
                """.format(placeholders=placeholders)
                financial_rows_params = (company_id, *source_document_ids)
            else:
                financial_rows_query = """
                    SELECT fr.document_id, fr.statement, fr.row_key, fr.row_label, fr.period,
                           fr.value, fr.currency, fr.unit, fr.confidence, d.filename
                    FROM financial_rows fr
                    JOIN documents d ON d.id = fr.document_id
                    WHERE fr.company_id=?
                    ORDER BY fr.statement, fr.row_key, fr.period DESC, fr.document_id ASC
                """
                financial_rows_params = (company_id,)
            async with db.execute(financial_rows_query, financial_rows_params) as cur:
                raw_fin_rows = [dict(r) for r in await cur.fetchall()]

            reconciliation_overrides = _normalise_financial_reconciliation_overrides(
                intake_answers.get("_financial_reconciliation_overrides")
                if isinstance(intake_answers, dict)
                else None
            )
            reconciliation = reconcile_financial_rows(
                raw_fin_rows,
                overrides=reconciliation_overrides,
            )
            if reconciliation["invalid_override_ids"] or reconciliation["unresolved_conflict_ids"]:
                raise RuntimeError(
                    "The uploaded financial statements contain unresolved overlapping-year differences. "
                    "Please review the statement sources and retry the report."
                )
            raw_fin_rows = reconciliation["rows"]

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
            credit_research_brief = None

            if report_type == "valuation_advisory":
                readiness = assess_valuation_financial_readiness(raw_fin_rows)
                if not readiness["ready"]:
                    raise RuntimeError(
                        _valuation_financial_readiness_message(readiness["issues"])
                    )

                # 5a. Update status so the wizard can show 'researching' in real time
                await db.execute(
                    "UPDATE reports SET status='researching' WHERE id=?", (report_id,)
                )
                await db.commit()

                # 5b. Run agentic web research loop (Plan 02)
                company_location = (intake_answers.get("company_location") or "New Zealand") if isinstance(intake_answers, dict) else "New Zealand"
                company_website = (intake_answers.get("company_website") or "") if isinstance(intake_answers, dict) else ""
                public_source_urls = intake_answers.get("public_source_urls", []) if isinstance(intake_answers, dict) else []
                industry_sector_for_research = company_sector or "General SME"
                if generation_mode == "demo":
                    brief = _demo_research_brief(
                        company_name=company_name,
                        company_location=company_location,
                        industry_sector=industry_sector_for_research,
                    )
                elif generation_mode == "evidence":
                    brief = await collect_evidence_research(
                        company_name=company_name,
                        company_location=company_location,
                        industry_sector=industry_sector_for_research,
                        company_website=company_website,
                        public_source_urls=public_source_urls,
                    )
                else:
                    brief = await run_valuation_research(
                        company_name=company_name,
                        company_location=company_location,
                        industry_sector=industry_sector_for_research,
                        company_website=company_website,
                        public_source_urls=public_source_urls,
                        sector_context=sector_context,
                    )
                brief_data = enrich_research_brief(
                    brief.model_dump(),
                    sector_match,
                    report_type,
                )
                management_supplied_sources: list[object] = []
                if company_website:
                    management_supplied_sources.append(company_website)
                if isinstance(public_source_urls, (list, tuple, set)):
                    management_supplied_sources.extend(public_source_urls)
                elif public_source_urls:
                    management_supplied_sources.append(public_source_urls)
                sources_table = build_sources_table(
                    brief_data.get("sources"),
                    management_supplied_sources=management_supplied_sources,
                )
                comparable_evidence_table = build_comparable_evidence_table(
                    comparable_transactions=brief_data.get("comparable_transactions"),
                    sources=brief_data.get("sources"),
                )
                if generation_mode == "evidence":
                    sources_table = evidence_sources_table(brief_data.get("evidence_sources") or [])
                await db.execute(
                    "UPDATE reports SET research_evidence=? WHERE id=?",
                    (json.dumps(brief_data), report_id),
                )
                await db.commit()

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

                depreciation_base = abs(
                    _latest_value(pnl_by_key, "depreciation_amortisation")
                    or _latest_value(pnl_by_key, "depreciation")
                )
                extracted_ebitda = _latest_value(pnl_by_key, "ebitda")
                if extracted_ebitda == 0.0:
                    net_p = _latest_value(pnl_by_key, "net_profit")
                    extracted_ebitda = net_p + depreciation_base

                revenues_val = _latest_value(pnl_by_key, "revenue")
                net_profit_latest = _latest_value(pnl_by_key, "net_profit")
                cash_val = abs(
                    _latest_value(bs_by_key, "cash_and_equivalents") or
                    _latest_value(bs_by_key, "cash_and_bank") or
                    _latest_value(bs_by_key, "cash")
                )

                latest_balance_sheet_values = {
                    key: _latest_value(bs_by_key, key)
                    for key in bs_by_key
                }
                reinvestment = derive_reinvestment_assumptions(
                    latest_balance_sheet_values,
                    revenues_val,
                    depreciation_base,
                )
                operating_working_capital = reinvestment["operating_working_capital"]
                working_capital_ratio = reinvestment["working_capital_ratio"]
                working_capital_source = reinvestment["working_capital_source"]
                maintenance_capex = reinvestment["maintenance_capex"]

                # Use the wizard earnings-review list as the authoritative
                # add-back source whenever it is present, even when the user
                # confirms an empty list. Fall back to legacy company-level
                # EBITDA adjustments only for older callers that omit the key.
                # If supplied, the collapsed replacement-manager-cost override
                # is deducted as its own normalisation row so it is visible in
                # the maintainable-earnings bridge rather than silently ignored.
                valuation_normalisations = _valuation_earnings_review_normalisations(
                    intake_answers if isinstance(intake_answers, dict) else None,
                    ebitda_adjustments,
                )
                addbacks_total = sum(
                    float(n.get("amount", 0) or 0)
                    for n in valuation_normalisations
                )
                normalised_ebitda = extracted_ebitda + addbacks_total
                normalisation_schedule = build_normalisation_schedule_table(
                    valuation_normalisations,
                    normalised_ebitda=normalised_ebitda,
                )
                financial_performance_table = build_financial_performance_table(raw_fin_rows)
                financial_ratio_table = build_financial_ratio_table(raw_fin_rows)

                # Use a consistent five-year explicit period and translate the
                # management-friendly forward view into a documented growth
                # assumption. The self-serve user is not asked to choose the
                # forecast horizon, WACC or terminal growth rate.
                forecast_years = 5
                revenue_outlook = intake_answers.get("revenue_outlook", "modest_growth") if isinstance(intake_answers, dict) else "modest_growth"
                custom_growth = intake_answers.get("custom_growth_rate") if isinstance(intake_answers, dict) else None
                revenue_growth_pct, growth_assumption_source = select_revenue_growth_assumption(
                    pnl_by_key.get("revenue", []),
                    str(revenue_outlook),
                    float(custom_growth) if custom_growth not in (None, "") else None,
                )

                # Current NZ inflation from the research brief anchors terminal
                # growth. This avoids asking users to choose a technical DCF
                # input they are unlikely to know.
                terminal_growth_pct = float(brief.inflation_rate)
                terminal_growth_pct = min(terminal_growth_pct, wacc_pct["low"] - 0.5)
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
                        revenue=revenues_val,
                        depreciation_per_year=depreciation_base,
                        capex_per_year=maintenance_capex,
                        working_capital_ratio=working_capital_ratio,
                    )

                # Report columns describe valuation outcomes, not WACC levels:
                # the high valuation uses the low WACC and vice versa.
                dcf_high = await loop.run_in_executor(None, _run_dcf_for_scenario, wacc_pct["low"])
                dcf_mid  = await loop.run_in_executor(None, _run_dcf_for_scenario, wacc_pct["mid"])
                dcf_low  = await loop.run_in_executor(None, _run_dcf_for_scenario, wacc_pct["high"])
                wacc_by_valuation_scenario = {
                    "high": wacc_pct["low"],
                    "mid": wacc_pct["mid"],
                    "low": wacc_pct["high"],
                }

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
                forecast_cash_flow_schedule = build_forecast_cash_flow_schedule(dcf_mid)
                sensitivity_matrix = compute_dcf_sensitivity_matrix(
                    ebitda=normalised_ebitda,
                    revenue=revenues_val,
                    depreciation_per_year=depreciation_base,
                    capex_per_year=maintenance_capex,
                    working_capital_ratio=working_capital_ratio,
                    wacc_by_valuation_scenario_pct=wacc_by_valuation_scenario,
                    base_growth_pct=revenue_growth_pct,
                    tax_rate=tax_rate,
                    years=forecast_years,
                    terminal_growth_pct=terminal_growth_pct,
                    illiquidity_discount=illiq_rate,
                )
                sensitivity_table = build_sensitivity_analysis_table(
                    sensitivity_matrix,
                    base_growth_pct=revenue_growth_pct,
                )

                # Comparable multiples are a researched cross-check range. Do
                # not manufacture a single multiple from eight owner ratings.
                multiples_result = compute_multiples_range(
                    normalised_ebitda=normalised_ebitda,
                    ev_ebitda_low=brief.ev_ebitda_low,
                    ev_ebitda_high=brief.ev_ebitda_high,
                )
                wacc_assumptions_table = build_wacc_assumptions_table(
                    risk_free_rate=brief.risk_free_rate,
                    erp=brief.erp,
                    industry_beta=brief.industry_beta,
                    wacc_by_valuation_scenario_pct=wacc_by_valuation_scenario,
                    illiquidity_discount=illiq_rate,
                )
                dcf_analysis_table = build_dcf_analysis_table(
                    dcf_scenarios={"high": dcf_high, "mid": dcf_mid, "low": dcf_low},
                    adjusted_enterprise_values=ev_adjusted,
                    wacc_by_valuation_scenario_pct=wacc_by_valuation_scenario,
                    terminal_growth_pct=terminal_growth_pct,
                    revenue=revenues_val,
                    normalised_ebitda=normalised_ebitda,
                    depreciation_base=depreciation_base,
                    maintenance_capex=maintenance_capex,
                    working_capital_ratio_pct=reinvestment["working_capital_ratio_pct"],
                    illiquidity_discount=illiq_rate,
                )
                multiples_crosscheck_table = build_multiples_crosscheck_table(multiples_result)

                gross_debt = abs(
                    _latest_value(bs_by_key, "short_term_debt")
                    + _latest_value(bs_by_key, "long_term_debt")
                )
                debt_override = intake_answers.get("debt_override") if isinstance(intake_answers, dict) else None
                debt_override_used = debt_override not in (None, "")
                if debt_override not in (None, ""):
                    gross_debt = abs(float(debt_override))
                raw_surplus_assets = (
                    intake_answers.get("surplus_assets")
                    if isinstance(intake_answers, dict)
                    else None
                )
                surplus_assets_supplied = raw_surplus_assets not in (None, "")
                surplus_assets = float(raw_surplus_assets or 0) if isinstance(intake_answers, dict) else 0.0
                net_debt = gross_debt - cash_val
                executive_summary_table = build_executive_summary_table(
                    adjusted_enterprise_values=ev_adjusted,
                    gross_debt=gross_debt,
                    cash=cash_val,
                    surplus_assets=surplus_assets,
                )
                valuation_summary_table = build_valuation_summary_table(
                    dcf_scenarios={"high": dcf_high, "mid": dcf_mid, "low": dcf_low},
                    adjusted_enterprise_values=ev_adjusted,
                    wacc_by_valuation_scenario_pct=wacc_by_valuation_scenario,
                    multiples_result=multiples_result,
                    gross_debt=gross_debt,
                    cash=cash_val,
                    surplus_assets=surplus_assets,
                )
                balance_sheet_summary_table = build_balance_sheet_summary_table(
                    raw_fin_rows,
                    gross_debt=gross_debt,
                    cash=cash_val,
                    surplus_assets=surplus_assets,
                    midpoint_enterprise_value=ev_adjusted["mid"],
                    operating_working_capital=operating_working_capital,
                    working_capital_source=working_capital_source,
                    debt_override_used=debt_override_used,
                    surplus_assets_supplied=surplus_assets_supplied,
                )
                owner_dependency_answer = str(intake_answers.get("owner_dependency", "")) if isinstance(intake_answers, dict) else ""
                customer_concentration_answer = str(intake_answers.get("customer_concentration", "")) if isinstance(intake_answers, dict) else ""
                revenue_quality_answer = str(intake_answers.get("revenue_quality", "")) if isinstance(intake_answers, dict) else ""
                revenue_outlook_answer = str(intake_answers.get("revenue_outlook", "")) if isinstance(intake_answers, dict) else ""
                private_context_answer = str(intake_answers.get("private_context", "")) if isinstance(intake_answers, dict) else ""
                assumption_source_trail = build_assumption_source_trail(
                    normalised_ebitda=normalised_ebitda,
                    forecast_years=forecast_years,
                    revenue_growth_pct=revenue_growth_pct,
                    growth_assumption_source=growth_assumption_source,
                    terminal_growth_pct=terminal_growth_pct,
                    wacc_by_valuation_scenario_pct=wacc_by_valuation_scenario,
                    maintenance_capex=maintenance_capex,
                    working_capital_ratio_pct=reinvestment["working_capital_ratio_pct"],
                    working_capital_source=working_capital_source,
                    gross_debt=gross_debt,
                    cash=cash_val,
                    surplus_assets=surplus_assets,
                    owner_dependency=owner_dependency_answer,
                    customer_concentration=customer_concentration_answer,
                    revenue_quality=revenue_quality_answer,
                    revenue_outlook=revenue_outlook_answer,
                    debt_override_used=debt_override_used,
                    surplus_assets_supplied=surplus_assets_supplied,
                )
                specific_risk_factors = build_specific_risk_factor_table(
                    owner_dependency=owner_dependency_answer,
                    customer_concentration=customer_concentration_answer,
                    revenue_quality=revenue_quality_answer,
                    revenue_outlook=revenue_outlook_answer,
                    private_context=private_context_answer,
                )

                valuation_result = {
                    "research_brief": brief_data,
                    "wacc_scenarios_pct": wacc_by_valuation_scenario,
                    "dcf_scenarios": {"high": dcf_high, "mid": dcf_mid, "low": dcf_low},
                    "illiquidity_discount": {"rate": illiq_rate, "ev_adjusted": ev_adjusted},
                    "normalised_ebitda": normalised_ebitda,
                    "revenues": revenues_val,
                    "gross_debt": gross_debt,
                    "net_debt": net_debt,
                    "cash": cash_val,
                    "surplus_assets": surplus_assets,
                    "forecast_years": forecast_years,
                    "revenue_growth_pct": revenue_growth_pct,
                    "growth_assumption_source": growth_assumption_source,
                    "terminal_growth_pct": terminal_growth_pct,
                    "depreciation_base": depreciation_base,
                    "maintenance_capex": maintenance_capex,
                    "operating_working_capital": operating_working_capital,
                    "working_capital_ratio_pct": reinvestment["working_capital_ratio_pct"],
                    "working_capital_source": working_capital_source,
                    "executive_summary_table": executive_summary_table,
                    "wacc_assumptions_table": wacc_assumptions_table,
                    "dcf_analysis_table": dcf_analysis_table,
                    "financial_performance_table": financial_performance_table,
                    "financial_ratio_table": financial_ratio_table,
                    "balance_sheet_summary_table": balance_sheet_summary_table,
                    "valuation_summary_table": valuation_summary_table,
                    "multiples_crosscheck_table": multiples_crosscheck_table,
                    "assumption_source_trail": assumption_source_trail,
                    "comparable_evidence_table": comparable_evidence_table,
                    "sources_table": sources_table,
                    "normalisation_schedule": normalisation_schedule,
                    "forecast_cash_flow_schedule": forecast_cash_flow_schedule,
                    "sensitivity_matrix": sensitivity_matrix,
                    "sensitivity_table": sensitivity_table,
                    "specific_risk_factors": specific_risk_factors,
                    "multiples_result": multiples_result,
                }
            elif report_type == "bank_credit_paper":
                await db.execute(
                    "UPDATE reports SET status='researching' WHERE id=?", (report_id,)
                )
                await db.commit()
                company_location = (
                    intake_answers.get("company_location") or "New Zealand"
                    if isinstance(intake_answers, dict)
                    else "New Zealand"
                )
                company_website = (
                    intake_answers.get("company_website") or ""
                    if isinstance(intake_answers, dict)
                    else ""
                )
                public_source_urls = (
                    intake_answers.get("public_source_urls", [])
                    if isinstance(intake_answers, dict)
                    else []
                )
                industry_sector_for_research = company_sector or "General SME"
                if generation_mode == "demo":
                    credit_brief = _demo_research_brief(
                        company_name=company_name,
                        company_location=company_location,
                        industry_sector=industry_sector_for_research,
                    )
                elif generation_mode == "evidence":
                    credit_brief = await collect_evidence_research(
                        company_name=company_name,
                        company_location=company_location,
                        industry_sector=industry_sector_for_research,
                        company_website=company_website,
                        public_source_urls=public_source_urls,
                    )
                else:
                    credit_brief = await run_valuation_research(
                        company_name=company_name,
                        company_location=company_location,
                        industry_sector=industry_sector_for_research,
                        company_website=company_website,
                        public_source_urls=public_source_urls,
                        sector_context=sector_context,
                    )
                credit_research_brief = enrich_research_brief(
                    credit_brief.model_dump(),
                    sector_match,
                    report_type,
                )
                if generation_mode == "evidence":
                    await db.execute(
                        "UPDATE reports SET research_evidence=? WHERE id=?",
                        (json.dumps(credit_research_brief), report_id),
                    )
                    await db.commit()
                bank_credit_figs = compute_bank_credit_figures(
                    financial_rows_for_prompt, intake_answers
                )

            if generation_mode == "demo":
                content_json = _demo_report_content_from_inputs(
                    report_type=report_type,
                    company_name=company_name,
                    financial_rows=financial_rows_for_prompt,
                    valuation_result=valuation_result,
                    bank_credit_figures=bank_credit_figs,
                    credit_research_brief=credit_research_brief,
                    intake_answers=intake_answers,
                )
            elif generation_mode == "evidence":
                content_json = _evidence_mode_report_content_from_inputs(
                    report_type=report_type,
                    company_name=company_name,
                    financial_rows=financial_rows_for_prompt,
                    valuation_result=valuation_result,
                    bank_credit_figures=bank_credit_figs,
                    research_brief=(valuation_result or {}).get("research_brief")
                    if report_type == "valuation_advisory"
                    else credit_research_brief,
                    intake_answers=intake_answers,
                )
            else:
                # --- 6. Build OpenAI prompt via report_prompts.build_prompt() ---
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
                    credit_research_brief=credit_research_brief,
                )

                # --- 7. Call OpenAI Responses API for the structured report JSON ---
                content_json = await _call_openai_for_report(
                    system_prompt, user_message,
                    sections=SECTION_SCHEMAS[report_type],
                )

            if report_type in {"valuation_advisory", "bank_credit_paper"}:
                content_json = apply_market_intelligence_to_report_content(
                    content_json,
                    sector_match,
                    report_type,
                )

            # --- 8. Validate the complete customer-facing report structure ---
            _validate_generated_report_content(content_json, report_type)
            if report_type == "valuation_advisory" and generation_mode == "provider":
                if valuation_result is not None:
                    _validate_valuation_report_figures(content_json, valuation_result)
                _enforce_valuation_professional_content_audit(content_json)

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
                    safe_err = _customer_safe_report_failure_message(
                        ValueError(err),
                        report_type,
                    )
                    print(f"[REPORT ERROR] report_id={report_id} disclaimer_incomplete: {missing_phrases}")
                    await db.execute(
                        "UPDATE reports SET status='failed', error_message=? WHERE id=?",
                        (safe_err, report_id),
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
            safe_err_msg = _customer_safe_report_failure_message(exc, report_type)
            print(f"[REPORT ERROR] report_id={report_id}: {err_msg}")
            try:
                await db.execute("""
                    UPDATE reports
                    SET status='failed', error_message=?
                    WHERE id=?
                """, (safe_err_msg, report_id))
                await db.commit()
            except Exception as db_exc:
                print(f"[REPORT ERROR] Failed to mark report failed: {db_exc}")


async def _call_openai_for_report(
    system_prompt: str,
    user_message: str,
    sections: list[str],
) -> dict:
    """
    Call the OpenAI Responses API for report generation (plain JSON, no tool-use).
    Returns parsed dict with section keys.
    """
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The OpenAI SDK is not installed.") from exc
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set — cannot generate report")

    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
    client = OpenAI(api_key=key)

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, lambda: client.responses.create(
        model=model,
        max_output_tokens=8192,
        instructions=system_prompt,
        input=user_message,
        text={"format": {"type": "json_object"}},
    ))

    incomplete_details = getattr(response, "incomplete_details", None)
    if (
        getattr(response, "status", "") == "incomplete"
        and getattr(incomplete_details, "reason", "") == "max_output_tokens"
    ):
        raise RuntimeError(
            "Report generation was truncated before completion. Please retry."
        )
    raw_text = str(getattr(response, "output_text", "") or "")

    # Parse JSON from the provider response.
    content_json = _parse_json_from_response(raw_text, sections)
    return content_json


def _parse_json_from_response(raw_text: str, sections: list[str]) -> dict:
    """
    Extract JSON from a provider response text.
    Handles cases where a model wraps JSON in markdown code fences.
    Raises when a complete JSON object cannot be parsed. Missing sections are
    handled by the report-content validation gate rather than hidden with
    customer-visible placeholder text.
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

    raise ValueError(
        "Report generation returned invalid JSON and could not be completed. Please retry."
    )


def _missing_required_text_concepts(
    text: object,
    required_concepts: dict[str, tuple[str, ...]],
) -> list[str]:
    """Return concept labels that are not represented by any accepted marker."""
    lowered = str(text).lower()
    return [
        label
        for label, markers in required_concepts.items()
        if not any(marker in lowered for marker in markers)
    ]


_GENERIC_SOURCE_SUPPORT_VALUES = {
    "source",
    "sources",
    "source url",
    "url",
    "website",
    "public source",
    "online source",
    "general source",
    "general reference",
    "reference",
    "supporting source",
    "supporting evidence",
}
_SOURCE_SUPPORT_USE_MARKERS = (
    "benchmark",
    "beta",
    "company",
    "comparable",
    "context",
    "corroboration",
    "discount",
    "evidence",
    "equity",
    "financial",
    "growth",
    "inflation",
    "market",
    "multiple",
    "profile",
    "public",
    "rate",
    "risk",
    "sector",
    "terminal",
    "valuation",
    "wacc",
)


def _source_support_description_is_thin(value: object) -> bool:
    """Return whether a source support/use description is too generic for a valuation report."""
    support_lower = " ".join(str(value or "").split()).lower().strip(" .:;-")
    words = re.findall(r"[a-z0-9]+", support_lower)
    return (
        support_lower in _GENERIC_SOURCE_SUPPORT_VALUES
        or len(words) < 3
        or not any(marker in support_lower for marker in _SOURCE_SUPPORT_USE_MARKERS)
    )


def _validate_generated_report_content(content: dict, report_type: str) -> None:
    """Reject incomplete AI output before it can be marked customer-ready."""
    if not isinstance(content, dict):
        raise ValueError("Generated report must be a JSON object")

    expected = SECTION_SCHEMAS[report_type]
    missing = [section for section in expected if section not in content]
    unexpected = [section for section in content if section not in expected]
    if missing:
        raise ValueError(f"Generated report is missing required sections: {missing}")
    if unexpected:
        raise ValueError(f"Generated report contains unexpected sections: {unexpected}")

    placeholder_markers = (
        "tbd",
        "tbc",
        "to be confirmed",
        "to be advised",
        "lorem ipsum",
        "[insert",
        "[placeholder",
        "placeholder",
        "not generated",
        "generation error",
        "could not be parsed",
        "[section",
        "please retry]",
    )
    client_facing_implementation_markers = (
        "python-built",
        "python-computed",
        "model-computed",
        "json object",
        "code fence",
        "system prompt",
        "user prompt",
        "openai",
        "language model",
        "ai narrative",
    )
    if report_type == "valuation_advisory":
        table_sections = set(TABLE_SECTIONS_VALUATION)
    elif report_type == "bank_credit_paper":
        table_sections = set(TABLE_SECTIONS_BANK_CREDIT)
    else:
        table_sections = set()

    for section in expected:
        value = content[section]
        if section in table_sections:
            if not isinstance(value, dict):
                raise ValueError(f"Section '{section}' must contain narrative and table data")
            narrative = value.get("narrative")
            table = value.get("table")
            if not isinstance(narrative, str) or len(narrative.strip()) < 20:
                raise ValueError(f"Section '{section}' has empty or insufficient narrative")
            if not isinstance(table, dict):
                raise ValueError(f"Section '{section}' is missing its table")
            headers = table.get("headers")
            rows = table.get("rows")
            if not isinstance(headers, list) or not headers or not all(isinstance(cell, str) and cell.strip() for cell in headers):
                raise ValueError(f"Section '{section}' has invalid table headers")
            if not isinstance(rows, list) or not rows or not all(isinstance(row, list) and row for row in rows):
                raise ValueError(f"Section '{section}' has no table rows")
            section_text = narrative + " " + json.dumps(table)
            if report_type == "valuation_advisory" and section == "dcf_analysis":
                cash_flow_schedule = value.get("cash_flow_schedule")
                if not isinstance(cash_flow_schedule, dict):
                    raise ValueError("Section 'dcf_analysis' is missing its cash_flow_schedule")
                schedule_headers = cash_flow_schedule.get("headers")
                schedule_rows = cash_flow_schedule.get("rows")
                if (
                    not isinstance(schedule_headers, list)
                    or len(schedule_headers) < 2
                    or not all(isinstance(cell, str) and cell.strip() for cell in schedule_headers)
                ):
                    raise ValueError("Section 'dcf_analysis' has invalid cash_flow_schedule headers")
                if (
                    not isinstance(schedule_rows, list)
                    or not schedule_rows
                    or not all(isinstance(row, list) and len(row) == len(schedule_headers) for row in schedule_rows)
                ):
                    raise ValueError("Section 'dcf_analysis' has invalid cash_flow_schedule rows")
                section_text += " " + json.dumps(cash_flow_schedule)
            if report_type == "bank_credit_paper" and section == "coverage_and_sensitivity":
                amortisation_profile_table = value.get("amortisation_profile_table")
                if not isinstance(amortisation_profile_table, dict):
                    raise ValueError("Section 'coverage_and_sensitivity' is missing its amortisation_profile_table")
                amortisation_headers = amortisation_profile_table.get("headers")
                amortisation_rows = amortisation_profile_table.get("rows")
                if (
                    not isinstance(amortisation_headers, list)
                    or len(amortisation_headers) < 2
                    or not all(isinstance(cell, str) and cell.strip() for cell in amortisation_headers)
                ):
                    raise ValueError("Section 'coverage_and_sensitivity' has invalid amortisation_profile_table headers")
                if (
                    not isinstance(amortisation_rows, list)
                    or not amortisation_rows
                    or not all(isinstance(row, list) and len(row) == len(amortisation_headers) for row in amortisation_rows)
                ):
                    raise ValueError("Section 'coverage_and_sensitivity' has invalid amortisation_profile_table rows")
                section_text += " " + json.dumps(amortisation_profile_table)
            if report_type == "bank_credit_paper" and section == "balance_sheet_debt_capacity":
                debt_capacity_table = value.get("debt_capacity_table")
                if not isinstance(debt_capacity_table, dict):
                    raise ValueError("Section 'balance_sheet_debt_capacity' is missing its debt_capacity_table")
                capacity_headers = debt_capacity_table.get("headers")
                capacity_rows = debt_capacity_table.get("rows")
                if (
                    not isinstance(capacity_headers, list)
                    or len(capacity_headers) < 2
                    or not all(isinstance(cell, str) and cell.strip() for cell in capacity_headers)
                ):
                    raise ValueError("Section 'balance_sheet_debt_capacity' has invalid debt_capacity_table headers")
                if (
                    not isinstance(capacity_rows, list)
                    or not capacity_rows
                    or not all(isinstance(row, list) and len(row) == len(capacity_headers) for row in capacity_rows)
                ):
                    raise ValueError("Section 'balance_sheet_debt_capacity' has invalid debt_capacity_table rows")
                section_text += " " + json.dumps(debt_capacity_table)
            if report_type == "valuation_advisory" and section == "valuation_assumptions":
                source_text = json.dumps(table).lower()
                required_sources = {
                    "uploaded financial": "uploaded financial data",
                    "management-confirmed private": "management-confirmed private inputs",
                    "public research": "public research inputs",
                }
                missing_sources = [
                    label
                    for marker, label in required_sources.items()
                    if marker not in source_text
                ]
                if missing_sources:
                    raise ValueError(
                        "Section 'valuation_assumptions' source trail is missing: "
                        f"{missing_sources}"
                    )
                required_assumption_topics = {
                    "key-person dependency": "owner or key-person dependency",
                    "largest-customer": "largest-customer concentration",
                    "revenue predictability": "revenue predictability",
                    "revenue outlook": "revenue outlook",
                }
                missing_assumption_topics = [
                    label
                    for marker, label in required_assumption_topics.items()
                    if marker not in source_text
                ]
                if missing_assumption_topics:
                    raise ValueError(
                        "Section 'valuation_assumptions' source trail is missing private-fact topics: "
                        f"{missing_assumption_topics}"
                    )
            if report_type == "valuation_advisory" and section == "sensitivity_and_risks":
                specific_risk_factors = value.get("specific_risk_factors")
                if not isinstance(specific_risk_factors, dict):
                    raise ValueError("Section 'sensitivity_and_risks' is missing its specific_risk_factors")
                risk_headers = specific_risk_factors.get("headers")
                risk_rows = specific_risk_factors.get("rows")
                if (
                    not isinstance(risk_headers, list)
                    or len(risk_headers) < 2
                    or not all(isinstance(cell, str) and cell.strip() for cell in risk_headers)
                ):
                    raise ValueError("Section 'sensitivity_and_risks' has invalid specific_risk_factors headers")
                if (
                    not isinstance(risk_rows, list)
                    or len(risk_rows) < 4
                    or not all(isinstance(row, list) and len(row) == len(risk_headers) for row in risk_rows)
                ):
                    raise ValueError("Section 'sensitivity_and_risks' has invalid specific_risk_factors rows")
                risk_text = json.dumps(specific_risk_factors).lower()
                required_risk_topics = {
                    "key-person": "owner or key-person dependency",
                    "customer concentration": "customer concentration",
                    "revenue predictability": "revenue predictability",
                    "revenue outlook": "revenue outlook",
                }
                missing_risks = [
                    label
                    for marker, label in required_risk_topics.items()
                    if marker not in risk_text
                ]
                if missing_risks:
                    raise ValueError(
                        "Section 'sensitivity_and_risks' specific risk table is missing: "
                        f"{missing_risks}"
                    )
            if report_type == "valuation_advisory" and section == "sources":
                rows_without_urls = []
                source_support_index = 2
                for index, header in enumerate(headers):
                    header_text = str(header or "").lower()
                    if any(marker in header_text for marker in ("support", "used for", "description", "why")):
                        source_support_index = index
                        break
                rows_with_thin_support = []
                for index, row in enumerate(rows, start=1):
                    row_text = " ".join(str(cell) for cell in row)
                    if "http://" not in row_text and "https://" not in row_text:
                        rows_without_urls.append(index)
                    if (
                        len(row) <= source_support_index
                        or _source_support_description_is_thin(row[source_support_index])
                    ):
                        rows_with_thin_support.append(index)
                if rows_without_urls:
                    raise ValueError(
                        "Valuation sources table rows must include source URLs: "
                        f"{rows_without_urls}"
                    )
                if rows_with_thin_support:
                    raise ValueError(
                        "Valuation sources table rows must explain what each source supports or is used for: "
                        f"{rows_with_thin_support}"
                    )
        else:
            if not isinstance(value, str) or len(value.strip()) < 20:
                raise ValueError(f"Section '{section}' is empty or insufficient")
            section_text = value

        lowered = section_text.lower()
        if any(marker in lowered for marker in placeholder_markers):
            raise ValueError(f"Section '{section}' contains generation placeholder text")
        if report_type == "valuation_advisory" and any(marker in lowered for marker in UNFINISHED_FOLLOWUP_MARKERS):
            raise ValueError(f"Section '{section}' contains unfinished follow-up language")
        if report_type == "valuation_advisory":
            leaked_markers = [
                marker
                for marker in client_facing_implementation_markers
                if marker in lowered
            ]
            if leaked_markers:
                raise ValueError(
                    f"Section '{section}' contains client-facing implementation language: "
                    f"{leaked_markers}"
                )

    if report_type == "valuation_advisory":
        intro_required_topics = {
            "client or intended user": ("client", "prepared for", "owner"),
            "valuation purpose": ("purpose",),
            "valuation date": ("valuation date", "as of", "as at", "prepared date"),
            "basis of value": ("basis of value", "fair-market", "fair market", "going-concern", "going concern"),
            "sources of information": (
                "sources of information",
                "uploaded financial",
                "financial information",
                "management-confirmed",
                "public research",
                "source urls",
            ),
            "liability, confidentiality or compliance": (
                "liability",
                "confidential",
                "compliance",
                "fmca",
                "financial advice",
                "not relied",
                "should not be relied",
                "independent business valuation",
            ),
        }
        missing_intro_topics = _missing_required_text_concepts(
            content.get("introduction", ""),
            intro_required_topics,
        )
        if missing_intro_topics:
            raise ValueError(
                "Valuation introduction is missing formal report framing: "
                f"{missing_intro_topics}"
            )

        disclaimer_required_topics = {
            "indicative purpose": ("indicative",),
            "financial advice limitation": (
                "does not constitute financial advice",
                "not financial advice",
                "financial advice",
            ),
            "FMCA or Financial Markets Conduct": ("fmca", "financial markets conduct"),
            "not relied": ("not relied", "should not be relied", "not be relied"),
            "independent professional advice": (
                "independent professional",
                "professional advice",
                "legal, tax or accounting advice",
            ),
        }
        missing_disclaimer_topics = _missing_required_text_concepts(
            content.get("disclaimer", ""),
            disclaimer_required_topics,
        )
        if missing_disclaimer_topics:
            raise ValueError(
                "Valuation disclaimer is missing required reliance and compliance framing: "
                f"{missing_disclaimer_topics}"
            )

        about_valuation_required_topics = {
            "enterprise value": ("enterprise value",),
            "equity value": ("equity value",),
            "going concern": ("going-concern", "going concern"),
            "maintainable earnings": ("maintainable earnings",),
            "valuation range": ("range", "high", "midpoint", "low"),
            "risk and uncertainty perspective": ("risk", "uncertainty", "market participant", "investor", "stakeholder"),
        }
        missing_about_valuation_topics = _missing_required_text_concepts(
            content.get("about_business_valuations", ""),
            about_valuation_required_topics,
        )
        if missing_about_valuation_topics:
            raise ValueError(
                "About business valuations section is missing core explanatory concepts: "
                f"{missing_about_valuation_topics}"
            )

        methodology_required_topics = {
            "DCF primary method": ("dcf", "discounted cash flow"),
            "future cash flows": ("future cash", "free cash flow", "cash-generating"),
            "discount rate": ("discount rate", "discounted", "cost of capital", "wacc"),
            "market multiples cross-check": ("market multiple", "ev/ebitda", "multiples", "cross-check"),
            "comparability limitations": ("scale", "growth", "customer", "contract", "comparability", "not directly comparable"),
        }
        missing_methodology_topics = _missing_required_text_concepts(
            content.get("valuation_methodology", ""),
            methodology_required_topics,
        )
        if missing_methodology_topics:
            raise ValueError(
                "Valuation methodology section is missing core method concepts: "
                f"{missing_methodology_topics}"
            )

        principles_required_topics = {
            "willing buyer": ("willing buyer", "willing but not anxious buyer"),
            "willing seller": ("willing seller", "willing but not anxious seller"),
            "arm's-length transaction": (
                "arm's-length",
                "arm's length",
                "arm’s-length",
                "arm’s length",
                "arms-length",
                "arms length",
            ),
            "going concern": ("going concern",),
            "reasonable knowledge": ("reasonable knowledge", "knowledgeable", "knowledgeably"),
            "no compulsion": ("without compulsion", "no compulsion", "not compelled"),
            "valuation-date sensitivity": (
                "valuation date",
                "date-sensitive",
                "date sensitive",
                "as at",
                "as of",
            ),
        }
        missing_principles = _missing_required_text_concepts(
            content.get("general_principles", ""),
            principles_required_topics,
        )
        if missing_principles:
            raise ValueError(
                "Valuation general principles section is missing core assumptions: "
                f"{missing_principles}"
            )

        glossary_required_terms = {
            "DCF": ("dcf", "discounted cash flow"),
            "enterprise value": ("enterprise value",),
            "equity value": ("equity value",),
            "EBITDA": ("ebitda", "earnings before interest"),
            "maintainable earnings": ("maintainable earnings",),
            "terminal value": ("terminal value",),
            "WACC": ("wacc", "weighted average cost of capital"),
            "illiquidity discount": ("illiquidity discount", "limited marketability"),
            "normalisation": ("normalisation", "normalization"),
            "FMCA": ("fmca", "financial markets conduct"),
        }
        missing_glossary_terms = _missing_required_text_concepts(
            content.get("glossary", ""),
            glossary_required_terms,
        )
        if missing_glossary_terms:
            raise ValueError(
                "Valuation glossary section is missing core terms: "
                f"{missing_glossary_terms}"
            )

        sources_text = str(content["sources"])
        if "http://" not in sources_text and "https://" not in sources_text:
            raise ValueError("Valuation report sources section does not contain source URLs")
        comparable_evidence = content.get("comparable_evidence")
        comparable_table = comparable_evidence.get("table") if isinstance(comparable_evidence, dict) else {}
        comparable_rows = comparable_table.get("rows") if isinstance(comparable_table, dict) else []
        if not isinstance(comparable_rows, list) or not comparable_rows:
            raise ValueError("Valuation comparable evidence table has no rows")
        rows_without_urls = []
        for index, row in enumerate(comparable_rows, start=1):
            row_text = " ".join(str(cell) for cell in (row if isinstance(row, list) else [row]))
            if "http://" not in row_text and "https://" not in row_text:
                rows_without_urls.append(index)
        if rows_without_urls:
            raise ValueError(
                "Valuation comparable evidence rows must include source URLs: "
                f"{rows_without_urls}"
            )


def _enforce_valuation_professional_content_audit(content: dict) -> None:
    """Reject valuation reports that fail the professional-pack content audit."""
    audit = audit_valuation_report_content(content)
    if audit.passed:
        return
    issue_codes = [
        issue.get("code", "quality_issue")
        for issue in (audit.as_dict().get("issues") or [])
        if isinstance(issue, dict)
    ]
    raise ValueError(
        "Valuation report failed professional content audit"
        + (f": {issue_codes}" if issue_codes else ".")
    )


def _numbers_from_report_text(value: object) -> list[float]:
    """Extract numeric values from generated report content for consistency checks."""
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    matches = _re.findall(r"\(?\$?-?\d[\d,]*(?:\.\d+)?%?\)?", text)
    numbers: list[float] = []
    for raw in matches:
        cleaned = raw.strip("()").replace("$", "").replace("%", "").replace(",", "")
        try:
            numbers.append(float(cleaned))
        except ValueError:
            continue
    return numbers


def _money_amounts_from_report_text(value: object) -> list[float]:
    """Extract dollar-denominated amounts, including rounded million/billion wording."""
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    amounts: list[float] = []
    pattern = _re.compile(
        r"\(?\$\s*-?(?P<number>\d[\d,]*(?:\.\d+)?)(?:\s*(?P<unit>m|mn|million|b|bn|billion|k|thousand))?\)?",
        _re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        raw_number = match.group("number").replace(",", "")
        try:
            amount = float(raw_number)
        except ValueError:
            continue
        unit = (match.group("unit") or "").lower()
        if unit in {"m", "mn", "million"}:
            amount *= 1_000_000
        elif unit in {"b", "bn", "billion"}:
            amount *= 1_000_000_000
        elif unit in {"k", "thousand"}:
            amount *= 1_000
        if math.isfinite(amount):
            amounts.append(abs(amount))
    return amounts


def _valuation_metric_tokens_from_report_text(value: object) -> list[tuple[str, float, str]]:
    """Extract explicit valuation metric tokens such as percentages and EV/EBITDA multiples."""
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    tokens: list[tuple[str, float, str]] = []
    for match in _re.finditer(r"(?<![\w$])-?\d[\d,]*(?:\.\d+)?\s*%", text):
        raw = match.group(0).strip()
        try:
            value_number = float(raw.replace("%", "").replace(",", "").strip())
        except ValueError:
            continue
        tokens.append(("percentage", value_number, raw))
    for match in _re.finditer(r"(?<![\w$])-?\d[\d,]*(?:\.\d+)?\s*[xX]\b", text):
        raw = match.group(0).strip()
        try:
            value_number = float(raw[:-1].replace(",", "").strip())
        except ValueError:
            continue
        tokens.append(("multiple", value_number, raw))
    return tokens


def _valuation_model_metric_tokens_from_report_text(value: object) -> list[tuple[str, float, str]]:
    """Extract explicit percentage/multiple tokens that are presented as valuation-model metrics."""
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    markers = (
        "beta",
        "discount",
        "discount-rate",
        "ebitda margin",
        "equity risk",
        "ev/ebitda",
        "forecast",
        "growth",
        "gross margin",
        "illiquidity",
        "margin",
        "multiple",
        "net profit margin",
        "risk-free",
        "sensitivity",
        "tax",
        "terminal",
        "valuation range",
        "wacc",
        "working capital",
    )
    tokens: list[tuple[str, float, str]] = []
    patterns = (
        ("percentage", _re.compile(r"(?<![\w$])-?\d[\d,]*(?:\.\d+)?\s*%")),
        ("multiple", _re.compile(r"(?<![\w$])-?\d[\d,]*(?:\.\d+)?\s*[xX]\b")),
    )
    for kind, pattern in patterns:
        for match in pattern.finditer(text):
            start, end = match.span()
            context = text[max(0, start - 120): min(len(text), end + 120)].lower()
            if kind == "percentage":
                local_context = text[max(0, start - 60): min(len(text), end + 60)].lower()
                if "customer" in local_context and "revenue" in local_context:
                    continue
                if not any(marker in context for marker in markers):
                    continue
            raw = match.group(0).strip()
            cleaned = raw.replace("%", "").replace(",", "").strip()
            if kind == "multiple":
                cleaned = cleaned[:-1].strip()
            try:
                value_number = float(cleaned)
            except ValueError:
                continue
            tokens.append((kind, value_number, raw))
    return tokens


def _named_transaction_claims_from_report_text(value: object) -> list[str]:
    """Extract concrete named M&A-style transaction claims from report prose."""
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    name = r"[A-Z][A-Za-z0-9&.'’/-]*(?:\s+[A-Z][A-Za-z0-9&.'’/-]*){0,5}"
    patterns = (
        rf"\b{name}\s+(?:acquired|bought|purchased)\s+{name}\b",
        rf"\b{name}\s+merged\s+with\s+{name}\b",
        rf"\b{name}\s+was\s+sold\s+to\s+{name}\b",
    )
    claims: list[str] = []
    for pattern in patterns:
        for match in _re.finditer(pattern, text):
            claims.append(" ".join(match.group(0).split()))
    return claims


def _urls_from_report_text(value: object) -> list[str]:
    """Extract source URLs from report content or AccountIQ-calculated valuation evidence."""
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    return [
        match.rstrip(").,;]")
        for match in _re.findall(r"https?://[^\s\"'<>]+", text)
    ]


def _section_contains_number(content: dict, section: str, expected: float, tolerance: float) -> bool:
    numbers = _numbers_from_report_text(content.get(section, ""))
    return any(abs(number - expected) <= tolerance for number in numbers)


def _require_report_number(
    content: dict,
    section: str,
    expected: float,
    label: str,
    *,
    tolerance: float,
) -> None:
    if not _section_contains_number(content, section, expected, tolerance):
        raise ValueError(
            f"Valuation report section '{section}' is missing an AccountIQ-calculated figure "
            f"for {label}: {expected}"
        )


def _money_tolerance(value: float) -> float:
    """Allow nearest-thousand presentation while preventing material drift."""
    return max(1_000.0, abs(value) * 0.001)


def _validate_valuation_report_figures(content: dict, valuation_result: dict) -> None:
    """Ensure generated narrative/tables preserve AccountIQ-calculated valuation figures."""
    illiquidity = valuation_result.get("illiquidity_discount") or {}
    ev_adjusted = illiquidity.get("ev_adjusted") or {}
    dcf_scenarios = valuation_result.get("dcf_scenarios") or {}
    multiples_result = valuation_result.get("multiples_result") or {}
    wacc_scenarios = valuation_result.get("wacc_scenarios_pct") or {}
    sensitivity_matrix = valuation_result.get("sensitivity_matrix") or {}

    gross_debt = float(valuation_result.get("gross_debt") or 0)
    cash = float(valuation_result.get("cash") or 0)
    surplus_assets = float(valuation_result.get("surplus_assets") or 0)
    normalised_ebitda = float(valuation_result.get("normalised_ebitda") or 0)

    def _validate_python_built_table(
        section: str,
        table_key: str,
        label: str,
        *,
        require_text_cells: bool = False,
    ) -> None:
        table = valuation_result.get(table_key) or {}
        rows = table.get("rows") if isinstance(table, dict) else []
        if not isinstance(rows, list) or not rows:
            return
        section_content = content.get(section, {})
        section_text = json.dumps(section_content, ensure_ascii=False).lower()
        content_table = (
            section_content.get(table_key)
            if isinstance(section_content, dict) and isinstance(section_content.get(table_key), dict)
            else section_content.get("table")
            if isinstance(section_content, dict)
            else None
        )
        content_table_rows = (
            content_table.get("rows")
            if isinstance(content_table, dict)
            else []
        )
        content_rows_by_label = {
            str(content_row[0] or "").strip().lower(): content_row
            for content_row in content_table_rows
            if isinstance(content_row, list) and content_row
        } if isinstance(content_table_rows, list) else {}
        for row_index, row in enumerate(rows, start=1):
            if not isinstance(row, list) or not row:
                continue
            row_label = str(row[0] or "").strip()
            content_row = content_rows_by_label.get(row_label.lower()) if row_label else None
            if row_label and content_rows_by_label and content_row is None:
                raise ValueError(
                    f"Valuation report {label} is missing an AccountIQ-calculated row "
                    f"{row_index}: {row_label}"
                )
            if row_label and not content_rows_by_label and row_label.lower() not in section_text:
                raise ValueError(
                    f"Valuation report {label} is missing an AccountIQ-calculated row "
                    f"{row_index}: {row_label}"
                )
            row_text = json.dumps(content_row, ensure_ascii=False).lower() if content_row is not None else section_text
            row_numbers = _numbers_from_report_text(content_row) if content_row is not None else []
            for cell_index, cell in enumerate(row[1:], start=2):
                cell_text = str(cell)
                if require_text_cells and cell_text.strip() and cell_text.lower() not in row_text:
                    raise ValueError(
                        f"Valuation report {label} is missing AccountIQ-calculated cell text "
                        f"from row {row_index} column {cell_index}: {cell_text}"
                    )
                for expected_url in _urls_from_report_text(cell):
                    if expected_url.lower() not in row_text:
                        raise ValueError(
                            f"Valuation report {label} is missing AccountIQ-calculated source URL "
                            f"from row {row_index} column {cell_index}: {expected_url}"
                        )
                tolerance = 0.1 if "%" in cell_text else None
                for expected in _numbers_from_report_text(cell):
                    if expected == 0 and tolerance is None:
                        continue
                    if content_row is not None and not any(
                        abs(number - expected) <= (
                            tolerance if tolerance is not None else _money_tolerance(expected)
                        )
                        for number in row_numbers
                    ):
                        raise ValueError(
                            f"Valuation report {label} row {row_index} column {cell_index} "
                            f"is missing AccountIQ-calculated value: {cell_text}"
                        )
                    _require_report_number(
                        content,
                        section,
                        expected,
                        f"{label} row {row_index} column {cell_index}",
                        tolerance=tolerance if tolerance is not None else _money_tolerance(expected),
                    )

    def _validate_python_built_nested_table(
        section: str,
        content_table_key: str,
        table_key: str,
        label: str,
    ) -> None:
        table = valuation_result.get(table_key) or {}
        expected_headers = table.get("headers") if isinstance(table, dict) else []
        expected_rows = table.get("rows") if isinstance(table, dict) else []
        if not isinstance(expected_headers, list) or not isinstance(expected_rows, list) or not expected_rows:
            return

        section_content = content.get(section, {})
        content_table = (
            section_content.get(content_table_key)
            if isinstance(section_content, dict)
            else None
        )
        if not isinstance(content_table, dict):
            raise ValueError(f"Valuation report {label} is missing {content_table_key}")

        content_headers = content_table.get("headers")
        content_rows = content_table.get("rows")
        if not isinstance(content_headers, list) or not isinstance(content_rows, list):
            raise ValueError(f"Valuation report {label} has invalid table shape")

        content_header_text = " ".join(str(header).strip().lower() for header in content_headers)
        for header in expected_headers:
            header_text = str(header).strip().lower()
            if header_text and header_text not in content_header_text:
                raise ValueError(
                    f"Valuation report {label} is missing an AccountIQ-calculated header: {header}"
                )

        content_rows_by_label = {
            str(row[0] or "").strip().lower(): row
            for row in content_rows
            if isinstance(row, list) and row
        }
        for row_index, expected_row in enumerate(expected_rows, start=1):
            if not isinstance(expected_row, list) or not expected_row:
                continue
            row_label = str(expected_row[0] or "").strip()
            content_row = content_rows_by_label.get(row_label.lower())
            if content_row is None:
                raise ValueError(
                    f"Valuation report {label} is missing an AccountIQ-calculated row "
                    f"{row_index}: {row_label}"
                )
            content_row_text = json.dumps(content_row, ensure_ascii=False).lower()
            content_row_numbers = _numbers_from_report_text(content_row)
            for cell_index, expected_cell in enumerate(expected_row[1:], start=2):
                expected_text = str(expected_cell).strip()
                for expected in _numbers_from_report_text(expected_cell):
                    if not any(
                        abs(number - expected) <= _money_tolerance(expected)
                        for number in content_row_numbers
                    ):
                        raise ValueError(
                            f"Valuation report {label} row {row_index} is missing "
                            f"an AccountIQ-calculated value from column {cell_index}: {expected_cell}"
                        )
                if not _numbers_from_report_text(expected_cell) and expected_text.lower() not in content_row_text:
                    raise ValueError(
                        f"Valuation report {label} row {row_index} is missing "
                        f"AccountIQ-calculated text from column {cell_index}: {expected_text}"
                    )

    def _ev_from_dcf(dcf: dict) -> float:
        return float(
            dcf.get("enterprise_value_dcf")
            or dcf.get("enterprise_value")
            or dcf.get("ev")
            or 0
        )

    for scenario in ("high", "mid", "low"):
        adjusted_ev = float(ev_adjusted.get(scenario) or 0)
        if adjusted_ev:
            _require_report_number(
                content,
                "dcf_analysis",
                adjusted_ev,
                f"DCF {scenario} adjusted enterprise value",
                tolerance=_money_tolerance(adjusted_ev),
            )
            _require_report_number(
                content,
                "valuation_summary",
                adjusted_ev,
                f"DCF {scenario} adjusted enterprise value",
                tolerance=_money_tolerance(adjusted_ev),
            )
            equity_value = adjusted_ev - gross_debt + cash + surplus_assets
            _require_report_number(
                content,
                "valuation_summary",
                equity_value,
                f"DCF {scenario} equity value",
                tolerance=_money_tolerance(equity_value),
            )

        unadjusted_ev = _ev_from_dcf(dcf_scenarios.get(scenario) or {})
        if unadjusted_ev:
            _require_report_number(
                content,
                "dcf_analysis",
                unadjusted_ev,
                f"DCF {scenario} enterprise value before illiquidity",
                tolerance=_money_tolerance(unadjusted_ev),
            )

        wacc = float(wacc_scenarios.get(scenario) or 0)
        if wacc:
            _require_report_number(
                content,
                "wacc_assumptions",
                wacc,
                f"{scenario} WACC",
                tolerance=0.1,
            )
            _require_report_number(
                content,
                "dcf_analysis",
                wacc,
                f"{scenario} WACC",
                tolerance=0.1,
            )

    for key, label in (
        ("enterprise_value_low", "multiples low enterprise value"),
        ("enterprise_value_mid", "multiples midpoint enterprise value"),
        ("enterprise_value_high", "multiples high enterprise value"),
    ):
        value = float(multiples_result.get(key) or 0)
        if value:
            _require_report_number(
                content,
                "multiples_crosscheck",
                value,
                label,
                tolerance=_money_tolerance(value),
            )

    if normalised_ebitda:
        for section in ("dcf_analysis", "multiples_crosscheck"):
            _require_report_number(
                content,
                section,
                normalised_ebitda,
                f"normalised EBITDA in {section}",
                tolerance=_money_tolerance(normalised_ebitda),
            )

    _validate_python_built_table(
        "executive_summary",
        "executive_summary_table",
        "executive summary valuation snapshot",
    )
    _validate_python_built_table(
        "wacc_assumptions",
        "wacc_assumptions_table",
        "WACC assumptions table",
    )
    _validate_python_built_table(
        "dcf_analysis",
        "dcf_analysis_table",
        "DCF analysis table",
    )
    _validate_python_built_nested_table(
        "dcf_analysis",
        "cash_flow_schedule",
        "forecast_cash_flow_schedule",
        "DCF cash-flow schedule",
    )
    _validate_python_built_table(
        "financial_performance",
        "financial_performance_table",
        "financial performance table",
    )
    _validate_python_built_table(
        "financial_ratio_analysis",
        "financial_ratio_table",
        "financial ratio table",
    )
    _validate_python_built_table(
        "balance_sheet_summary",
        "balance_sheet_summary_table",
        "balance sheet summary table",
    )
    _validate_python_built_table(
        "valuation_summary",
        "valuation_summary_table",
        "valuation summary table",
    )
    _validate_python_built_table(
        "multiples_crosscheck",
        "multiples_crosscheck_table",
        "multiples cross-check table",
    )
    _validate_python_built_table(
        "normalisations_schedule",
        "normalisation_schedule",
        "normalisation schedule table",
        require_text_cells=True,
    )
    _validate_python_built_table(
        "valuation_assumptions",
        "assumption_source_trail",
        "assumption/source trail table",
        require_text_cells=True,
    )
    _validate_python_built_table(
        "comparable_evidence",
        "comparable_evidence_table",
        "comparable evidence table",
        require_text_cells=True,
    )
    _validate_python_built_table(
        "sources",
        "sources_table",
        "sources table",
        require_text_cells=True,
    )
    _validate_python_built_table(
        "sensitivity_and_risks",
        "sensitivity_table",
        "sensitivity analysis table",
    )
    _validate_python_built_table(
        "sensitivity_and_risks",
        "specific_risk_factors",
        "specific risk factor table",
        require_text_cells=True,
    )
    allowed_source_urls = {url.lower() for url in _urls_from_report_text(valuation_result)}
    unexpected_source_urls = [
        url
        for url in _urls_from_report_text(content)
        if url.lower() not in allowed_source_urls
    ]
    if unexpected_source_urls:
        raise ValueError(
            "Valuation report contains source URLs not present in the AccountIQ-calculated evidence: "
            f"{unexpected_source_urls}"
        )

    allowed_money_amounts = [
        abs(number)
        for number in (
            _money_amounts_from_report_text(valuation_result)
            + _numbers_from_report_text(valuation_result)
        )
        if math.isfinite(number)
    ]
    unsupported_money_amounts = [
        amount
        for amount in _money_amounts_from_report_text(content)
        if amount
        and not any(
            abs(amount - allowed) <= max(5_000.0, amount * 0.005, allowed * 0.005)
            for allowed in allowed_money_amounts
        )
    ]
    if unsupported_money_amounts:
        raise ValueError(
            "Valuation report contains dollar amounts not present in the AccountIQ-calculated evidence: "
            f"{unsupported_money_amounts}"
        )

    allowed_metric_tokens = _valuation_metric_tokens_from_report_text(valuation_result)
    # The current NZ SME valuation model uses the standard 28% company tax rate
    # when converting EBIT to free cash flow; it is disclosed in report
    # assumptions even though historical valuation_result payloads do not carry
    # a separate tax_rate field.
    allowed_metric_tokens.append(("percentage", float(valuation_result.get("tax_rate_pct") or 28.0), "28%"))
    unsupported_metric_tokens = [
        raw
        for kind, value, raw in _valuation_model_metric_tokens_from_report_text(content)
        if not any(
            allowed_kind == kind
            and abs(value - allowed_value) <= (0.1 if kind == "percentage" else 0.05)
            for allowed_kind, allowed_value, _allowed_raw in allowed_metric_tokens
        )
    ]
    if unsupported_metric_tokens:
        raise ValueError(
            "Valuation report contains percentage or multiple metrics not present in the "
            "AccountIQ-calculated evidence: "
            f"{unsupported_metric_tokens}"
        )

    allowed_transaction_text = json.dumps(
        valuation_result.get("comparable_evidence_table") or valuation_result.get("sources_table") or {},
        ensure_ascii=False,
    ).lower()
    unsupported_transaction_claims = [
        claim
        for claim in _named_transaction_claims_from_report_text(content)
        if claim.lower() not in allowed_transaction_text
    ]
    if unsupported_transaction_claims:
        raise ValueError(
            "Valuation report contains named transaction claims not present in the "
            "AccountIQ-calculated comparable evidence: "
            f"{unsupported_transaction_claims}"
        )

    normalisation_schedule = valuation_result.get("normalisation_schedule") or {}
    normalisation_rows = normalisation_schedule.get("rows") if isinstance(normalisation_schedule, dict) else []
    if isinstance(normalisation_rows, list) and normalisation_rows:
        normalisations_text = json.dumps(content.get("normalisations_schedule", {}), ensure_ascii=False).lower()
        for index, row in enumerate(normalisation_rows, start=1):
            if not isinstance(row, list) or not row:
                continue
            label = str(row[0] or "").strip()
            if label and label.lower() not in normalisations_text:
                raise ValueError(
                    "Valuation report normalisations schedule is missing an AccountIQ-calculated row "
                    f"{index}: {label}"
                )
            row_numbers = _numbers_from_report_text(row[1] if len(row) > 1 else "")
            if row_numbers:
                expected_amount = row_numbers[0]
                if expected_amount:
                    _require_report_number(
                        content,
                        "normalisations_schedule",
                        expected_amount,
                        f"normalisation row {index} amount",
                        tolerance=_money_tolerance(expected_amount),
                    )

    mid_yearly = (dcf_scenarios.get("mid") or {}).get("yearly") or []
    for yearly_row in mid_yearly:
        if not isinstance(yearly_row, dict):
            continue
        year = int(float(yearly_row.get("year") or 0))
        for key, label in (
            ("revenue", "revenue"),
            ("ebit", "EBIT"),
            ("tax", "tax"),
            ("capex", "maintenance capex"),
            ("change_nwc", "change in operating working capital"),
            ("fcff", "free cash flow to firm"),
            ("dcf", "discounted free cash flow"),
        ):
            value = float(yearly_row.get(key) or 0)
            if value:
                _require_report_number(
                    content,
                    "dcf_analysis",
                    value,
                    f"mid-case year {year} {label}",
                    tolerance=_money_tolerance(value),
                )

    for row in sensitivity_matrix.get("adjusted_enterprise_value_rows") or []:
        if not isinstance(row, dict):
            continue
        growth_pct = float(row.get("growth_pct") or 0)
        if growth_pct:
            _require_report_number(
                content,
                "sensitivity_and_risks",
                growth_pct,
                f"sensitivity growth {growth_pct}",
                tolerance=0.1,
            )
        for scenario in ("high", "mid", "low"):
            value = float(row.get(scenario) or 0)
            if value:
                _require_report_number(
                    content,
                    "sensitivity_and_risks",
                    value,
                    f"sensitivity {growth_pct} {scenario} valuation",
                    tolerance=_money_tolerance(value),
                )


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
