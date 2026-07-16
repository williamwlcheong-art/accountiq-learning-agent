"""
Valuation Advisory algorithm -- AccountIQ Phase 05.1.

Refactored per D-W1/D-W2/D-W5/D-W6:
  - Scoring-based EV/EBITDA logic removed (compute_ev_ebitda_multiple, compute_wacc,
    compute_valuation, SECTOR_STARTING_MULTIPLES, SECTOR_WEIGHTS, etc.)
  - compute_wacc_scenarios() added for High/Mid/Low WACC from researched inputs
  - compute_dcf() and compute_illiquidity_discount() retained verbatim

All computation is deterministic Python. Claude receives the output dict and writes narrative only.
"""
from __future__ import annotations
import math
import re
from typing import Optional
from urllib.parse import urlparse


VALUATION_REVENUE_KEYS = {
    "revenue",
    "sales",
    "turnover",
    "operating_revenue",
}

VALUATION_EARNINGS_KEYS = {
    "ebitda",
    "operating_profit",
    "profit_before_tax",
    "net_profit_before_tax",
    "net_profit",
    "net_profit_after_tax",
}


_MANAGEMENT_INTAKE_LABELS = {
    "valuation_purpose": {
        "understand_value": "Understand what the business may be worth",
        "sale_or_transaction": "Prepare for a sale or transaction",
        "shareholder_or_employee_scheme": "Shareholder or employee share scheme",
        "succession_planning": "Succession or estate planning",
        "finance_or_investment": "Finance or investment discussions",
        "other": "Another valuation purpose",
    },
    "owner_dependency": {
        "independent": "Management team runs day-to-day operations",
        "shared": "Responsibility is shared across leadership and team",
        "important": "An owner or key person is important day to day",
        "critical": "Business depends heavily on an owner or key person",
        "unknown": "Not sure",
    },
    "customer_concentration": {
        "under_10": "Less than 10%",
        "10_to_25": "10% to 25%",
        "over_25": "More than 25%",
        "consumer_or_diversified": "Consumer or highly diversified revenue",
        "unknown": "Not sure",
    },
    "revenue_quality": {
        "mostly_contract": "Mostly contracted or recurring revenue",
        "mixed": "A mix of recurring and one-off revenue",
        "mostly_one_off": "Mostly one-off or transactional revenue",
        "unknown": "Not sure",
    },
    "revenue_outlook": {
        "lower": "Likely lower than today",
        "steady": "Broadly steady",
        "modest_growth": "Modest growth",
        "strong_growth": "Strong growth backed by pipeline or contracts",
        "not_sure": "No specific forecast provided; growth derived from uploaded financial history",
    },
}

_GROWTH_ASSUMPTION_SOURCE_LABELS = {
    "management_custom_override": "Management-supplied growth override",
    "management_outlook_lower": "Management outlook: likely lower than today",
    "management_outlook_steady": "Management outlook: broadly steady",
    "management_outlook_modest_growth": "Management outlook: modest growth",
    "management_outlook_strong_growth": "Management outlook: strong growth backed by pipeline or contracts",
    "owner_custom_override": "Management-supplied growth override",
    "owner_outlook_lower": "Management outlook: likely lower than today",
    "owner_outlook_steady": "Management outlook: broadly steady",
    "owner_outlook_modest_growth": "Management outlook: modest growth",
    "owner_outlook_strong_growth": "Management outlook: strong growth backed by pipeline or contracts",
    "historical_revenue_cagr_capped": "Uploaded revenue history: CAGR capped between -5% and 12%",
    "insufficient_history_fallback": "Model fallback: insufficient revenue history",
}

_WORKING_CAPITAL_SOURCE_LABELS = {
    "extracted_operating_line_items": "Uploaded balance sheet: operating working-capital line items",
    "extracted_current_totals": "Uploaded balance sheet: current asset and liability totals",
    "insufficient_history_zero_assumption": "Model fallback: no usable working-capital history",
}


def report_answer_label(field_name: str, value: str) -> str:
    """Return report-ready wording for a short management-intake answer."""
    raw = str(value or "").strip()
    if not raw:
        return "Not supplied"
    return _MANAGEMENT_INTAKE_LABELS.get(field_name, {}).get(raw, raw.replace("_", " "))


def growth_assumption_source_label(source: str) -> str:
    """Return report-ready wording for the source of the DCF growth assumption."""
    raw = str(source or "").strip()
    if not raw:
        return "Not supplied"
    return _GROWTH_ASSUMPTION_SOURCE_LABELS.get(raw, raw.replace("_", " "))


def working_capital_source_label(source: str) -> str:
    """Return report-ready wording for the source of the working-capital assumption."""
    raw = str(source or "").strip()
    if not raw:
        return "Not supplied"
    return _WORKING_CAPITAL_SOURCE_LABELS.get(raw, raw.replace("_", " "))


def debt_cash_surplus_source_label(
    *,
    debt_override_used: bool = False,
    surplus_assets_supplied: bool = False,
) -> str:
    """Return transparent source wording for the enterprise-to-equity bridge inputs."""
    debt_source = (
        "Debt: management-supplied debt override"
        if debt_override_used
        else "Debt: uploaded balance sheet borrowings where extracted"
    )
    surplus_source = (
        "surplus assets: management-supplied amount"
        if surplus_assets_supplied
        else "surplus assets: no management-supplied amount identified"
    )
    return f"{debt_source}; cash: uploaded balance sheet cash balance; {surplus_source}"


def assess_valuation_financial_readiness(financial_rows: list[dict]) -> dict:
    """Check whether extracted rows can support a professional valuation report.

    The owner should not have to compensate for poor extraction by answering
    more valuation questions. Instead, the live report flow needs at least a
    recognisable revenue base and an earnings/profit basis from the uploaded
    statements before a DCF/multiples report can be prepared.
    """
    revenue_periods: set[str] = set()
    earnings_periods: set[str] = set()

    for row in financial_rows:
        if str(row.get("statement") or "").lower() != "pnl":
            continue
        key = str(row.get("row_key") or row.get("canonical_key") or "").lower()
        period = str(row.get("period") or "")
        value = row.get("value")
        if value is None and isinstance(row.get("values"), dict):
            for nested_period, nested_value in row["values"].items():
                nested_row = {
                    "statement": row.get("statement"),
                    "row_key": key,
                    "period": nested_period,
                    "value": nested_value,
                }
                nested = assess_valuation_financial_readiness([nested_row])
                revenue_periods.update(nested.get("revenue_periods", []))
                earnings_periods.update(nested.get("earnings_periods", []))
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(number):
            continue
        if key in VALUATION_REVENUE_KEYS and number > 0:
            revenue_periods.add(period)
        if key in VALUATION_EARNINGS_KEYS:
            earnings_periods.add(period)

    issues: list[str] = []
    warnings: list[str] = []
    if not revenue_periods:
        issues.append("revenue")
    if not earnings_periods:
        issues.append("EBITDA or profit")
    if len(revenue_periods) == 1:
        warnings.append("Only one revenue period was extracted; the report will have limited trend analysis.")
    if len(earnings_periods) == 1:
        warnings.append("Only one earnings period was extracted; the report will have limited earnings trend analysis.")

    return {
        "ready": not issues,
        "issues": issues,
        "warnings": warnings,
        "revenue_periods": sorted(revenue_periods),
        "earnings_periods": sorted(earnings_periods),
    }


def _coerce_financial_value(value: object) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    is_negative = text.startswith("(") and text.endswith(")")
    cleaned = (
        text.strip("()")
        .replace("$", "")
        .replace(",", "")
        .replace("%", "")
        .strip()
    )
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return -number if is_negative else number


def _normalise_financial_row_input(financial_rows: list[dict]) -> dict[str, dict[str, dict[str, float]]]:
    """Convert flat DB rows or grouped prompt rows into statement/key/period maps."""
    grouped: dict[str, dict[str, dict[str, float]]] = {}

    def add_value(statement: object, key: object, period: object, value: object) -> None:
        period_text = str(period or "").strip()
        key_text = str(key or "").strip().lower()
        if not period_text or not key_text:
            return
        number = _coerce_financial_value(value)
        if number is None:
            return
        statement_text = str(statement or "pnl").strip().lower()
        grouped.setdefault(statement_text, {}).setdefault(key_text, {})[period_text] = number

    for row in financial_rows or []:
        if not isinstance(row, dict):
            continue
        statement = row.get("statement", "pnl")
        key = row.get("row_key") or row.get("canonical_key")
        values = row.get("values")
        if isinstance(values, dict):
            for period, value in values.items():
                add_value(statement, key, period, value)
        else:
            add_value(statement, key, row.get("period"), row.get("value"))

    return grouped


