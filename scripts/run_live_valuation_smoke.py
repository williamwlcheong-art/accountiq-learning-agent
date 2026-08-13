"""Run a live AccountIQ valuation-report smoke test.

This is intentionally separate from normal pytest and E2E runs because it uses
the configured OpenAI account. It proves that the live model can turn
AccountIQ-computed valuation inputs into strict report JSON, pass the same
backend quality gates as customer reports, and render browser/PDF artifacts for
professional-output review.

Usage:
    OPENAI_API_KEY=sk-proj-... python scripts/run_live_valuation_smoke.py

The script refuses to run in demo mode or without a real-looking key. It never
prints the key.
"""
from __future__ import annotations

import argparse
import asyncio
import html as html_lib
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import (  # noqa: E402
    _REPORT_SECTION_TITLES,
    _call_openai_for_report,
    _demo_mode_enabled,
    _live_openai_key_configured,
    _render_cover_report_brief_html,
    _render_cover_valuation_snapshot_html,
    _render_report_contents_html,
    _render_report_sections_html,
    _render_valuation_basis_html,
    _run_live_research_preflight,
    _validate_generated_report_content,
    _validate_valuation_report_figures,
)
from report_prompts import SECTION_SCHEMAS, build_prompt  # noqa: E402
from report_quality import (  # noqa: E402
    audit_valuation_report_content,
    audit_valuation_report_html,
    audit_valuation_report_pdf,
)
from report_rendering import write_report_pdf  # noqa: E402
from valuation import (  # noqa: E402
    build_assumption_source_trail,
    build_balance_sheet_summary_table,
    build_comparable_evidence_table,
    build_dcf_analysis_table,
    build_executive_summary_table,
    build_financial_performance_table,
    build_financial_ratio_table,
    build_forecast_cash_flow_schedule,
    build_multiples_crosscheck_table,
    build_normalisation_schedule_table,
    build_sensitivity_analysis_table,
    build_sources_table,
    build_specific_risk_factor_table,
    build_valuation_summary_table,
    build_wacc_assumptions_table,
    compute_dcf,
    compute_dcf_sensitivity_matrix,
    compute_illiquidity_discount,
    compute_multiples_range,
    compute_wacc_scenarios,
    derive_reinvestment_assumptions,
    select_revenue_growth_assumption,
)


DEFAULT_JSON_OUTPUT = ROOT / "output" / "live-smoke" / "accountiq-live-valuation-smoke.json"
DEFAULT_HTML_OUTPUT = ROOT / "output" / "html" / "accountiq-live-valuation-smoke.html"
DEFAULT_PDF_OUTPUT = ROOT / "output" / "pdf" / "accountiq-live-valuation-smoke.pdf"
DEFAULT_PREPARED_AT = "2026-07-04 09:30:00"


def _sample_raw_financial_rows() -> list[dict[str, Any]]:
    """Return flat financial rows shaped like database extraction output."""
    return [
        {"statement": "pnl", "row_key": "revenue", "row_label": "Revenue", "period": "FY2023", "value": 980_000},
        {"statement": "pnl", "row_key": "revenue", "row_label": "Revenue", "period": "FY2024", "value": 1_110_000},
        {"statement": "pnl", "row_key": "revenue", "row_label": "Revenue", "period": "FY2025", "value": 1_250_000},
        {"statement": "pnl", "row_key": "gross_profit", "row_label": "Gross profit", "period": "FY2023", "value": 588_000},
        {"statement": "pnl", "row_key": "gross_profit", "row_label": "Gross profit", "period": "FY2024", "value": 682_600},
        {"statement": "pnl", "row_key": "gross_profit", "row_label": "Gross profit", "period": "FY2025", "value": 787_500},
        {"statement": "pnl", "row_key": "ebitda", "row_label": "EBITDA", "period": "FY2023", "value": 165_000},
        {"statement": "pnl", "row_key": "ebitda", "row_label": "EBITDA", "period": "FY2024", "value": 205_000},
        {"statement": "pnl", "row_key": "ebitda", "row_label": "EBITDA", "period": "FY2025", "value": 240_000},
        {"statement": "pnl", "row_key": "net_profit", "row_label": "Net profit after tax", "period": "FY2023", "value": 105_000},
        {"statement": "pnl", "row_key": "net_profit", "row_label": "Net profit after tax", "period": "FY2024", "value": 128_000},
        {"statement": "pnl", "row_key": "net_profit", "row_label": "Net profit after tax", "period": "FY2025", "value": 150_000},
        {"statement": "pnl", "row_key": "depreciation_amortisation", "row_label": "Depreciation", "period": "FY2025", "value": 25_000},
        {"statement": "bs", "row_key": "cash_and_bank", "row_label": "Cash and bank", "period": "FY2025", "value": 95_000},
        {"statement": "bs", "row_key": "operating_fixed_assets", "row_label": "Operating fixed assets", "period": "FY2025", "value": 185_000},
        {"statement": "bs", "row_key": "trade_debtors", "row_label": "Trade debtors", "period": "FY2025", "value": 92_000},
        {"statement": "bs", "row_key": "inventory", "row_label": "Inventory", "period": "FY2025", "value": 18_000},
        {"statement": "bs", "row_key": "other_current_assets", "row_label": "Other current assets", "period": "FY2025", "value": 24_000},
        {"statement": "bs", "row_key": "trade_creditors", "row_label": "Trade creditors", "period": "FY2025", "value": 68_000},
        {"statement": "bs", "row_key": "other_current_liab", "row_label": "Other current liabilities", "period": "FY2025", "value": 4_000},
        {"statement": "bs", "row_key": "short_term_debt", "row_label": "Short-term debt", "period": "FY2025", "value": 35_000},
        {"statement": "bs", "row_key": "long_term_debt", "row_label": "Long-term debt", "period": "FY2025", "value": 125_000},
    ]


