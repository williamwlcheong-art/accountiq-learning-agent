"""Unit tests for the Phase 05.1 valuation engine (REPT-01)."""
import sys
from pathlib import Path

import pytest

# Backend sys.path bootstrap — must run before any `from valuation import ...`
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# Module-level helper: FMCA disclaimer compliance checker
# ---------------------------------------------------------------------------

def _assert_disclaimer_compliant(text: str) -> None:
    """Assert that *text* contains all four FMCA-required disclaimer phrases.

    Raises AssertionError if any required phrase is absent.
    """
    required_phrases = [
        "indicative",
        "financial advice",
        ("FMCA", "Financial Markets Conduct"),
        ("not relied", "should not be relied"),
    ]
    lowered = text.lower()
    for phrase in required_phrases:
        if isinstance(phrase, tuple):
            assert any(p.lower() in lowered for p in phrase), (
                f"Disclaimer missing one of {phrase}"
            )
        else:
            assert phrase.lower() in lowered, (
                f"Disclaimer missing required phrase: {phrase}"
            )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_valuation_financial_readiness_requires_revenue_and_earnings_basis():
    from valuation import assess_valuation_financial_readiness

    result = assess_valuation_financial_readiness([])

    assert result["ready"] is False
    assert result["issues"] == ["revenue", "EBITDA or profit"]


def test_valuation_financial_readiness_accepts_revenue_and_profit_rows():
    from valuation import assess_valuation_financial_readiness

    result = assess_valuation_financial_readiness(
        [
            {"statement": "pnl", "row_key": "revenue", "period": "2024", "value": 950_000},
            {"statement": "pnl", "row_key": "revenue", "period": "2025", "value": 1_100_000},
            {"statement": "pnl", "row_key": "net_profit", "period": "2024", "value": 90_000},
            {"statement": "pnl", "row_key": "net_profit", "period": "2025", "value": 120_000},
        ]
    )

    assert result["ready"] is True
    assert result["issues"] == []
    assert result["warnings"] == []
    assert result["revenue_periods"] == ["2024", "2025"]
    assert result["earnings_periods"] == ["2024", "2025"]


def test_valuation_financial_readiness_handles_grouped_prompt_rows():
    from valuation import assess_valuation_financial_readiness

    result = assess_valuation_financial_readiness(
        [
            {
                "statement": "pnl",
                "canonical_key": "revenue",
                "values": {"2024": 900_000, "2025": 1_000_000},
            },
            {
                "statement": "pnl",
                "canonical_key": "ebitda",
                "values": {"2024": 180_000, "2025": 210_000},
            },
        ]
    )

    assert result["ready"] is True
    assert result["revenue_periods"] == ["2024", "2025"]
    assert result["earnings_periods"] == ["2024", "2025"]


def test_valuation_financial_readiness_warns_when_only_one_period_extracted():
    from valuation import assess_valuation_financial_readiness

    result = assess_valuation_financial_readiness(
        [
            {"statement": "pnl", "row_key": "revenue", "period": "2025", "value": 1_100_000},
            {"statement": "pnl", "row_key": "ebitda", "period": "2025", "value": 210_000},
        ]
    )

    assert result["ready"] is True
    assert len(result["warnings"]) == 2


def test_compute_wacc_scenarios_basic():
    """WACC scenarios return correct keys, mid value, ordering, and spread (D-W2/D-W6)."""
    from valuation import compute_wacc_scenarios
    result = compute_wacc_scenarios(risk_free_rate=4.65, industry_beta=1.08, erp=5.94)
    assert set(result.keys()) == {"high", "mid", "low"}
    # mid = round(4.65 + 1.08 * 5.94, 2) = 11.07
    assert result["mid"] == round(4.65 + 1.08 * 5.94, 2), (
        f"Expected mid=11.07, got {result['mid']}"
    )
    assert result["high"] > result["mid"] > result["low"], (
        "Expected high > mid > low ordering"
    )
    spread = result["high"] - result["low"]
    assert 1.0 <= spread <= 4.0, f"WACC spread {spread} outside expected 1.0-4.0pp"


def test_compute_wacc_scenarios_returns_percent_not_decimal():
    """All WACC scenario values are in percent form (5–25), not decimal form (0.05–0.25)."""
    from valuation import compute_wacc_scenarios
    # Realistic NZ inputs: 10-yr bond ~4.65%, beta ~1.08, ERP ~5.94%
    result = compute_wacc_scenarios(risk_free_rate=4.65, industry_beta=1.08, erp=5.94)
    for label, value in result.items():
        assert 5.0 <= value <= 25.0, (
            f"WACC scenario '{label}' = {value} looks like a decimal, not a percent. "
            "compute_wacc_scenarios must return percent values."
        )


def test_wacc_decimal_form_guard():
    """Decimal-form risk_free_rate should be rejected by ResearchBrief validation."""
    from research_loop import ResearchBrief
    from pydantic import ValidationError

    # 0.0465 is the decimal form of 4.65% — should be rejected
    try:
        brief = ResearchBrief(
            risk_free_rate=0.0465,
            industry_beta=1.08,
            erp=5.94,
            company_summary="Test",
            sector_context="Test",
            comparable_transactions=[],
            comparable_multiples_summary="Test",
            inflation_rate=2.5,
        )
        # If ResearchBrief accepts 0.0465, check that the validator catches it
        assert brief.risk_free_rate >= 1.0, (
            f"risk_free_rate={brief.risk_free_rate} is in decimal form — "
            "validator should reject values below 1.0 (percent convention)"
        )
    except ValidationError:
        pass  # Correct: ResearchBrief rejected the decimal-form input


