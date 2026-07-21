from decimal import Decimal

import aiosqlite
import pytest

from db import DB_PATH
import main as main_module
from report_prompts import SECTION_SCHEMAS, TABLE_SECTIONS_VALUATION
from report_validation import validate_generated_report


SAFE_GENERATION_ERROR = (
    "We couldn't generate a complete report. Please retry, or contact support if the problem continues."
)


def _valid_section(section: str):
    if section in TABLE_SECTIONS_VALUATION:
        return {
            "narrative": f"Complete analysis for {section} based on the supplied financial data.",
            "table": {
                "headers": ["Metric", "Value"],
                "rows": [["Revenue", "$1,250,000"]],
            },
        }
    if section == "disclaimer":
        return (
            "This report is indicative only and does not constitute financial advice under the "
            "Financial Markets Conduct Act (FMCA). It should not be relied on without independent "
            "professional advice."
        )
    return f"Complete analysis for {section} based on the supplied financial data."


def _valid_report(report_type: str = "valuation_advisory") -> dict:
    return {section: _valid_section(section) for section in SECTION_SCHEMAS[report_type]}


def _decimal_fcff_result():
    scenarios = []
    bridges = {}
    for name, wacc, terminal_value, terminal_pv, dlom_rate, dlom_amount, ev, equity in (
        ("high_wacc_low_value", "0.11", "1400", "900", "0.10", "132", "1400", "1188"),
        ("mid_wacc_mid_value", "0.10", "1500", "1000", "0.09", "127.8", "1500", "1292.2"),
        ("low_wacc_high_value", "0.09", "1600", "1100", "0.08", "121.6", "1600", "1398.4"),
    ):
        scenarios.append({
            "name": name,
            "wacc": wacc,
            "terminal_value": terminal_value,
            "terminal_present_value": terminal_pv,
            "enterprise_value": ev,
            "net_debt": "80",
            "approved_surplus_assets": "0",
            "pre_dlom_equity_value": str(Decimal(ev) - Decimal("80")),
            "dlom_rate": dlom_rate,
            "dlom_amount": dlom_amount,
            "equity_value": equity,
        })
        bridges[name] = {
            "enterprise_value": Decimal(ev),
            "interest_bearing_debt": Decimal("100"),
            "unrestricted_cash": Decimal("20"),
            "net_debt": Decimal("80"),
            "approved_surplus_assets": Decimal("0"),
            "pre_dlom_equity_value": Decimal(ev) - Decimal("80"),
            "dlom_amount": Decimal(dlom_amount),
            "equity_value": Decimal(equity),
        }
    return {
        "deterministic_fcff": {
            "engine_version": "fcff-decimal-v1",
            "forecast": [
                {"year": 1, "fcff": "100"},
                {"year": 2, "fcff": "110"},
            ],
            "terminal_forecast": {"year": 3, "fcff": "120"},
            "wacc": {
                "risk_free_rate": "0.04",
                "equity_risk_premium": "0.055",
                "beta": "1.1",
                "additional_premium": "0.02",
                "pre_tax_cost_of_debt": "0.06",
                "target_debt_weight": "0.3",
                "target_equity_weight": "0.7",
                "cost_of_equity": "0.1205",
                "after_tax_cost_of_debt": "0.0432",
                "high": "0.11",
                "mid": "0.10",
                "low": "0.09",
            },
            "scenarios": scenarios,
        },
        "scenario_bridges": bridges,
        "multiples_result": {
            "multiple_low": 3, "multiple_high": 4,
            "normalised_ebitda": 100,
            "enterprise_value_low": 300, "enterprise_value_high": 400,
        },
    }