def _period_sort_key(period: str) -> tuple[int, int, str]:
    """Sort likely financial periods oldest-to-newest while preserving labels."""
    text = str(period)
    matches = re.findall(r"\d{2,4}", text)
    if not matches:
        return (1, 0, text.lower())
    raw_year = matches[-1]
    year = int(raw_year)
    if len(raw_year) == 2:
        year += 2000 if year < 80 else 1900
    return (0, year, text.lower())


def _series_for_keys(
    grouped: dict[str, dict[str, dict[str, float]]],
    statement: str,
    keys: tuple[str, ...],
) -> dict[str, float]:
    statement_rows = grouped.get(statement, {})
    for key in keys:
        series = statement_rows.get(key)
        if series:
            return dict(series)
    return {}


def _currency_cell(value: float | None) -> str:
    if value is None:
        return "Not available"
    return f"${float(value):,.0f}"


def _percentage_cell(value: float | None) -> str:
    if value is None:
        return "Not available"
    return f"{float(value):.1f}%"


def build_financial_performance_table(financial_rows: list[dict]) -> dict:
    """Build a report-ready summary P&L table from extracted P&L rows.

    The generated valuation report should not rely on the language model to
    decide which financial figures to present. This table uses only uploaded
    statement rows that were extracted into AccountIQ's canonical keys, and
    derives simple bridge rows where enough uploaded data exists. Expenses are
    shown as deductions so a reader can see the route from revenue to EBITDA.
    """
    grouped = _normalise_financial_row_input(financial_rows)
    revenue = _series_for_keys(grouped, "pnl", ("revenue", "sales", "turnover", "operating_revenue"))
    direct_costs_raw = _series_for_keys(grouped, "pnl", ("cogs", "cost_of_sales", "direct_costs"))
    gross_profit = _series_for_keys(grouped, "pnl", ("gross_profit",))
    operating_expenses_raw = _series_for_keys(grouped, "pnl", ("operating_expenses", "total_expenses"))
    ebitda = _series_for_keys(grouped, "pnl", ("ebitda",))
    depreciation_raw = _series_for_keys(
        grouped,
        "pnl",
        ("depreciation_amortisation", "depreciation", "amortisation", "amortization"),
    )
    ebit = _series_for_keys(grouped, "pnl", ("ebit", "operating_profit"))
    interest_raw = _series_for_keys(grouped, "pnl", ("interest_expense",))
    tax_raw = _series_for_keys(grouped, "pnl", ("tax", "tax_expense", "income_tax"))
    net_profit = _series_for_keys(grouped, "pnl", ("net_profit", "net_profit_after_tax"))

    def expense_series(series: dict[str, float]) -> dict[str, float]:
        return {
            period: -abs(float(value))
            for period, value in series.items()
            if value is not None
        }

    def add_series(*series_list: dict[str, float]) -> dict[str, float]:
        periods = {period for series in series_list for period in series}
        result: dict[str, float] = {}
        for period in periods:
            values = [float(series[period]) for series in series_list if period in series]
            if values:
                result[period] = sum(values)
        return result

    def residual_expense_series(
        total_series: dict[str, float],
        component_series: list[dict[str, float]],
    ) -> dict[str, float]:
        residual: dict[str, float] = {}
        for period, total_value in total_series.items():
            component_total = sum(
                float(series.get(period) or 0.0)
                for series in component_series
            )
            value = float(total_value) - component_total
            if abs(value) > 0.5:
                residual[period] = value
        return residual

    def latest_abs(series: dict[str, float]) -> float:
        if not series:
            return 0.0
        latest_period = sorted(series, key=_period_sort_key)[-1]
        return abs(float(series.get(latest_period) or 0.0))

    def direct_cost_series() -> dict[str, float]:
        if direct_costs_raw:
            return expense_series(direct_costs_raw)
        derived: dict[str, float] = {}
        for period, revenue_value in revenue.items():
            gross_value = gross_profit.get(period)
            if revenue_value is not None and gross_value is not None:
                derived[period] = float(gross_value) - float(revenue_value)
        return derived

    direct_costs = direct_cost_series()
    if gross_profit:
        gross_profit_series = dict(gross_profit)
    else:
        gross_profit_series = {
            period: float(revenue_value) + float(direct_costs[period])
            for period, revenue_value in revenue.items()
            if revenue_value is not None and period in direct_costs
        }

    if operating_expenses_raw:
        operating_expenses = expense_series(operating_expenses_raw)
    else:
        operating_expenses = {
            period: float(ebitda_value) - float(gross_profit_series[period])
            for period, ebitda_value in ebitda.items()
            if ebitda_value is not None and period in gross_profit_series
        }

    opex_breakdown_candidates: list[tuple[str, dict[str, float], bool]] = [
        (
            "Key expense breakdown - wages and salaries",
            expense_series(_series_for_keys(grouped, "pnl", ("wages_salaries", "wages", "salaries"))),
            True,
        ),
        (
            "Key expense breakdown - rent and occupancy",
            expense_series(_series_for_keys(grouped, "pnl", ("rent_occupancy", "rent", "occupancy_costs"))),
            True,
        ),
        (
            "Key expense breakdown - advertising and marketing",
            expense_series(_series_for_keys(grouped, "pnl", ("advertising_marketing", "marketing", "advertising"))),
            False,
        ),
        (
            "Key expense breakdown - insurance",
            expense_series(_series_for_keys(grouped, "pnl", ("insurance",))),
            False,
        ),
        (
            "Key expense breakdown - motor vehicle expenses",
            expense_series(_series_for_keys(grouped, "pnl", ("motor_vehicle_expenses", "vehicle_costs"))),
            False,
        ),
        (
            "Key expense breakdown - repairs and maintenance",
            expense_series(_series_for_keys(grouped, "pnl", ("repairs_maintenance", "repairs", "maintenance"))),
            False,
        ),
        (
            "Key expense breakdown - administration and professional fees",
            expense_series(_series_for_keys(grouped, "pnl", ("admin_professional_fees", "admin_expenses", "professional_fees"))),
            False,
        ),
    ]
    latest_total_opex = latest_abs(operating_expenses)
    materiality_threshold = latest_total_opex * 0.10 if latest_total_opex else 0.0
    opex_breakdown: list[tuple[str, dict[str, float]]] = []
    for label, series, always_show in opex_breakdown_candidates:
        if not series:
            continue
        if always_show or latest_abs(series) >= materiality_threshold:
            opex_breakdown.append((label, series))
    residual_opex = (
        residual_expense_series(
            operating_expenses,
            [series for _label, series in opex_breakdown],
        )
        if opex_breakdown
        else {}
    )
    explicit_other_opex = expense_series(
        _series_for_keys(grouped, "pnl", ("other_operating_expenses", "other_expenses"))
    )
    other_opex = explicit_other_opex or residual_opex
    if other_opex:
        opex_breakdown.append(("Key expense breakdown - other operating expenses", other_opex))

    depreciation = expense_series(depreciation_raw)
    if ebit:
        ebit_series = dict(ebit)
    else:
        ebit_series = {
            period: float(ebitda_value) + float(depreciation[period])
            for period, ebitda_value in ebitda.items()
            if ebitda_value is not None and period in depreciation
        }

    metrics: list[tuple[str, dict[str, float]]] = [
        ("Revenue", revenue),
        ("Less: direct costs / cost of sales", direct_costs),
        ("Gross profit", gross_profit_series),
        ("Less: operating expenses before EBITDA", operating_expenses),
        *opex_breakdown,
        ("EBITDA", ebitda),
        ("Less: depreciation and amortisation", depreciation),
        ("EBIT", ebit_series),
        ("Less: interest expense", expense_series(interest_raw)),
        ("Less: income tax expense", expense_series(tax_raw)),
        ("Net profit after tax", net_profit),
    ]
    metrics = [(label, series) for label, series in metrics if series]
    periods = sorted(
        {period for _label, series in metrics for period in series},
        key=_period_sort_key,
    )
    if not periods or not metrics:
        return {"headers": [], "rows": []}

    rows = []
    for label, series in metrics:
        row = [label]
        for period in periods:
            value = series.get(period)
            row.append(_bridge_cell(float(value)) if value is not None else "Not available")
        rows.append(row)
    return {
        "headers": ["Metric"] + periods,
        "rows": rows,
    }