def test_dcf_correctness_fixed_inputs():
    """DCF with fixed NZ baseline inputs returns positive, finite enterprise_value_dcf.

    Snapshot: compute_dcf(ebitda=800000, wacc=0.1082, growth_rate=0.08, tax_rate=0.28,
    years=5, terminal_growth=0.025) => enterprise_value_dcf ~= 8905541.29 (±0.5%).
    """
    from valuation import compute_dcf
    result = compute_dcf(
        ebitda=800000,
        wacc=0.1082,
        growth_rate=0.08,
        tax_rate=0.28,
        years=5,
        terminal_growth=0.025,
    )
    # Confirm the return key name
    assert "enterprise_value_dcf" in result, (
        f"Expected key 'enterprise_value_dcf' in DCF result, got keys: {list(result.keys())}"
    )
    ev = result["enterprise_value_dcf"]
    assert ev > 0, f"enterprise_value_dcf must be positive, got {ev}"
    assert ev == ev, "enterprise_value_dcf must be finite (not NaN)"  # NaN != NaN
    # Snapshot assertion within ±0.5% tolerance
    expected = 8905541.29
    tolerance = expected * 0.005
    assert abs(ev - expected) <= tolerance, (
        f"enterprise_value_dcf={ev} is outside ±0.5% of expected {expected}. "
        "Formula may have changed — update this snapshot if intentional."
    )


def test_dcf_models_reinvestment_and_operating_working_capital():
    """FCFF uses EBIT after tax + D&A - capex - change in operating NWC."""
    from valuation import compute_dcf

    result = compute_dcf(
        ebitda=200_000,
        revenue=1_000_000,
        depreciation_per_year=20_000,
        capex_per_year=20_000,
        working_capital_ratio=0.10,
        wacc=0.10,
        growth_rate=0.10,
        tax_rate=0.28,
        years=1,
        terminal_growth=0.02,
    )

    year_one = result["yearly"][0]
    assert year_one == {
        "year": 1,
        "revenue": 1_100_000.0,
        "ebitda": 220_000.0,
        "depreciation": 22_000.0,
        "ebit": 198_000.0,
        "tax": 55_440.0,
        "capex": 22_000.0,
        "change_nwc": 10_000.0,
        "fcff": 132_560.0,
        "dcf": 120_509.09,
    }


def test_dcf_rejects_implausible_working_capital_ratio():
    from valuation import compute_dcf

    with pytest.raises(ValueError, match="working_capital_ratio"):
        compute_dcf(
            ebitda=200_000,
            revenue=1_000_000,
            working_capital_ratio=1.2,
            wacc=0.10,
            growth_rate=0.05,
            tax_rate=0.28,
            years=5,
            terminal_growth=0.02,
        )


def test_reinvestment_assumptions_prefer_operating_line_items():
    from valuation import derive_reinvestment_assumptions

    result = derive_reinvestment_assumptions(
        {
            "cash_and_bank": 500_000,
            "trade_debtors": 200_000,
            "inventory": 100_000,
            "other_current_assets": 50_000,
            "trade_creditors": 120_000,
            "other_current_liab": 30_000,
            "short_term_debt": 80_000,
        },
        revenue=2_000_000,
        depreciation=75_000,
    )

    assert result == {
        "depreciation_base": 75_000.0,
        "maintenance_capex": 75_000.0,
        "operating_working_capital": 200_000.0,
        "working_capital_ratio": 0.10,
        "working_capital_ratio_pct": 10.0,
        "working_capital_source": "extracted_operating_line_items",
    }


def test_reinvestment_assumptions_fallback_and_ratio_cap():
    from valuation import derive_reinvestment_assumptions

    result = derive_reinvestment_assumptions(
        {
            "total_current_assets": 900_000,
            "cash_and_bank": 100_000,
            "total_current_liab": 200_000,
            "short_term_debt": 50_000,
        },
        revenue=1_000_000,
        depreciation=40_000,
    )

    assert result["operating_working_capital"] == 650_000.0
    assert result["working_capital_ratio"] == 0.30
    assert result["working_capital_ratio_pct"] == 30.0
    assert result["working_capital_source"] == "extracted_current_totals"


def test_dcf_sensitivity_matrix_is_monotonic_and_contains_base_case():
    from valuation import compute_dcf_sensitivity_matrix

    matrix = compute_dcf_sensitivity_matrix(
        ebitda=287_000,
        revenue=1_250_000,
        depreciation_per_year=25_000,
        capex_per_year=25_000,
        working_capital_ratio=0.05,
        wacc_by_valuation_scenario_pct={"high": 9.9, "mid": 11.5, "low": 13.4},
        base_growth_pct=8.0,
        tax_rate=0.28,
        years=5,
        terminal_growth_pct=2.5,
        illiquidity_discount=0.118,
    )

    assert matrix["growth_rates_pct"] == [6.0, 8.0, 10.0]
    rows = matrix["adjusted_enterprise_value_rows"]
    assert rows[1] == {
        "growth_pct": 8.0,
        "high": 2_830_669.0,
        "mid": 2_314_121.0,
        "low": 1_898_471.0,
    }
    for row in rows:
        assert row["high"] > row["mid"] > row["low"]
    assert rows[0]["mid"] < rows[1]["mid"] < rows[2]["mid"]


def test_sensitivity_analysis_table_uses_computed_matrix_and_marks_base_case():
    from valuation import build_sensitivity_analysis_table

    table = build_sensitivity_analysis_table(
        {
            "wacc_by_valuation_scenario_pct": {"high": 9.9, "mid": 11.5, "low": 13.4},
            "adjusted_enterprise_value_rows": [
                {"growth_pct": 6.0, "high": 2_621_000, "mid": 2_147_000, "low": 1_765_000},
                {"growth_pct": 8.0, "high": 2_831_000, "mid": 2_314_000, "low": 1_898_000},
                {"growth_pct": 10.0, "high": 3_054_000, "mid": 2_492_000, "low": 2_040_000},
            ],
        },
        base_growth_pct=8.0,
    )

    assert table == {
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
    }


