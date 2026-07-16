"""
Report section schemas and Claude prompt builders for all 5 AccountIQ report types.

SECTION_SCHEMAS: stable section key lists used by generate_report() and Phase 7 templates.
build_prompt(): returns (system_prompt, user_message) tuple for Claude messages.create().
compute_bank_credit_figures(): deterministic DSCR and sensitivity computations (D-09).
"""
from __future__ import annotations

import json
import math
from typing import Optional

from valuation import (
    growth_assumption_source_label,
    report_answer_label,
    working_capital_source_label,
)

# ---------------------------------------------------------------------------
# Section schemas (D-10) — stable keys used by generate_report() + Phase 7 Jinja2
# ---------------------------------------------------------------------------

TABLE_SECTIONS_VALUATION = [
    "executive_summary",
    "financial_performance",
    "financial_ratio_analysis",
    "normalisations_schedule",
    "balance_sheet_summary",
    "valuation_assumptions",
    "wacc_assumptions",
    "dcf_analysis",
    "valuation_summary",
    "multiples_crosscheck",
    "sensitivity_and_risks",
    "comparable_evidence",
    "sources",
]

TABLE_SECTIONS_BANK_CREDIT = [
    "executive_summary",
    "transaction_summary",
    "sources_and_uses",
    "facilities_requested",
    "security_package",
    "financial_performance_forecast",
    "coverage_and_sensitivity",
    "balance_sheet_debt_capacity",
    "proposed_covenants",
    "key_risks_and_mitigants",
    "conditions_precedent",
    "recommendation",
]

VALUATION_TABLE_SCHEDULE_KEYS = {
    "executive_summary": "executive_summary_table",
    "financial_performance": "financial_performance_table",
    "financial_ratio_analysis": "financial_ratio_table",
    "normalisations_schedule": "normalisation_schedule",
    "balance_sheet_summary": "balance_sheet_summary_table",
    "valuation_assumptions": "assumption_source_trail",
    "wacc_assumptions": "wacc_assumptions_table",
    "dcf_analysis": "dcf_analysis_table",
    "valuation_summary": "valuation_summary_table",
    "multiples_crosscheck": "multiples_crosscheck_table",
    "sensitivity_and_risks": "sensitivity_table",
    "comparable_evidence": "comparable_evidence_table",
    "sources": "sources_table",
}

VALUATION_REQUIRED_SUBTABLE_SCHEDULE_KEYS = {
    "dcf_analysis.cash_flow_schedule": "forecast_cash_flow_schedule",
    "sensitivity_and_risks.specific_risk_factors": "specific_risk_factors",
}