def build_financial_ratio_table(financial_rows: list[dict]) -> dict:
    """Build a report-ready ratio table from extracted P&L rows.

    Missing inputs are shown transparently as ``Not available`` so the wizard
    does not need to ask owners for accounting ratios they may not know.
    """
    grouped = _normalise_financial_row_input(financial_rows)
    revenue = _series_for_keys(grouped, "pnl", ("revenue", "sales", "turnover", "operating_revenue"))
    gross_profit = _series_for_keys(grouped, "pnl", ("gross_profit",))
    ebitda = _series_for_keys(grouped, "pnl", ("ebitda",))
    net_profit = _series_for_keys(grouped, "pnl", ("net_profit", "net_profit_after_tax"))
    periods = sorted(
        set(revenue) | set(gross_profit) | set(ebitda) | set(net_profit),
        key=_period_sort_key,
    )
    if not periods:
        return {"headers": [], "rows": []}

    def ratio_for(series: dict[str, float], period: str) -> float | None:
        denominator = revenue.get(period)
        numerator = series.get(period)
        if denominator in (None, 0) or numerator is None:
            return None
        return numerator / denominator * 100

    rows: list[list[str]] = []
    if len(periods) > 1 and revenue:
        growth_values: list[str] = []
        previous: float | None = None
        for period in periods:
            current = revenue.get(period)
            if previous in (None, 0) or current is None:
                growth_values.append("Not available")
            else:
                growth_values.append(_percentage_cell((current / previous - 1) * 100))
            if current is not None:
                previous = current
        rows.append(["Revenue growth"] + growth_values)

    for label, series in (
        ("Gross margin", gross_profit),
        ("EBITDA margin", ebitda),
        ("Net profit margin", net_profit),
    ):
        values = [_percentage_cell(ratio_for(series, period)) for period in periods]
        if any(value != "Not available" for value in values):
            rows.append([label] + values)

    return {
        "headers": ["Ratio"] + periods,
        "rows": rows,
    }


def _latest_statement_value(
    grouped: dict[str, dict[str, dict[str, float]]],
    statement: str,
    keys: tuple[str, ...],
) -> float | None:
    for key in keys:
        series = grouped.get(statement, {}).get(key)
        if not series:
            continue
        latest_period = sorted(series, key=_period_sort_key)[-1]
        return series.get(latest_period)
    return None


def _bridge_cell(value: float) -> str:
    if value < 0:
        return f"(${abs(float(value)):,.0f})"
    return f"${float(value):,.0f}"


def build_balance_sheet_summary_table(
    financial_rows: list[dict],
    *,
    gross_debt: float,
    cash: float,
    surplus_assets: float,
    midpoint_enterprise_value: float,
    operating_working_capital: float,
    working_capital_source: str,
    debt_override_used: bool = False,
    surplus_assets_supplied: bool = False,
) -> dict:
    """Build a report-ready balance sheet and EV-to-equity bridge table.

    This table keeps the valuation bridge deterministic and avoids asking the
    owner for balance-sheet facts that should come from the uploaded statements.
    If fixed assets were not extracted, the table discloses that limitation.
    """
    grouped = _normalise_financial_row_input(financial_rows)
    fixed_assets = _latest_statement_value(
        grouped,
        "bs",
        ("fixed_assets_net", "property_plant_equipment", "total_fixed_assets"),
    )
    trade_debtors = _latest_statement_value(grouped, "bs", ("trade_debtors", "accounts_receivable"))
    inventory = _latest_statement_value(grouped, "bs", ("inventory", "stock"))
    other_current_assets = _latest_statement_value(grouped, "bs", ("other_current_assets",))
    total_current_assets = _latest_statement_value(grouped, "bs", ("total_current_assets",))
    other_noncurrent_assets = _latest_statement_value(grouped, "bs", ("other_noncurrent_assets",))
    total_current_liabilities = _latest_statement_value(grouped, "bs", ("total_current_liab",))
    trade_creditors = _latest_statement_value(grouped, "bs", ("trade_creditors", "accounts_payable"))
    other_current_liabilities = _latest_statement_value(grouped, "bs", ("other_current_liab",))
    short_term_debt = _latest_statement_value(grouped, "bs", ("short_term_debt",))
    long_term_debt = _latest_statement_value(grouped, "bs", ("long_term_debt",))
    other_noncurrent_liabilities = _latest_statement_value(grouped, "bs", ("other_noncurrent_liab",))
    total_assets = _latest_statement_value(grouped, "bs", ("total_assets",))
    total_liabilities = _latest_statement_value(grouped, "bs", ("total_liabilities",))
    shareholders_equity = _latest_statement_value(grouped, "bs", ("shareholders_equity",))
    operating_asset_values = [
        value
        for value in (
            trade_debtors,
            inventory,
            other_current_assets,
            fixed_assets,
        )
        if value is not None
    ]
    operating_liability_values = [
        value
        for value in (
            trade_creditors,
            other_current_liabilities,
        )
        if value is not None
    ]
    if operating_asset_values or operating_liability_values:
        net_tangible_operating_assets = sum(abs(float(value)) for value in operating_asset_values) - sum(
            abs(float(value)) for value in operating_liability_values
        )
    elif fixed_assets is not None:
        net_tangible_operating_assets = float(operating_working_capital or 0.0) + abs(float(fixed_assets))
    else:
        net_tangible_operating_assets = None
    net_debt = float(gross_debt or 0.0) - float(cash or 0.0)
    midpoint_equity_value = (
        float(midpoint_enterprise_value or 0.0)
        - net_debt
        + float(surplus_assets or 0.0)
    )
    bridge_row_label = "Less: net debt" if net_debt >= 0 else "Add: net cash"
    bridge_row_value = (
        f"(${net_debt:,.0f})" if net_debt >= 0 else f"${abs(net_debt):,.0f}"
    )
    debt_treatment = (
        "Management-supplied debt override."
        if debt_override_used
        else "Uploaded balance sheet borrowings where extracted."
    )
    surplus_treatment = (
        "Management-supplied surplus or non-operating asset amount."
        if surplus_assets_supplied
        else "No management-supplied surplus or non-operating assets identified."
    )

    return {
        "headers": ["Item", "Value", "Source / treatment"],
        "rows": [
            [
                "Cash and bank",
                _currency_cell(abs(float(cash or 0.0))),
                "Cash is shown separately from operating assets and is included in the enterprise-to-equity bridge.",
            ],
            [
                "Accounts receivable / trade debtors",
                _currency_cell(abs(trade_debtors)) if trade_debtors is not None else "Not available",
                "Uploaded receivables where extracted; included in operating asset and NTOA context.",
            ],
            [
                "Inventory / stock",
                _currency_cell(abs(inventory)) if inventory is not None else "Not available",
                "Uploaded stock balance where extracted; included in operating asset and NTOA context.",
            ],
            [
                "Other current assets",
                _currency_cell(abs(other_current_assets)) if other_current_assets is not None else "Not available",
                "Other operating current assets where extracted.",
            ],
            [
                "Total current assets",
                _currency_cell(abs(total_current_assets)) if total_current_assets is not None else "Not available",
                "Uploaded balance sheet current-asset total where extracted; supports working-capital context.",
            ],
            [
                "Fixed assets (net)",
                _currency_cell(abs(fixed_assets)) if fixed_assets is not None else "Not available",
                "Uploaded balance sheet where extracted; otherwise not used as a separate valuation adjustment.",
            ],
            [
                "Other non-current assets",
                _currency_cell(abs(other_noncurrent_assets)) if other_noncurrent_assets is not None else "Not available",
                "Other long-term operating or investment assets where extracted.",
            ],
            [
                "Total assets",
                _currency_cell(abs(total_assets)) if total_assets is not None else "Not available",
                "Uploaded balance sheet total assets where extracted; used as financial-position context rather than the primary valuation basis.",
            ],
            [
                "Accounts payable / trade creditors",
                _currency_cell(abs(trade_creditors)) if trade_creditors is not None else "Not available",
                "Uploaded trade payables where extracted; included in operating liability and NTOA context.",
            ],
            [
                "Other current liabilities",
                _currency_cell(abs(other_current_liabilities)) if other_current_liabilities is not None else "Not available",
                "Other operating current liabilities where extracted.",
            ],
            [
                "Short-term loans / current borrowings",
                _currency_cell(abs(short_term_debt)) if short_term_debt is not None else "Not available",
                "Current interest-bearing borrowings where extracted; included in the debt bridge when no override is supplied.",
            ],
            [
                "Total current liabilities",
                _currency_cell(abs(total_current_liabilities)) if total_current_liabilities is not None else "Not available",
                "Uploaded balance sheet current-liability total where extracted; supports working-capital context.",
            ],
            [
                "Long-term loans / borrowings",
                _currency_cell(abs(long_term_debt)) if long_term_debt is not None else "Not available",
                "Non-current interest-bearing borrowings where extracted; included in the debt bridge when no override is supplied.",
            ],
            [
                "Other non-current liabilities",
                _currency_cell(abs(other_noncurrent_liabilities)) if other_noncurrent_liabilities is not None else "Not available",
                "Other long-term liabilities where extracted.",
            ],
            [
                "Total liabilities",
                _currency_cell(abs(total_liabilities)) if total_liabilities is not None else "Not available",
                "Uploaded balance sheet total liabilities where extracted; provides solvency and leverage context.",
            ],
            [
                "Shareholders' equity / net assets",
                _currency_cell(abs(shareholders_equity)) if shareholders_equity is not None else "Not available",
                "Uploaded balance sheet net-asset position where extracted; shown for context and reconciled separately from enterprise value.",
            ],
            [
                "Net tangible operating assets (NTOA)",
                _bridge_cell(net_tangible_operating_assets) if net_tangible_operating_assets is not None else "Not available",
                "Indicative operating asset position: receivables, stock, other operating current assets and fixed assets less operating payables and other operating current liabilities, excluding cash and interest-bearing debt.",
            ],
            [
                "Operating working capital",
                _currency_cell(operating_working_capital),
                working_capital_source_label(working_capital_source),
            ],
            [
                "Interest-bearing debt",
                _currency_cell(abs(float(gross_debt or 0.0))),
                debt_treatment,
            ],
            [
                "Net debt",
                _bridge_cell(net_debt),
                "Interest-bearing debt less cash and bank.",
            ],
            [
                "Surplus / non-operating assets",
                _currency_cell(float(surplus_assets or 0.0)),
                surplus_treatment,
            ],
            [
                "Midpoint enterprise value",
                _currency_cell(float(midpoint_enterprise_value or 0.0)),
                "AccountIQ-calculated DCF midpoint after the illiquidity adjustment.",
            ],
            [
                bridge_row_label,
                bridge_row_value,
                "Enterprise value to equity value bridge.",
            ],
            [
                "Add: surplus assets",
                _currency_cell(float(surplus_assets or 0.0)),
                "Separately identified assets not required for normal operations.",
            ],
            [
                "Midpoint equity value",
                _currency_cell(midpoint_equity_value),
                "Midpoint enterprise value less net debt plus surplus assets.",
            ],
        ],
    }