def test_forecast_cash_flow_schedule_uses_computed_mid_case_rows():
    from valuation import build_forecast_cash_flow_schedule, compute_dcf

    dcf = compute_dcf(
        ebitda=287_000,
        revenue=1_250_000,
        depreciation_per_year=25_000,
        capex_per_year=25_000,
        working_capital_ratio=0.05,
        wacc=0.115,
        growth_rate=0.08,
        tax_rate=0.28,
        years=5,
        terminal_growth=0.025,
    )

    schedule = build_forecast_cash_flow_schedule(dcf)

    assert schedule["headers"] == [
        "Mid-case forecast",
        "Year 1",
        "Year 2",
        "Year 3",
        "Year 4",
        "Year 5",
    ]
    assert schedule["rows"][0] == [
        "Revenue",
        1_350_000.0,
        1_458_000.0,
        1_574_640.0,
        1_700_611.0,
        1_836_660.0,
    ]
    assert schedule["rows"][6] == [
        "Free cash flow to firm",
        198_731.0,
        214_630.0,
        231_800.0,
        250_344.0,
        270_372.0,
    ]


def test_assumption_source_trail_distinguishes_input_sources():
    from valuation import build_assumption_source_trail

    trail = build_assumption_source_trail(
        normalised_ebitda=287_000,
        forecast_years=5,
        revenue_growth_pct=8.0,
        growth_assumption_source="management_outlook_modest_growth",
        terminal_growth_pct=2.5,
        wacc_by_valuation_scenario_pct={"high": 9.9, "mid": 11.5, "low": 13.4},
        maintenance_capex=25_000,
        working_capital_ratio_pct=5.0,
        working_capital_source="extracted_operating_line_items",
        gross_debt=160_000,
        cash=95_000,
        surplus_assets=0,
        owner_dependency="shared",
        customer_concentration="10_to_25",
        revenue_quality="mixed",
        revenue_outlook="modest_growth",
    )

    assert trail["headers"] == [
        "Assumption / input",
        "Value used",
        "Primary source",
        "Why it matters",
    ]
    row_text = " ".join(" ".join(str(cell) for cell in row) for row in trail["rows"])
    assert "Uploaded financial statements" in row_text
    assert "Public research" in row_text
    assert "Management-confirmed private input" in row_text
    assert "Revenue and earnings growth" in row_text
    assert "8.0%" in row_text
    assert "Management outlook: modest growth" in row_text
    assert "Uploaded balance sheet: operating working-capital line items" in row_text
    assert "Debt: uploaded balance sheet borrowings where extracted" in row_text
    assert "cash: uploaded balance sheet cash balance" in row_text
    assert "continuity planning" in row_text
    assert "buyer diligence focus" not in row_text
    assert "surplus assets: no management-supplied amount identified" in row_text
    assert "Responsibility is shared across leadership and team" in row_text
    assert "10% to 25%" in row_text
    assert "A mix of recurring and one-off revenue" in row_text
    assert "Revenue outlook" in row_text
    assert "Modest growth" in row_text
    assert "owner_outlook_modest_growth" not in row_text
    assert "management_outlook_modest_growth" not in row_text
    assert "extracted_operating_line_items" not in row_text
    assert "10_to_25" not in row_text


def test_assumption_source_trail_labels_management_supplied_bridge_overrides():
    from valuation import build_assumption_source_trail

    trail = build_assumption_source_trail(
        normalised_ebitda=287_000,
        forecast_years=5,
        revenue_growth_pct=8.0,
        growth_assumption_source="management_outlook_modest_growth",
        terminal_growth_pct=2.5,
        wacc_by_valuation_scenario_pct={"high": 9.9, "mid": 11.5, "low": 13.4},
        maintenance_capex=25_000,
        working_capital_ratio_pct=5.0,
        working_capital_source="extracted_operating_line_items",
        gross_debt=220_000,
        cash=95_000,
        surplus_assets=40_000,
        debt_override_used=True,
        surplus_assets_supplied=True,
    )

    row_text = " ".join(" ".join(str(cell) for cell in row) for row in trail["rows"])

    assert "Debt $220,000; cash $95,000; surplus assets $40,000" in row_text
    assert "Debt: management-supplied debt override" in row_text
    assert "cash: uploaded balance sheet cash balance" in row_text
    assert "surplus assets: management-supplied amount" in row_text


def test_normalisation_schedule_table_handles_empty_earnings_review():
    from valuation import build_normalisation_schedule_table

    table = build_normalisation_schedule_table([], normalised_ebitda=32_000)

    assert table["headers"] == ["Label", "Amount ($)", "Rationale"]
    assert table["rows"] == [
        [
            "No adjustments confirmed",
            "$0",
            "The earnings review did not identify genuine one-off, owner-specific or non-operating items for this upload.",
        ],
        [
            "Normalised EBITDA",
            "$32,000",
            "Uploaded earnings basis plus the confirmed adjustments above.",
        ],
    ]