SECTION_SCHEMAS: dict[str, list[str]] = {
    "valuation_advisory": [
        "introduction",
        "executive_summary",
        "business_overview",
        "market_position",
        "about_business_valuations",
        "valuation_methodology",
        "financial_performance",
        "financial_ratio_analysis",
        "normalisations_schedule",
        "balance_sheet_summary",
        "valuation_assumptions",
        "wacc_assumptions",
        "dcf_analysis",
        "valuation_summary",
        "multiples_crosscheck",
        "sensitivity_and_risks",
        "comparable_evidence",
        "sources",
        "disclaimer",
        "general_principles",
        "glossary",
    ],
    "bank_credit_paper": [
        "executive_summary",
        "transaction_summary",
        "sources_and_uses",
        "borrower_and_sponsor_profile",
        "facilities_requested",
        "security_package",
        "financial_performance_forecast",
        "coverage_and_sensitivity",
        "balance_sheet_debt_capacity",
        "industry_and_competitive_landscape",
        "proposed_covenants",
        "key_risks_and_mitigants",
        "conditions_precedent",
        "recommendation",
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

BANK_CREDIT_COVENANT_PACKAGE_LABELS = {
    "light_touch": "Light touch",
    "balanced": "Balanced",
    "more_control": "More protective",
}

BANK_CREDIT_COVENANT_DEFINITIONS = {
    "min_dscr": "Minimum DSCR",
    "min_interest_cover": "Minimum interest cover",
    "max_senior_leverage": "Maximum senior leverage",
    "liquidity_minimum": "Minimum liquidity",
    "no_additional_debt": "No additional debt",
    "distribution_lockup": "Distribution lock-up",
    "capex_controls": "Capex / asset-disposal controls",
    "information_reporting": "Information reporting",
    "collateral_reporting": "Collateral reporting",
    "borrowing_base_reporting": "Borrowing-base reporting",
}

BANK_CREDIT_COVENANT_PACKAGE_DEFAULTS = {
    "light_touch": [
        "min_dscr",
        "max_senior_leverage",
        "information_reporting",
    ],
    "balanced": [
        "min_dscr",
        "min_interest_cover",
        "max_senior_leverage",
        "distribution_lockup",
        "information_reporting",
        "collateral_reporting",
    ],
    "more_control": [
        "min_dscr",
        "min_interest_cover",
        "max_senior_leverage",
        "liquidity_minimum",
        "no_additional_debt",
        "distribution_lockup",
        "capex_controls",
        "information_reporting",
        "collateral_reporting",
        "borrowing_base_reporting",
    ],
}

# ---------------------------------------------------------------------------
# Disclaimer requirement (REPT-06) — injected into every prompt
# ---------------------------------------------------------------------------

_DISCLAIMER_INSTRUCTION = (
    "IMPORTANT COMPLIANCE REQUIREMENT (REPT-06): "
    "The dedicated 'disclaimer' section must state that the report is indicative only, "
    "does not constitute financial advice, should not be relied on as a substitute for "
    "independent professional advice, and is subject to the Financial Markets Conduct Act "
    "(FMCA). Do not repeat disclaimer wording at the end of every other section."
)

_SYSTEM_BASE = (
    "You are a professional financial report writer producing completed professional reports for New Zealand and "
    "Australian SMEs. Write in clear, professional business English. Be specific and data-driven — "
    "reference the exact numbers provided. Do not invent numbers or assumptions not given to you. "
    "Return your response as a single valid JSON object using the exact section schema supplied below. "
    "Do not use markdown code fences around the JSON. "
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


def _require_valuation_table_schedules(valuation_result: dict) -> None:
    """Require every valuation table section to have an AccountIQ-calculated schedule."""
    missing: list[str] = []
    for section, schedule_key in VALUATION_TABLE_SCHEDULE_KEYS.items():
        table = valuation_result.get(schedule_key)
        rows = table.get("rows") if isinstance(table, dict) else None
        headers = table.get("headers") if isinstance(table, dict) else None
        if not isinstance(headers, list) or not isinstance(rows, list) or not rows:
            missing.append(f"{section}->{schedule_key}")

    for section, schedule_key in VALUATION_REQUIRED_SUBTABLE_SCHEDULE_KEYS.items():
        table = valuation_result.get(schedule_key)
        rows = table.get("rows") if isinstance(table, dict) else None
        headers = table.get("headers") if isinstance(table, dict) else None
        if not isinstance(headers, list) or not isinstance(rows, list) or not rows:
            missing.append(f"{section}->{schedule_key}")

    if missing:
        raise ValueError(
            "valuation_result is missing required AccountIQ-calculated valuation table schedules: "
            + ", ".join(missing)
        )


_VALUATION_INTAKE_FIELD_LABELS = {
    "valuation_purpose": "Valuation purpose",
    "owner_dependency": "Owner or key-person dependency",
    "customer_concentration": "Largest-customer concentration",
    "revenue_quality": "Revenue predictability",
    "revenue_outlook": "Revenue outlook",
    "private_context": "Other private context",
    "debt_override": "Interest-bearing debt override",
    "surplus_assets": "Surplus or non-operating assets",
    "replacement_manager_cost": "Replacement manager cost",
    "custom_growth_rate": "Specific supported annual revenue growth",
}

_VALUATION_OWNER_LABEL_FIELDS = {
    "valuation_purpose",
    "owner_dependency",
    "customer_concentration",
    "revenue_quality",
    "revenue_outlook",
}

_VALUATION_PRIVATE_INTAKE_FIELDS = (
    "valuation_purpose",
    "owner_dependency",
    "customer_concentration",
    "revenue_quality",
    "revenue_outlook",
    "private_context",
)

_VALUATION_OPTIONAL_EXPERT_FIELDS = {
    "debt_override",
    "surplus_assets",
    "replacement_manager_cost",
    "custom_growth_rate",
}


def _format_valuation_private_intake(intake_answers: dict) -> str:
    """Format valuation intake for the live prompt using report-ready labels."""
    lines: list[str] = []
    intake_answers = intake_answers or {}
    for key in _VALUATION_PRIVATE_INTAKE_FIELDS:
        value = intake_answers.get(key)
        if value in (None, ""):
            continue
        field_label = _VALUATION_INTAKE_FIELD_LABELS.get(key, key.replace("_", " ").title())
        if key in _VALUATION_OWNER_LABEL_FIELDS:
            display_value = report_answer_label(key, str(value))
        else:
            display_value = str(value).strip()
        lines.append(f"- {field_label}: {display_value}")
    return "\n".join(lines) or "Not provided."


def _format_valuation_optional_expert_overrides(intake_answers: dict) -> str:
    """Format collapsed advanced valuation inputs separately from private facts."""
    lines: list[str] = []
    for key in (
        "replacement_manager_cost",
        "debt_override",
        "surplus_assets",
        "custom_growth_rate",
    ):
        value = (intake_answers or {}).get(key)
        if value in (None, ""):
            continue
        field_label = _VALUATION_INTAKE_FIELD_LABELS.get(key, key.replace("_", " ").title())
        lines.append(f"- {field_label}: {str(value).strip()}")
    return "\n".join(lines) or "Not provided."


# ---------------------------------------------------------------------------
# Bank Credit Paper: compute DSCR and sensitivity (D-09)
# ---------------------------------------------------------------------------

def normalise_bank_credit_covenant_selection(intake_answers: dict | None) -> dict:
    """Return a safe covenant package and ordered covenant key selection."""
    intake_answers = intake_answers or {}
    package_level = str(intake_answers.get("covenant_package_level") or "balanced").strip()
    if package_level not in BANK_CREDIT_COVENANT_PACKAGE_DEFAULTS:
        package_level = "balanced"

    raw_selection = intake_answers.get("selected_covenants")
    selected: list[str] = []
    if isinstance(raw_selection, str):
        selected = [
            item.strip()
            for item in raw_selection.replace("\n", ",").split(",")
            if item.strip()
        ]
    elif isinstance(raw_selection, (list, tuple, set)):
        selected = [str(item).strip() for item in raw_selection if str(item).strip()]

    if selected:
        selected = [
            key
            for key in BANK_CREDIT_COVENANT_DEFINITIONS
            if key in selected
        ]
    else:
        selected = list(BANK_CREDIT_COVENANT_PACKAGE_DEFAULTS[package_level])

    if not selected:
        selected = list(BANK_CREDIT_COVENANT_PACKAGE_DEFAULTS["balanced"])

    raw_notes = str(intake_answers.get("covenant_package_notes") or "").strip()
    notes = " ".join(raw_notes.split())

    return {
        "level": package_level,
        "label": BANK_CREDIT_COVENANT_PACKAGE_LABELS.get(package_level, "Balanced"),
        "selected_keys": selected,
        "selected_labels": [BANK_CREDIT_COVENANT_DEFINITIONS[key] for key in selected],
        "notes": notes,
    }


def _build_bank_credit_covenants_table(
    selected_covenants: list[str],
    *,
    min_dscr: float,
    min_icr: float,
    max_leverage: float,
    lvr_pct: float,
) -> dict:
    """Build the proposed-covenant table from user-selected covenant keys."""
    rows_by_key = {
        "min_dscr": [
            "Minimum DSCR",
            f">= {min_dscr:.2f}x",
            "Test quarterly on trailing 12-month lender EBITDA / cash interest plus scheduled principal.",
            "Protects principal and interest serviceability.",
        ],
        "min_interest_cover": [
            "Minimum interest cover",
            f">= {min_icr:.2f}x",
            "Test lender EBITDA / cash interest; base and rate-stress cases are shown in the coverage table.",
            "Protects rate-risk headroom where interest cost moves against the borrower.",
        ],
        "max_senior_leverage": [
            "Maximum senior leverage",
            f"<= {max_leverage:.2f}x",
            "Debt / latest uploaded EBITDA until formal lender EBITDA and permitted adjustments are agreed.",
            "Constrains over-leverage and keeps debt sized to maintainable cash earnings.",
        ],
        "liquidity_minimum": [
            "Minimum liquidity",
            "To be agreed with lender",
            "Set as a minimum cash / undrawn headroom test once seasonality and working-capital needs are confirmed.",
            "Gives early warning where cash conversion weakens before a payment default.",
        ],
        "no_additional_debt": [
            "No additional debt",
            "No new financial indebtedness without lender consent",
            "Permit ordinary-course trade creditors but restrict new loans, leases, asset finance or subordinated debt.",
            "Prevents security dilution, hidden leverage and cash-flow leakage.",
        ],
        "distribution_lockup": [
            "Distribution lock-up",
            f"Lock-up if DSCR < {max(min_dscr + 0.10, 1.50):.2f}x",
            "Permit debt-service distributions but restrict discretionary dividends, drawings or shareholder repayments while stressed.",
            "Preserves cash for the lender when coverage headroom narrows.",
        ],
        "capex_controls": [
            "Capex / asset-disposal controls",
            "Outside approved budget requires lender consent",
            "Set annual capex and disposal permissions after fleet, plant or property schedules are reviewed.",
            "Protects collateral quality and prevents cash drain from unfunded growth.",
        ],
        "information_reporting": [
            "Information reporting",
            "Monthly management accounts; annual accounts; compliance certificate",
            "Timing, template and officer certification to be agreed with the bank.",
            "Lets the lender monitor trading, covenant headroom and early-warning indicators.",
        ],
        "collateral_reporting": [
            "Collateral reporting",
            "AR/AP/stock aging, fleet/property valuation and insurance schedule where relevant",
            "Required where receivables, stock, fixed assets, fleet or property support the lend.",
            "Confirms borrowing-base support, security value and insurance coverage.",
        ],
        "borrowing_base_reporting": [
            "Borrowing-base reporting",
            f"Eligibility and advance rates to be agreed; target LVR / advance-rate input is {lvr_pct:.1f}%" if lvr_pct else "Eligibility and advance rates to be agreed",
            "Use receivables, stock and fixed-asset schedules to reconcile eligible collateral against outstanding debt.",
            "Helps right-size working-capital or asset-backed facilities as collateral moves.",
        ],
    }
    return {
        "headers": ["Covenant / control", "Proposed threshold or requirement", "Mechanics / headroom", "Why it matters"],
        "rows": [
            rows_by_key[key]
            for key in selected_covenants
            if key in rows_by_key
        ],
    }


def compute_bank_credit_figures(
    financial_rows: list[dict],
    intake_answers: dict,
) -> dict:
    """
    Deterministic computations for Bank Credit Paper:
    - DSCR/ICR for up to 3 fiscal years from uploaded financial rows
    - 3-year financial trend table (revenue, EBITDA, net profit)
    - Rate and EBITDA downside sensitivity
    - Balance-sheet strength and NTOA view
    - Debt-capacity constraints using leverage, coverage, collateral/LVR and NTOA

    The language model may explain these figures, but must not recalculate them.
    """
    intake_answers = intake_answers or {}

    def _answer_number(key: str, default: float = 0.0) -> float:
        value = intake_answers.get(key, default)
        try:
            return float(value or default)
        except (TypeError, ValueError):
            return default

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

    def _first_values(statement: str, *keys: str) -> dict:
        for key in keys:
            values = _get_values(financial_rows, key, statement)
            if values:
                return values
        return {}

    def _latest(values: dict) -> float:
        if not values:
            return 0.0
        latest_period = sorted(values.keys())[-1]
        try:
            return float(values.get(latest_period) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _latest_for(statement: str, *keys: str) -> float:
        return _latest(_first_values(statement, *keys))

    def _fmt_amount(value: float | None) -> str:
        if value is None:
            return "Not available"
        return f"${value:,.0f}"

    def _fmt_ratio(value: float | None, suffix: str = "x") -> str:
        if value is None:
            return "N/M"
        return f"{value:.2f}{suffix}"

    def _fmt_percent(value: float | None) -> str:
        if value is None:
            return "Not available"
        return f"{value:.1f}%"

    def _answer_text(key: str, default: str = "Not provided") -> str:
        value = intake_answers.get(key)
        if value in (None, ""):
            return default
        return str(value).strip()

    def _friendly_choice(value: object) -> str:
        text = str(value or "").strip()
        return text.replace("_", " ") if text else "Not provided"

    amount = _answer_number("amount_requested")
    term = _answer_number("proposed_term_years", 1.0)
    if term <= 0:
        term = 1.0
    funding_cost_pct = _answer_number("conservative_funding_cost_pct", _answer_number("interest_rate", 0.0))
    funding_rate = funding_cost_pct / 100.0 if funding_cost_pct else 0.0
    lvr_pct = _answer_number("lvr_percent", 0.0)
    lvr_rate = lvr_pct / 100.0 if lvr_pct else 0.0
    security_value = _answer_number("security_value", 0.0)
    repayment_profile = str(intake_answers.get("repayment_profile") or "principal_and_interest")
    amortising = repayment_profile != "interest_only"
    annual_principal = amount / term if amount > 0 and amortising else 0.0
    annual_interest = amount * funding_rate if amount > 0 and funding_rate > 0 else 0.0
    annual_debt_service = annual_interest + annual_principal
    min_dscr = _answer_number("minimum_dscr", 1.40) or 1.40
    min_icr = _answer_number("minimum_interest_cover", 3.00) or 3.00
    max_leverage = _answer_number("maximum_senior_leverage", 2.50) or 2.50
    covenant_package = normalise_bank_credit_covenant_selection(intake_answers)
    transaction_value = _answer_number("transaction_value", _answer_number("purchase_price", 0.0))
    refinance_amount = _answer_number("refinance_amount", _answer_number("existing_debt_to_refinance", 0.0))
    transaction_costs = _answer_number("transaction_costs", _answer_number("transaction_fees", 0.0))
    working_capital_buffer = _answer_number("working_capital_buffer", 0.0)
    equity_contribution = _answer_number("equity_contribution", 0.0)
    sponsor_bridge_amount = _answer_number("sponsor_bridge_amount", 0.0)
    sponsor_bridge_term_months = _answer_number("sponsor_bridge_term_months", 0.0)

    ebitda_vals = _get_values(financial_rows, "ebitda")
    interest_vals = _get_values(financial_rows, "interest_expense")
    revenue_vals = _get_values(financial_rows, "revenue")
    net_profit_vals = _get_values(financial_rows, "net_profit")
    depreciation_vals = _first_values("pnl", "depreciation_amortisation", "depreciation")

    years = sorted(set(revenue_vals) | set(ebitda_vals) | set(net_profit_vals))[-3:]

    dscr_table: dict[str, Optional[float]] = {}
    for yr in years:
        ebitda = abs(float(ebitda_vals.get(yr) or 0))
        if ebitda == 0:
            ebitda = (
                float(net_profit_vals.get(yr) or 0)
                + abs(float(interest_vals.get(yr) or 0))
                + abs(float(depreciation_vals.get(yr) or 0))
            )
        scheduled = annual_debt_service
        dscr_table[yr] = round(ebitda / scheduled, 2) if scheduled > 0 else None

    trend_table: dict[str, dict] = {}
    financial_trend_rows: list[list[str]] = []
    for yr in years:
        revenue_value = revenue_vals.get(yr)
        ebitda_value = ebitda_vals.get(yr)
        net_profit_value = net_profit_vals.get(yr)
        trend_table[yr] = {
            "revenue": revenue_value,
            "ebitda": ebitda_value,
            "net_profit": net_profit_value,
        }
        ebitda_margin = (
            float(ebitda_value) / float(revenue_value) * 100.0
            if revenue_value not in (None, 0) and ebitda_value is not None
            else None
        )
        financial_trend_rows.append([
            str(yr),
            _fmt_amount(float(revenue_value)) if revenue_value is not None else "Not available",
            _fmt_amount(float(ebitda_value)) if ebitda_value is not None else "Not available",
            _fmt_amount(float(net_profit_value)) if net_profit_value is not None else "Not available",
            _fmt_percent(ebitda_margin),
        ])
    financial_trend_table = {
        "headers": ["Period", "Revenue", "EBITDA", "Net profit", "EBITDA margin"],
        "rows": financial_trend_rows,
    }

    # Sensitivity: EBITDA downside and funding-cost stress on the most recent year.
    last_yr = years[-1] if years else None
    last_ebitda = abs(float(ebitda_vals.get(last_yr) or 0)) if last_yr else 0.0
    if last_ebitda == 0 and last_yr:
        last_ebitda = (
            float(net_profit_vals.get(last_yr) or 0)
            + abs(float(interest_vals.get(last_yr) or 0))
            + abs(float(depreciation_vals.get(last_yr) or 0))
        )
    last_interest = abs(float(interest_vals.get(last_yr) or 0)) if last_yr else 0.0

    sensitivity: dict[str, Optional[float]] = {}
    for pct, label in [(-0.10, "minus_10pct"), (-0.20, "minus_20pct")]:
        stressed_ebitda = last_ebitda * (1 + pct)
        sensitivity[label] = round(stressed_ebitda / annual_debt_service, 2) if annual_debt_service > 0 else None

    rate_stress_pct = funding_cost_pct + 1.50 if funding_cost_pct else 0.0
    rate_stress_interest = amount * (rate_stress_pct / 100.0) if amount > 0 and rate_stress_pct else 0.0
    rate_stress_service = rate_stress_interest + annual_principal
    coverage_table = [
        {
            "case": "Base case",
            "ebitda": _fmt_amount(last_ebitda),
            "funding_cost": f"{funding_cost_pct:.2f}%" if funding_cost_pct else "Not provided",
            "cash_interest": _fmt_amount(annual_interest),
            "annual_principal": _fmt_amount(annual_principal),
            "dscr": _fmt_ratio(round(last_ebitda / annual_debt_service, 2) if annual_debt_service > 0 else None),
            "icr": _fmt_ratio(round(last_ebitda / annual_interest, 2) if annual_interest > 0 else None),
        },
        {
            "case": "Rate stress +1.50%",
            "ebitda": _fmt_amount(last_ebitda),
            "funding_cost": f"{rate_stress_pct:.2f}%" if rate_stress_pct else "Not provided",
            "cash_interest": _fmt_amount(rate_stress_interest),
            "annual_principal": _fmt_amount(annual_principal),
            "dscr": _fmt_ratio(round(last_ebitda / rate_stress_service, 2) if rate_stress_service > 0 else None),
            "icr": _fmt_ratio(round(last_ebitda / rate_stress_interest, 2) if rate_stress_interest > 0 else None),
        },
        {
            "case": "EBITDA downside -10%",
            "ebitda": _fmt_amount(last_ebitda * 0.90),
            "funding_cost": f"{funding_cost_pct:.2f}%" if funding_cost_pct else "Not provided",
            "cash_interest": _fmt_amount(annual_interest),
            "annual_principal": _fmt_amount(annual_principal),
            "dscr": _fmt_ratio(sensitivity["minus_10pct"]),
            "icr": _fmt_ratio(round((last_ebitda * 0.90) / annual_interest, 2) if annual_interest > 0 else None),
        },
        {
            "case": "EBITDA downside -20%",
            "ebitda": _fmt_amount(last_ebitda * 0.80),
            "funding_cost": f"{funding_cost_pct:.2f}%" if funding_cost_pct else "Not provided",
            "cash_interest": _fmt_amount(annual_interest),
            "annual_principal": _fmt_amount(annual_principal),
            "dscr": _fmt_ratio(sensitivity["minus_20pct"]),
            "icr": _fmt_ratio(round((last_ebitda * 0.80) / annual_interest, 2) if annual_interest > 0 else None),
        },
    ]

    cash = abs(_latest_for("bs", "cash_and_bank", "cash_and_equivalents", "cash"))
    receivables = abs(_latest_for("bs", "trade_debtors", "accounts_receivable", "debtors"))
    inventory = abs(_latest_for("bs", "inventory", "stock"))
    total_current_assets = abs(_latest_for("bs", "total_current_assets", "current_assets"))
    fixed_assets = abs(_latest_for("bs", "fixed_assets_net", "fixed_assets", "property_plant_equipment"))
    total_assets = abs(_latest_for("bs", "total_assets"))
    payables = abs(_latest_for("bs", "trade_creditors", "accounts_payable", "creditors"))
    short_term_debt = abs(_latest_for("bs", "short_term_debt", "current_borrowings"))
    long_term_debt = abs(_latest_for("bs", "long_term_debt", "non_current_borrowings"))
    total_current_liabilities = abs(_latest_for("bs", "total_current_liab", "total_current_liabilities"))
    total_liabilities = abs(_latest_for("bs", "total_liabilities"))
    shareholders_equity = _latest_for("bs", "shareholders_equity", "net_assets")
    extracted_interest_bearing_debt = short_term_debt + long_term_debt
    if extracted_interest_bearing_debt == 0:
        extracted_interest_bearing_debt = abs(_latest_for("bs", "total_debt", "borrowings"))

    other_operating_current_assets = max(total_current_assets - cash - receivables - inventory, 0.0)
    other_operating_current_liabilities = max(
        total_current_liabilities - payables - short_term_debt,
        0.0,
    )
    operating_working_capital = (
        receivables + inventory + other_operating_current_assets - payables - other_operating_current_liabilities
    )
    ntoa = operating_working_capital + fixed_assets
    borrowing_base_proxy = (receivables * 0.75) + (inventory * 0.50) + (fixed_assets * 0.50)
    calculated_lvr = (amount / security_value * 100.0) if amount > 0 and security_value > 0 else None
    implied_security_value = (amount / lvr_rate) if amount > 0 and lvr_rate > 0 and security_value == 0 else None
    transaction_lvr = (amount / transaction_value * 100.0) if amount > 0 and transaction_value > 0 else None

    balance_sheet_strength = {
        "cash": _fmt_amount(cash),
        "accounts_receivable": _fmt_amount(receivables),
        "stock_inventory": _fmt_amount(inventory),
        "fixed_assets": _fmt_amount(fixed_assets),
        "accounts_payable": _fmt_amount(payables),
        "short_term_debt": _fmt_amount(short_term_debt),
        "long_term_debt": _fmt_amount(long_term_debt),
        "interest_bearing_debt": _fmt_amount(extracted_interest_bearing_debt),
        "net_debt": _fmt_amount(extracted_interest_bearing_debt - cash),
        "shareholders_equity": _fmt_amount(shareholders_equity),
        "operating_working_capital": _fmt_amount(operating_working_capital),
        "ntoa": _fmt_amount(ntoa),
        "borrowing_base_proxy": _fmt_amount(borrowing_base_proxy),
        "total_assets": _fmt_amount(total_assets),
        "total_liabilities": _fmt_amount(total_liabilities),
    }
    balance_sheet_strength_table = {
        "headers": ["Balance-sheet item", "Latest extracted value", "Credit relevance"],
        "rows": [
            ["Cash", balance_sheet_strength["cash"], "Immediate liquidity and net-debt offset."],
            ["Accounts receivable", balance_sheet_strength["accounts_receivable"], "Core working-capital asset and borrowing-base support, subject to aging and eligibility."],
            ["Stock / inventory", balance_sheet_strength["stock_inventory"], "Potential asset support if saleable and lender-eligible."],
            ["Fixed assets", balance_sheet_strength["fixed_assets"], "Tangible asset support for fleet, equipment or plant security where appraisals are available."],
            ["Accounts payable", balance_sheet_strength["accounts_payable"], "Operating liabilities that reduce net tangible operating asset support."],
            ["Short-term debt", balance_sheet_strength["short_term_debt"], "Current interest-bearing obligations and refinance risk."],
            ["Long-term debt", balance_sheet_strength["long_term_debt"], "Term borrowings that affect leverage and security priority."],
            ["Operating working capital", balance_sheet_strength["operating_working_capital"], "Receivables plus stock and other operating current assets less operating current liabilities."],
            ["NTOA", balance_sheet_strength["ntoa"], "Net tangible operating assets used as a balance-sheet strength proxy before formal collateral valuation."],
            ["Borrowing-base proxy", balance_sheet_strength["borrowing_base_proxy"], "Illustrative 75% receivables, 50% stock and 50% fixed-asset support before lender eligibility checks."],
        ],
    }

    leverage_capacity = last_ebitda * max_leverage if last_ebitda > 0 else 0.0
    interest_capacity = last_ebitda / (min_icr * funding_rate) if last_ebitda > 0 and funding_rate > 0 else 0.0
    service_factor = funding_rate + ((1.0 / term) if amortising and term > 0 else 0.0)
    dscr_capacity = last_ebitda / (min_dscr * service_factor) if last_ebitda > 0 and service_factor > 0 else 0.0
    collateral_capacity = security_value * lvr_rate if security_value > 0 and lvr_rate > 0 else borrowing_base_proxy
    ntoa_capacity = max(ntoa * 0.75, 0.0)

    constraints = [
        {
            "constraint": "Leverage limit",
            "supportable_debt": leverage_capacity,
            "basis": f"{max_leverage:.2f}x latest uploaded EBITDA",
            "caveat": "Illustrative senior-debt leverage ceiling; final appetite depends on business quality and lender policy.",
        },
        {
            "constraint": "Interest-cover limit",
            "supportable_debt": interest_capacity,
            "basis": f"{min_icr:.2f}x minimum interest cover at {funding_cost_pct:.2f}% funding cost",
            "caveat": "Uses EBITDA / cash interest as a lender-view proxy.",
        },
        {
            "constraint": "DSCR / debt-service limit",
            "supportable_debt": dscr_capacity,
            "basis": f"{min_dscr:.2f}x minimum DSCR over a {term:.1f}-year term",
            "caveat": "Uses straight-line amortisation unless the intake marks the facility as interest-only.",
        },
        {
            "constraint": "Collateral / LVR limit",
            "supportable_debt": collateral_capacity,
            "basis": (
                f"{lvr_pct:.1f}% LVR on supplied security value"
                if security_value > 0 and lvr_rate > 0
                else "Uploaded balance-sheet borrowing-base proxy: 75% debtors, 50% stock, 50% fixed assets"
            ),
            "caveat": "Requires actual security valuation, ownership, lien priority and lender eligibility checks.",
        },
        {
            "constraint": "Balance-sheet / NTOA support",
            "supportable_debt": ntoa_capacity,
            "basis": "75% of net tangible operating assets from uploaded balance-sheet items",
            "caveat": "NTOA is an operating balance-sheet strength proxy, not a formal collateral valuation.",
        },
    ]
    positive_constraints = [row for row in constraints if row["supportable_debt"] > 0]
    supportable_debt = min((row["supportable_debt"] for row in positive_constraints), default=0.0)
    binding = next((row for row in positive_constraints if row["supportable_debt"] == supportable_debt), None)
    debt_capacity_table = [
        {
            "constraint": row["constraint"],
            "supportable_debt": _fmt_amount(row["supportable_debt"]) if row["supportable_debt"] > 0 else "Not available",
            "basis": row["basis"],
            "binding": "Yes" if binding and row["constraint"] == binding["constraint"] else "No",
            "caveat": row["caveat"],
        }
        for row in constraints
    ]

    requested_facility_summary = {
        "amount_requested": _fmt_amount(amount),
        "loan_purpose": str(intake_answers.get("loan_purpose") or "Not provided"),
        "transaction_value": _fmt_amount(transaction_value) if transaction_value else "Not provided",
        "term": f"{term:.1f} years",
        "funding_cost": f"{funding_cost_pct:.2f}%" if funding_cost_pct else "Not provided",
        "repayment_profile": repayment_profile.replace("_", " "),
        "annual_interest": _fmt_amount(annual_interest),
        "annual_principal": _fmt_amount(annual_principal),
        "annual_debt_service": _fmt_amount(annual_debt_service),
        "security_package": str(intake_answers.get("security_package") or "Not provided").replace("_", " "),
        "security_value": _fmt_amount(security_value) if security_value else "Not provided",
        "target_lvr": f"{lvr_pct:.1f}%" if lvr_pct else "Not provided",
        "calculated_lvr": f"{calculated_lvr:.1f}%" if calculated_lvr is not None else "Not available",
        "transaction_lvr": f"{transaction_lvr:.1f}%" if transaction_lvr is not None else "Not available",
        "implied_security_value": _fmt_amount(implied_security_value) if implied_security_value else "Not available",
        "supportable_debt": _fmt_amount(supportable_debt) if supportable_debt > 0 else "Not available",
        "capacity_headroom": _fmt_amount(supportable_debt - amount) if supportable_debt > 0 and amount > 0 else "Not available",
        "binding_constraint": binding["constraint"] if binding else "Not available",
    }
    facility_terms_table = {
        "headers": ["Facility term", "Proposed / supplied detail", "Credit treatment"],
        "rows": [
            ["Borrower / structure", _answer_text("borrower_structure"), "Confirm legal borrower, guarantors and obligors before credit committee."],
            ["Facility type", _answer_text("facility_type", "Senior secured term debt"), "Used as the base structure for lender screening."],
            ["Amount requested", requested_facility_summary["amount_requested"], "Compared with cash-flow, LVR, collateral and balance-sheet capacity."],
            ["Purpose", requested_facility_summary["loan_purpose"], "Use of funds drives sources-and-uses and required diligence."],
            ["Term", requested_facility_summary["term"], "Determines scheduled amortisation and DSCR pressure."],
            ["Repayment profile", requested_facility_summary["repayment_profile"], "Principal repayment is modelled unless interest-only is selected."],
            ["Conservative funding cost", requested_facility_summary["funding_cost"], "Used for cash interest, ICR and rate-stress sensitivity."],
            ["Annual interest", requested_facility_summary["annual_interest"], "Estimated annual cash interest on the requested facility."],
            ["Annual principal", requested_facility_summary["annual_principal"], "Straight-line annual principal where amortising."],
            ["Annual debt service", requested_facility_summary["annual_debt_service"], "Interest plus scheduled principal used in DSCR."],
            ["Source of repayment", _answer_text("source_of_repayment", "Operating cash flow from the uploaded financials"), "Primary cash source to service interest, principal and any bridge repayment."],
            ["Security package", requested_facility_summary["security_package"], "Controls LVR and collateral diligence requirements."],
            ["Target LVR / advance rate", requested_facility_summary["target_lvr"], "Conservative lender advance-rate assumption supplied by the user."],
        ],
    }
    source_use_rows = [[
        requested_facility_summary["loan_purpose"],
        requested_facility_summary["amount_requested"],
        "Requested senior facility",
        requested_facility_summary["amount_requested"],
        "Only the supplied request is treated as committed; detailed funds flow remains a committee condition.",
    ]]
    if transaction_value:
        source_use_rows.append([
            "Transaction / asset value",
            _fmt_amount(transaction_value),
            "Equity contribution",
            _fmt_amount(equity_contribution) if equity_contribution else "Not provided",
            "Supports LVR/equity context but does not replace a signed sale and purchase agreement or funds-flow statement.",
        ])
    if refinance_amount:
        source_use_rows.append([
            "Refinance existing debt",
            _fmt_amount(refinance_amount),
            "Included in facility request",
            _fmt_amount(refinance_amount),
            "Debt schedule and payout letters required before credit committee.",
        ])
    if transaction_costs:
        source_use_rows.append([
            "Transaction / advisory costs",
            _fmt_amount(transaction_costs),
            "Facility or equity funding",
            "Not allocated",
            "Legal, advisory, bank and diligence costs should be supported by invoices or estimates.",
        ])
    if working_capital_buffer:
        source_use_rows.append([
            "Working-capital / integration buffer",
            _fmt_amount(working_capital_buffer),
            "Facility or retained cash",
            "Not allocated",
            "Buffer should be checked against monthly trading seasonality and creditor terms.",
        ])
    if sponsor_bridge_amount:
        bridge_repayment_source = _answer_text("sponsor_bridge_repayment_source")
        source_use_rows.append([
            "Additional bridge / sponsor facility",
            _fmt_amount(sponsor_bridge_amount),
            "Separate bridge funding",
            _fmt_amount(sponsor_bridge_amount),
            (
                f"Indicative {sponsor_bridge_term_months:.0f}-month bridge; repayment source: {bridge_repayment_source}."
                if sponsor_bridge_term_months
                else f"Separate bridge repayment source: {bridge_repayment_source}."
            ),
        ])
    sources_and_uses_table = {
        "headers": ["Uses", "Amount", "Sources", "Amount", "Credit comment"],
        "rows": source_use_rows,
    }
    security_analysis_table = {
        "headers": ["Security / LVR item", "Value", "Credit comment"],
        "rows": [
            ["Security package", _friendly_choice(intake_answers.get("security_package")), "Confirms whether GSA, fleet, property, guarantee or unsecured treatment is being tested."],
            ["Security notes", _answer_text("security_notes"), "Operational detail to verify through PPSR, title, fleet schedule, property valuation or guarantees."],
            ["Supplied security value", requested_facility_summary["security_value"], "Used for calculated LVR where supplied."],
            ["Target LVR / advance rate", requested_facility_summary["target_lvr"], "Conservative advance-rate assumption used for debt-capacity screening."],
            ["Calculated LVR on supplied security", requested_facility_summary["calculated_lvr"], "Shows facility amount divided by supplied collateral value."],
            ["Transaction LVR / LTV", requested_facility_summary["transaction_lvr"], "Shows facility amount divided by supplied transaction or asset value where provided."],
            ["Implied security value needed", requested_facility_summary["implied_security_value"], "Security value implied by the requested amount and target LVR when no appraised value is supplied."],
            ["Lien / priority checks", "Required before credit committee", "PPSR, property title, prior-ranking debt, insurance and lender form-security documents required."],
        ],
    }
    credit_metrics_table = {
        "headers": ["Metric", "Base case", "Threshold / interpretation", "Comment"],
        "rows": [
            ["Latest uploaded EBITDA", _fmt_amount(last_ebitda), "Credit anchor", f"Based on {last_yr or 'the latest uploaded period'}."],
            ["Requested senior debt", _fmt_amount(amount), "Facility amount", "Compared with EBITDA, debt service, LVR and NTOA constraints."],
            ["Senior leverage", _fmt_ratio(round(amount / last_ebitda, 2) if last_ebitda > 0 and amount > 0 else None), f"Illustrative max {max_leverage:.2f}x", "Debt divided by latest uploaded EBITDA."],
            ["Base ICR", _fmt_ratio(round(last_ebitda / annual_interest, 2) if annual_interest > 0 else None), f"Minimum {min_icr:.2f}x", "EBITDA divided by cash interest."],
            ["Base DSCR", _fmt_ratio(round(last_ebitda / annual_debt_service, 2) if annual_debt_service > 0 else None), f"Minimum {min_dscr:.2f}x", "EBITDA divided by cash interest plus scheduled principal."],
            ["Target LVR", requested_facility_summary["target_lvr"], "Security advance-rate assumption", "Must be confirmed against lender collateral policy."],
            ["Supportable debt", requested_facility_summary["supportable_debt"], "Minimum of capacity constraints", "The binding constraint should drive the recommended structure."],
            ["Headroom / shortfall", requested_facility_summary["capacity_headroom"], "Positive is headroom", "Supportable debt less requested debt."],
            ["Binding constraint", requested_facility_summary["binding_constraint"], "Most conservative available limit", "Use this as the credit sizing conclusion unless overridden by bank policy."],
        ],
    }
    amortisation_rows: list[list[str]] = []
    opening_debt = amount
    years_to_show = min(max(1, int(math.ceil(term))), 10)
    for year_index in range(1, years_to_show + 1):
        if opening_debt <= 0:
            break
        principal = min(annual_principal, opening_debt) if amortising else 0.0
        interest = opening_debt * funding_rate if funding_rate > 0 else 0.0
        closing_debt = max(opening_debt - principal, 0.0)
        leverage = opening_debt / last_ebitda if last_ebitda > 0 else None
        amortisation_rows.append([
            f"Year {year_index}",
            _fmt_amount(opening_debt),
            _fmt_amount(principal),
            _fmt_amount(interest),
            _fmt_amount(closing_debt),
            _fmt_ratio(round(leverage, 2) if leverage is not None else None),
        ])
        opening_debt = closing_debt
    if term > years_to_show and opening_debt > 0:
        amortisation_rows.append([
            "Years thereafter",
            _fmt_amount(opening_debt),
            "See term sheet",
            "See pricing",
            "Not modelled",
            "Not modelled",
        ])
    amortisation_profile_table = {
        "headers": ["Period", "Opening debt", "Principal", "Interest", "Closing debt", "Debt / EBITDA"],
        "rows": amortisation_rows,
    }
    proposed_covenants_table = _build_bank_credit_covenants_table(
        covenant_package["selected_keys"],
        min_dscr=min_dscr,
        min_icr=min_icr,
        max_leverage=max_leverage,
        lvr_pct=lvr_pct,
    )
    key_risks_mitigants_table = {
        "headers": ["Risk", "Credit impact", "Mitigant / condition"],
        "rows": [
            ["Trading variance", "Lower EBITDA reduces DSCR, ICR and leverage headroom.", "Anchor the credit case on the latest uploaded EBITDA and require monthly management accounts before committee."],
            ["Interest-rate sensitivity", "Higher funding cost compresses ICR and DSCR.", "Use the conservative funding cost and +1.50% rate stress; consider hedging or fixed-rate tranche if bank policy requires."],
            ["Collateral value / lien priority", "LVR support can fail if fleet/property values are stale or prior-ranking debt exists.", "Require appraisals, PPSR/title searches, insurance, and bank-form security documents."],
            ["Balance-sheet support", "Weak receivables, stock or fixed-asset support can make NTOA debt capacity binding.", "Require AR/AP/stock aging, debt schedule and fixed-asset/fleet register."],
            ["Documentation and committee readiness", "The paper is screening-only without signed terms, debt schedules, tax position and security documents.", "Treat missing documents as conditions precedent before credit committee."],
            ["Management / key-person dependence", "Owner/operator reliance can affect continuity and repayment source.", "Confirm management bench, succession cover, key-person insurance and guarantor support where relevant."],
        ],
    }
    conditions_precedent_table = {
        "headers": ["Priority", "Required before credit committee", "Why it matters", "Likely source / owner"],
        "rows": [
            ["1", "Latest management accounts and final FY financial statements", "Confirms the EBITDA anchor, trading trend and cash conversion.", "Borrower / accountant"],
            ["1", "Current debt schedule, payout letters and lender statements", "Confirms existing debt, refinance need, pricing and security priority.", "Borrower / existing lender"],
            ["1", "Signed or draft term sheet with facility amount, tenor, pricing, fees and repayment profile", "Locks the structure tested in the paper.", "Bank / borrower"],
            ["1", "Security schedule: fleet/equipment list, property title, PPSR searches and appraisals where applicable", "Confirms collateral value, ownership and lien priority.", "Borrower / valuer / solicitor"],
            ["2", "AR, AP and stock aging reports", "Tests working-capital quality and borrowing-base eligibility.", "Borrower / accountant"],
            ["2", "Tax status, GST/PAYE position and insurance certificates", "Identifies leakage, arrears and asset-protection issues.", "Borrower / accountant / broker"],
            ["2", "Companies Office extracts, ownership chart and guarantor information", "Confirms borrower perimeter and guarantee/security parties.", "Solicitor / borrower"],
            ["3", "Customer, contract, fleet, property or integration diligence relevant to the loan purpose", "Supports risks and mitigants specific to the transaction.", "Borrower / adviser"],
        ],
    }

    return {
        "dscr_table": dscr_table,
        "trend_table": trend_table,
        "financial_trend_table": financial_trend_table,
        "sensitivity": sensitivity,
        "annual_principal": annual_principal,
        "requested_facility_summary": requested_facility_summary,
        "sources_and_uses_table": sources_and_uses_table,
        "facility_terms_table": facility_terms_table,
        "security_analysis_table": security_analysis_table,
        "credit_metrics_table": credit_metrics_table,
        "coverage_table": coverage_table,
        "amortisation_profile_table": amortisation_profile_table,
        "balance_sheet_strength": balance_sheet_strength,
        "balance_sheet_strength_table": balance_sheet_strength_table,
        "debt_capacity_table": debt_capacity_table,
        "covenant_package": covenant_package,
        "proposed_covenants_table": proposed_covenants_table,
        "key_risks_mitigants_table": key_risks_mitigants_table,
        "conditions_precedent_table": conditions_precedent_table,
        "supportable_debt": supportable_debt,
        "capacity_headroom": supportable_debt - amount if supportable_debt > 0 and amount > 0 else None,
        "binding_constraint": binding["constraint"] if binding else None,
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
    credit_research_brief: Optional[dict] = None,
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

    if report_type == "valuation_advisory":
        table_sections_spec = json.dumps(TABLE_SECTIONS_VALUATION)
        sections_instruction = (
            f"Return a JSON object with exactly these keys (in this order): {sections_spec}. "
            f"For the keys in this list: {table_sections_spec}, the value MUST be a JSON object "
            f"with two keys: 'narrative' (a non-empty string) and 'table' (an object with 'headers' "
            f"(array of strings) and 'rows' (array of arrays of strings)). "
            f"For dcf_analysis only, also include 'cash_flow_schedule' with the same table shape. "
            f"For sensitivity_and_risks only, also include 'specific_risk_factors' with the same table shape. "
            f"For all other keys, the value MUST be a non-empty plain string. "
            f"Do not include any keys not in this list."
        )
    elif report_type == "bank_credit_paper":
        table_sections_spec = json.dumps(TABLE_SECTIONS_BANK_CREDIT)
        sections_instruction = (
            f"Return a JSON object with exactly these keys (in this order): {sections_spec}. "
            f"For the keys in this list: {table_sections_spec}, the value MUST be a JSON object "
            "with two keys: 'narrative' (a non-empty string) and 'table' (an object with 'headers' "
            "(array of strings) and 'rows' (array of arrays of strings)). "
            "For coverage_and_sensitivity only, also include 'amortisation_profile_table' with the same table shape. "
            "For balance_sheet_debt_capacity only, also include 'debt_capacity_table' with the same table shape. "
            "For all other keys, the value MUST be a non-empty plain string. "
            "Do not include any keys not in this list."
        )
    else:
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
        _require_valuation_table_schedules(valuation_result)

        research_brief_text = json.dumps(valuation_result.get("research_brief", {}), indent=2)
        dcf_block = {
            "wacc_scenarios_pct": valuation_result.get("wacc_scenarios_pct", {}),
            "dcf_scenarios": valuation_result.get("dcf_scenarios", {}),
            "illiquidity_discount": valuation_result.get("illiquidity_discount", {}),
            "normalised_ebitda": valuation_result.get("normalised_ebitda"),
            "revenues": valuation_result.get("revenues"),
            "gross_debt": valuation_result.get("gross_debt"),
            "net_debt": valuation_result.get("net_debt"),
            "cash": valuation_result.get("cash"),
            "surplus_assets": valuation_result.get("surplus_assets"),
            "forecast_years": valuation_result.get("forecast_years"),
            "revenue_growth_pct": valuation_result.get("revenue_growth_pct"),
            "growth_assumption_source": growth_assumption_source_label(
                valuation_result.get("growth_assumption_source") or ""
            ),
            "terminal_growth_pct": valuation_result.get("terminal_growth_pct"),
            "depreciation_base": valuation_result.get("depreciation_base"),
            "maintenance_capex": valuation_result.get("maintenance_capex"),
            "operating_working_capital": valuation_result.get("operating_working_capital"),
            "working_capital_ratio_pct": valuation_result.get("working_capital_ratio_pct"),
            "working_capital_source": working_capital_source_label(
                valuation_result.get("working_capital_source") or ""
            ),
            "executive_summary_table": valuation_result.get("executive_summary_table"),
            "wacc_assumptions_table": valuation_result.get("wacc_assumptions_table"),
            "dcf_analysis_table": valuation_result.get("dcf_analysis_table"),
            "financial_performance_table": valuation_result.get("financial_performance_table"),
            "financial_ratio_table": valuation_result.get("financial_ratio_table"),
            "balance_sheet_summary_table": valuation_result.get("balance_sheet_summary_table"),
            "valuation_summary_table": valuation_result.get("valuation_summary_table"),
            "multiples_crosscheck_table": valuation_result.get("multiples_crosscheck_table"),
            "assumption_source_trail": valuation_result.get("assumption_source_trail"),
            "comparable_evidence_table": valuation_result.get("comparable_evidence_table"),
            "sources_table": valuation_result.get("sources_table"),
            "normalisation_schedule": valuation_result.get("normalisation_schedule"),
            "forecast_cash_flow_schedule": valuation_result.get("forecast_cash_flow_schedule"),
            "sensitivity_matrix": valuation_result.get("sensitivity_matrix"),
            "sensitivity_table": valuation_result.get("sensitivity_table"),
            "specific_risk_factors": valuation_result.get("specific_risk_factors"),
        }
        dcf_block_text = json.dumps(dcf_block, indent=2)
        multiples_result = valuation_result.get("multiples_result") or {}
        multiples_block_text = json.dumps(multiples_result, indent=2)

        normalisations = intake_answers.get("normalisations", []) if isinstance(intake_answers, dict) else []
        public_source_urls = intake_answers.get("public_source_urls", []) if isinstance(intake_answers, dict) else []
        if isinstance(public_source_urls, str):
            public_source_urls = [public_source_urls] if public_source_urls.strip() else []
        company_website = (intake_answers.get("company_website") or "") if isinstance(intake_answers, dict) else ""
        source_hint_lines = []
        if company_website:
            source_hint_lines.append(f"- Official website: {company_website}")
        company_location = (intake_answers.get("company_location") or "") if isinstance(intake_answers, dict) else ""
        if company_location:
            source_hint_lines.append(f"- Main location: {company_location}")
        source_hint_lines.extend(f"- {url}" for url in public_source_urls if str(url).strip())
        source_hint_text = "\n".join(source_hint_lines) or "Not provided."
        narrative_intake_text = _format_valuation_private_intake(intake_answers or {})
        optional_overrides_text = _format_valuation_optional_expert_overrides(intake_answers or {})
        has_wizard_normalisations = isinstance(intake_answers, dict) and "normalisations" in intake_answers
        prior_ebitda_text = (
            "Not used for this valuation. The earnings-review schedule below is authoritative "
            "for the normalisations_schedule table and normalised EBITDA calculation."
            if has_wizard_normalisations
            else ebitda_text
        )
        norm_lines = (
            "\n".join(
                f"- {n.get('label', '?')}: ${float(n.get('amount', 0) or 0):,.0f}"
                + (f" — {n.get('rationale')}" if n.get('rationale') else "")
                for n in normalisations
            )
            or "No normalisation items provided."
        )

        user_message = f"""Generate a Valuation Advisory report for {company_name} matching the Propellerhead and Marina Terrace indicative valuation report standard.

## Company Information
- Name: {company_name}
- Industry: {industry or 'Not specified'}
- Business Description: {description or 'Not provided'}

## Extracted Financials
{financials_text}

## Management Team
{mgmt_text}

## Earlier EBITDA Add-backs (used only when no earnings-review schedule is supplied)
{prior_ebitda_text}

## Management Intake — Private Facts and Judgement
{narrative_intake_text}

## Optional Expert Overrides (collapsed advanced inputs; do not treat as required management questions)
{optional_overrides_text}

## Management-Supplied Public Source Hints (corroboration hints, not standalone proof)
{source_hint_text}

Use these optional links only to identify and corroborate the correct business. Do not treat them as
standalone proof. Any public fact included in the report must be supported by a source URL retained
in the AccountIQ-calculated sources or comparable-evidence tables.

## Earnings Review — Normalisation Schedule (use these to populate the normalisations_schedule table)
{norm_lines}

## AccountIQ-Calculated Executive Valuation Snapshot (use verbatim for executive_summary.table)
```json
{json.dumps(valuation_result.get("executive_summary_table") or {}, indent=2)}
```

## AccountIQ-Calculated Financial Performance Table (use verbatim for financial_performance.table)
```json
{json.dumps(valuation_result.get("financial_performance_table") or {}, indent=2)}
```

## AccountIQ-Calculated Financial Ratio Table (use verbatim for financial_ratio_analysis.table)
```json
{json.dumps(valuation_result.get("financial_ratio_table") or {}, indent=2)}
```

## AccountIQ-Calculated Balance Sheet Summary and EV-to-Equity Bridge (use verbatim for balance_sheet_summary.table)
```json
{json.dumps(valuation_result.get("balance_sheet_summary_table") or {}, indent=2)}
```

## AccountIQ-Calculated Valuation Summary Table (use verbatim for valuation_summary.table)
```json
{json.dumps(valuation_result.get("valuation_summary_table") or {}, indent=2)}
```

## AccountIQ-Calculated WACC Assumptions Table (use verbatim for wacc_assumptions.table)
```json
{json.dumps(valuation_result.get("wacc_assumptions_table") or {}, indent=2)}
```

## AccountIQ-Calculated DCF Analysis Table (use verbatim for dcf_analysis.table)
```json
{json.dumps(valuation_result.get("dcf_analysis_table") or {}, indent=2)}
```

## AccountIQ-Calculated Multiples Cross-check Table (use verbatim for multiples_crosscheck.table)
```json
{json.dumps(valuation_result.get("multiples_crosscheck_table") or {}, indent=2)}
```

## AccountIQ-Calculated Comparable Evidence Table (use verbatim for comparable_evidence.table)
```json
{json.dumps(valuation_result.get("comparable_evidence_table") or {}, indent=2)}
```

## AccountIQ-Calculated Sources Table (use verbatim for sources.table)
```json
{json.dumps(valuation_result.get("sources_table") or {}, indent=2)}
```

## AccountIQ-Calculated Sensitivity Analysis Table (use verbatim for sensitivity_and_risks.table)
```json
{json.dumps(valuation_result.get("sensitivity_table") or {}, indent=2)}
```

## AccountIQ-Calculated Normalisation Schedule (use verbatim for normalisations_schedule.table)
```json
{json.dumps(valuation_result.get("normalisation_schedule") or {}, indent=2)}
```

## Public Research Brief (do NOT modify any figure here)
```json
{research_brief_text}
```

## AccountIQ-Calculated DCF Scenarios and Illiquidity Discount (do NOT change any number)
```json
{dcf_block_text}
```

## AccountIQ-Calculated Comparable Multiples Method (do NOT change any number)
```json
{multiples_block_text}
```

## Finished-report discipline
- Write as a completed professional valuation report, not a questionnaire or request for more information.
- Do not ask management, the user or client to provide more documents, answers, assumptions or technical valuation inputs.
- If a fact is unavailable, disclose the limitation using professional report language and the supplied schedules; do not say the report cannot be completed.
- Do not introduce extra required valuation questions beyond the five private facts and earnings-adjustment review already captured.

## Section-specific instructions
- introduction: Engagement scope, client, purpose, valuation date, sources of information, basis of valuation, liability and confidentiality, and indicative/FMCA compliance.
- executive_summary: Lead with the DCF valuation range and midpoint, then explain the purpose, primary method, key earnings base, and the two or three assumptions with the greatest valuation impact. Keep it decision-useful and concise. Use executive_summary_table verbatim {{headers: executive_summary_table.headers, rows: executive_summary_table.rows}}.
- business_overview: Use research_brief.company_summary; do not invent facts.
- market_position: Use research_brief.sector_summary; reference credible NZ-specific competitors, regulators, or market evidence where available.
- about_business_valuations: Explain enterprise value versus equity value, going-concern value, maintainable earnings, why a range is more appropriate than false precision, and how readers, management and market participants should think about risk and uncertainty. Keep this educational and specific to an SME valuation audience.
- valuation_methodology: Explain that DCF is the primary method and researched comparable market multiples are an independent cross-check. Explain why these methods are appropriate for this business and do not refer to a user risk score.
- financial_performance: narrative + table using financial_performance_table verbatim {{headers: financial_performance_table.headers, rows: financial_performance_table.rows}}. The commentary must walk through the summary P&L in plain language: revenue, direct costs or cost of sales, gross profit, operating expenses, EBITDA, depreciation/amortisation where available, EBIT and net profit. Where the table includes key expense breakdown rows, explain the major cost categories such as wages/salaries and rent/occupancy, and call out other material expenses shown in the table. Explain the bridge from revenue to EBITDA and why expense rows matter for the earnings view. Explain only trends that are visible in the uploaded financials; do not invent missing periods or metrics.
- financial_ratio_analysis: narrative + table using financial_ratio_table verbatim {{headers: financial_ratio_table.headers, rows: financial_ratio_table.rows}}. Explain unavailable ratios as extraction limitations; do not invent accounting inputs.
- normalisations_schedule: narrative + table using normalisation_schedule verbatim {{headers: normalisation_schedule.headers, rows: normalisation_schedule.rows}}. If the table says no adjustments were confirmed, explain that maintainable earnings equal the uploaded earnings basis and do not invent add-backs.
- balance_sheet_summary: narrative + table using balance_sheet_summary_table verbatim {{headers: balance_sheet_summary_table.headers, rows: balance_sheet_summary_table.rows}}. Explain the balance-sheet position in plain language, including accounts receivable, stock/inventory, fixed assets, accounts payable, short-term and long-term loans, current assets, current liabilities, total assets, total liabilities and shareholders' equity where available. Explain the net tangible operating assets (NTOA) row as operating tangible assets less operating liabilities before cash and interest-bearing debt. Then explain the enterprise-value-to-equity-value bridge and note any 'Not available' extracted balance-sheet line without inventing replacements.
- valuation_assumptions: narrative + table using assumption_source_trail verbatim {{headers: assumption_source_trail.headers, rows: assumption_source_trail.rows}}. Explain the selected maintainable earnings base, explicit forecast period, revenue/earnings growth, terminal growth and tax assumptions. State that maintenance capex equals extracted depreciation when depreciation is available. Explain the extracted operating working-capital amount, its capped percentage of revenue, and working_capital_source. Use growth_assumption_source to state whether growth came from a management input, an override, or uploaded historical revenue; distinguish management-confirmed private inputs, uploaded financial data, model conventions and public research.
- wacc_assumptions: narrative + table using wacc_assumptions_table verbatim {{headers: wacc_assumptions_table.headers, rows: wacc_assumptions_table.rows}}. Explain that the high valuation uses the lowest WACC and the low valuation uses the highest WACC.
- dcf_analysis: Narrative + table using dcf_analysis_table verbatim {{headers: dcf_analysis_table.headers, rows: dcf_analysis_table.rows}}. Also include cash_flow_schedule using forecast_cash_flow_schedule verbatim: {{headers: forecast_cash_flow_schedule.headers, rows: forecast_cash_flow_schedule.rows}}. Explain that FCFF is EBIT after tax plus depreciation, less capex and change in operating working capital. The cash_flow_schedule must show the mid-case yearly revenue, EBITDA, EBIT, tax, maintenance capex, change in operating working capital, free cash flow to firm and discounted free cash flow.
- valuation_summary: narrative + table using valuation_summary_table verbatim {{headers: valuation_summary_table.headers, rows: valuation_summary_table.rows}}. Conclude with whether the researched market range supports the DCF conclusion.
- multiples_crosscheck: narrative + table using multiples_crosscheck_table verbatim {{headers: multiples_crosscheck_table.headers, rows: multiples_crosscheck_table.rows}}. Explain how the range is used as a reasonableness check and the material comparability limitations.
- sensitivity_and_risks: narrative + table using sensitivity_table verbatim {{headers: sensitivity_table.headers, rows: sensitivity_table.rows}}. Also include specific_risk_factors using specific_risk_factors verbatim: {{headers: specific_risk_factors.headers, rows: specific_risk_factors.rows}}. Identify the base case, then cover owner or key-person dependency, customer concentration, revenue quality, contract security, pipeline and any other private context supplied by the user. Clearly distinguish the quantified WACC/growth sensitivity from unquantified business risks.
- comparable_evidence: narrative + table using comparable_evidence_table verbatim {{headers: comparable_evidence_table.headers, rows: comparable_evidence_table.rows}}. Clearly state when evidence is indicative, broad-sector or not directly comparable. Use natural-language explanations of how each evidence point informs the cross-check; avoid vague status words such as "covered".
- sources: narrative + table using sources_table verbatim {{headers: sources_table.headers, rows: sources_table.rows}}. Include URLs verbatim and do not invent or alter URLs. Each row's "Supports / used for" text must explain the assumption, benchmark, company fact or market context supported by that URL; do not use generic labels such as "website", "source", "online reference" or vague status words such as "covered".
- disclaimer: Full FMCA-compliant disclaimer paragraph containing: 'indicative', 'does not constitute financial advice', 'FMCA' or 'Financial Markets Conduct', and 'not relied' or 'should not be relied'.
- general_principles: Explain the report's core assumptions: willing buyer/willing seller, arm's-length transaction, going concern, reasonable knowledge, no compulsion, and valuation-date sensitivity.
- glossary: Define at least DCF, enterprise value, equity value, EBITDA, maintainable earnings, terminal value, WACC, illiquidity discount, normalisation and FMCA in clear plain-English, management-friendly language. Each definition should be a useful explanatory sentence or short paragraph, not just a brief label.

All figures in the structured blocks above are AccountIQ-calculated — copy them verbatim into the report. Do not estimate, round, or recalculate. This report is indicative only and does not constitute financial advice."""

    elif report_type == "bank_credit_paper":
        if bank_credit_figures is None:
            raise ValueError("bank_credit_figures is required for bank_credit_paper report type")
        credit_research_text = json.dumps(credit_research_brief or {}, indent=2)
        user_message = f"""Generate a Bank Credit Paper for {company_name} in the style and depth of a professional SME lender credit paper.

## Company Information
- Name: {company_name}
- Industry: {industry or 'Not specified'}
- Business Description: {description or 'Not provided'}

## Extracted Financials
{financials_text}

## Public Research / Client Context
```json
{credit_research_text}
```

Use public research to describe the business, sector, competitive position and operating context. Do not invent client facts. If the research brief is thin, say that the public-source context is limited and rely on uploaded financials plus user-supplied debt inputs.

## Proposed Facility Details and Credit Questions (User-supplied)
{intake_text}

## Python-Computed Credit Figures (DO NOT change these numbers)
Requested facility summary: {json.dumps(bank_credit_figures.get('requested_facility_summary') or {}, indent=2)}
3-year financial trend: {json.dumps(bank_credit_figures.get('trend_table') or {}, indent=2)}
Financial trend table: {json.dumps(bank_credit_figures.get('financial_trend_table') or {}, indent=2)}
Historical DSCR by year: {json.dumps(bank_credit_figures.get('dscr_table') or {}, indent=2)}
Sources and uses table: {json.dumps(bank_credit_figures.get('sources_and_uses_table') or {}, indent=2)}
Facility terms table: {json.dumps(bank_credit_figures.get('facility_terms_table') or {}, indent=2)}
Security and LVR table: {json.dumps(bank_credit_figures.get('security_analysis_table') or {}, indent=2)}
Credit metrics table: {json.dumps(bank_credit_figures.get('credit_metrics_table') or {}, indent=2)}
Coverage and rate/downside sensitivity: {json.dumps(bank_credit_figures.get('coverage_table') or [], indent=2)}
Amortisation / deleveraging profile: {json.dumps(bank_credit_figures.get('amortisation_profile_table') or {}, indent=2)}
Balance-sheet strength and NTOA: {json.dumps(bank_credit_figures.get('balance_sheet_strength') or {}, indent=2)}
Balance-sheet strength table: {json.dumps(bank_credit_figures.get('balance_sheet_strength_table') or {}, indent=2)}
Debt-capacity constraints: {json.dumps(bank_credit_figures.get('debt_capacity_table') or [], indent=2)}
Selected covenant package: {json.dumps(bank_credit_figures.get('covenant_package') or {}, indent=2)}
Proposed covenants table: {json.dumps(bank_credit_figures.get('proposed_covenants_table') or {}, indent=2)}
Key risks and mitigants table: {json.dumps(bank_credit_figures.get('key_risks_mitigants_table') or {}, indent=2)}
Conditions precedent table: {json.dumps(bank_credit_figures.get('conditions_precedent_table') or {}, indent=2)}
Supportable debt: ${float(bank_credit_figures.get('supportable_debt') or 0):,.0f}
Capacity headroom / shortfall: {bank_credit_figures.get('capacity_headroom')}
Binding constraint: {bank_credit_figures.get('binding_constraint') or 'Not available'}
Annual principal repayment: ${bank_credit_figures['annual_principal']:,.0f}

## Credit-paper discipline
- Write as a completed lender credit paper, not a questionnaire.
- Follow the section order exactly. The shape should be similar to a bank paper: executive summary, transaction summary, sources and uses, borrower profile, facilities requested, security, financial performance, coverage/sensitivity, balance-sheet debt capacity, industry context, covenants, risks/mitigants, conditions precedent, recommendation and disclaimer.
- Use the uploaded financials and Python-computed credit schedules as the controlling numbers. Do not recalculate, round differently or invent missing financials.
- Explicitly discuss LVR, conservative funding cost, term, annual interest, annual principal, DSCR, ICR, security type, security value where supplied, and whether fleet/property/general security appears available.
- The balance_sheet_debt_capacity section must explain accounts receivable, stock/inventory, fixed assets, accounts payable, short-term loans, long-term loans, operating working capital, NTOA and the debt-capacity constraint table.
- Do not say a facility is bank-approved. Use lender-screening language such as indicative, proposed, supportable, not supportable, proceed-to-diligence, revise structure or not committee-ready.
- Where collateral values, covenant definitions, debt agreements, AR aging, stock aging, fleet/property appraisals or lender term sheets are not supplied, list them as conditions precedent or required before credit committee.
- Use the selected covenant package and proposed_covenants_table as the controlling covenant list. Do not add extra proposed covenants to that section; if an additional control may be useful, describe it as a possible mitigant or condition to discuss.

## Section-specific instructions
- executive_summary: narrative + table using credit_metrics_table verbatim {{headers: credit_metrics_table.headers, rows: credit_metrics_table.rows}}. Lead with the requested facility, purpose, funding cost, term, security package, LVR and headline debt-capacity conclusion. State whether the request appears supportable, supportable only with conditions, or requires revised structure based on the computed figures.
- transaction_summary: narrative + table using facility_terms_table verbatim {{headers: facility_terms_table.headers, rows: facility_terms_table.rows}}. Explain the proposed use of funds, borrower structure, facility type, term, repayment profile and source of repayment.
- sources_and_uses: narrative + table using sources_and_uses_table verbatim {{headers: sources_and_uses_table.headers, rows: sources_and_uses_table.rows}}. If detail is missing, state that only the total requested facility and stated purpose were provided.
- borrower_and_sponsor_profile: Use public research, company description and user context to describe business model, owner/sponsor, operating footprint, market position and repayment source.
- facilities_requested: narrative + table using facility_terms_table verbatim. Detail amount, tenor, pricing/funding cost, repayment profile, annual interest, annual principal, fees if supplied, and the borrower/lender request.
- security_package: narrative + table using security_analysis_table verbatim {{headers: security_analysis_table.headers, rows: security_analysis_table.rows}}. Explain the security indicated by the user: fleet, property, general security, guarantees or unsecured. Discuss calculated LVR, supplied security value, implied security value and documents required to confirm collateral value and lien priority.
- financial_performance_forecast: narrative + table using financial_trend_table verbatim {{headers: financial_trend_table.headers, rows: financial_trend_table.rows}}. Explain revenue, EBITDA and net profit trends from uploaded financials and whether the latest year is a conservative credit anchor. Do not invent forecasts unless the user supplied them.
- coverage_and_sensitivity: narrative + table using the coverage_table converted into headers/rows with columns case, EBITDA, funding cost, cash interest, annual principal, DSCR and ICR. Also include amortisation_profile_table verbatim as an additional table. Explain base DSCR/ICR, rate stress, EBITDA downside and deleveraging through the debt term.
- balance_sheet_debt_capacity: narrative + table using balance_sheet_strength_table verbatim. Also include debt_capacity_table verbatim as an additional table. Explain NTOA as operating tangible assets less operating liabilities before cash/debt. Identify the binding debt-capacity constraint.
- industry_and_competitive_landscape: Use public research for business/sector context, competitive position, regulatory or contract drivers, and cyclicality. Keep unsupported claims appropriately caveated.
- proposed_covenants: narrative + table using proposed_covenants_table verbatim {{headers: proposed_covenants_table.headers, rows: proposed_covenants_table.rows}}. Label these as proposed, not agreed.
- key_risks_and_mitigants: narrative + table using key_risks_mitigants_table verbatim {{headers: key_risks_mitigants_table.headers, rows: key_risks_mitigants_table.rows}}. Cover trading variance, customer/contract concentration, rate sensitivity, collateral valuation, liquidity, management/key person, refinancing and documentation gaps.
- conditions_precedent: narrative + table using conditions_precedent_table verbatim {{headers: conditions_precedent_table.headers, rows: conditions_precedent_table.rows}}. List exact items required before credit committee.
- recommendation: narrative + table using credit_metrics_table verbatim. Conclude with a lender-readable recommendation and posture. Be clear if the package is screening-only or not committee-ready until open items are satisfied.
- disclaimer: Full FMCA-compliant disclaimer paragraph containing: 'indicative', 'does not constitute financial advice', 'FMCA' or 'Financial Markets Conduct', and 'not relied' or 'should not be relied'.

All figures are indicative only and do not constitute financial advice."""

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