def _equity_value_from_enterprise_value(
    enterprise_value: float,
    *,
    gross_debt: float,
    cash: float,
    surplus_assets: float,
) -> float:
    return (
        float(enterprise_value or 0.0)
        - float(gross_debt or 0.0)
        + float(cash or 0.0)
        + float(surplus_assets or 0.0)
    )


def build_executive_summary_table(
    *,
    adjusted_enterprise_values: dict[str, float],
    gross_debt: float,
    cash: float,
    surplus_assets: float,
) -> dict:
    """Build the headline valuation snapshot shown in the executive summary."""
    scenarios = ("high", "mid", "low")
    net_debt = float(gross_debt or 0.0) - float(cash or 0.0)
    bridge_label = "Less: net debt" if net_debt >= 0 else "Add: net cash"
    bridge_values = [
        f"(${net_debt:,.0f})" if net_debt >= 0 else f"${abs(net_debt):,.0f}"
        for _scenario in scenarios
    ]
    equity_values = [
        _equity_value_from_enterprise_value(
            float(adjusted_enterprise_values.get(scenario) or 0.0),
            gross_debt=gross_debt,
            cash=cash,
            surplus_assets=surplus_assets,
        )
        for scenario in scenarios
    ]

    return {
        "headers": ["Indicative valuation", "High valuation", "Midpoint", "Low valuation"],
        "rows": [
            [
                "Enterprise value",
                *[
                    _currency_cell(float(adjusted_enterprise_values.get(scenario) or 0.0))
                    for scenario in scenarios
                ],
            ],
            [bridge_label, *bridge_values],
            [
                "Add: surplus assets",
                *[_currency_cell(float(surplus_assets or 0.0)) for _scenario in scenarios],
            ],
            [
                "Indicative equity value",
                *[_currency_cell(value) for value in equity_values],
            ],
        ],
    }


def _enterprise_value_from_dcf(dcf: dict) -> float:
    if not isinstance(dcf, dict):
        return 0.0
    return float(
        dcf.get("enterprise_value_dcf")
        or dcf.get("enterprise_value")
        or dcf.get("ev")
        or 0.0
    )


def build_valuation_summary_table(
    *,
    dcf_scenarios: dict[str, dict],
    adjusted_enterprise_values: dict[str, float],
    wacc_by_valuation_scenario_pct: dict[str, float],
    multiples_result: dict,
    gross_debt: float,
    cash: float,
    surplus_assets: float,
) -> dict:
    """Build the DCF and market-multiples summary table for the report."""
    rows: list[list[str]] = []
    dcf_labels = {
        "high": "DCF - high valuation",
        "mid": "DCF - midpoint",
        "low": "DCF - low valuation",
    }
    for scenario in ("high", "mid", "low"):
        enterprise_value = _enterprise_value_from_dcf(dcf_scenarios.get(scenario) or {})
        adjusted_ev = float(adjusted_enterprise_values.get(scenario) or 0.0)
        rows.append([
            dcf_labels[scenario],
            f"{float(wacc_by_valuation_scenario_pct.get(scenario) or 0.0):.1f}% WACC",
            _currency_cell(enterprise_value),
            _currency_cell(adjusted_ev),
            _currency_cell(
                _equity_value_from_enterprise_value(
                    adjusted_ev,
                    gross_debt=gross_debt,
                    cash=cash,
                    surplus_assets=surplus_assets,
                )
            ),
        ])

    multiple_rows = (
        ("low", "Multiples - low", "multiple_low", "enterprise_value_low"),
        ("mid", "Multiples - midpoint", "multiple_mid", "enterprise_value_mid"),
        ("high", "Multiples - high", "multiple_high", "enterprise_value_high"),
    )
    for _scenario, label, multiple_key, ev_key in multiple_rows:
        enterprise_value = float(multiples_result.get(ev_key) or 0.0)
        multiple = float(multiples_result.get(multiple_key) or 0.0)
        rows.append([
            label,
            f"{multiple:.2f}x EBITDA",
            _currency_cell(enterprise_value),
            "Not applied",
            _currency_cell(
                _equity_value_from_enterprise_value(
                    enterprise_value,
                    gross_debt=gross_debt,
                    cash=cash,
                    surplus_assets=surplus_assets,
                )
            ),
        ])

    return {
        "headers": [
            "Method / scenario",
            "Scenario / input",
            "Enterprise value",
            "Illiquidity-adjusted EV",
            "Equity value",
        ],
        "rows": rows,
    }


def build_wacc_assumptions_table(
    *,
    risk_free_rate: float,
    erp: float,
    industry_beta: float,
    wacc_by_valuation_scenario_pct: dict[str, float],
    illiquidity_discount: float,
) -> dict:
    """Build a report-ready WACC assumptions table from researched inputs."""
    scenarios = ("high", "mid", "low")
    return {
        "headers": ["Component", "High valuation", "Midpoint", "Low valuation"],
        "rows": [
            ["Risk-free rate", *[_percentage_cell(float(risk_free_rate or 0.0)) for _ in scenarios]],
            ["Equity risk premium", *[_percentage_cell(float(erp or 0.0)) for _ in scenarios]],
            ["Industry beta", *[f"{float(industry_beta or 0.0):.2f}" for _ in scenarios]],
            [
                "Private-company WACC",
                *[
                    _percentage_cell(float(wacc_by_valuation_scenario_pct.get(scenario) or 0.0))
                    for scenario in scenarios
                ],
            ],
            [
                "Illiquidity discount",
                *[_percentage_cell(float(illiquidity_discount or 0.0) * 100) for _ in scenarios],
            ],
        ],
    }


def build_dcf_analysis_table(
    *,
    dcf_scenarios: dict[str, dict],
    adjusted_enterprise_values: dict[str, float],
    wacc_by_valuation_scenario_pct: dict[str, float],
    terminal_growth_pct: float,
    revenue: float,
    normalised_ebitda: float,
    depreciation_base: float,
    maintenance_capex: float,
    working_capital_ratio_pct: float,
    illiquidity_discount: float,
) -> dict:
    """Build the main DCF scenario table for the report."""
    scenarios = ("high", "mid", "low")
    return {
        "headers": ["DCF item", "High valuation", "Midpoint", "Low valuation"],
        "rows": [
            [
                "WACC",
                *[
                    _percentage_cell(float(wacc_by_valuation_scenario_pct.get(scenario) or 0.0))
                    for scenario in scenarios
                ],
            ],
            ["Terminal growth", *[_percentage_cell(float(terminal_growth_pct or 0.0)) for _ in scenarios]],
            ["Base revenue", *[_currency_cell(float(revenue or 0.0)) for _ in scenarios]],
            ["Normalised EBITDA", *[_currency_cell(float(normalised_ebitda or 0.0)) for _ in scenarios]],
            ["Base depreciation", *[_currency_cell(float(depreciation_base or 0.0)) for _ in scenarios]],
            ["Maintenance capex", *[_currency_cell(float(maintenance_capex or 0.0)) for _ in scenarios]],
            [
                "Operating working capital / revenue",
                *[_percentage_cell(float(working_capital_ratio_pct or 0.0)) for _ in scenarios],
            ],
            [
                "Enterprise value before illiquidity",
                *[
                    _currency_cell(_enterprise_value_from_dcf(dcf_scenarios.get(scenario) or {}))
                    for scenario in scenarios
                ],
            ],
            [
                "Illiquidity discount",
                *[_percentage_cell(float(illiquidity_discount or 0.0) * 100) for _ in scenarios],
            ],
            [
                "Adjusted enterprise value",
                *[
                    _currency_cell(float(adjusted_enterprise_values.get(scenario) or 0.0))
                    for scenario in scenarios
                ],
            ],
        ],
    }