def test_financial_performance_table_uses_extracted_pnl_rows():
    from valuation import build_financial_performance_table

    table = build_financial_performance_table(
        [
            {"statement": "pnl", "row_key": "revenue", "period": "2025", "value": 1_250_000},
            {"statement": "pnl", "row_key": "revenue", "period": "2023", "value": 980_000},
            {"statement": "pnl", "row_key": "revenue", "period": "2024", "value": 1_110_000},
            {"statement": "pnl", "row_key": "gross_profit", "period": "2023", "value": 588_000},
            {"statement": "pnl", "row_key": "gross_profit", "period": "2024", "value": 682_600},
            {"statement": "pnl", "row_key": "gross_profit", "period": "2025", "value": 787_500},
            {"statement": "pnl", "row_key": "wages_salaries", "period": "2023", "value": 240_000},
            {"statement": "pnl", "row_key": "wages_salaries", "period": "2024", "value": 272_000},
            {"statement": "pnl", "row_key": "wages_salaries", "period": "2025", "value": 310_000},
            {"statement": "pnl", "row_key": "rent_occupancy", "period": "2023", "value": 84_000},
            {"statement": "pnl", "row_key": "rent_occupancy", "period": "2024", "value": 90_000},
            {"statement": "pnl", "row_key": "rent_occupancy", "period": "2025", "value": 96_000},
            {"statement": "pnl", "row_key": "advertising_marketing", "period": "2023", "value": 30_000},
            {"statement": "pnl", "row_key": "advertising_marketing", "period": "2024", "value": 36_000},
            {"statement": "pnl", "row_key": "advertising_marketing", "period": "2025", "value": 42_000},
            {"statement": "pnl", "row_key": "insurance", "period": "2023", "value": 15_000},
            {"statement": "pnl", "row_key": "insurance", "period": "2024", "value": 16_600},
            {"statement": "pnl", "row_key": "insurance", "period": "2025", "value": 18_000},
            {"statement": "pnl", "row_key": "other_operating_expenses", "period": "2023", "value": 54_000},
            {"statement": "pnl", "row_key": "other_operating_expenses", "period": "2024", "value": 63_000},
            {"statement": "pnl", "row_key": "other_operating_expenses", "period": "2025", "value": 81_500},
            {"statement": "pnl", "row_key": "ebitda", "period": "2023", "value": 165_000},
            {"statement": "pnl", "row_key": "ebitda", "period": "2024", "value": 205_000},
            {"statement": "pnl", "row_key": "ebitda", "period": "2025", "value": 240_000},
            {"statement": "pnl", "row_key": "net_profit", "period": "2023", "value": 105_000},
            {"statement": "pnl", "row_key": "net_profit", "period": "2024", "value": 128_000},
            {"statement": "pnl", "row_key": "net_profit", "period": "2025", "value": 150_000},
        ]
    )

    assert table == {
        "headers": ["Metric", "2023", "2024", "2025"],
        "rows": [
            ["Revenue", "$980,000", "$1,110,000", "$1,250,000"],
            ["Less: direct costs / cost of sales", "($392,000)", "($427,400)", "($462,500)"],
            ["Gross profit", "$588,000", "$682,600", "$787,500"],
            ["Less: operating expenses before EBITDA", "($423,000)", "($477,600)", "($547,500)"],
            ["Key expense breakdown - wages and salaries", "($240,000)", "($272,000)", "($310,000)"],
            ["Key expense breakdown - rent and occupancy", "($84,000)", "($90,000)", "($96,000)"],
            ["Key expense breakdown - other operating expenses", "($54,000)", "($63,000)", "($81,500)"],
            ["EBITDA", "$165,000", "$205,000", "$240,000"],
            ["Net profit after tax", "$105,000", "$128,000", "$150,000"],
        ],
    }


def test_financial_ratio_table_marks_missing_inputs_unavailable():
    from valuation import build_financial_ratio_table

    table = build_financial_ratio_table(
        [
            {"statement": "pnl", "row_key": "revenue", "period": "2023", "value": 980_000},
            {"statement": "pnl", "row_key": "revenue", "period": "2024", "value": 1_110_000},
            {"statement": "pnl", "row_key": "revenue", "period": "2025", "value": 1_250_000},
            {"statement": "pnl", "row_key": "gross_profit", "period": "2023", "value": 588_000},
            {"statement": "pnl", "row_key": "gross_profit", "period": "2024", "value": 682_600},
            {"statement": "pnl", "row_key": "gross_profit", "period": "2025", "value": 787_500},
            {"statement": "pnl", "row_key": "ebitda", "period": "2023", "value": 165_000},
            {"statement": "pnl", "row_key": "ebitda", "period": "2024", "value": 205_000},
            {"statement": "pnl", "row_key": "ebitda", "period": "2025", "value": 240_000},
            {"statement": "pnl", "row_key": "net_profit", "period": "2023", "value": 105_000},
            {"statement": "pnl", "row_key": "net_profit", "period": "2024", "value": 128_000},
        ]
    )

    assert table == {
        "headers": ["Ratio", "2023", "2024", "2025"],
        "rows": [
            ["Revenue growth", "Not available", "13.3%", "12.6%"],
            ["Gross margin", "60.0%", "61.5%", "63.0%"],
            ["EBITDA margin", "16.8%", "18.5%", "19.2%"],
            ["Net profit margin", "10.7%", "11.5%", "Not available"],
        ],
    }


