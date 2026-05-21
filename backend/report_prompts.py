"""
Report section schemas and Claude prompt builders for all 5 AccountIQ report types.

SECTION_SCHEMAS: stable section key lists used by generate_report() and Phase 7 templates.
build_prompt(): returns (system_prompt, user_message) tuple for Claude messages.create().
compute_bank_credit_figures(): deterministic DSCR and sensitivity computations (D-09).
"""
from __future__ import annotations

import json
from typing import Optional

# ---------------------------------------------------------------------------
# Section schemas (D-10) — stable keys used by generate_report() + Phase 7 Jinja2
# ---------------------------------------------------------------------------

SECTION_SCHEMAS: dict[str, list[str]] = {
    "valuation_advisory": [
        "executive_summary",
        "business_overview",
        "financial_analysis",
        "valuation_methodology",
        "dcf_analysis",
        "multiples_analysis",
        "concluded_value",
        "disclaimer",
    ],
    "bank_credit_paper": [
        "executive_summary",
        "borrower_overview",
        "financial_analysis",
        "dscr_analysis",
        "sensitivity_analysis",
        "risk_assessment",
        "disclaimer",
    ],
    "financial_forecast": [
        "executive_summary",
        "historical_performance",
        "key_assumptions",
        "base_scenario",
        "bull_scenario",
        "bear_scenario",
        "disclaimer",
    ],
    "capital_raising": [
        "executive_summary",
        "investment_thesis",
        "business_overview",
        "financial_performance",
        "use_of_funds",
        "management_team",
        "disclaimer",
    ],
    "information_memorandum": [
        "executive_summary",
        "business_overview",
        "products_and_services",
        "operations",
        "management_team",
        "financial_performance",
        "financial_projections",
        "growth_opportunities",
        "transaction_structure",
        "disclaimer",
    ],
}

# ---------------------------------------------------------------------------
# Disclaimer requirement (REPT-06) — injected into every prompt
# ---------------------------------------------------------------------------

_DISCLAIMER_INSTRUCTION = (
    "IMPORTANT COMPLIANCE REQUIREMENT (REPT-06): "
    "Every section you write MUST end with the following disclaimer sentence: "
    "'This report is indicative only and does not constitute financial advice. "
    "Readers should seek independent professional advice before making any financial decision.' "
    "The 'disclaimer' section should contain only this disclaimer text, expanded to a full paragraph."
)

_SYSTEM_BASE = (
    "You are a professional financial report writer producing first-draft reports for New Zealand and "
    "Australian SMEs. Write in clear, professional business English. Be specific and data-driven — "
    "reference the exact numbers provided. Do not invent numbers or assumptions not given to you. "
    "Return your response as a single valid JSON object where each key is a section name and the value "
    "is the section content as a plain string (no nested objects, no markdown code fences). "
    "\n\n"
    + _DISCLAIMER_INSTRUCTION
)


# ---------------------------------------------------------------------------
# Helper: format financial rows for prompt context
# ---------------------------------------------------------------------------

def _format_financials(financial_rows: list[dict]) -> str:
    """Group financial_rows by statement type and format as a readable table."""
    by_type: dict[str, list] = {}
    for row in financial_rows:
        st = row.get("statement", "pnl")
        by_type.setdefault(st, []).append(row)

    lines = []
    stmt_labels = {"pnl": "P&L / Income Statement", "bs": "Balance Sheet",
                   "cf": "Cash Flow Statement", "eq": "Statement of Changes in Equity"}
    for st in ("pnl", "bs", "cf", "eq"):
        if st not in by_type:
            continue
        lines.append(f"\n### {stmt_labels.get(st, st.upper())}")
        for row in by_type[st]:
            vals = row.get("values", {})
            if isinstance(vals, dict):
                vals_str = "; ".join(
                    f"{yr}: {v:,.0f}" for yr, v in sorted(vals.items()) if v is not None
                )
            else:
                vals_str = str(vals)
            key = row.get("canonical_key") or row.get("row_key", "?")
            lines.append(f"  {key}: {vals_str}")

    return "\n".join(lines) if lines else "No financial data extracted."


# ---------------------------------------------------------------------------
# Bank Credit Paper: compute DSCR and sensitivity (D-09)
# ---------------------------------------------------------------------------