def build_multiples_crosscheck_table(multiples_result: dict) -> dict:
    """Build the market-multiples cross-check table from researched multiple range."""
    normalised_ebitda = float(multiples_result.get("normalised_ebitda") or 0.0)
    return {
        "headers": ["Input", "Low", "Mid", "High"],
        "rows": [
            [
                "EV/EBITDA multiple",
                f"{float(multiples_result.get('multiple_low') or 0.0):.2f}x",
                f"{float(multiples_result.get('multiple_mid') or 0.0):.2f}x",
                f"{float(multiples_result.get('multiple_high') or 0.0):.2f}x",
            ],
            [
                "Normalised EBITDA",
                _currency_cell(normalised_ebitda),
                _currency_cell(normalised_ebitda),
                _currency_cell(normalised_ebitda),
            ],
            [
                "Indicated enterprise value",
                _currency_cell(float(multiples_result.get("enterprise_value_low") or 0.0)),
                _currency_cell(float(multiples_result.get("enterprise_value_mid") or 0.0)),
                _currency_cell(float(multiples_result.get("enterprise_value_high") or 0.0)),
            ],
        ],
    }


_URL_PATTERN = re.compile(r"https?://[^\s\])>,]+")


def _dedupe_urls(sources: object) -> list[str]:
    if sources in (None, ""):
        return []
    candidates = sources if isinstance(sources, (list, tuple, set)) else [sources]
    urls: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        text = str(item or "").strip()
        if not text:
            continue
        matches = _URL_PATTERN.findall(text) or [text]
        for match in matches:
            url = match.strip().rstrip(".")
            if not url.startswith(("http://", "https://")):
                continue
            key = url.lower()
            if key not in seen:
                seen.add(key)
                urls.append(url)
    return urls


def _source_host(url: str) -> str:
    host = urlparse(url).hostname or ""
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _source_path(url: str) -> str:
    return urlparse(url).path.lower()


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _is_rbnz_source(url: str) -> bool:
    return _host_matches(_source_host(url), "rbnz.govt.nz")


def _is_damodaran_source(url: str) -> bool:
    host = _source_host(url)
    path = _source_path(url)
    if _host_matches(host, "stern.nyu.edu") and "adamodar" in path:
        return True
    return _host_matches(host, "damodaran.com")


def _is_stats_source(url: str) -> bool:
    return _host_matches(_source_host(url), "stats.govt.nz")


def _is_companies_office_source(url: str) -> bool:
    return _source_host(url) == "companies-register.companiesoffice.govt.nz"


def _is_linkedin_source(url: str) -> bool:
    return _host_matches(_source_host(url), "linkedin.com")


def _source_label(url: str) -> str:
    host = _source_host(url)
    if _is_rbnz_source(url):
        return "Reserve Bank of New Zealand"
    if _is_damodaran_source(url):
        return "Damodaran Online"
    if _is_stats_source(url):
        return "Stats NZ"
    if _is_companies_office_source(url):
        return "NZ Companies Office"
    if _is_linkedin_source(url):
        return "LinkedIn public profile"
    if host:
        return host
    return "Public source"


def _source_support(url: str) -> str:
    lowered = url.lower()
    if _is_rbnz_source(url) and "inflation" in lowered:
        return "Inflation and terminal-growth context"
    if _is_rbnz_source(url):
        return "Risk-free-rate and New Zealand macroeconomic context"
    if _is_damodaran_source(url):
        return "Equity risk premium, beta, multiples and private-company valuation inputs"
    if _is_stats_source(url):
        return "New Zealand sector and economic context"
    if _is_companies_office_source(url):
        return "Company public-profile corroboration"
    if _is_linkedin_source(url):
        return "Public business profile and market-position context"
    return "Business-profile, company-fact or market-context corroboration used for report drafting"


def _management_supplied_source_support(url: str) -> str:
    """Return professional support wording for optional management-supplied source hints."""
    if _is_companies_office_source(url):
        return "Management-supplied public record retained for company public-profile corroboration"
    if _is_linkedin_source(url):
        return "Management-supplied public profile retained for business-profile and market-position context"
    return "Management-supplied public source hint retained for company-fact, business-profile or market-context corroboration"


def _management_supplied_source_label(url: str) -> str:
    """Return a concise source label that makes optional management hints visible."""
    return f"Management-supplied {_source_label(url)}"


def build_sources_table(
    sources: object,
    *,
    management_supplied_sources: object = None,
    owner_supplied_sources: object = None,
) -> dict:
    """Build a report-ready source table using research URLs plus optional management hints."""
    research_urls = _dedupe_urls(sources)
    if management_supplied_sources is None:
        management_supplied_sources = owner_supplied_sources
    seen = {url.lower() for url in research_urls}
    rows = [
        [_source_label(url), url, _source_support(url)]
        for url in research_urls
    ]
    for url in _dedupe_urls(management_supplied_sources):
        key = url.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append([
            _management_supplied_source_label(url),
            url,
            _management_supplied_source_support(url),
        ])
    return {
        "headers": ["Source", "URL", "Supports / used for"],
        "rows": rows,
    }


def _comparable_transaction_lines(comparable_transactions: object) -> list[str]:
    if isinstance(comparable_transactions, list):
        raw_lines = [str(item or "") for item in comparable_transactions]
    else:
        text = str(comparable_transactions or "")
        raw_lines = re.split(r"(?:\n+|;\s+)", text)
    lines: list[str] = []
    for raw in raw_lines:
        cleaned = re.sub(r"^\s*[-*•\d.)]+\s*", "", str(raw or "").strip())
        if cleaned:
            lines.append(cleaned)
    return lines


def _transaction_date(line: str) -> str:
    match = re.search(r"\b(20\d{2}|19\d{2})\b", line)
    return match.group(1) if match else "Not disclosed"


def _transaction_metric(line: str) -> str:
    match = re.search(r"\b\d+(?:\.\d+)?\s*x\b", line, flags=re.IGNORECASE)
    return match.group(0).replace(" ", "") if match else "Not disclosed"