def _group_financial_rows_for_prompt(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in raw_rows:
        key = (str(row["statement"]), str(row["row_key"]))
        item = grouped.setdefault(
            key,
            {
                "canonical_key": row["row_key"],
                "statement": row["statement"],
                "values": {},
            },
        )
        item["values"][str(row["period"])] = row["value"]
    return list(grouped.values())


def _latest_value(rows_by_key: dict[str, list[tuple[str, float]]], key: str) -> float:
    entries = rows_by_key.get(key, [])
    if not entries:
        return 0.0
    return sorted(entries, key=lambda item: item[0], reverse=True)[0][1]


def build_smoke_inputs() -> dict[str, Any]:
    """Build deterministic AccountIQ-computed valuation inputs for the live smoke."""
    company_name = "AccountIQ Sample Limited"
    company_sector = "SME business services"
    company_description = (
        "New Zealand SME services business with recurring customer relationships, "
        "project delivery work and owner-transition considerations."
    )
    intake_answers = {
        "valuation_purpose": "understand_value",
        "company_location": "Auckland, New Zealand",
        "company_website": "https://example.co.nz",
        "public_source_urls": [
            "https://www.rbnz.govt.nz/statistics",
            "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
        ],
        "owner_dependency": "shared",
        "customer_concentration": "10_to_25",
        "revenue_quality": "mixed",
        "revenue_outlook": "modest_growth",
        "private_context": "A key customer contract renews next year and management has started documenting delivery processes.",
        "normalisations": [
            {
                "label": "Owner remuneration above market",
                "amount": 35_000,
                "rationale": "Replace with an arm's-length management cost.",
            },
            {
                "label": "One-off legal costs",
                "amount": 12_000,
                "rationale": "Non-recurring transaction expenditure.",
            },
        ],
    }
    raw_rows = _sample_raw_financial_rows()
    financial_rows_for_prompt = _group_financial_rows_for_prompt(raw_rows)

    pnl_by_key: dict[str, list[tuple[str, float]]] = {}
    bs_by_key: dict[str, list[tuple[str, float]]] = {}
    for row in raw_rows:
        key = str(row["row_key"])
        period = str(row["period"])
        value = float(row["value"])
        if row["statement"] == "pnl":
            pnl_by_key.setdefault(key, []).append((period, value))
        elif row["statement"] == "bs":
            bs_by_key.setdefault(key, []).append((period, value))

    depreciation_base = abs(_latest_value(pnl_by_key, "depreciation_amortisation"))
    extracted_ebitda = _latest_value(pnl_by_key, "ebitda")
    revenues_val = _latest_value(pnl_by_key, "revenue")
    net_profit_latest = _latest_value(pnl_by_key, "net_profit")
    cash_val = abs(_latest_value(bs_by_key, "cash_and_bank"))
    latest_balance_sheet_values = {
        key: _latest_value(bs_by_key, key)
        for key in bs_by_key
    }
    reinvestment = derive_reinvestment_assumptions(
        latest_balance_sheet_values,
        revenues_val,
        depreciation_base,
    )
    addbacks_total = sum(
        float(item.get("amount", 0) or 0)
        for item in intake_answers["normalisations"]
    )
    normalised_ebitda = extracted_ebitda + addbacks_total
    revenue_growth_pct, growth_assumption_source = select_revenue_growth_assumption(
        pnl_by_key.get("revenue", []),
        intake_answers["revenue_outlook"],
    )

    forecast_years = 5
    tax_rate = 0.28
    wacc_pct = compute_wacc_scenarios(
        risk_free_rate=4.4,
        industry_beta=1.2,
        erp=5.9,
    )
    terminal_growth_pct = min(2.5, wacc_pct["low"] - 0.5)

    def _run_dcf(wacc_percent: float) -> dict[str, Any]:
        return compute_dcf(
            ebitda=normalised_ebitda,
            wacc=wacc_percent / 100.0,
            growth_rate=revenue_growth_pct / 100.0,
            tax_rate=tax_rate,
            years=forecast_years,
            terminal_growth=terminal_growth_pct / 100.0,
            revenue=revenues_val,
            depreciation_per_year=depreciation_base,
            capex_per_year=reinvestment["maintenance_capex"],
            working_capital_ratio=reinvestment["working_capital_ratio"],
        )

    dcf_high = _run_dcf(wacc_pct["low"])
    dcf_mid = _run_dcf(wacc_pct["mid"])
    dcf_low = _run_dcf(wacc_pct["high"])
    wacc_by_valuation_scenario = {
        "high": wacc_pct["low"],
        "mid": wacc_pct["mid"],
        "low": wacc_pct["high"],
    }

    ev_mid = float(dcf_mid["enterprise_value_dcf"])
    illiq_rate = compute_illiquidity_discount(
        revenues_val,
        net_profit_latest > 0,
        cash_val,
        ev_mid,
    )
    ev_adjusted = {
        "high": float(dcf_high["enterprise_value_dcf"]) * (1.0 - illiq_rate),
        "mid": ev_mid * (1.0 - illiq_rate),
        "low": float(dcf_low["enterprise_value_dcf"]) * (1.0 - illiq_rate),
    }
    gross_debt = abs(
        _latest_value(bs_by_key, "short_term_debt")
        + _latest_value(bs_by_key, "long_term_debt")
    )
    surplus_assets = 0.0
    net_debt = gross_debt - cash_val
    multiples_result = compute_multiples_range(
        normalised_ebitda=normalised_ebitda,
        ev_ebitda_low=3.5,
        ev_ebitda_high=5.0,
    )
    sensitivity_matrix = compute_dcf_sensitivity_matrix(
        ebitda=normalised_ebitda,
        revenue=revenues_val,
        depreciation_per_year=depreciation_base,
        capex_per_year=reinvestment["maintenance_capex"],
        working_capital_ratio=reinvestment["working_capital_ratio"],
        wacc_by_valuation_scenario_pct=wacc_by_valuation_scenario,
        base_growth_pct=revenue_growth_pct,
        tax_rate=tax_rate,
        years=forecast_years,
        terminal_growth_pct=terminal_growth_pct,
        illiquidity_discount=illiq_rate,
    )

    sources = [
        "https://www.rbnz.govt.nz/statistics",
        "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
    ]
    valuation_result = {
        "research_brief": {
            "company_summary": "Sample company profile used only for the live smoke test.",
            "sector_summary": "Business-services SME sector context used to test report generation quality.",
            "industry_category": "Business and consumer services",
            "risk_free_rate": 4.4,
            "industry_beta": 1.2,
            "erp": 5.9,
            "inflation_rate": 2.5,
            "ev_ebitda_low": 3.5,
            "ev_ebitda_high": 5.0,
            "comparable_transactions": [
                {
                    "name": "NZ SME services transaction evidence",
                    "date": "2024",
                    "multiple": "3.5x-5.0x EV/EBITDA",
                    "source_url": "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
                    "notes": "Public benchmark evidence; comparability depends on scale, growth and buyer terms.",
                }
            ],
            "sources": sources,
        },
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
        "maintenance_capex": reinvestment["maintenance_capex"],
        "operating_working_capital": reinvestment["operating_working_capital"],
        "working_capital_ratio_pct": reinvestment["working_capital_ratio_pct"],
        "working_capital_source": reinvestment["working_capital_source"],
        "executive_summary_table": build_executive_summary_table(
            adjusted_enterprise_values=ev_adjusted,
            gross_debt=gross_debt,
            cash=cash_val,
            surplus_assets=surplus_assets,
        ),
        "wacc_assumptions_table": build_wacc_assumptions_table(
            risk_free_rate=4.4,
            erp=5.9,
            industry_beta=1.2,
            wacc_by_valuation_scenario_pct=wacc_by_valuation_scenario,
            illiquidity_discount=illiq_rate,
        ),
        "dcf_analysis_table": build_dcf_analysis_table(
            dcf_scenarios={"high": dcf_high, "mid": dcf_mid, "low": dcf_low},
            adjusted_enterprise_values=ev_adjusted,
            wacc_by_valuation_scenario_pct=wacc_by_valuation_scenario,
            terminal_growth_pct=terminal_growth_pct,
            revenue=revenues_val,
            normalised_ebitda=normalised_ebitda,
            depreciation_base=depreciation_base,
            maintenance_capex=reinvestment["maintenance_capex"],
            working_capital_ratio_pct=reinvestment["working_capital_ratio_pct"],
            illiquidity_discount=illiq_rate,
        ),
        "financial_performance_table": build_financial_performance_table(raw_rows),
        "financial_ratio_table": build_financial_ratio_table(raw_rows),
        "balance_sheet_summary_table": build_balance_sheet_summary_table(
            raw_rows,
            gross_debt=gross_debt,
            cash=cash_val,
            surplus_assets=surplus_assets,
            midpoint_enterprise_value=ev_adjusted["mid"],
            operating_working_capital=reinvestment["operating_working_capital"],
            working_capital_source=reinvestment["working_capital_source"],
        ),
        "valuation_summary_table": build_valuation_summary_table(
            dcf_scenarios={"high": dcf_high, "mid": dcf_mid, "low": dcf_low},
            adjusted_enterprise_values=ev_adjusted,
            wacc_by_valuation_scenario_pct=wacc_by_valuation_scenario,
            multiples_result=multiples_result,
            gross_debt=gross_debt,
            cash=cash_val,
            surplus_assets=surplus_assets,
        ),
        "multiples_crosscheck_table": build_multiples_crosscheck_table(multiples_result),
        "assumption_source_trail": build_assumption_source_trail(
            normalised_ebitda=normalised_ebitda,
            forecast_years=forecast_years,
            revenue_growth_pct=revenue_growth_pct,
            growth_assumption_source=growth_assumption_source,
            terminal_growth_pct=terminal_growth_pct,
            wacc_by_valuation_scenario_pct=wacc_by_valuation_scenario,
            maintenance_capex=reinvestment["maintenance_capex"],
            working_capital_ratio_pct=reinvestment["working_capital_ratio_pct"],
            working_capital_source=reinvestment["working_capital_source"],
            gross_debt=gross_debt,
            cash=cash_val,
            surplus_assets=surplus_assets,
            owner_dependency=intake_answers["owner_dependency"],
            customer_concentration=intake_answers["customer_concentration"],
            revenue_quality=intake_answers["revenue_quality"],
            revenue_outlook=intake_answers["revenue_outlook"],
        ),
        "comparable_evidence_table": build_comparable_evidence_table(
            comparable_transactions=[
                {
                    "name": "NZ SME services transaction evidence",
                    "date": "2024",
                    "metric": "3.5x-5.0x EV/EBITDA",
                    "relevance": "Benchmark range only; comparability depends on scale, growth, contract quality and deal terms.",
                    "source_url": "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
                }
            ],
            sources=sources,
        ),
        "sources_table": build_sources_table(sources),
        "normalisation_schedule": build_normalisation_schedule_table(
            intake_answers["normalisations"],
            normalised_ebitda=normalised_ebitda,
        ),
        "forecast_cash_flow_schedule": build_forecast_cash_flow_schedule(dcf_mid),
        "sensitivity_matrix": sensitivity_matrix,
        "sensitivity_table": build_sensitivity_analysis_table(
            sensitivity_matrix,
            base_growth_pct=revenue_growth_pct,
        ),
        "specific_risk_factors": build_specific_risk_factor_table(
            owner_dependency=intake_answers["owner_dependency"],
            customer_concentration=intake_answers["customer_concentration"],
            revenue_quality=intake_answers["revenue_quality"],
            revenue_outlook=intake_answers["revenue_outlook"],
            private_context=intake_answers["private_context"],
        ),
        "multiples_result": multiples_result,
    }

    return {
        "company_name": company_name,
        "company_sector": company_sector,
        "company_description": company_description,
        "financial_rows": financial_rows_for_prompt,
        "intake_answers": intake_answers,
        "management_team": [
            {
                "name": "Sample owner",
                "title": "Managing Director",
                "bio": "Founder with responsibility shared across the operating team.",
            }
        ],
        "ebitda_adjustments": intake_answers["normalisations"],
        "valuation_result": valuation_result,
    }


def _render_live_smoke_html(
    *,
    sections: dict[str, Any],
    inputs: dict[str, Any],
    prepared_at: str,
    pdf_href: str = "./pdf",
) -> str:
    """Render a standalone browser report artifact for the live smoke run."""
    report_label = "Live Smoke Indicative Valuation Report"
    company_name = str(inputs["company_name"])
    valuation_purpose = "Understand what the business may be worth"
    section_order = SECTION_SCHEMAS["valuation_advisory"]
    contents_html = _render_report_contents_html(sections, section_order)
    basis_html = _render_valuation_basis_html(
        company_name=company_name,
        report_label=report_label,
        report_id=9901,
        demo_mode=False,
        valuation_purpose=valuation_purpose,
        generated_at=prepared_at,
        intake_answers=inputs["intake_answers"],
    )
    section_html = _render_report_sections_html(sections, section_order)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_lib.escape(report_label)} - {html_lib.escape(company_name)}</title>
