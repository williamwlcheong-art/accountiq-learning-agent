"""Shared deterministic inputs for the AccountIQ sample credit-paper pack.

The sample is deliberately fictional. It exercises the same intake-derived
credit calculations and renderers used by the application without carrying
client-reference data into durable output artifacts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import (  # noqa: E402
    _REPORT_SECTION_TITLES,
    _demo_report_content_from_inputs,
    _demo_research_brief,
    _render_cover_report_basis_html,
    _render_cover_report_brief_html,
    _render_report_contents_html,
    _render_report_sections_html,
)
from report_prompts import SECTION_SCHEMAS, compute_bank_credit_figures  # noqa: E402
from report_quality import audit_bank_credit_report_html, audit_bank_credit_report_pdf  # noqa: E402
from report_rendering import report_display_date, report_reference_code, write_report_pdf  # noqa: E402


DEFAULT_COMPANY_NAME = "AccountIQ Sample Services Limited"
DEFAULT_PREPARED_AT = "2026-07-04 09:30:00"
DEFAULT_REPORT_ID = 9002
DEFAULT_REPORT_LABEL = "Demo Bank Credit Paper"
DEFAULT_PDF_NAME = "accountiq-demo-sample-bank-credit-paper.pdf"
DEFAULT_HTML_NAME = "accountiq-demo-sample-bank-credit-paper.html"


def sample_financial_rows() -> list[dict]:
    """Return fictional P&L and balance-sheet rows in the app's prompt format."""
    rows: list[dict] = []

    def add(statement: str, canonical_key: str, row_label: str, values: dict[str, float]) -> None:
        rows.append(
            {
                "statement": statement,
                "canonical_key": canonical_key,
                "row_key": canonical_key,
                "row_label": row_label,
                "values": values,
            }
        )

    add("pnl", "revenue", "Revenue", {"2023": 2_800_000, "2024": 3_250_000, "2025": 3_760_000})
    add("pnl", "ebitda", "EBITDA", {"2023": 410_000, "2024": 505_000, "2025": 620_000})
    add("pnl", "interest_expense", "Interest expense", {"2023": -34_000, "2024": -38_000, "2025": -42_000})
    add("pnl", "depreciation_amortisation", "Depreciation and amortisation", {"2023": 72_000, "2024": 78_000, "2025": 86_000})
    add("pnl", "net_profit", "Net profit", {"2023": 228_000, "2024": 300_000, "2025": 382_000})

    add("bs", "cash_and_bank", "Cash and bank", {"2025": 185_000})
    add("bs", "trade_debtors", "Accounts receivable", {"2025": 410_000})
    add("bs", "inventory", "Stock on hand", {"2025": 95_000})
    add("bs", "total_current_assets", "Total current assets", {"2025": 690_000})
    add("bs", "trade_creditors", "Accounts payable", {"2025": 260_000})
    add("bs", "other_current_liab", "Other current liabilities", {"2025": 80_000})
    add("bs", "short_term_debt", "Current portion of loans", {"2025": 95_000})
    add("bs", "total_current_liab", "Total current liabilities", {"2025": 435_000})
    add("bs", "fixed_assets_net", "Fixed assets", {"2025": 520_000})
    add("bs", "total_assets", "Total assets", {"2025": 1_420_000})
    add("bs", "long_term_debt", "Term loans", {"2025": 280_000})
    add("bs", "total_liabilities", "Total liabilities", {"2025": 795_000})
    add("bs", "shareholders_equity", "Shareholders equity", {"2025": 625_000})
    return rows