def build_comparable_evidence_table(
    *,
    comparable_transactions: object,
    sources: object,
) -> dict:
    """Build a sourced comparable-evidence table without inventing citations."""
    source_urls = _dedupe_urls(sources)
    lines = _comparable_transaction_lines(comparable_transactions)
    if not lines and source_urls:
        lines = ["Public valuation benchmark evidence identified in the research brief"]

    rows: list[list[str]] = []
    for index, line in enumerate(lines):
        urls_in_line = _dedupe_urls(line)
        source_url = urls_in_line[0] if urls_in_line else (
            source_urls[min(index, len(source_urls) - 1)] if source_urls else ""
        )
        if not source_url:
            continue
        rows.append([
            re.sub(_URL_PATTERN, "", line).strip(" -—") or "Public comparable evidence",
            _transaction_date(line),
            _transaction_metric(line),
            "Indicative public evidence; comparability depends on scale, margins, growth, customer mix, contract security and deal terms.",
            f"{_source_label(source_url)} - {source_url}",
        ])

    return {
        "headers": ["Evidence / transaction", "Date", "Metric or multiple", "Relevance and limitations", "Source"],
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# WACC scenarios (D-W2, D-W6)
# ---------------------------------------------------------------------------

def compute_wacc_scenarios(
    risk_free_rate: float,
    industry_beta: float,
    erp: float,
) -> dict:
    """
    Compute High/Mid/Low WACC scenarios from researched inputs (D-W2, D-W6).

    Inputs are in PERCENT form (e.g. risk_free_rate=4.65 not 0.0465,
    erp=5.94 not 0.0594, industry_beta=1.08).

    Returns a dict {"high": float, "mid": float, "low": float} with values
    in PERCENT. Caller is responsible for dividing by 100 before passing
    to compute_dcf() which takes wacc as a decimal.

    Spread formula (per AI-SPEC Section 4b.1):
      mid  = risk_free_rate + (industry_beta * erp)
      high = mid + beta_spread * erp + erp_spread
      low  = mid - beta_spread * erp - erp_spread
    where beta_spread = 0.15 (±15% beta variation) and
          erp_spread  = 0.25 (±0.25 percentage point ERP variation).
    """
    beta_spread = 0.15
    erp_spread = 0.25
    mid = risk_free_rate + (industry_beta * erp)
    return {
        "high": round(mid + beta_spread * erp + erp_spread, 2),
        "mid":  round(mid, 2),
        "low":  round(mid - beta_spread * erp - erp_spread, 2),
    }


# ---------------------------------------------------------------------------
# DCF (Discounted Cash Flow)
# ---------------------------------------------------------------------------

def compute_dcf(
    ebitda: float,
    wacc: float,
    growth_rate: float,
    tax_rate: float,
    years: int,
    terminal_growth: float,
    capex_per_year: Optional[float] = None,
    revenue: Optional[float] = None,
    depreciation_per_year: Optional[float] = None,
    working_capital_ratio: float = 0.0,
) -> dict:
    """
    Compute DCF enterprise value using FCFF projections and Gordon's Growth Model terminal value.

    ebitda:          normalised EBITDA (year 0 base, from Phase 3 ebitda_adjustments)
    wacc:            post-tax WACC as decimal (from compute_wacc_scenarios / 100)
    growth_rate:     annual EBITDA/revenue growth rate as decimal
    tax_rate:        corporate tax rate as decimal
    years:           forecast horizon (typically 3 or 5)
    terminal_growth: long-run sustainable CAGR as decimal (typically 0.02-0.04)
    capex_per_year:  base-year maintenance capex; defaults to 0
    revenue:          base-year revenue, used to project change in working capital
    depreciation_per_year: base-year depreciation and amortisation; defaults to 0
    working_capital_ratio: operating net working capital as a decimal of revenue

    Formulas (per year):
        ebitda[yr]   = ebitda[yr-1] x (1 + growth_rate)
        ebit[yr]     = ebitda[yr] - depreciation[yr]
        tax[yr]      = max(ebit[yr], 0) x tax_rate
        change_nwc   = (revenue[yr] - revenue[yr-1]) x working_capital_ratio
        fcff[yr]     = ebit[yr] - tax[yr] + depreciation[yr]
                       - capex[yr] - change_nwc
        dcf[yr]      = fcff[yr] / (1 + wacc)^yr

    Terminal value (Gordon's Growth Model):
        terminal_value     = fcff[years] x (1 + terminal_growth) / (wacc - terminal_growth)
        terminal_value_npv = terminal_value / (1 + wacc)^years

    NOTE: caller must ensure wacc > terminal_growth to avoid division by zero.

    returns: {
        'yearly': list of per-year breakdowns,
        'cumulative_dcf': float,
        'terminal_value': float,
        'terminal_value_npv': float,
        'enterprise_value_dcf': float
    }
    """
    if wacc <= terminal_growth:
        raise ValueError(
            f"WACC ({wacc:.4f}) must be greater than terminal_growth ({terminal_growth:.4f}) "
            "to avoid division by zero in Gordon's Growth Model."
        )

    if not -1.0 <= working_capital_ratio <= 1.0:
        raise ValueError("working_capital_ratio must be between -1.0 and 1.0")

    base_capex = max(float(capex_per_year or 0.0), 0.0)
    base_depreciation = max(float(depreciation_per_year or 0.0), 0.0)
    current_revenue = max(float(revenue or 0.0), 0.0)
    yearly = []
    current_ebitda = ebitda
    cumulative_dcf = 0.0

    for yr in range(1, years + 1):
        prior_revenue = current_revenue
        current_revenue = current_revenue * (1 + growth_rate) if current_revenue else 0.0
        current_ebitda = current_ebitda * (1 + growth_rate)
        depreciation = base_depreciation * ((1 + growth_rate) ** yr)
        capex = base_capex * ((1 + growth_rate) ** yr)
        ebit = current_ebitda - depreciation
        tax_charge = max(ebit, 0.0) * tax_rate
        change_nwc = (
            (current_revenue - prior_revenue) * working_capital_ratio
            if current_revenue
            else 0.0
        )
        fcff = ebit - tax_charge + depreciation - capex - change_nwc
        discounted     = fcff / ((1 + wacc) ** yr)
        cumulative_dcf += discounted
        yearly.append({
            "year":   yr,
            "revenue": round(current_revenue, 2) if current_revenue else None,
            "ebitda": round(current_ebitda, 2),
            "depreciation": round(depreciation, 2),
            "ebit": round(ebit, 2),
            "tax":    round(tax_charge, 2),
            "capex": round(capex, 2),
            "change_nwc": round(change_nwc, 2),
            "fcff":   round(fcff, 2),
            "dcf":    round(discounted, 2),
        })

    final_fcff     = yearly[-1]["fcff"]
    terminal_value = final_fcff * (1 + terminal_growth) / (wacc - terminal_growth)
    terminal_npv   = terminal_value / ((1 + wacc) ** years)
    enterprise_value_dcf = cumulative_dcf + terminal_npv

    return {
        "yearly":               yearly,
        "cumulative_dcf":       round(cumulative_dcf, 2),
        "terminal_value":       round(terminal_value, 2),
        "terminal_value_npv":   round(terminal_npv, 2),
        "enterprise_value_dcf": round(enterprise_value_dcf, 2),
    }


# ---------------------------------------------------------------------------
# Illiquidity discount (Damodaran bid-ask spread regression)
# ---------------------------------------------------------------------------

def compute_illiquidity_discount(
    revenues: float,
    is_profitable: bool,
    cash: float,
    ev: float,
    iterations: int = 2,
) -> float:
    """
    Compute illiquidity discount rate using Damodaran bid-ask spread regression formula.
    Returns discount as a decimal (e.g. 0.12 for 12%).

    Formula:
        illiquidity_discount = 0.145
            - 0.0022 x ln(annual_revenues)
            - 0.015  x is_profitable          (1 if NPBT > 0, else 0)
            - 0.016  x (cash / enterprise_value)
            - 0.11   x (monthly_trading_volume / enterprise_value)   [= 0 for private companies]

    For private SMEs: monthly_trading_volume = 0 (no public market).
    cash = cash and bank balance from extracted balance sheet.

    Circular dependency note (VALUATION-ALGORITHM.md Known Limitations #4):
    The discount depends on EV, but EV is what we're computing. Solved with `iterations`
    iterations starting from the initial EV estimate (typically the average of multiples and DCF).

    Result is clamped to [0%, 50%] to prevent nonsensical valuations.
    """
    if ev <= 0:
        return 0.0

    discount = 0.0
    current_ev = ev

    for _ in range(iterations):
        cash_ratio = cash / current_ev if current_ev > 0 else 0.0
        ln_rev     = math.log(revenues) if revenues > 0 else 0.0
        discount = (
            0.145
            - 0.0022 * ln_rev
            - 0.015  * (1 if is_profitable else 0)
            - 0.016  * cash_ratio
            # 0.11 * (trading_vol / ev) = 0 for private companies (no public market)
        )
        # Clamp to [0%, 50%] -- prevents negative concluded values from extreme discount rates
        discount    = max(0.0, min(discount, 0.50))
        current_ev  = ev * (1 - discount)

    return round(discount, 6)


# ---------------------------------------------------------------------------
# Comparable-multiples cross-check
# ---------------------------------------------------------------------------

def compute_multiples_range(
    normalised_ebitda: float,
    ev_ebitda_low: float,
    ev_ebitda_high: float,
) -> dict:
    """Return a transparent market range without a user scoring model.

    Public research supplies the observed low/high EV/EBITDA range. The DCF
    remains the primary method; this calculation shows the corresponding
    market range and midpoint for comparison.
    """
    if normalised_ebitda < 0:
        raise ValueError("normalised_ebitda must be non-negative")
    if ev_ebitda_low <= 0 or ev_ebitda_high <= 0:
        raise ValueError("EV/EBITDA multiples must be positive")
    if ev_ebitda_low >= ev_ebitda_high:
        raise ValueError("ev_ebitda_low must be less than ev_ebitda_high")

    multiple_mid = (ev_ebitda_low + ev_ebitda_high) / 2
    return {
        "multiple_low": round(ev_ebitda_low, 2),
        "multiple_mid": round(multiple_mid, 2),
        "multiple_high": round(ev_ebitda_high, 2),
        "enterprise_value_low": round(normalised_ebitda * ev_ebitda_low, 0),
        "enterprise_value_mid": round(normalised_ebitda * multiple_mid, 0),
        "enterprise_value_high": round(normalised_ebitda * ev_ebitda_high, 0),
        "normalised_ebitda": round(normalised_ebitda, 0),
    }


def _period_year(period: object) -> int | None:
    """Extract a financial year from a statement period label."""
    text = str(period or "")
    range_match = re.search(r"(?<!\d)((?:19|20)\d{2})\s*[/\-.]\s*(\d{2})(?!\d)", text)
    if range_match:
        start_year = int(range_match.group(1))
        end_suffix = int(range_match.group(2))
        century = start_year - (start_year % 100)
        end_year = century + end_suffix
        if end_year <= start_year:
            end_year += 100
        if 0 < end_year - start_year <= 1:
            return end_year
    four_digit_matches = re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text)
    if four_digit_matches:
        return int(four_digit_matches[-1])
    two_digit_matches = re.findall(r"(?<!\d)(\d{2})(?!\d)", text)
    if not two_digit_matches:
        return None
    year = int(two_digit_matches[-1])
    return 2000 + year if year < 80 else 1900 + year


