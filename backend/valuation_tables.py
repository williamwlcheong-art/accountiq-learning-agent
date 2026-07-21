"""Python-owned structured tables for Valuation Advisory reports."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import json
import re
from typing import Any

from fcff_engine import FCFFResult
from report_prompts import TABLE_SECTIONS_VALUATION
from valuation_inputs import ValuationInputs


TABLES_VERSION = "valuation-tables-v1"
TABLES_ROUNDING_POLICY = "half-even-money-percent-2dp-beta-4dp-v1"
_MONEY_QUANTUM = Decimal("0.01")
_PERCENT_QUANTUM = Decimal("0.01")
_RATIO_QUANTUM = Decimal("0.0001")
_UNIT_FACTORS = {
    "whole": Decimal("1"),
    "thousands": Decimal("1000"),
    "millions": Decimal("1000000"),
}
_SCENARIO_LABELS = {
    "high_wacc_low_value": "High WACC / Low Value",
    "mid_wacc_mid_value": "Mid WACC / Mid Value",
    "low_wacc_high_value": "Low WACC / High Value",
}
_PNL_ORDER = (
    "revenue",
    "cost_of_sales",
    "gross_profit",
    "ebitda",
    "depreciation",
    "depreciation_and_amortisation",
    "ebit",
    "interest_expense",
    "tax_expense",
    "net_profit",
)


def _decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _format_decimal(value: Any, quantum: Decimal, *, grouping: bool = False) -> str:
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        rounded = _decimal(value).quantize(quantum)
    return format(rounded, ",.2f" if grouping else "f")


def _money(value: Any) -> str:
    return _format_decimal(value, _MONEY_QUANTUM, grouping=True)


def _percent(value: Any) -> str:
    return f"{_format_decimal(_decimal(value) * 100, _PERCENT_QUANTUM)}%"


def _ratio(value: Any) -> str:
    return _format_decimal(value, _RATIO_QUANTUM)


def _multiple(value: Any) -> str:
    return f"{_format_decimal(value, _PERCENT_QUANTUM)}x"


def _period_sort_key(period: str) -> tuple[int, str]:
    match = re.search(r"(?:19|20)\d{2}", period)
    return (int(match.group()) if match else 0, period)


def _financial_performance_table(
    financial_rows: list[dict],
    currency: str,
) -> dict[str, list]:
    pnl_rows = [
        row for row in financial_rows
        if row.get("statement") == "pnl" and row.get("value") is not None
    ]
    periods = sorted(
        {str(row.get("period") or "") for row in pnl_rows if row.get("period")},
        key=_period_sort_key,
    )
    grouped: dict[str, dict[str, Any]] = {}
    for row in pnl_rows:
        key = str(row.get("row_key") or "")
        period = str(row.get("period") or "")
        unit = str(row.get("unit") or "").lower()
        if not key or not period or unit not in _UNIT_FACTORS:
            raise ValueError("financial performance rows are incomplete")
        entry = grouped.setdefault(key, {
            "label": str(row.get("row_label") or key.replace("_", " ").title()),
            "values": {},
        })
        if period in entry["values"]:
            raise ValueError("financial performance contains duplicate period values")
        entry["values"][period] = _decimal(row["value"]) * _UNIT_FACTORS[unit]

    order = {key: index for index, key in enumerate(_PNL_ORDER)}
    rows = []
    for key, entry in sorted(
        grouped.items(),
        key=lambda item: (order.get(item[0], len(order)), item[1]["label"].lower()),
    ):
        rows.append([
            entry["label"],
            *(
                _money(entry["values"][period])
                if period in entry["values"] else "—"
                for period in periods
            ),
        ])
    return {"headers": [f"Metric ({currency})", *periods], "rows": rows}


def _normalisations_table(inputs: ValuationInputs) -> dict[str, list]:
    rows = [
        [item.label, _money(item.amount), item.rationale]
        for item in inputs.normalisations
    ]
    if not rows:
        rows = [["No approved normalisations", _money(Decimal("0")), "None"]]
    return {
        "headers": ["Label", f"Amount ({inputs.currency})", "Rationale"],
        "rows": rows,
    }


def _balance_sheet_table(result: FCFFResult) -> dict[str, list]:
    return {
        "headers": ["Item", f"Value ({result.currency})"],
        "rows": [
            ["Interest-bearing debt", _money(result.interest_bearing_debt)],
            ["Unrestricted cash", _money(result.unrestricted_cash)],
            ["Net debt", _money(result.net_debt)],
            ["Approved surplus assets", _money(result.approved_surplus_assets)],
        ],
    }


def _wacc_table(result: FCFFResult) -> dict[str, list]:
    wacc = result.wacc
    scenario_rates = {scenario.name: scenario.wacc for scenario in result.scenarios}
    names = tuple(_SCENARIO_LABELS)
    shared = (
        ("Risk-free rate", _percent(wacc.risk_free_rate)),
        ("Equity risk premium", _percent(wacc.equity_risk_premium)),
        ("Beta", _ratio(wacc.beta)),
        ("Additional premium", _percent(wacc.additional_premium)),
        ("Pre-tax cost of debt", _percent(wacc.pre_tax_cost_of_debt)),
        ("Target debt weight", _percent(wacc.target_debt_weight)),
        ("Target equity weight", _percent(wacc.target_equity_weight)),
        ("Cost of equity", _percent(wacc.cost_of_equity)),
        ("After-tax cost of debt", _percent(wacc.after_tax_cost_of_debt)),
    )
    rows = [[label, *(value for _ in names)] for label, value in shared]
    rows.append(["WACC", *(_percent(scenario_rates[name]) for name in names)])
    return {
        "headers": ["Component", *(_SCENARIO_LABELS[name] for name in names)],
        "rows": rows,
    }


def _valuation_summary_table(result: FCFFResult) -> dict[str, list]:
    rows = []
    for scenario in result.scenarios:
        rows.append([
            _SCENARIO_LABELS[scenario.name],
            _percent(scenario.wacc),
            _money(scenario.enterprise_value),
            _money(scenario.net_debt),
            _money(scenario.pre_dlom_equity_value),
            f"{_percent(scenario.dlom_rate)} / {_money(scenario.dlom_amount)}",
            _money(scenario.equity_value),
        ])
    return {
        "headers": [
            "Scenario",
            "WACC",
            f"Enterprise Value ({result.currency})",
            f"Net Debt ({result.currency})",
            f"Pre-DLOM Equity ({result.currency})",
            f"DLOM (Rate / {result.currency})",
            f"Equity Value ({result.currency})",
        ],
        "rows": rows,
    }


def _multiples_table(multiples: dict) -> dict[str, list]:
    required = (
        "multiple_low",
        "multiple_high",
        "normalised_ebitda",
        "enterprise_value_low",
        "enterprise_value_high",
    )
    if any(multiples.get(key) is None for key in required):
        raise ValueError("deterministic multiples cross-check is incomplete")
    return {
        "headers": ["Input", "Low", "High"],
        "rows": [
            ["Market multiple", _multiple(multiples["multiple_low"]), _multiple(multiples["multiple_high"])],
            ["Normalised EBITDA", _money(multiples["normalised_ebitda"]), _money(multiples["normalised_ebitda"])],
            ["Indicated enterprise value", _money(multiples["enterprise_value_low"]), _money(multiples["enterprise_value_high"])],
        ],
    }


def build_valuation_tables(
    financial_rows: list[dict],
    inputs: ValuationInputs,
    fcff_result: FCFFResult,
    multiples_result: dict,
) -> dict[str, Any]:
    """Build and digest every structured Valuation Advisory table."""
    sections = {
        "financial_performance": _financial_performance_table(financial_rows, inputs.currency),
        "normalisations_schedule": _normalisations_table(inputs),
        "balance_sheet_summary": _balance_sheet_table(fcff_result),
        "wacc_assumptions": _wacc_table(fcff_result),
        "valuation_summary": _valuation_summary_table(fcff_result),
        "multiples_crosscheck": _multiples_table(multiples_result),
    }
    if list(sections) != TABLE_SECTIONS_VALUATION:
        raise ValueError("deterministic valuation table order does not match the report schema")
    authority = {
        "version": TABLES_VERSION,
        "rounding_policy": TABLES_ROUNDING_POLICY,
        "sections": sections,
    }
    return {**authority, "digest": _authority_digest(authority)}


def _authority_digest(authority: dict) -> str:
    encoded = json.dumps(
        authority,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def valuation_table_sections(table_authority: dict) -> dict:
    """Validate table authority metadata and return its ordered sections."""
    if not isinstance(table_authority, dict):
        raise ValueError("deterministic valuation tables are missing")
    authority = {
        "version": table_authority.get("version"),
        "rounding_policy": table_authority.get("rounding_policy"),
        "sections": table_authority.get("sections"),
    }
    if authority["version"] != TABLES_VERSION:
        raise ValueError("unsupported deterministic valuation table version")
    if authority["rounding_policy"] != TABLES_ROUNDING_POLICY:
        raise ValueError("unsupported deterministic valuation table rounding policy")
    sections = authority["sections"]
    if not isinstance(sections, dict) or list(sections) != TABLE_SECTIONS_VALUATION:
        raise ValueError("deterministic valuation tables are incomplete")
    if table_authority.get("digest") != _authority_digest(authority):
        raise ValueError("deterministic valuation table digest verification failed")
    return sections


def attach_valuation_tables(content_json: dict, table_authority: dict) -> dict:
    """Replace all model-supplied valuation tables with Python-owned tables."""
    if not isinstance(content_json, dict):
        raise ValueError("generated report must be a JSON object")
    sections = valuation_table_sections(table_authority)

    assembled = deepcopy(content_json)
    for section_name in TABLE_SECTIONS_VALUATION:
        content = assembled.get(section_name)
        narrative = content.get("narrative") if isinstance(content, dict) else content
        assembled[section_name] = {
            "narrative": narrative,
            "table": deepcopy(sections[section_name]),
        }
    return assembled