def sample_intake_answers() -> dict:
    """Return fictional lender, transaction, security and covenant inputs."""
    return {
        "loan_purpose": "Acquisition of a complementary operating business and refinance of existing debt",
        "amount_requested": 1_250_000,
        "proposed_term_years": 5,
        "conservative_funding_cost_pct": 8.5,
        "lvr_percent": 60,
        "security_package": "general_security_and_guarantee",
        "repayment_profile": "principal_and_interest",
        "borrower_structure": "New HoldCo owns the existing operating company and the acquired target; both OpCos remain trading entities and provide guarantees.",
        "transaction_structure": "Acquisition and refinance debt are consolidated at HoldCo, with one senior term facility and a separate short-dated sponsor bridge.",
        "ownership_and_sponsor": "Founder retains operating control; an incoming investor subscribes for a minority interest and contributes acquisition equity.",
        "acquisition_rationale": "Adds recurring customer relationships, geographic coverage and operating capacity; integration benefits remain subject to diligence.",
        "refinance_context": "Existing equipment debt is to be repaid at completion; payout letters and current lender security releases are required.",
        "facility_type": "Senior secured acquisition and refinance term facility",
        "facility_structure": "Senior term facility plus a separate sponsor bridge; bridge repayment is not assumed in senior DSCR.",
        "transaction_value": 1_900_000,
        "refinance_amount": 280_000,
        "transaction_costs": 55_000,
        "equity_contribution": 705_000,
        "working_capital_buffer": 120_000,
        "sponsor_bridge_amount": 180_000,
        "sponsor_bridge_term_months": 9,
        "sponsor_bridge_repayment_source": "Refinancing or sponsor distribution after completion accounts and transaction proceeds are finalised.",
        "security_value": 2_050_000,
        "security_notes": "General security over both OpCos, equipment register and guarantees; independent collateral confirmation required.",
        "security_structure": "First-ranking GSA over the operating entities, cross-guarantees and shareholder support; no property security assumed.",
        "sponsor_bridge_security": "Personal guarantee and negative pledge to be documented separately from the OpCo security package.",
        "source_of_repayment": "Operating cash flow from the combined group, supported by recurring service revenue and post-completion management accounts.",
        "minimum_dscr": 1.4,
        "minimum_interest_cover": 3.0,
        "maximum_senior_leverage": 2.5,
        "covenant_package_level": "balanced",
        "selected_covenants": [
            "min_dscr",
            "min_interest_cover",
            "max_senior_leverage",
            "no_additional_debt",
            "information_reporting",
        ],
        "covenant_package_notes": "Keep the senior package measurable and testable; bridge controls remain separate until repayment is documented.",
    }


def sample_report_content(*, run_audit: bool = True) -> tuple[dict, dict]:
    """Return rendered-section content and the intake used to produce it."""
    intake_answers = sample_intake_answers()
    figures = compute_bank_credit_figures(sample_financial_rows(), intake_answers)
    brief = _demo_research_brief(
        company_name=DEFAULT_COMPANY_NAME,
        company_location="New Zealand",
        industry_sector="Business services",
    ).model_dump()
    sections = _demo_report_content_from_inputs(
        report_type="bank_credit_paper",
        company_name=DEFAULT_COMPANY_NAME,
        financial_rows=sample_financial_rows(),
        valuation_result=None,
        bank_credit_figures=figures,
        credit_research_brief=brief,
        intake_answers=intake_answers,
    )
    if run_audit:
        _assert_sections_ready(sections)
    return sections, intake_answers


def _assert_sections_ready(sections: dict) -> None:
    """Fail fast if the deterministic sample drops a required section."""
    missing = [key for key in SECTION_SCHEMAS["bank_credit_paper"] if not sections.get(key)]
    if missing:
        raise RuntimeError(json.dumps({"missing_sections": missing}, indent=2))


def generate_sample_pdf(output_path: Path, *, report_id: int = DEFAULT_REPORT_ID) -> Path:
    """Generate and audit the fictional sample credit-paper PDF."""
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sections, intake_answers = sample_report_content()
    write_report_pdf(
        output_path,
        company_name=DEFAULT_COMPANY_NAME,
        report_label=DEFAULT_REPORT_LABEL,
        report_type="bank_credit_paper",
        valuation_purpose="",
        intake_answers=intake_answers,
        sections=sections,
        section_order=SECTION_SCHEMAS["bank_credit_paper"],
        section_titles=_REPORT_SECTION_TITLES,
        report_id=report_id,
        generated_at=DEFAULT_PREPARED_AT,
        demo_mode=True,
    )
    audit = audit_bank_credit_report_pdf(output_path, demo_mode=True)
    if not audit.passed:
        raise RuntimeError(json.dumps(audit.as_dict(), indent=2))
    return output_path