def _revenue_history_sort_key(entry: tuple[str, float]) -> tuple[int, int | str, str]:
    """Sort revenue history chronologically when period labels include years."""
    period = str(entry[0])
    year = _period_year(period)
    if year is not None:
        return (0, year, period)
    return (1, period, period)


def select_revenue_growth_assumption(
    revenue_history: list[tuple[str, float]],
    outlook: str,
    custom_growth_pct: Optional[float] = None,
) -> tuple[float, str]:
    """Translate management-friendly outlook input into a documented DCF assumption.

    Management can choose ``not_sure`` instead of estimating a technical growth
    percentage. In that case, the function uses the CAGR in uploaded revenue
    history, conservatively capped between -5% and 12%. If there is not enough
    usable history, it falls back to 2% rather than assuming high growth.
    """
    if custom_growth_pct is not None:
        return round(float(custom_growth_pct), 1), "management_custom_override"

    outlook_growth_rates = {
        "lower": -5.0,
        "steady": 2.0,
        "modest_growth": 8.0,
        "strong_growth": 15.0,
    }
    if outlook in outlook_growth_rates:
        return outlook_growth_rates[outlook], f"management_outlook_{outlook}"
    if outlook != "not_sure":
        raise ValueError(f"Unsupported revenue outlook: {outlook}")

    usable_history = sorted(
        (
            (str(period), float(value))
            for period, value in revenue_history
            if value is not None and float(value) > 0
        ),
        key=_revenue_history_sort_key,
    )
    if len(usable_history) < 2:
        return 2.0, "insufficient_history_fallback"

    first_year = _period_year(usable_history[0][0])
    latest_year = _period_year(usable_history[-1][0])
    first_value = usable_history[0][1]
    latest_value = usable_history[-1][1]
    years = (
        latest_year - first_year
        if first_year is not None and latest_year is not None and latest_year > first_year
        else len(usable_history) - 1
    )
    historical_cagr_pct = ((latest_value / first_value) ** (1 / years) - 1) * 100
    conservative_pct = max(-5.0, min(historical_cagr_pct, 12.0))
    return round(conservative_pct, 1), "historical_revenue_cagr_capped"


def derive_reinvestment_assumptions(
    balance_sheet_values: dict[str, float],
    revenue: float,
    depreciation: float,
) -> dict:
    """Derive DCF reinvestment inputs from extracted financial statements.

    Operating working capital excludes cash and interest-bearing debt. Detailed
    operating line items are preferred; current totals are a fallback. The
    working-capital ratio is capped to prevent extraction outliers from
    dominating the valuation.
    """
    operating_asset_keys = (
        "trade_debtors",
        "inventory",
        "other_current_assets",
    )
    operating_liability_keys = (
        "trade_creditors",
        "other_current_liab",
    )
    has_detailed = any(
        key in balance_sheet_values and balance_sheet_values[key] is not None
        for key in operating_asset_keys + operating_liability_keys
    )

    def absolute_value(key: str) -> float:
        return abs(float(balance_sheet_values.get(key) or 0.0))

    if has_detailed:
        operating_working_capital = (
            sum(absolute_value(key) for key in operating_asset_keys)
            - sum(absolute_value(key) for key in operating_liability_keys)
        )
        source = "extracted_operating_line_items"
    elif (
        balance_sheet_values.get("total_current_assets") is not None
        or balance_sheet_values.get("total_current_liab") is not None
    ):
        operating_working_capital = (
            absolute_value("total_current_assets")
            - absolute_value("cash_and_bank")
            - (
                absolute_value("total_current_liab")
                - absolute_value("short_term_debt")
            )
        )
        source = "extracted_current_totals"
    else:
        operating_working_capital = 0.0
        source = "insufficient_history_zero_assumption"

    raw_ratio = operating_working_capital / revenue if revenue > 0 else 0.0
    capped_ratio = max(-0.10, min(raw_ratio, 0.30))
    maintenance_capex = max(float(depreciation or 0.0), 0.0)
    return {
        "depreciation_base": maintenance_capex,
        "maintenance_capex": maintenance_capex,
        "operating_working_capital": round(operating_working_capital, 2),
        "working_capital_ratio": round(capped_ratio, 6),
        "working_capital_ratio_pct": round(capped_ratio * 100, 2),
        "working_capital_source": source,
    }


def compute_dcf_sensitivity_matrix(
    *,
    ebitda: float,
    revenue: float,
    depreciation_per_year: float,
    capex_per_year: float,
    working_capital_ratio: float,
    wacc_by_valuation_scenario_pct: dict[str, float],
    base_growth_pct: float,
    tax_rate: float,
    years: int,
    terminal_growth_pct: float,
    illiquidity_discount: float,
    growth_step_pct: float = 2.0,
) -> dict:
    """Compute a 3x3 adjusted-EV matrix without asking for additional user inputs."""
    growth_rates = [
        round(max(-20.0, base_growth_pct - growth_step_pct), 2),
        round(base_growth_pct, 2),
        round(min(30.0, base_growth_pct + growth_step_pct), 2),
    ]
    scenarios = ("high", "mid", "low")
    rows = []
    for growth_pct in growth_rates:
        values = {"growth_pct": growth_pct}
        for scenario in scenarios:
            wacc_pct = float(wacc_by_valuation_scenario_pct[scenario])
            dcf = compute_dcf(
                ebitda=ebitda,
                revenue=revenue,
                depreciation_per_year=depreciation_per_year,
                capex_per_year=capex_per_year,
                working_capital_ratio=working_capital_ratio,
                wacc=wacc_pct / 100.0,
                growth_rate=growth_pct / 100.0,
                tax_rate=tax_rate,
                years=years,
                terminal_growth=terminal_growth_pct / 100.0,
            )
            values[scenario] = round(
                float(dcf["enterprise_value_dcf"]) * (1.0 - illiquidity_discount),
                0,
            )
        rows.append(values)

    return {
        "growth_rates_pct": growth_rates,
        "wacc_by_valuation_scenario_pct": {
            scenario: float(wacc_by_valuation_scenario_pct[scenario])
            for scenario in scenarios
        },
        "adjusted_enterprise_value_rows": rows,
    }


def build_sensitivity_analysis_table(
    sensitivity_matrix: dict,
    *,
    base_growth_pct: float,
) -> dict:
    """Build a report-ready sensitivity table from the computed DCF matrix."""
    wacc = sensitivity_matrix.get("wacc_by_valuation_scenario_pct") or {}
    matrix_rows = sensitivity_matrix.get("adjusted_enterprise_value_rows") or []
    headers = [
        "Growth assumption",
        f"High valuation / {_percentage_cell(float(wacc.get('high') or 0.0))} WACC",
        f"Mid valuation / {_percentage_cell(float(wacc.get('mid') or 0.0))} WACC",
        f"Low valuation / {_percentage_cell(float(wacc.get('low') or 0.0))} WACC",
    ]
    rows: list[list[str]] = []
    for row in matrix_rows:
        if not isinstance(row, dict):
            continue
        growth_pct = float(row.get("growth_pct") or 0.0)
        growth_label = _percentage_cell(growth_pct)
        if abs(growth_pct - float(base_growth_pct or 0.0)) <= 0.05:
            growth_label = f"{growth_label} - base"
        rows.append([
            growth_label,
            _currency_cell(float(row.get("high") or 0.0)),
            _currency_cell(float(row.get("mid") or 0.0)),
            _currency_cell(float(row.get("low") or 0.0)),
        ])

    return {
        "headers": headers,
        "rows": rows,
    }