def test_balance_sheet_summary_table_builds_equity_bridge_from_extracted_inputs():
    from valuation import build_balance_sheet_summary_table

    table = build_balance_sheet_summary_table(
        [
            {"statement": "bs", "row_key": "trade_debtors", "period": "2025", "value": 210_000},
            {"statement": "bs", "row_key": "inventory", "period": "2025", "value": 65_000},
            {"statement": "bs", "row_key": "total_current_assets", "period": "2025", "value": 370_000},
            {"statement": "bs", "row_key": "trade_creditors", "period": "2025", "value": 155_000},
            {"statement": "bs", "row_key": "other_current_liab", "period": "2025", "value": 45_000},
            {"statement": "bs", "row_key": "total_current_liab", "period": "2025", "value": 260_000},
            {"statement": "bs", "row_key": "fixed_assets_net", "period": "2025", "value": 185_000},
            {"statement": "bs", "row_key": "cash_and_bank", "period": "2025", "value": 95_000},
            {"statement": "bs", "row_key": "short_term_debt", "period": "2025", "value": 60_000},
            {"statement": "bs", "row_key": "long_term_debt", "period": "2025", "value": 100_000},
            {"statement": "bs", "row_key": "other_noncurrent_assets", "period": "2025", "value": 295_000},
            {"statement": "bs", "row_key": "other_noncurrent_liab", "period": "2025", "value": 60_000},
            {"statement": "bs", "row_key": "total_assets", "period": "2025", "value": 850_000},
            {"statement": "bs", "row_key": "total_liabilities", "period": "2025", "value": 420_000},
            {"statement": "bs", "row_key": "shareholders_equity", "period": "2025", "value": 430_000},
        ],
        gross_debt=160_000,
        cash=95_000,
        surplus_assets=50_000,
        midpoint_enterprise_value=2_314_000,
        operating_working_capital=62_000,
        working_capital_source="extracted_operating_line_items",
        surplus_assets_supplied=True,
    )

    assert table == {
        "headers": ["Item", "Value", "Source / treatment"],
        "rows": [
            [
                "Cash and bank",
                "$95,000",
                "Cash is shown separately from operating assets and is included in the enterprise-to-equity bridge.",
            ],
            [
                "Accounts receivable / trade debtors",
                "$210,000",
                "Uploaded receivables where extracted; included in operating asset and NTOA context.",
            ],
            [
                "Inventory / stock",
                "$65,000",
                "Uploaded stock balance where extracted; included in operating asset and NTOA context.",
            ],
            [
                "Other current assets",
                "Not available",
                "Other operating current assets where extracted.",
            ],
            [
                "Total current assets",
                "$370,000",
                "Uploaded balance sheet current-asset total where extracted; supports working-capital context.",
            ],
            [
                "Fixed assets (net)",
                "$185,000",
                "Uploaded balance sheet where extracted; otherwise not used as a separate valuation adjustment.",
            ],
            [
                "Other non-current assets",
                "$295,000",
                "Other long-term operating or investment assets where extracted.",
            ],
            [
                "Total assets",
                "$850,000",
                "Uploaded balance sheet total assets where extracted; used as financial-position context rather than the primary valuation basis.",
            ],
            [
                "Accounts payable / trade creditors",
                "$155,000",
                "Uploaded trade payables where extracted; included in operating liability and NTOA context.",
            ],
            [
                "Other current liabilities",
                "$45,000",
                "Other operating current liabilities where extracted.",
            ],
            [
                "Short-term loans / current borrowings",
                "$60,000",
                "Current interest-bearing borrowings where extracted; included in the debt bridge when no override is supplied.",
            ],
            [
                "Total current liabilities",
                "$260,000",
                "Uploaded balance sheet current-liability total where extracted; supports working-capital context.",
            ],
            [
                "Long-term loans / borrowings",
                "$100,000",
                "Non-current interest-bearing borrowings where extracted; included in the debt bridge when no override is supplied.",
            ],
            [
                "Other non-current liabilities",
                "$60,000",
                "Other long-term liabilities where extracted.",
            ],
            [
                "Total liabilities",
                "$420,000",
                "Uploaded balance sheet total liabilities where extracted; provides solvency and leverage context.",
            ],
            [
                "Shareholders' equity / net assets",
                "$430,000",
                "Uploaded balance sheet net-asset position where extracted; shown for context and reconciled separately from enterprise value.",
            ],
            [
                "Net tangible operating assets (NTOA)",
                "$260,000",
                "Indicative operating asset position: receivables, stock, other operating current assets and fixed assets less operating payables and other operating current liabilities, excluding cash and interest-bearing debt.",
            ],
            [
                "Operating working capital",
                "$62,000",
                "Uploaded balance sheet: operating working-capital line items",
            ],
            [
                "Interest-bearing debt",
                "$160,000",
                "Uploaded balance sheet borrowings where extracted.",
            ],
            ["Net debt", "$65,000", "Interest-bearing debt less cash and bank."],
            [
                "Surplus / non-operating assets",
                "$50,000",
                "Management-supplied surplus or non-operating asset amount.",
            ],
            [
                "Midpoint enterprise value",
                "$2,314,000",
                "AccountIQ-calculated DCF midpoint after the illiquidity adjustment.",
            ],
            ["Less: net debt", "($65,000)", "Enterprise value to equity value bridge."],
            [
                "Add: surplus assets",
                "$50,000",
                "Separately identified assets not required for normal operations.",
            ],
            [
                "Midpoint equity value",
                "$2,299,000",
                "Midpoint enterprise value less net debt plus surplus assets.",
            ],
        ],
    }


def test_balance_sheet_summary_table_labels_management_supplied_debt_override():
    from valuation import build_balance_sheet_summary_table

    table = build_balance_sheet_summary_table(
        [
            {"statement": "bs", "row_key": "cash_and_bank", "period": "2025", "value": 25_000},
            {"statement": "bs", "row_key": "short_term_debt", "period": "2025", "value": 60_000},
        ],
        gross_debt=125_000,
        cash=25_000,
        surplus_assets=0,
        midpoint_enterprise_value=900_000,
        operating_working_capital=30_000,
        working_capital_source="extracted_current_totals",
        debt_override_used=True,
    )

    assert [
        "Interest-bearing debt",
        "$125,000",
        "Management-supplied debt override.",
    ] in table["rows"]
    assert [
        "Surplus / non-operating assets",
        "$0",
        "No management-supplied surplus or non-operating assets identified.",
    ] in table["rows"]


def test_executive_summary_table_builds_headline_equity_range():
    from valuation import build_executive_summary_table

    table = build_executive_summary_table(
        adjusted_enterprise_values={"high": 2_831_000, "mid": 2_314_000, "low": 1_898_000},
        gross_debt=160_000,
        cash=95_000,
        surplus_assets=0,
    )

    assert table == {
        "headers": ["Indicative valuation", "High valuation", "Midpoint", "Low valuation"],
        "rows": [
            ["Enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"],
            ["Less: net debt", "($65,000)", "($65,000)", "($65,000)"],
            ["Add: surplus assets", "$0", "$0", "$0"],
            ["Indicative equity value", "$2,766,000", "$2,249,000", "$1,833,000"],
        ],
    }