def _html_styles() -> str:
    return """
    :root { --navy:#082b4c; --blue:#1769aa; --ink:#172033; --muted:#667085; --line:#d7dee8; }
    * { box-sizing:border-box; }
    body { margin:0; background:#edf1f5; color:var(--ink); font-family:Arial,"Segoe UI",sans-serif; line-height:1.55; }
    .viewer-toolbar { position:sticky; top:0; z-index:5; display:flex; justify-content:space-between; align-items:center; gap:14px; padding:10px max(20px,calc((100vw - 900px)/2)); background:rgba(8,43,76,.97); color:white; }
    .viewer-toolbar a { color:white; text-decoration:none; font-weight:700; }
    .viewer-toolbar-actions { display:flex; align-items:center; gap:14px; }
    .viewer-download { padding:7px 12px; border:1px solid rgba(255,255,255,.55); border-radius:999px; }
    .report { width:min(900px,calc(100% - 32px)); margin:28px auto 64px; }
    .demo-banner { margin:0 0 18px; padding:14px 18px; border:1px solid #e3ad55; border-radius:8px; background:#fff8e8; color:#70450a; }
    .demo-banner strong { display:block; margin-bottom:2px; }
    .cover, .report-page, .report-section { background:white; box-shadow:0 12px 30px rgba(15,23,42,.1); }
    .cover { position:relative; min-height:1120px; display:flex; flex-direction:column; justify-content:flex-end; padding:78px 74px; overflow:hidden; background:linear-gradient(150deg,#f8fbff 0 52%,#dceafb 52% 64%,#082b4c 64%); color:white; }
    .brand { position:absolute; top:88px; left:74px; color:var(--navy); font-size:1.1rem; font-weight:900; letter-spacing:.04em; }
    .cover-report-basis { position:relative; margin:64px 0 36px; padding:18px 22px; border:1px solid var(--line); border-radius:16px; background:rgba(255,255,255,.94); color:var(--ink); }
    .cover-report-basis > span { display:block; margin-bottom:13px; color:var(--blue); font-size:.72rem; font-weight:850; letter-spacing:.08em; text-transform:uppercase; }
    .cover-report-basis dl { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:0; margin:0; }
    .cover-report-basis div { min-width:0; padding:0 15px; border-left:1px solid var(--line); }
    .cover-report-basis div:first-child { padding-left:0; border-left:0; }
    .cover-report-basis dt { margin:0 0 4px; color:var(--navy); font-size:.75rem; font-weight:850; }
    .cover-report-basis dd { margin:0; color:var(--muted); font-size:.68rem; line-height:1.35; }
    .cover-copy { position:relative; padding:28px 32px 30px; border:1px solid rgba(207,226,243,.3); border-radius:18px; background:rgba(8,43,76,.93); }
    .cover-kicker { display:block; margin-bottom:12px; color:#b9d8f2; font-size:.78rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }
    .cover h1 { margin:0 0 16px; font-size:3.15rem; line-height:1.06; }
    .company { margin:0; font-size:1.4rem; font-weight:650; }
    .cover-brief { margin:28px 0 0; padding:18px 20px; border:1px solid rgba(207,226,243,.35); border-radius:14px; background:rgba(255,255,255,.08); }
    .cover-brief dl { display:grid; grid-template-columns:1fr 1fr; gap:13px 22px; margin:0; }
    .cover-brief dt { color:#b9d8f2; font-size:.67rem; font-weight:850; letter-spacing:.09em; text-transform:uppercase; }
    .cover-brief dd { margin:3px 0 0; color:white; font-size:.84rem; font-weight:700; overflow-wrap:anywhere; }
    .report-page { min-height:1120px; margin-top:22px; padding:78px 74px; }
    .contents h2, .report-section h2 { margin:0 0 26px; color:var(--navy); font-size:2.2rem; font-weight:400; }
    .contents ol { display:grid; grid-template-columns:1fr 1fr; gap:0 36px; margin:0; padding:0; list-style:none; }
    .contents li { border-bottom:1px solid var(--line); }
    .contents a { display:flex; gap:12px; padding:12px 0; color:var(--ink); text-decoration:none; font-weight:700; }
    .contents-number { min-width:2ch; color:var(--blue); }
    .report-section { min-height:760px; margin-top:22px; padding:68px 74px 78px; }
    .section-kicker { display:block; margin-bottom:8px; color:var(--blue); font-size:.68rem; font-weight:850; letter-spacing:.12em; text-transform:uppercase; }
    .report-section h2 { padding-bottom:14px; border-bottom:1px solid var(--navy); }
    .section-number { display:inline-block; min-width:2.5rem; margin-right:.7rem; color:var(--blue); font-size:1rem; font-weight:850; vertical-align:.3rem; }
    h3 { margin:1.55rem 0 .55rem; color:var(--navy); font-size:1rem; }
    p { margin:0 0 .9rem; font-size:.92rem; }
    a { color:var(--blue); overflow-wrap:anywhere; }
    ul { margin:.25rem 0 1rem 1.25rem; padding:0; }
    table.report-table { width:100%; margin:20px 0 28px; border-collapse:collapse; font-size:.79rem; }
    table.report-table caption { caption-side:top; margin:0 0 8px; color:var(--muted); font-size:.7rem; font-weight:850; letter-spacing:.08em; text-align:left; text-transform:uppercase; }
    table.report-table th, table.report-table td { padding:9px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
    table.report-table thead th { background:var(--navy); color:white; font-weight:750; }
    table.report-table tbody tr:nth-child(even) { background:#f6f8fb; }
    .disclaimer { border-top:8px solid #c9932f; background:#fffdf8; }
    @media (max-width:720px) {
      .report { width:100%; margin:0; }
      .cover, .report-page, .report-section { min-height:auto; padding:46px 24px; box-shadow:none; }
      .cover { min-height:80vh; }
      .cover h1 { font-size:2.25rem; }
      .brand { left:24px; }
      .cover-report-basis { margin:88px 0 28px; padding:16px; }
      .cover-report-basis dl, .cover-brief dl, .contents ol { grid-template-columns:1fr; }
      .cover-report-basis div { padding:0; border-left:0; }
      table.report-table { display:block; overflow-x:auto; }
      .viewer-toolbar { flex-wrap:wrap; }
      .viewer-toolbar-actions { width:100%; justify-content:space-between; }
    }
    @media print {
      @page { size:A4; margin:0; }
      body { background:white; }
      .viewer-toolbar { display:none; }
      .report { width:100%; margin:0; }
      .cover, .report-page, .report-section { width:210mm; min-height:297mm; margin:0; padding:20mm 18mm; box-shadow:none; break-after:page; page-break-after:always; }
      .report-section:last-child { break-after:auto; page-break-after:auto; }
      tr, p, li { break-inside:avoid; page-break-inside:avoid; }
    }
    """