def build_forecast_cash_flow_schedule(dcf_scenario: dict) -> dict:
    """Build a report-ready mid-case cash-flow schedule from computed DCF rows."""
    yearly = dcf_scenario.get("yearly") or []
    if not isinstance(yearly, list) or not yearly:
        return {"headers": [], "rows": []}

    def value_for(row: dict, key: str) -> float:
        try:
            return float(row.get(key) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    years = [f"Year {int(value_for(row, 'year'))}" for row in yearly]
    rows = []
    for label, key in (
        ("Revenue", "revenue"),
        ("EBITDA", "ebitda"),
        ("EBIT", "ebit"),
        ("Tax", "tax"),
        ("Maintenance capex", "capex"),
        ("Change in operating working capital", "change_nwc"),
        ("Free cash flow to firm", "fcff"),
        ("Discounted free cash flow", "dcf"),
    ):
        rows.append([label] + [round(value_for(row, key), 0) for row in yearly])

    return {
        "headers": ["Mid-case forecast"] + years,
        "rows": rows,
    }


def build_normalisation_schedule_table(
    normalisations: list[dict] | None,
    *,
    normalised_ebitda: float,
) -> dict:
    """Build a report-ready normalisation table from the earnings review.

    The self-serve wizard always submits ``normalisations`` once the customer
    reaches the earnings-review step. An explicit empty list means the customer
    confirmed no genuine add-backs for this upload; represent that as a clear
    table row rather than asking the language model to improvise.
    """
    rows: list[list[str]] = []
    for item in normalisations or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        amount = float(item.get("amount") or 0)
        rationale = str(item.get("rationale") or "").strip() or "Confirmed in the earnings review."
        rows.append([label, _bridge_cell(amount), rationale])

    if not rows:
        rows.append([
            "No adjustments confirmed",
            "$0",
            "The earnings review did not identify genuine one-off, owner-specific or non-operating items for this upload.",
        ])

    rows.append([
        "Normalised EBITDA",
        f"${float(normalised_ebitda):,.0f}",
        "Uploaded earnings basis plus the confirmed adjustments above.",
    ])

    return {
        "headers": ["Label", "Amount ($)", "Rationale"],
        "rows": rows,
    }


def build_assumption_source_trail(
    *,
    normalised_ebitda: float,
    forecast_years: int,
    revenue_growth_pct: float,
    growth_assumption_source: str,
    terminal_growth_pct: float,
    wacc_by_valuation_scenario_pct: dict[str, float],
    maintenance_capex: float,
    working_capital_ratio_pct: float,
    working_capital_source: str,
    gross_debt: float,
    cash: float,
    surplus_assets: float,
    owner_dependency: str = "",
    customer_concentration: str = "",
    revenue_quality: str = "",
    revenue_outlook: str = "",
    debt_override_used: bool = False,
    surplus_assets_supplied: bool = False,
) -> dict:
    """Build a report-ready assumption/source trail without new owner questions."""
    wacc_range = (
        f"{float(wacc_by_valuation_scenario_pct.get('high', 0)):.1f}% / "
        f"{float(wacc_by_valuation_scenario_pct.get('mid', 0)):.1f}% / "
        f"{float(wacc_by_valuation_scenario_pct.get('low', 0)):.1f}%"
    )
    return {
        "headers": ["Assumption / input", "Value used", "Primary source", "Why it matters"],
        "rows": [
            [
                "Normalised EBITDA",
                f"${float(normalised_ebitda):,.0f}",
                "Uploaded financial statements plus management-confirmed earnings adjustments",
                "Sets the maintainable earnings base for DCF and multiples cross-checks.",
            ],
            [
                "Explicit forecast period",
                f"{int(forecast_years)} years",
                "AccountIQ valuation model convention",
                "Defines the period over which cash flows are forecast before terminal value.",
            ],
            [
                "Revenue and earnings growth",
                f"{float(revenue_growth_pct):.1f}%",
                growth_assumption_source_label(growth_assumption_source),
                "Drives the forecast cash-flow build and sensitivity matrix.",
            ],
            [
                "Terminal growth",
                f"{float(terminal_growth_pct):.1f}%",
                "Public research: New Zealand inflation input",
                "Anchors long-term growth and must remain below the discount rate.",
            ],
            [
                "WACC scenarios: high / mid / low valuation",
                wacc_range,
                "Public research: RBNZ risk-free rate and Damodaran ERP/beta",
                "Discounts forecast cash flows and creates the valuation range.",
            ],
            [
                "Maintenance capital expenditure",
                f"${float(maintenance_capex):,.0f}",
                "Uploaded financial statements: depreciation proxy",
                "Converts EBITDA into free cash flow by allowing for asset reinvestment.",
            ],
            [
                "Operating working capital ratio",
                f"{float(working_capital_ratio_pct):.1f}%",
                working_capital_source_label(working_capital_source),
                "Captures the cash investment required to support revenue growth.",
            ],
            [
                "Debt, cash and surplus assets",
                (
                    f"Debt ${float(gross_debt):,.0f}; "
                    f"cash ${float(cash):,.0f}; "
                    f"surplus assets ${float(surplus_assets):,.0f}"
                ),
                debt_cash_surplus_source_label(
                    debt_override_used=debt_override_used,
                    surplus_assets_supplied=surplus_assets_supplied,
                ),
                "Bridges enterprise value to indicative equity value.",
            ],
            [
                "Owner or key-person dependency",
                report_answer_label("owner_dependency", owner_dependency),
                "Management-confirmed private input",
                "Informs transition risk, key-person exposure and continuity planning.",
            ],
            [
                "Largest-customer concentration",
                report_answer_label("customer_concentration", customer_concentration),
                "Management-confirmed private input",
                "Highlights concentration risk that is not usually visible online.",
            ],
            [
                "Revenue predictability",
                report_answer_label("revenue_quality", revenue_quality),
                "Management-confirmed private input",
                "Distinguishes contracted revenue from transactional or project income.",
            ],
            [
                "Revenue outlook",
                report_answer_label("revenue_outlook", revenue_outlook),
                "Management-confirmed private input",
                "Documents the short-term outlook used to support or derive the growth assumption.",
            ],
        ],
    }


def build_specific_risk_factor_table(
    *,
    owner_dependency: str = "",
    customer_concentration: str = "",
    revenue_quality: str = "",
    revenue_outlook: str = "",
    private_context: str = "",
) -> dict:
    """Build a report-ready specific-risk table from the short management intake."""

    owner_treatment = {
        "independent": "Lower key-person risk; confirm management retention and delegated authority.",
        "shared": "Moderate transition risk; diligence should confirm responsibilities and handover depth.",
        "important": "Elevated key-person risk; transition support or retention planning may be required.",
        "critical": "High owner or key-person dependency risk; valuation should be read subject to succession and transition planning.",
        "unknown": "Uncertain key-person risk; diligence should test management depth and delegated authority.",
    }.get(owner_dependency, "Diligence should confirm owner or key-person involvement and transition requirements.")

    customer_treatment = {
        "under_10": "Diversified revenue base reduces single-customer exposure.",
        "10_to_25": "Moderate concentration risk; review top-customer retention and contract terms.",
        "over_25": "High concentration risk; value is sensitive to retention of the largest customer.",
        "consumer_or_diversified": "Broad customer base reduces named-account concentration risk.",
        "unknown": "Customer concentration is uncertain; diligence should review customer revenue analysis.",
    }.get(customer_concentration, "Diligence should confirm customer concentration.")

    revenue_treatment = {
        "mostly_contract": "Recurring or contracted income improves earnings visibility, subject to renewal terms.",
        "mixed": "Mixed recurring and project revenue creates moderate earnings visibility.",
        "mostly_one_off": "Transactional revenue increases forecast risk and may reduce cash-flow confidence.",
        "unknown": "Revenue quality is uncertain; diligence should test recurring revenue and churn.",
    }.get(revenue_quality, "Diligence should confirm revenue predictability.")

    outlook_treatment = {
        "lower": "Downside outlook is reflected in the growth assumption and should be monitored before reliance.",
        "steady": "Stable outlook supports a conservative base case, subject to maintaining current revenue.",
        "modest_growth": "Modest growth supports the base forecast, subject to delivery and customer retention.",
        "strong_growth": "Strong growth should be supported by signed pipeline, contracts or visible demand.",
        "not_sure": "Growth is derived from uploaded history rather than a management forecast; review pipeline evidence before reliance.",
    }.get(revenue_outlook, "Growth outlook should be reconciled to financial history and pipeline evidence.")

    context = str(private_context or "").strip()
    context_treatment = (
        "Management-supplied context should be confirmed and reflected in diligence, forecast cases or reliance limitations."
        if context
        else "No additional private context supplied; the report relies on the five required private-fact answers."
    )

    return {
        "headers": ["Specific risk factor", "Management input", "Valuation relevance", "Report treatment"],
        "rows": [
            [
                "Owner or key-person transition",
                report_answer_label("owner_dependency", owner_dependency),
                "Affects operating continuity, handover depth and confidence in maintainable earnings.",
                owner_treatment,
            ],
            [
                "Customer concentration",
                report_answer_label("customer_concentration", customer_concentration),
                "Large customer exposure can increase earnings volatility and diligence risk.",
                customer_treatment,
            ],
            [
                "Revenue predictability",
                report_answer_label("revenue_quality", revenue_quality),
                "Contracted or recurring revenue usually supports more reliable cash-flow forecasts.",
                revenue_treatment,
            ],
            [
                "Revenue outlook and pipeline",
                report_answer_label("revenue_outlook", revenue_outlook),
                "Growth expectations affect forecast cash flows and sensitivity cases.",
                outlook_treatment,
            ],
            [
                "Other private context",
                context if context else "Not supplied",
                "Captures risks or opportunities not normally visible in public research.",
                context_treatment,
            ],
        ],
    }