def _set_decimal_fcff_tables(report):
    report["wacc_assumptions"]["table"] = {
        "headers": [
            "Component", "High WACC / Low Value", "Mid WACC / Mid Value",
            "Low WACC / High Value",
        ],
        "rows": [
            ["Risk-free rate", "0.04", "0.04", "0.04"],
            ["Equity risk premium", "0.055", "0.055", "0.055"],
            ["Beta", "1.1", "1.1", "1.1"],
            ["Additional premium", "0.02", "0.02", "0.02"],
            ["Pre-tax cost of debt", "0.06", "0.06", "0.06"],
            ["Target debt weight", "0.3", "0.3", "0.3"],
            ["Target equity weight", "0.7", "0.7", "0.7"],
            ["Cost of equity", "0.1205", "0.1205", "0.1205"],
            ["After-tax cost of debt", "0.0432", "0.0432", "0.0432"],
            ["WACC", "0.11", "0.10", "0.09"],
        ],
    }
    report["valuation_summary"]["table"] = {
        "headers": [
            "Method", "Scenario", "Enterprise Value", "Interest-bearing Debt",
            "Unrestricted Cash", "Net Debt", "Surplus Assets", "Equity Value",
        ],
        "rows": [
            ["DCF", "High WACC / Low Value", "1400", "100", "20", "80", "0", "1188"],
            ["DCF", "Mid WACC / Mid Value", "1500", "100", "20", "80", "0", "1292.2"],
            ["DCF", "Low WACC / High Value", "1600", "100", "20", "80", "0", "1398.4"],
        ],
    }
    report["multiples_crosscheck"]["table"] = {
        "headers": ["Input", "Low", "High"],
        "rows": [
            ["Market multiple", "3", "4"],
            ["Normalised EBITDA", "100", "100"],
            ["Indicated enterprise value", "300", "400"],
        ],
    }


@pytest.mark.parametrize(
    "raw_text",
    [
        "not JSON",
        '{"introduction": "truncated"',
        "```json\nnot JSON\n```",
    ],
)
def test_report_parser_rejects_malformed_json(raw_text):
    with pytest.raises(ValueError, match="valid JSON object"):
        main_module._parse_json_from_response(raw_text)


@pytest.mark.parametrize(
    ("mutate", "error_match"),
    [
        (lambda report: report.pop("business_overview"), "missing required sections"),
        (lambda report: report.__setitem__("business_overview", "  "), "empty required section"),
        (
            lambda report: report.__setitem__(
                "business_overview", "[Section 'business_overview' not generated — please retry]"
            ),
            "placeholder content",
        ),
        (
            lambda report: report["financial_performance"]["table"]["rows"].__setitem__(
                0, ["Revenue", "[Generation error — please retry]"]
            ),
            "placeholder content",
        ),
        (
            lambda report: report["financial_performance"].__setitem__(
                "table", {"headers": ["Metric", "Value"], "rows": [["Revenue"]]}
            ),
            "invalid table",
        ),
        (
            lambda report: report.__setitem__(
                "disclaimer", "This report contains a preliminary valuation estimate."
            ),
            "disclaimer",
        ),
    ],
)
def test_generated_valuation_validation_fails_closed(mutate, error_match):
    report = _valid_report()
    mutate(report)

    with pytest.raises(ValueError, match=error_match):
        validate_generated_report(report, "valuation_advisory")