def test_valuation_summary_table_builds_dcf_and_multiples_equity_bridge():
    from valuation import build_valuation_summary_table

    table = build_valuation_summary_table(
        dcf_scenarios={
            "high": {"enterprise_value_dcf": 3_209_000},
            "mid": {"enterprise_value_dcf": 2_624_000},
            "low": {"enterprise_value_dcf": 2_152_000},
        },
        adjusted_enterprise_values={"high": 2_831_000, "mid": 2_314_000, "low": 1_898_000},
        wacc_by_valuation_scenario_pct={"high": 9.9, "mid": 11.5, "low": 13.4},
        multiples_result={
            "multiple_low": 5.0,
            "multiple_mid": 6.0,
            "multiple_high": 7.0,
            "enterprise_value_low": 1_435_000,
            "enterprise_value_mid": 1_722_000,
            "enterprise_value_high": 2_009_000,
        },
        gross_debt=160_000,
        cash=95_000,
        surplus_assets=0,
    )

    assert table["headers"] == [
        "Method / scenario",
        "Scenario / input",
        "Enterprise value",
        "Illiquidity-adjusted EV",
        "Equity value",
    ]
    assert table["rows"] == [
        ["DCF - high valuation", "9.9% WACC", "$3,209,000", "$2,831,000", "$2,766,000"],
        ["DCF - midpoint", "11.5% WACC", "$2,624,000", "$2,314,000", "$2,249,000"],
        ["DCF - low valuation", "13.4% WACC", "$2,152,000", "$1,898,000", "$1,833,000"],
        ["Multiples - low", "5.00x EBITDA", "$1,435,000", "Not applied", "$1,370,000"],
        ["Multiples - midpoint", "6.00x EBITDA", "$1,722,000", "Not applied", "$1,657,000"],
        ["Multiples - high", "7.00x EBITDA", "$2,009,000", "Not applied", "$1,944,000"],
    ]


def test_wacc_assumptions_table_uses_researched_inputs_and_computed_wacc():
    from valuation import build_wacc_assumptions_table

    table = build_wacc_assumptions_table(
        risk_free_rate=4.4,
        erp=5.9,
        industry_beta=1.2,
        wacc_by_valuation_scenario_pct={"high": 9.9, "mid": 11.5, "low": 13.4},
        illiquidity_discount=0.118,
    )

    assert table == {
        "headers": ["Component", "High valuation", "Midpoint", "Low valuation"],
        "rows": [
            ["Risk-free rate", "4.4%", "4.4%", "4.4%"],
            ["Equity risk premium", "5.9%", "5.9%", "5.9%"],
            ["Industry beta", "1.20", "1.20", "1.20"],
            ["Private-company WACC", "9.9%", "11.5%", "13.4%"],
            ["Illiquidity discount", "11.8%", "11.8%", "11.8%"],
        ],
    }


def test_dcf_analysis_table_uses_python_computed_scenarios():
    from valuation import build_dcf_analysis_table

    table = build_dcf_analysis_table(
        dcf_scenarios={
            "high": {"enterprise_value_dcf": 3_209_000},
            "mid": {"enterprise_value_dcf": 2_624_000},
            "low": {"enterprise_value_dcf": 2_152_000},
        },
        adjusted_enterprise_values={"high": 2_831_000, "mid": 2_314_000, "low": 1_898_000},
        wacc_by_valuation_scenario_pct={"high": 9.9, "mid": 11.5, "low": 13.4},
        terminal_growth_pct=2.5,
        revenue=1_250_000,
        normalised_ebitda=287_000,
        depreciation_base=25_000,
        maintenance_capex=25_000,
        working_capital_ratio_pct=5.0,
        illiquidity_discount=0.118,
    )

    assert table == {
        "headers": ["DCF item", "High valuation", "Midpoint", "Low valuation"],
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
    }


def test_multiples_crosscheck_table_uses_researched_multiple_range():
    from valuation import build_multiples_crosscheck_table

    table = build_multiples_crosscheck_table(
        {
            "multiple_low": 5.0,
            "multiple_mid": 6.0,
            "multiple_high": 7.0,
            "enterprise_value_low": 1_435_000,
            "enterprise_value_mid": 1_722_000,
            "enterprise_value_high": 2_009_000,
            "normalised_ebitda": 287_000,
        }
    )

    assert table == {
        "headers": ["Input", "Low", "Mid", "High"],
        "rows": [
            ["EV/EBITDA multiple", "5.00x", "6.00x", "7.00x"],
            ["Normalised EBITDA", "$287,000", "$287,000", "$287,000"],
            ["Indicated enterprise value", "$1,435,000", "$1,722,000", "$2,009,000"],
        ],
    }


def test_sources_table_classifies_research_urls_without_inventing_sources():
    from valuation import build_sources_table

    table = build_sources_table(
        [
            "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
            "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
            "https://companies-register.companiesoffice.govt.nz/",
            "https://companies-register.companiesoffice.govt.nz/",
        ]
    )

    assert table == {
        "headers": ["Source", "URL", "Supports / used for"],
        "rows": [
            [
                "Reserve Bank of New Zealand",
                "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
                "Risk-free-rate and New Zealand macroeconomic context",
            ],
            [
                "Damodaran Online",
                "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
                "Equity risk premium, beta, multiples and private-company valuation inputs",
            ],
            [
                "NZ Companies Office",
                "https://companies-register.companiesoffice.govt.nz/",
                "Company public-profile corroboration",
            ],
        ],
    }


def test_sources_table_does_not_classify_lookalike_authority_urls():
    from valuation import build_sources_table

    table = build_sources_table(
        [
            "https://rbnz.govt.nz.evil.example/statistics",
            "https://example.com/damodaran-total-beta",
        ]
    )

    assert table["rows"] == [
        [
            "rbnz.govt.nz.evil.example",
            "https://rbnz.govt.nz.evil.example/statistics",
            "Business-profile, company-fact or market-context corroboration used for report drafting",
        ],
        [
            "example.com",
            "https://example.com/damodaran-total-beta",
            "Business-profile, company-fact or market-context corroboration used for report drafting",
        ],
    ]