</head>
<body>
  <nav class="viewer-toolbar" aria-label="Report actions">
    <a href="/wizard">Back to wizard</a>
    <a class="viewer-download" href="{html_lib.escape(pdf_href, quote=True)}">Download PDF</a>
  </nav>
  <main class="report">
    <section class="cover">
      <div class="brand">AccountIQ</div>
      {_render_cover_valuation_snapshot_html(sections)}
      <div class="cover-copy">
        <span class="cover-kicker">Confidential - indicative only</span>
        <h1>{html_lib.escape(report_label)}</h1>
        <p class="company">{html_lib.escape(company_name)}</p>
        {_render_cover_report_brief_html(
            company_name=company_name,
            report_label=report_label,
            report_id=9901,
            generated_at=prepared_at,
            valuation_purpose=valuation_purpose,
            demo_mode=False,
        )}
      </div>
    </section>
    <section class="report-page contents">
      <h2>Contents</h2>
      <div class="contents-frontmatter">
        <a href="#basis-of-preparation"><span>Front matter</span>Report letter and basis of preparation</a>
      </div>
      <ol>
        {contents_html}
      </ol>
    </section>
    {basis_html}
    {section_html}
  </main>
</body>
</html>
"""


async def run_live_valuation_smoke(
    *,
    output_json: Path = DEFAULT_JSON_OUTPUT,
    output_html: Path | None = DEFAULT_HTML_OUTPUT,
    output_pdf: Path | None = DEFAULT_PDF_OUTPUT,
    prepared_at: str = DEFAULT_PREPARED_AT,
) -> dict[str, Any]:
    """Run the live smoke test and return a compact summary."""
    if _demo_mode_enabled():
        raise RuntimeError(
            "Live valuation smoke requires demo mode to be off. "
            "Unset ACCOUNTIQ_DEMO_MODE and do not run with ACCOUNTIQ_E2E_MODE=true."
        )
    if not _live_openai_key_configured():
        raise RuntimeError(
            "Live valuation smoke requires a real OpenAI API key in OPENAI_API_KEY."
        )

    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    preflight_fresh = await _run_live_research_preflight(api_key, model)

    inputs = build_smoke_inputs()
    system_prompt, user_message = build_prompt(
        report_type="valuation_advisory",
        company_name=inputs["company_name"],
        industry=inputs["company_sector"],
        description=inputs["company_description"],
        financial_rows=inputs["financial_rows"],
        intake_answers=inputs["intake_answers"],
        management_team=inputs["management_team"],
        ebitda_adjustments=inputs["ebitda_adjustments"],
        valuation_result=inputs["valuation_result"],
    )
    content_json = await _call_openai_for_report(
        system_prompt,
        user_message,
        sections=SECTION_SCHEMAS["valuation_advisory"],
    )
    _validate_generated_report_content(content_json, "valuation_advisory")
    _validate_valuation_report_figures(content_json, inputs["valuation_result"])
    content_audit = audit_valuation_report_content(content_json)
    if not content_audit.passed:
        raise RuntimeError(
            "Live valuation report failed professional content audit: "
            f"{[issue.as_dict() for issue in content_audit.issues]}"
        )

    output_json = output_json.expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(
            {
                "metadata": {
                    "purpose": "AccountIQ live valuation smoke test",
                    "model": model,
                    "preflight_fresh": preflight_fresh,
                    "prepared_at": prepared_at,
                    "company_name": inputs["company_name"],
                },
                "content": content_json,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    html_path = None
    html_audit_dict = None
    if output_html is not None:
        output_html = output_html.expanduser().resolve()
        output_html.parent.mkdir(parents=True, exist_ok=True)
        output_html.write_text(
            _render_live_smoke_html(
                sections=content_json,
                inputs=inputs,
                prepared_at=prepared_at,
            ),
            encoding="utf-8",
        )
        html_audit = audit_valuation_report_html(output_html.read_text(encoding="utf-8"), demo_mode=False)
        if not html_audit.passed:
            raise RuntimeError(
                "Live valuation browser HTML failed professional artifact audit: "
                f"{[issue.as_dict() for issue in html_audit.issues]}"
            )
        html_path = str(output_html)
        html_audit_dict = html_audit.as_dict()

    pdf_path = None
    pdf_audit_dict = None
    if output_pdf is not None:
        output_pdf = output_pdf.expanduser().resolve()
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        write_report_pdf(
            output_pdf,
            company_name=inputs["company_name"],
            report_label="Live Smoke Indicative Valuation Report",
            report_type="valuation_advisory",
            valuation_purpose="Understand what the business may be worth",
            sections=content_json,
            section_order=SECTION_SCHEMAS["valuation_advisory"],
            section_titles=_REPORT_SECTION_TITLES,
            report_id=9901,
            generated_at=prepared_at,
            demo_mode=False,
            intake_answers=inputs["intake_answers"],
        )
        pdf_audit = audit_valuation_report_pdf(output_pdf, demo_mode=False)
        if not pdf_audit.passed:
            raise RuntimeError(
                "Live valuation PDF failed professional artifact audit: "
                f"{[issue.as_dict() for issue in pdf_audit.issues]}"
            )
        pdf_path = str(output_pdf)
        pdf_audit_dict = pdf_audit.as_dict()

    return {
        "status": "passed",
        "model": model,
        "preflight_fresh": preflight_fresh,
        "json_path": str(output_json),
        "html_path": html_path,
        "pdf_path": pdf_path,
        "sections": len(content_json),
        "content_audit": content_audit.as_dict(),
        "html_audit": html_audit_dict,
        "pdf_audit": pdf_audit_dict,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a live AccountIQ valuation-report smoke test.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_JSON_OUTPUT,
        help=f"Validated JSON output path. Default: {DEFAULT_JSON_OUTPUT}",
    )
    parser.add_argument(
        "--output-html",
        type=Path,
        default=DEFAULT_HTML_OUTPUT,
        help=f"Validated browser HTML output path. Default: {DEFAULT_HTML_OUTPUT}",
    )
    parser.add_argument(
        "--skip-html",
        action="store_true",
        help="Do not render a browser HTML artifact.",
    )
    parser.add_argument(
        "--output-pdf",
        type=Path,
        default=DEFAULT_PDF_OUTPUT,
        help=f"Validated PDF output path. Default: {DEFAULT_PDF_OUTPUT}",
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Validate live JSON only and do not render a PDF artifact.",
    )
    parser.add_argument(
        "--prepared-at",
        default=DEFAULT_PREPARED_AT,
        help=f"Prepared timestamp for the smoke artifact. Default: {DEFAULT_PREPARED_AT}",
    )
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    result = await run_live_valuation_smoke(
        output_json=args.output_json,
        output_html=None if args.skip_html else args.output_html,
        output_pdf=None if args.skip_pdf else args.output_pdf,
        prepared_at=args.prepared_at,
    )
    print(json.dumps(result, indent=2))
    return 0


def main() -> int:
    try:
        return asyncio.run(async_main())
    except Exception as exc:
        print(f"Live valuation smoke failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