def test_valuation_summary_must_match_deterministic_bridge():
    report = _valid_report()
    report["valuation_summary"]["table"] = {
        "headers": [
            "Method", "Scenario", "Enterprise Value", "Interest-bearing Debt",
            "Unrestricted Cash", "Net Debt", "Surplus Assets", "Equity Value",
        ],
        "rows": [
            ["DCF", "High WACC / Low Value", "400", "100", "20", "80", "0", "320"],
            ["DCF", "Mid WACC / Mid Value", "500", "100", "20", "80", "0", "420"],
            ["DCF", "Low WACC / High Value", "600", "100", "20", "80", "0", "520"],
        ],
    }
    bridges = {
        "scenario_bridges": {
            key: {
                "enterprise_value": ev,
                "interest_bearing_debt": 100,
                "unrestricted_cash": 20,
                "net_debt": 80,
                "approved_surplus_assets": 0,
                "equity_value": ev - 80,
            }
            for key, ev in (
                ("high_wacc_low_value", 400),
                ("mid_wacc_mid_value", 500),
                ("low_wacc_high_value", 600),
            )
        },
        "multiples_result": {
            "multiple_low": 3.0,
            "multiple_high": 4.0,
            "normalised_ebitda": 100,
            "enterprise_value_low": 300,
            "enterprise_value_high": 400,
        },
    }
    report["multiples_crosscheck"]["table"] = {
        "headers": ["Input", "Low", "High"],
        "rows": [
            ["Market multiple", "3", "4"],
            ["Normalised EBITDA", "100", "100"],
            ["Indicated enterprise value", "300", "400"],
        ],
    }
    validate_generated_report(report, "valuation_advisory", bridges)

    report["valuation_summary"]["table"]["rows"][1][-1] = "421"
    with pytest.raises(ValueError, match="differs from deterministic"):
        validate_generated_report(report, "valuation_advisory", bridges)


def test_valuation_summary_accepts_exact_decimal_fcff_bridges():
    report = _valid_report()
    report["valuation_summary"]["table"] = {
        "headers": [
            "Method", "Scenario", "Enterprise Value", "Interest-bearing Debt",
            "Unrestricted Cash", "Net Debt", "Surplus Assets", "Equity Value",
        ],
        "rows": [
            ["DCF", "High WACC / Low Value", "400.123", "100", "20", "80", "0", "288.1107"],
            ["DCF", "Mid WACC / Mid Value", "500.123", "100", "20", "80", "0", "378.1107"],
            ["DCF", "Low WACC / High Value", "600.123", "100", "20", "80", "0", "468.1107"],
        ],
    }
    report["multiples_crosscheck"]["table"] = {
        "headers": ["Input", "Low", "High"],
        "rows": [
            ["Market multiple", "3", "4"],
            ["Normalised EBITDA", "100", "100"],
            ["Indicated enterprise value", "300", "400"],
        ],
    }
    valuation_result = {
        "scenario_bridges": {
            key: {
                "enterprise_value": Decimal(str(ev)),
                "interest_bearing_debt": Decimal("100"),
                "unrestricted_cash": Decimal("20"),
                "net_debt": Decimal("80"),
                "approved_surplus_assets": Decimal("0"),
                "pre_dlom_equity_value": Decimal(str(ev - 80)),
                "dlom_amount": (ev - Decimal("80")) * Decimal("0.1"),
                "equity_value": (ev - Decimal("80")) * Decimal("0.9"),
            }
            for key, ev in (
                ("high_wacc_low_value", Decimal("400.123")),
                ("mid_wacc_mid_value", Decimal("500.123")),
                ("low_wacc_high_value", Decimal("600.123")),
            )
        },
        "multiples_result": {
            "multiple_low": 3, "multiple_high": 4,
            "normalised_ebitda": 100,
            "enterprise_value_low": 300, "enterprise_value_high": 400,
        },
    }

    validate_generated_report(report, "valuation_advisory", valuation_result)