def compute_bank_credit_figures(
    financial_rows: list[dict],
    intake_answers: dict,
) -> dict:
    """
    Deterministic computations for Bank Credit Paper (D-09):
    - DSCR for up to 3 fiscal years from financial_rows
    - 3-year financial trend table (revenue, EBITDA, net profit)
    - Sensitivity at -10% and -20% revenue on DSCR

    DSCR = EBITDA / (annual_interest + scheduled_principal_repayment)
    Scheduled principal = proposed_facility_amount / proposed_term_years (from intake).
    """
    amount = float(intake_answers.get("amount_requested", 0) or 0)
    term = float(intake_answers.get("proposed_term_years", 1) or 1)
    annual_principal = amount / term if term > 0 else 0.0

    def _get_values(rows: list[dict], key: str, statement: str = "pnl") -> dict:
        """Return the period->value dict for a given row key and statement type."""
        for r in rows:
            canonical = r.get("canonical_key") or r.get("row_key", "")
            if canonical == key and r.get("statement") == statement:
                vals = r.get("values", {})
                if isinstance(vals, dict):
                    return vals
                # Handle financial_rows from main.py format (period/value columns)
                return {}
        return {}

    ebitda_vals = _get_values(financial_rows, "ebitda")
    interest_vals = _get_values(financial_rows, "interest_expense")
    revenue_vals = _get_values(financial_rows, "revenue")
    net_profit_vals = _get_values(financial_rows, "net_profit")

    years = sorted(ebitda_vals.keys())[-3:] if ebitda_vals else []

    dscr_table: dict[str, Optional[float]] = {}
    for yr in years:
        ebitda = abs(float(ebitda_vals.get(yr) or 0))
        interest = abs(float(interest_vals.get(yr) or 0))
        scheduled = annual_principal + interest
        dscr_table[yr] = round(ebitda / scheduled, 2) if scheduled > 0 else None

    trend_table: dict[str, dict] = {}
    for yr in years:
        trend_table[yr] = {
            "revenue": revenue_vals.get(yr),
            "ebitda": ebitda_vals.get(yr),
            "net_profit": net_profit_vals.get(yr),
        }

    # Sensitivity: -10% and -20% on most recent year DSCR
    last_yr = years[-1] if years else None
    last_ebitda = abs(float(ebitda_vals.get(last_yr) or 0)) if last_yr else 0.0
    last_interest = abs(float(interest_vals.get(last_yr) or 0)) if last_yr else 0.0
    scheduled_last = annual_principal + last_interest

    sensitivity: dict[str, Optional[float]] = {}
    for pct, label in [(-0.10, "minus_10pct"), (-0.20, "minus_20pct")]:
        stressed_ebitda = last_ebitda * (1 + pct)
        sensitivity[label] = (
            round(stressed_ebitda / scheduled_last, 2) if scheduled_last > 0 else None
        )

    return {
        "dscr_table": dscr_table,
        "trend_table": trend_table,
        "sensitivity": sensitivity,
        "annual_principal": annual_principal,
    }


# ---------------------------------------------------------------------------
# Prompt builders — one per report type
# ---------------------------------------------------------------------------