def test_sources_table_retains_management_supplied_public_source_hints():
    from valuation import build_sources_table

    table = build_sources_table(
        [
            "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
            "https://www.linkedin.com/company/example",
        ],
        management_supplied_sources=[
            "https://example.co.nz/about",
            "https://www.linkedin.com/company/example",
            "https://companies-register.companiesoffice.govt.nz/companies/app/ui/pages/companies/123456",
        ],
    )

    assert table["rows"] == [
        [
            "Reserve Bank of New Zealand",
            "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
            "Risk-free-rate and New Zealand macroeconomic context",
        ],
        [
            "LinkedIn public profile",
            "https://www.linkedin.com/company/example",
            "Public business profile and market-position context",
        ],
        [
            "Management-supplied example.co.nz",
            "https://example.co.nz/about",
            "Management-supplied public source hint retained for company-fact, business-profile or market-context corroboration",
        ],
        [
            "Management-supplied NZ Companies Office",
            "https://companies-register.companiesoffice.govt.nz/companies/app/ui/pages/companies/123456",
            "Management-supplied public record retained for company public-profile corroboration",
        ],
    ]


def test_comparable_evidence_table_preserves_source_urls():
    from valuation import build_comparable_evidence_table

    table = build_comparable_evidence_table(
        comparable_transactions=(
            "- 2024 listed business services evidence at 6.2x EBITDA\n"
            "- Private SME benchmark at 5.0x EBITDA"
        ),
        sources=[
            "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
            "https://www.rbnz.govt.nz/statistics",
        ],
    )

    assert table["headers"] == [
        "Evidence / transaction",
        "Date",
        "Metric or multiple",
        "Relevance and limitations",
        "Source",
    ]
    assert table["rows"][0][0] == "2024 listed business services evidence at 6.2x EBITDA"
    assert table["rows"][0][1] == "2024"
    assert table["rows"][0][2] == "6.2x"
    assert "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html" in table["rows"][0][-1]
    assert table["rows"][1][2] == "5.0x"
    assert "https://www.rbnz.govt.nz/statistics" in table["rows"][1][-1]


def test_comparable_evidence_table_does_not_label_lookalike_sources_as_authoritative():
    from valuation import build_comparable_evidence_table

    table = build_comparable_evidence_table(
        comparable_transactions="- 2025 lookalike source benchmark at 5.0x EBITDA",
        sources=["https://example.com/damodaran-total-beta"],
    )

    assert table["rows"][0][-1] == "example.com - https://example.com/damodaran-total-beta"


def test_normalisation_schedule_table_uses_confirmed_adjustments():
    from valuation import build_normalisation_schedule_table

    table = build_normalisation_schedule_table(
        [
            {
                "label": "Owner salary above market",
                "amount": 50_000,
                "rationale": "Above market salary adjustment",
            }
        ],
        normalised_ebitda=280_000,
    )

    assert table["rows"] == [
        ["Owner salary above market", "$50,000", "Above market salary adjustment"],
        [
            "Normalised EBITDA",
            "$280,000",
            "Uploaded earnings basis plus the confirmed adjustments above.",
        ],
    ]


def test_normalisation_schedule_table_formats_negative_adjustments_professionally():
    from valuation import build_normalisation_schedule_table

    table = build_normalisation_schedule_table(
        [
            {
                "label": "Replacement manager cost",
                "amount": -75_000,
                "rationale": "Deducted to reflect maintainable earnings after replacing owner involvement.",
            }
        ],
        normalised_ebitda=212_000,
    )

    assert table["rows"] == [
        [
            "Replacement manager cost",
            "($75,000)",
            "Deducted to reflect maintainable earnings after replacing owner involvement.",
        ],
        [
            "Normalised EBITDA",
            "$212,000",
            "Uploaded earnings basis plus the confirmed adjustments above.",
        ],
    ]


def test_specific_risk_factor_table_uses_short_owner_intake():
    from valuation import build_specific_risk_factor_table

    table = build_specific_risk_factor_table(
        owner_dependency="shared",
        customer_concentration="10_to_25",
        revenue_quality="mixed",
        revenue_outlook="not_sure",
        private_context="A key contract renews next year.",
    )

    assert table["headers"] == [
        "Specific risk factor",
        "Management input",
        "Valuation relevance",
        "Report treatment",
    ]
    row_text = " ".join(" ".join(str(cell) for cell in row) for row in table["rows"])
    assert "Owner or key-person transition" in row_text
    assert "Customer concentration" in row_text
    assert "Revenue predictability" in row_text
    assert "Revenue outlook and pipeline" in row_text
    assert "A key contract renews next year." in row_text
    assert "Responsibility is shared across leadership and team" in row_text
    assert "10% to 25%" in row_text
    assert "A mix of recurring and one-off revenue" in row_text
    assert "No specific forecast provided; growth derived from uploaded financial history" in row_text
    assert "Growth is derived from uploaded history rather than a management forecast" in row_text
    assert "operating continuity, handover depth and confidence in maintainable earnings" in row_text
    assert "buyer confidence" not in row_text
    assert "buyer diligence" not in row_text.lower()
    assert "10_to_25" not in row_text
    assert "not_sure" not in row_text


def test_normalised_ebitda_addback_sum():
    """Normalised EBITDA = extracted_ebitda + sum(adjustment.amount) for all adjustments."""
    # Inline computation matching main.py lines 1470-1471 logic
    extracted_ebitda = 200000.0
    ebitda_adjustments = [{"amount": 50000}, {"amount": 30000}]
    normalised = extracted_ebitda + sum(
        float(a["amount"]) for a in ebitda_adjustments
    )
    assert normalised == 280000.0, (
        f"Expected normalised EBITDA = 280000.0, got {normalised}"
    )

    # Edge cases
    assert 200000.0 + sum(float(a["amount"]) for a in []) == 200000.0
    assert 0.0 + sum(float(a["amount"]) for a in [{"amount": -10000}]) == -10000.0