def test_valuation_validation_rejects_non_finite_and_changed_multiples():
    report = _valid_report()
    report["valuation_summary"]["table"] = {
        "headers": [
            "Method", "Scenario", "Enterprise Value", "Interest-bearing Debt",
            "Unrestricted Cash", "Net Debt", "Surplus Assets", "Equity Value",
        ],
        "rows": [
            ["DCF", "High WACC / Low Value", "NaN", "100", "20", "80", "0", "320"],
            ["DCF", "Mid WACC / Mid Value", "500", "100", "20", "80", "0", "420"],
            ["DCF", "Low WACC / High Value", "600", "100", "20", "80", "0", "520"],
        ],
    }
    report["multiples_crosscheck"]["table"] = {
        "headers": ["Input", "Low", "High"],
        "rows": [
            ["Market multiple", "3", "4"],
            ["Normalised EBITDA", "100", "100"],
            ["Indicated enterprise value", "300", "400"],
        ],
    }
    valuation_result = {
        "scenario_bridges": {
            key: {
                "enterprise_value": ev, "interest_bearing_debt": 100,
                "unrestricted_cash": 20, "net_debt": 80,
                "approved_surplus_assets": 0, "equity_value": ev - 80,
            }
            for key, ev in (
                ("high_wacc_low_value", 400),
                ("mid_wacc_mid_value", 500),
                ("low_wacc_high_value", 600),
            )
        },
        "multiples_result": {
            "multiple_low": 3, "multiple_high": 4,
            "normalised_ebitda": 100,
            "enterprise_value_low": 300, "enterprise_value_high": 400,
        },
    }
    with pytest.raises(ValueError, match="non-finite"):
        validate_generated_report(report, "valuation_advisory", valuation_result)

    report["valuation_summary"]["table"]["rows"][0][2] = "400"
    report["multiples_crosscheck"]["table"]["rows"][2][2] = "401"
    with pytest.raises(ValueError, match="multiples cross-check differs"):
        validate_generated_report(report, "valuation_advisory", valuation_result)


def test_schema_two_validation_accepts_exact_temporary_wacc_table():
    report = _valid_report()
    _set_decimal_fcff_tables(report)

    validate_generated_report(report, "valuation_advisory", _decimal_fcff_result())


@pytest.mark.parametrize(
    ("section", "row", "column"),
    [
        ("wacc_assumptions", 0, 1),
        ("wacc_assumptions", 9, 3),
    ],
)
def test_schema_two_validation_rejects_altered_temporary_table_value(
    section, row, column
):
    report = _valid_report()
    _set_decimal_fcff_tables(report)
    report[section]["table"]["rows"][row][column] = "999"

    with pytest.raises(ValueError, match="deterministic"):
        validate_generated_report(report, "valuation_advisory", _decimal_fcff_result())


def test_schema_two_validation_rejects_changed_scenario_order():
    report = _valid_report()
    _set_decimal_fcff_tables(report)
    result = _decimal_fcff_result()
    result["deterministic_fcff"]["scenarios"].reverse()

    with pytest.raises(ValueError, match="scenario order"):
        validate_generated_report(report, "valuation_advisory", result)


def test_generated_valuation_validation_accepts_complete_report_without_result():
    report = _valid_report()

    validate_generated_report(report, "valuation_advisory")


@pytest.mark.asyncio
async def test_invalid_generated_report_is_failed_with_safe_customer_error(
    fresh_all_db, monkeypatch
):
    report_type = "information_memorandum"
    invalid_content = _valid_report(report_type)
    invalid_content["operations"] = "TODO"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "INSERT INTO users (email, hashed_pw) VALUES ('buyer@example.com', 'hash')"
        ) as cur:
            user_id = cur.lastrowid
        async with db.execute(
            "INSERT INTO companies (name, exchange, user_id) VALUES ('Validation Ltd', 'Private', ?)",
            (user_id,),
        ) as cur:
            company_id = cur.lastrowid
        async with db.execute(
            """
            INSERT INTO reports (company_id, user_id, report_type, status)
            VALUES (?, ?, ?, 'queued')
            """,
            (company_id, user_id, report_type),
        ) as cur:
            report_id = cur.lastrowid
        await db.commit()

    async def fake_report_call(*args, **kwargs):
        return invalid_content

    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.setattr(main_module, "_call_claude_for_report", fake_report_call)

    await main_module._generate_report(report_id)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT status, content, error_message FROM reports WHERE id=?", (report_id,)
        ) as cur:
            report = await cur.fetchone()

    assert report["status"] == "failed"
    assert report["content"] is None
    assert report["error_message"] == SAFE_GENERATION_ERROR
    assert "TODO" not in report["error_message"]