def build_prompt(
    report_type: str,
    company_name: str,
    industry: str,
    description: str,
    financial_rows: list[dict],
    intake_answers: dict,
    management_team: list[dict],
    ebitda_adjustments: list[dict],
    valuation_result: Optional[dict] = None,
    bank_credit_figures: Optional[dict] = None,
) -> tuple[str, str]:
    """
    Build the (system_prompt, user_message) tuple for Claude messages.create().

    report_type must be a key in SECTION_SCHEMAS.
    valuation_result: output of compute_valuation() — required for valuation_advisory.
    bank_credit_figures: output of compute_bank_credit_figures() — required for bank_credit_paper.

    REPT-06 disclaimer language is injected via _SYSTEM_BASE into every prompt.
    """
    if report_type not in SECTION_SCHEMAS:
        raise ValueError(
            f"Unknown report type: '{report_type}'. "
            f"Valid types: {list(SECTION_SCHEMAS)}"
        )

    sections = SECTION_SCHEMAS[report_type]
    sections_spec = json.dumps(sections)
    sections_instruction = (
        f"Return a JSON object with exactly these keys (in this order): {sections_spec}. "
        "Each value must be a non-empty string containing the section content. "
        "Do not include any keys not in this list. No nested objects or arrays."
    )

    system_prompt = _SYSTEM_BASE + "\n\n" + sections_instruction

    financials_text = _format_financials(financial_rows)

    mgmt_text = (
        "\n".join(
            f"- {m.get('name', '?')} ({m.get('title', 'N/A')}): {m.get('bio', '')}"
            for m in management_team
        )
        or "Not provided."
    )

    ebitda_text = (
        "\n".join(
            f"- {a.get('label', '?')}: ${float(a.get('amount', 0)):,.0f}"
            + (f" — {a['rationale']}" if a.get("rationale") else "")
            for a in ebitda_adjustments
        )
        or "No add-backs provided."
    )

    intake_text = "\n".join(f"- {k}: {v}" for k, v in intake_answers.items())

    # Report-type-specific user messages
    if report_type == "valuation_advisory":
        if valuation_result is None:
            raise ValueError("valuation_result is required for valuation_advisory report type")
        user_message = f"""Generate a Valuation Advisory report for {company_name}.

## Company Information
- Name: {company_name}
- Industry: {industry or 'Not specified'}
- Business Description: {description or 'Not provided'}

## Extracted Financials
{financials_text}

## EBITDA Add-backs (Normalisation)
{ebitda_text}

## Management Team
{mgmt_text}

## Valuation Algorithm Outputs (Python-computed — DO NOT change these numbers)
{json.dumps(valuation_result, indent=2)}

## Questionnaire Inputs
{intake_text}

Write the Valuation Advisory report. The concluded_value section must reference the low/mid/high range from the algorithm outputs verbatim. The dcf_analysis and multiples_analysis sections must explain the respective methodologies using the inputs provided — do not recalculate or modify any numbers. This report is indicative only and does not constitute financial advice."""

    elif report_type == "bank_credit_paper":
        if bank_credit_figures is None:
            raise ValueError("bank_credit_figures is required for bank_credit_paper report type")
        user_message = f"""Generate a Bank Credit Paper for {company_name}.

## Company Information
- Name: {company_name}
- Industry: {industry or 'Not specified'}
- Business Description: {description or 'Not provided'}

## Extracted Financials
{financials_text}

## Proposed Facility Details (User-supplied)
{intake_text}

## Python-Computed Credit Figures (DO NOT change these numbers)
DSCR by year: {json.dumps(bank_credit_figures['dscr_table'])}
3-year financial trend: {json.dumps(bank_credit_figures['trend_table'])}
DSCR sensitivity (-10% / -20% revenue): {json.dumps(bank_credit_figures['sensitivity'])}
Annual principal repayment: ${bank_credit_figures['annual_principal']:,.0f}

Write the Bank Credit Paper. The dscr_analysis section must include the DSCR table, the trend table, and the sensitivity table using the Python-computed figures verbatim. The sensitivity_analysis section must explain the stress scenarios. All figures are indicative only and do not constitute financial advice."""

    elif report_type == "financial_forecast":
        user_message = f"""Generate a Financial Forecast report for {company_name}.

## Company Information
- Name: {company_name}
- Industry: {industry or 'Not specified'}
- Business Description: {description or 'Not provided'}

## Historical Extracted Financials (most recent years where available)
{financials_text}

## Forecast Inputs (User-supplied — use these assumptions exactly as stated)
{intake_text}

Write the Financial Forecast. The key_assumptions section must list every user-supplied input verbatim. The base_scenario must use the stated growth rate. The bull_scenario must use the stated growth rate plus 5 percentage points. The bear_scenario must use the stated growth rate minus 5 percentage points. All projection figures must be derived from the historical financials and stated assumptions — do not invent base figures. All projections are forward-looking estimates and indicative only."""

    elif report_type == "capital_raising":
        user_message = f"""Generate a Capital Raising Document for {company_name}.

## Company Information
- Name: {company_name}
- Industry: {industry or 'Not specified'}
- Business Description: {description or 'Not provided'}

## Extracted Financials
{financials_text}

## Capital Raise Details (User-supplied)
{intake_text}

## Management Team
{mgmt_text}

Write the Capital Raising Document. The use_of_funds section must itemise every use of proceeds from the intake answers. The management_team section must draw from the profile data above. All financial projections must be clearly labelled as forward-looking estimates and indicative only."""

    elif report_type == "information_memorandum":
        user_message = f"""Generate an Information Memorandum for {company_name}.

## Company Information
- Name: {company_name}
- Industry: {industry or 'Not specified'}
- Business Description: {description or 'Not provided'}

## Extracted Financials
{financials_text}

## EBITDA Add-backs
{ebitda_text}

## Management Team
{mgmt_text}

## Sale / Transaction Details (User-supplied)
{intake_text}

Write the Information Memorandum with all 10 standard sections. Every section must contain company-specific content — no generic placeholders. The management_team section must draw from the profile data above. The transaction_structure section must reference the user's stated preferences. The growth_opportunities section must include the user's stated opportunities verbatim. Risk factors must be balanced — identify both genuine risks and mitigating factors. This report is indicative only and does not constitute financial advice."""

    else:
        # Should never reach here due to guard at top of function
        raise ValueError(f"Unhandled report type: {report_type}")

    return system_prompt, user_message