def test_compute_multiples_range_uses_researched_bounds():
    """The market cross-check reports low/mid/high values without a user risk score."""
    import valuation
    from valuation import compute_multiples_range

    result = compute_multiples_range(
        normalised_ebitda=800000,
        ev_ebitda_low=3.5,
        ev_ebitda_high=6.0,
    )

    assert result == {
        "multiple_low": 3.5,
        "multiple_mid": 4.75,
        "multiple_high": 6.0,
        "enterprise_value_low": 2800000.0,
        "enterprise_value_mid": 3800000.0,
        "enterprise_value_high": 4800000.0,
        "normalised_ebitda": 800000,
    }
    assert "risk_score" not in result
    assert not hasattr(valuation, "compute_risk_score")
    assert not hasattr(valuation, "compute_multiples_ev")


def test_revenue_growth_assumption_uses_plain_language_outlook():
    from valuation import select_revenue_growth_assumption

    assert select_revenue_growth_assumption([], "lower") == (-5.0, "management_outlook_lower")
    assert select_revenue_growth_assumption([], "steady") == (2.0, "management_outlook_steady")
    assert select_revenue_growth_assumption([], "modest_growth") == (
        8.0,
        "management_outlook_modest_growth",
    )
    assert select_revenue_growth_assumption([], "strong_growth") == (
        15.0,
        "management_outlook_strong_growth",
    )


def test_revenue_growth_assumption_not_sure_uses_conservative_history():
    from valuation import select_revenue_growth_assumption

    growth, source = select_revenue_growth_assumption(
        [("2023", 1_000_000), ("2024", 1_200_000), ("2025", 1_440_000)],
        "not_sure",
    )
    assert growth == 12.0  # 20% historical CAGR is capped
    assert source == "historical_revenue_cagr_capped"

    decline, decline_source = select_revenue_growth_assumption(
        [("2024", 1_000_000), ("2025", 800_000)],
        "not_sure",
    )
    assert decline == -5.0  # historical decline is conservatively floored
    assert decline_source == "historical_revenue_cagr_capped"


def test_revenue_growth_assumption_not_sure_uses_actual_year_gap_for_sparse_history():
    from valuation import select_revenue_growth_assumption

    growth, source = select_revenue_growth_assumption(
        [("FY2023", 1_000_000), ("FY2025", 1_210_000)],
        "not_sure",
    )

    assert growth == 10.0
    assert source == "historical_revenue_cagr_capped"

    short_label_growth, short_label_source = select_revenue_growth_assumption(
        [("FY23", 1_000_000), ("FY25", 1_210_000)],
        "not_sure",
    )

    assert short_label_growth == 10.0
    assert short_label_source == "historical_revenue_cagr_capped"

    mixed_range_label_growth, mixed_range_label_source = select_revenue_growth_assumption(
        [("FY2023", 1_000_000), ("FY2024/25", 1_210_000)],
        "not_sure",
    )

    assert mixed_range_label_growth == 10.0
    assert mixed_range_label_source == "historical_revenue_cagr_capped"


def test_revenue_growth_assumption_not_sure_has_low_data_fallback_and_override():
    from valuation import select_revenue_growth_assumption

    assert select_revenue_growth_assumption([("2025", 1_000_000)], "not_sure") == (
        2.0,
        "insufficient_history_fallback",
    )
    assert select_revenue_growth_assumption([], "not_sure", custom_growth_pct=6.4) == (
        6.4,
        "management_custom_override",
    )


def test_growth_assumption_source_label_keeps_legacy_owner_keys_report_safe():
    from valuation import growth_assumption_source_label

    assert growth_assumption_source_label("owner_outlook_modest_growth") == "Management outlook: modest growth"
    assert growth_assumption_source_label("owner_custom_override") == "Management-supplied growth override"


def test_revenue_growth_assumption_has_no_legacy_growth_override():
    from valuation import select_revenue_growth_assumption

    assert "legacy_growth_pct" not in select_revenue_growth_assumption.__annotations__


def test_disclaimer_compliance_fmca():
    """_assert_disclaimer_compliant passes for compliant text and raises for non-compliant."""
    # Compliant disclaimer (all 4 required phrases present)
    compliant = (
        "This report is indicative only and does not constitute financial advice. "
        "It is prepared in accordance with the Financial Markets Conduct Act (FMCA). "
        "This document should not be relied upon as a substitute for professional advice."
    )
    _assert_disclaimer_compliant(compliant)  # must not raise

    # Non-compliant: missing "indicative"
    missing_indicative = (
        "This report does not constitute financial advice. "
        "Prepared under the FMCA. Should not be relied upon."
    )
    with pytest.raises(AssertionError, match="indicative"):
        _assert_disclaimer_compliant(missing_indicative)

    # Non-compliant: missing "financial advice"
    missing_fin_advice = (
        "This report is indicative only. "
        "Prepared under the Financial Markets Conduct Act (FMCA). "
        "Should not be relied upon as a substitute for professional guidance."
    )
    with pytest.raises(AssertionError, match="financial advice"):
        _assert_disclaimer_compliant(missing_fin_advice)

    # Non-compliant: missing FMCA/Financial Markets Conduct
    missing_fmca = (
        "This report is indicative only and does not constitute financial advice. "
        "Readers should seek independent professional advice. "
        "Should not be relied upon."
    )
    with pytest.raises(AssertionError):
        _assert_disclaimer_compliant(missing_fmca)

    # Non-compliant: missing "not relied" / "should not be relied"
    missing_relied = (
        "This report is indicative only and does not constitute financial advice. "
        "Prepared under the FMCA."
    )
    with pytest.raises(AssertionError):
        _assert_disclaimer_compliant(missing_relied)
