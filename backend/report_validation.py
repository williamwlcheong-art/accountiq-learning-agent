"""Shared fail-closed validation for generated report content."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation

from report_prompts import SECTION_SCHEMAS, TABLE_SECTIONS_VALUATION


_VALUATION_SUMMARY_HEADERS = [
    "Method",
    "Scenario",
    "Enterprise Value",
    "Interest-bearing Debt",
    "Unrestricted Cash",
    "Net Debt",
    "Surplus Assets",
    "Equity Value",
]
_SCENARIO_LABELS = {
    "high_wacc_low_value": "High WACC / Low Value",
    "mid_wacc_mid_value": "Mid WACC / Mid Value",
    "low_wacc_high_value": "Low WACC / High Value",
}


PLACEHOLDER_REPORT_PATTERNS = (
    "[section '",
    "[generation error",
    "not generated",
    "could not be parsed",
    "failed to parse",
    "please retry",
    "placeholder",
    "todo",
    "tbd",
    "lorem ipsum",
)


def section_narrative(section_content) -> str:
    if isinstance(section_content, str):
        return section_content.strip()
    if isinstance(section_content, dict):
        narrative = section_content.get("narrative")
        return narrative.strip() if isinstance(narrative, str) else ""
    return ""


def contains_report_placeholder(value) -> bool:
    if isinstance(value, str):
        lowered = value.lower()
        return any(pattern in lowered for pattern in PLACEHOLDER_REPORT_PATTERNS)
    if isinstance(value, dict):
        return any(contains_report_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_report_placeholder(item) for item in value)
    return False


def validate_report_table(section_name: str, table) -> None:
    if not isinstance(table, dict):
        raise ValueError(f"invalid table in section '{section_name}'")

    headers = table.get("headers")
    rows = table.get("rows")
    if not isinstance(headers, list) or not headers:
        raise ValueError(f"invalid table headers in section '{section_name}'")
    if any(
        not isinstance(header, (str, int, float)) or not str(header).strip()
        for header in headers
    ):
        raise ValueError(f"invalid table headers in section '{section_name}'")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"invalid table rows in section '{section_name}'")

    width = len(headers)
    for row in rows:
        if not isinstance(row, list) or len(row) != width:
            raise ValueError(f"invalid table row shape in section '{section_name}'")
        if any(isinstance(cell, (dict, list)) or cell is None for cell in row):
            raise ValueError(f"invalid table cell in section '{section_name}'")


def _table_decimal(value) -> Decimal:
    if isinstance(value, bool) or isinstance(value, (dict, list)):
        raise ValueError("valuation summary contains a non-numeric value")
    cleaned = str(value).strip().replace(",", "").replace("$", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    try:
        result = Decimal(cleaned)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("valuation summary contains a non-numeric value") from exc
    if not result.is_finite():
        raise ValueError("valuation summary contains a non-finite value")
    return result


def _table_number(value) -> float:
    return float(_table_decimal(value))


def validate_valuation_summary(content_json: dict, valuation_result: dict) -> None:
    """Require model output to reproduce the deterministic EV-to-equity bridges."""
    table = content_json["valuation_summary"]["table"]
    if table.get("headers") != _VALUATION_SUMMARY_HEADERS:
        raise ValueError("valuation summary headers do not match the deterministic contract")

    expected_bridges = valuation_result.get("scenario_bridges") or {}
    expected_rows = []
    for key in (
        "high_wacc_low_value",
        "mid_wacc_mid_value",
        "low_wacc_high_value",
    ):
        bridge = expected_bridges.get(key)
        if not isinstance(bridge, dict):
            raise ValueError("deterministic valuation bridge is incomplete")
        expected_rows.append((key, bridge))

    rows = table.get("rows", [])
    if len(rows) != len(expected_rows):
        raise ValueError("valuation summary scenario rows are incomplete")
    fields = (
        "enterprise_value",
        "interest_bearing_debt",
        "unrestricted_cash",
        "net_debt",
        "approved_surplus_assets",
        "equity_value",
    )
    for row, (key, bridge) in zip(rows, expected_rows):
        if row[0] != "DCF" or row[1] != _SCENARIO_LABELS[key]:
            raise ValueError("valuation summary scenario labels are invalid")
        actual = [_table_decimal(value) for value in row[2:]]
        expected = [Decimal(str(bridge[field])) for field in fields]
        if any(left != right for left, right in zip(actual, expected)):
            raise ValueError("valuation summary differs from deterministic valuation figures")
        if actual[3] != actual[1] - actual[2]:
            raise ValueError("valuation summary net debt does not reconcile")
        pre_dlom = bridge.get("pre_dlom_equity_value")
        dlom_amount = bridge.get("dlom_amount")
        if pre_dlom is None or dlom_amount is None:
            if actual[5] != actual[0] - actual[3] + actual[4]:
                raise ValueError("valuation summary equity value does not reconcile")
        elif actual[5] != Decimal(str(pre_dlom)) - Decimal(str(dlom_amount)):
            raise ValueError("valuation summary equity value does not reconcile")


def validate_wacc_assumptions(content_json: dict, valuation_result: dict) -> None:
    """Require model output to reproduce frozen Decimal WACC inputs and rates."""
    deterministic = valuation_result.get("deterministic_fcff") or {}
    scenarios = deterministic.get("scenarios") or []
    expected_names = list(_SCENARIO_LABELS)
    if [scenario.get("name") for scenario in scenarios] != expected_names:
        raise ValueError("deterministic WACC scenario order is invalid")

    wacc = deterministic.get("wacc") or {}
    table = content_json["wacc_assumptions"]["table"]
    expected_headers = ["Component", *(_SCENARIO_LABELS[name] for name in expected_names)]
    if table.get("headers") != expected_headers:
        raise ValueError("WACC assumptions headers do not match the deterministic contract")

    shared = (
        ("Risk-free rate", "risk_free_rate"),
        ("Equity risk premium", "equity_risk_premium"),
        ("Beta", "beta"),
        ("Additional premium", "additional_premium"),
        ("Pre-tax cost of debt", "pre_tax_cost_of_debt"),
        ("Target debt weight", "target_debt_weight"),
        ("Target equity weight", "target_equity_weight"),
        ("Cost of equity", "cost_of_equity"),
        ("After-tax cost of debt", "after_tax_cost_of_debt"),
    )
    expected_rows = [
        [label, *(wacc.get(field) for _ in expected_names)]
        for label, field in shared
    ]
    expected_rows.append(["WACC", *(scenario.get("wacc") for scenario in scenarios)])
    rows = table.get("rows", [])
    if len(rows) != len(expected_rows):
        raise ValueError("deterministic WACC assumptions rows are incomplete")
    for row, expected in zip(rows, expected_rows):
        if row[0] != expected[0]:
            raise ValueError("deterministic WACC assumptions labels are invalid")
        if any(value is None for value in expected[1:]):
            raise ValueError("deterministic WACC assumptions are incomplete")
        actual = [_table_decimal(value) for value in row[1:]]
        wanted = [Decimal(str(value)) for value in expected[1:]]
        if actual != wanted:
            raise ValueError("WACC assumptions differ from deterministic valuation figures")


def validate_multiples_crosscheck(content_json: dict, valuation_result: dict) -> None:
    """Require model output to reproduce the deterministic comparable range."""
    table = content_json["multiples_crosscheck"]["table"]
    if table.get("headers") != ["Input", "Low", "High"]:
        raise ValueError("multiples cross-check headers do not match the deterministic contract")
    multiples = valuation_result.get("multiples_result") or {}
    expected = [
        ["Market multiple", multiples.get("multiple_low"), multiples.get("multiple_high")],
        ["Normalised EBITDA", multiples.get("normalised_ebitda"), multiples.get("normalised_ebitda")],
        ["Indicated enterprise value", multiples.get("enterprise_value_low"), multiples.get("enterprise_value_high")],
    ]
    rows = table.get("rows", [])
    if len(rows) != len(expected):
        raise ValueError("multiples cross-check rows are incomplete")
    for row, expected_row in zip(rows, expected):
        if row[0] != expected_row[0]:
            raise ValueError("multiples cross-check labels are invalid")
        actual_values = [_table_number(value) for value in row[1:]]
        if any(value is None for value in expected_row[1:]):
            raise ValueError("deterministic multiples cross-check is incomplete")
        if any(
            abs(actual - float(expected_value)) > 0.01
            for actual, expected_value in zip(actual_values, expected_row[1:])
        ):
            raise ValueError("multiples cross-check differs from deterministic valuation figures")


def validate_generated_report(
    content_json: dict,
    report_type: str,
    valuation_result: dict | None = None,
) -> None:
    """Reject incomplete or malformed model output before review or release."""
    if not isinstance(content_json, dict):
        raise ValueError("generated report must be a JSON object")

    expected_sections = SECTION_SCHEMAS[report_type]
    missing = [section for section in expected_sections if section not in content_json]
    if missing:
        raise ValueError(f"missing required sections: {missing}")

    for section_name in expected_sections:
        section_content = content_json[section_name]
        if not section_narrative(section_content):
            raise ValueError(f"empty required section: {section_name}")
        if contains_report_placeholder(section_content):
            raise ValueError(f"placeholder content in section: {section_name}")

        if isinstance(section_content, dict):
            unexpected_keys = set(section_content) - {"narrative", "table"}
            if unexpected_keys:
                raise ValueError(f"invalid structured section shape: {section_name}")
            if "table" in section_content:
                validate_report_table(section_name, section_content["table"])
        elif not isinstance(section_content, str):
            raise ValueError(f"invalid section shape: {section_name}")

        if report_type == "valuation_advisory" and section_name in TABLE_SECTIONS_VALUATION:
            if not isinstance(section_content, dict) or "table" not in section_content:
                raise ValueError(f"invalid table in section '{section_name}'")

    if report_type == "valuation_advisory":
        if valuation_result is not None:
            if valuation_result.get("deterministic_fcff") is not None:
                validate_wacc_assumptions(content_json, valuation_result)
            validate_valuation_summary(content_json, valuation_result)
            validate_multiples_crosscheck(content_json, valuation_result)
        disclaimer = section_narrative(content_json["disclaimer"]).lower()
        required_phrases = (
            ("indicative",),
            ("financial advice",),
            ("fmca", "financial markets conduct"),
            ("not relied", "should not be relied"),
        )
        if any(
            not any(phrase in disclaimer for phrase in alternatives)
            for alternatives in required_phrases
        ):
            raise ValueError("valuation disclaimer is incomplete")