def render_sample_html(*, report_id: int = DEFAULT_REPORT_ID) -> str:
    """Render the same sample sections as the app's browser report viewer."""
    sections, _intake_answers = sample_report_content()
    section_order = SECTION_SCHEMAS["bank_credit_paper"]
    label = DEFAULT_REPORT_LABEL
    cover_basis = _render_cover_report_basis_html("bank_credit_paper")
    cover_brief = _render_cover_report_brief_html(
        company_name=DEFAULT_COMPANY_NAME,
        report_label=label,
        report_type="bank_credit_paper",
        report_id=report_id,
        generated_at=DEFAULT_PREPARED_AT,
        demo_mode=True,
    )
    contents = _render_report_contents_html(sections, section_order)
    section_html = _render_report_sections_html(sections, section_order, "bank_credit_paper")
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{label} - {DEFAULT_COMPANY_NAME}</title><style>{_html_styles()}</style></head>
<body>
<nav class="viewer-toolbar"><a href="/wizard">&#8592; Back to wizard</a><div class="viewer-toolbar-actions"><span>PDF download ready</span><a class="viewer-download" href="./pdf" download>Download PDF</a></div></nav>
<main class="report">
<aside class="demo-banner" role="note"><strong>Demo data - not for reliance.</strong>Financial figures and research are fictional and demonstrate the AccountIQ credit-paper workflow.</aside>
<section class="cover"><div class="brand">AccountIQ</div>{cover_basis}<div class="cover-copy"><span class="cover-kicker">Demo data - not for reliance</span><h1>{label}</h1><p class="company">{DEFAULT_COMPANY_NAME}</p>{cover_brief}</div></section>
<section class="report-page contents"><h2>Contents</h2><ol>{contents}</ol></section>
{section_html}
</main></body></html>"""
    audit = audit_bank_credit_report_html(html, demo_mode=True)
    if not audit.passed:
        raise RuntimeError(json.dumps(audit.as_dict(), indent=2))
    return html


def generate_sample_html(output_path: Path, *, report_id: int = DEFAULT_REPORT_ID) -> Path:
    """Generate and audit the fictional sample credit-paper browser HTML."""
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_sample_html(report_id=report_id), encoding="utf-8")
    return output_path
