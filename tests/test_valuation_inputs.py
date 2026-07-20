from dataclasses import FrozenInstanceError
from decimal import Decimal, ROUND_DOWN, localcontext

import pytest

from valuation_inputs import ValuationInputError, build_valuation_inputs


def row(statement, key, label, period, value, **overrides):
    result = {
        "document_id": 7,
        "statement": statement,
        "row_key": key,
        "row_label": label,
        "period": period,
        "value": value,
        "currency": "NZD",
        "unit": "whole",
        "source_text": label,
        "confidence": 0.95,
    }
    result.update(overrides)
    return result


def base_rows(period="2025", bs_period=None):
    bs_period = bs_period or period
    return [
        row("pnl", "revenue", "Revenue", period, 1_000_000),
        row("pnl", "ebitda", "EBITDA", period, 200_000),
        row("bs", "cash_and_bank", "Cash at bank", bs_period, 50_000),
        row("bs", "short_term_debt", "Bank overdraft", bs_period, 20_000),
        row("bs", "long_term_debt", "Bank loan", bs_period, 100_000),
    ]


def complete_fcff_rows():
    return base_rows() + [
        row("pnl", "depreciation", "Depreciation and amortisation", "2025", -30_000),
        row("bs", "trade_debtors", "Trade debtors", "2025", 120_000),
        row("bs", "inventory", "Inventory", "2025", 80_000),
        row("bs", "trade_creditors", "Trade creditors", "2025", 70_000),
    ]


def complete_fcff_frozen(**overrides):
    frozen = {
        "intake_answers": {
            "fcff_assumptions": {
                "forecast": {
                    "horizon_years": 5,
                    "revenue_growth_rate": "0.06",
                    "terminal_growth_rate": "0.025",
                    "confirmed": True,
                },
                "depreciation": {
                    "rate": "0.03", "confirmed": True, "rationale": "Matches FY2025 accounts.",
                    "confirmation_method": "calculated", "confirmation_source": "financial_statements",
                    "source_period": "2025",
                },
                "capex": {
                    "rate": "0.04", "confirmed": True, "rationale": "Confirmed replacement programme.",
                    "confirmation_method": "manual", "confirmation_source": "customer",
                },
                "operating_nwc": {
                    "rate": "0.13", "confirmed": True, "rationale": "Matches normal operating cycle.",
                    "confirmation_method": "calculated", "confirmation_source": "financial_statements",
                    "source_period": "2025",
                },
            }
        },
        "approved_wacc_assumption_set": {
            "id": 4,
            "name": "NZ SME services",
            "version": 2,
            "risk_free_rate": "0.0425",
            "equity_risk_premium": "0.055",
            "beta": "1.1",
            "beta_type": "industry_unlevered_relevered",
            "cost_of_debt": "0.0675",
            "target_debt_weight": "0.30",
            "target_equity_weight": "0.70",
            "additional_premium": "0.02",
            "scenario_spread": "0.01",
            "source_references": "Approved research file",
            "publisher": "AccountIQ valuation team",
            "as_of_date": "2026-07-01",
            "rationale": "Pilot assumptions",
            "approved_at": "2026-07-02 10:00:00",
            "approved_by": "reviewer@example.com",
        },
    }
    frozen.update(overrides)
    return frozen


def assert_error(code, rows, frozen_inputs=None):
    with pytest.raises(ValuationInputError) as exc:
        build_valuation_inputs(rows, frozen_inputs)
    assert exc.value.code == code
    assert exc.value.message
    assert isinstance(exc.value.details, dict)
    return exc.value


def test_fcff_inputs_freeze_same_period_amounts_ratios_tax_forecast_and_wacc():
    inputs = build_valuation_inputs(complete_fcff_rows(), complete_fcff_frozen())

    assert inputs.depreciation_and_amortisation.value == 30_000
    assert inputs.depreciation_and_amortisation.provenance[0].original_value == -30_000
    assert inputs.base_operating_nwc.value == 130_000
    assert [item.row_key for item in inputs.operating_nwc_components] == [
        "trade_debtors", "inventory", "trade_creditors"
    ]
    assert inputs.depreciation_policy.revenue_ratio == Decimal("0.03")
    assert inputs.capex_policy.revenue_ratio == Decimal("0.04")
    assert inputs.operating_nwc_policy.revenue_ratio == Decimal("0.13")
    assert inputs.forecast.horizon_years == 5
    assert inputs.forecast.normalised_ebitda_margin == Decimal("0.2")
    assert inputs.tax.rate == Decimal("0.28")
    assert inputs.tax.policy_version == "nz-company-tax-2026-v1"
    assert inputs.wacc_assumption_set.assumption_set_id == 4
    assert inputs.wacc_assumption_set.risk_free_rate == Decimal("0.0425")
    assert inputs.wacc_assumption_set.target_debt_weight == Decimal("0.30")


def test_fcff_zero_revenue_raises_structured_input_error_before_ratio_division():
    rows = complete_fcff_rows()
    next(item for item in rows if item["row_key"] == "revenue")["value"] = 0

    error = assert_error("missing_forecast_assumptions", rows, complete_fcff_frozen())

    assert error.message == "Revenue must be non-zero to establish FCFF assumptions."


def test_fcff_missing_differs_from_confirmed_zero_with_rationale():
    assert_error("missing_depreciation", base_rows(), complete_fcff_frozen())

    for section in ("depreciation", "capex", "operating_nwc"):
        frozen = complete_fcff_frozen()
        frozen["intake_answers"]["fcff_assumptions"][section] = {
            "rate": 0, "confirmed": True, "rationale": ""
        }
        assert_error(f"missing_{section}_rationale", complete_fcff_rows(), frozen)

    frozen = complete_fcff_frozen()
    frozen["intake_answers"]["fcff_assumptions"]["capex"] = {
        "rate": 0, "confirmed": True, "rationale": "No capital investment in the forecast period."
    }
    assert build_valuation_inputs(complete_fcff_rows(), frozen).capex_policy.revenue_ratio == 0


def test_fcff_annual_schedules_must_match_forecast_horizon():
    for section in ("depreciation", "capex", "operating_nwc"):
        frozen = complete_fcff_frozen()
        frozen["intake_answers"]["fcff_assumptions"][section] = {
            "annual_schedule": [10_000, 11_000, 12_000, 13_000],
            "confirmed": True,
            "rationale": "Annual adviser schedule.",
        }
        error = assert_error(f"missing_{section}", complete_fcff_rows(), frozen)
        assert error.details == {"expected_years": 5, "actual_years": 4}


def test_fcff_override_confirmation_method_and_source_are_retained():
    frozen = complete_fcff_frozen()
    frozen["intake_answers"]["fcff_assumptions"]["depreciation"] = {
        "rate": "0.04",
        "confirmed": True,
        "confirmation_method": "override",
        "confirmation_source": "customer",
        "rationale": "Updated asset register supports the override.",
    }

    policy = build_valuation_inputs(complete_fcff_rows(), frozen).depreciation_policy

    assert policy.confirmed is True
    assert policy.confirmation_method == "override"
    assert policy.confirmation_source == "customer"
    assert policy.rationale == "Updated asset register supports the override."


def test_fcff_non_terminating_derived_ratios_use_shared_ten_place_precision():
    rows = complete_fcff_rows()
    next(item for item in rows if item["row_key"] == "revenue")["value"] = 30
    next(item for item in rows if item["row_key"] == "ebitda")["value"] = 1
    next(item for item in rows if item["row_key"] == "depreciation")["value"] = -1
    next(item for item in rows if item["row_key"] == "trade_debtors")["value"] = 2
    next(item for item in rows if item["row_key"] == "inventory")["value"] = 0
    next(item for item in rows if item["row_key"] == "trade_creditors")["value"] = 0
    frozen = complete_fcff_frozen()
    frozen["intake_answers"]["fcff_assumptions"]["depreciation"]["rate"] = "0.0333333333"
    frozen["intake_answers"]["fcff_assumptions"]["operating_nwc"]["rate"] = "0.0666666667"

    from valuation_inputs import derive_fcff_assumption_readiness
    with localcontext() as context:
        context.rounding = ROUND_DOWN
        readiness = derive_fcff_assumption_readiness(rows)
        inputs = build_valuation_inputs(rows, frozen)

    assert readiness["depreciation"]["rate"] == Decimal("0.0333333333")
    assert readiness["operating_nwc"]["rate"] == Decimal("0.0666666667")
    assert inputs.depreciation_policy.revenue_ratio == Decimal("0.0333333333")
    assert inputs.operating_nwc_policy.revenue_ratio == Decimal("0.0666666667")
    assert inputs.forecast.normalised_ebitda_margin == Decimal("0.0333333333")


    for section, changed_rate in (("depreciation", "0.031"), ("operating_nwc", "0.131")):
        frozen = complete_fcff_frozen()
        frozen["intake_answers"]["fcff_assumptions"][section]["rate"] = changed_rate
        assert_error(f"invalid_calculated_{section}", complete_fcff_rows(), frozen)

        frozen = complete_fcff_frozen()
        frozen["intake_answers"]["fcff_assumptions"][section]["source_period"] = "2024"
        assert_error(f"invalid_calculated_{section}", complete_fcff_rows(), frozen)


def test_fcff_changed_derived_policy_requires_override_and_rationale():
    frozen = complete_fcff_frozen()
    frozen["intake_answers"]["fcff_assumptions"]["depreciation"].update({
        "rate": "0.04",
        "confirmation_method": "override",
        "confirmation_source": "customer",
        "rationale": "",
    })
    assert_error("missing_depreciation_rationale", complete_fcff_rows(), frozen)

    frozen["intake_answers"]["fcff_assumptions"]["depreciation"]["rationale"] = "Updated asset register."
    policy = build_valuation_inputs(complete_fcff_rows(), frozen).depreciation_policy
    assert policy.revenue_ratio == Decimal("0.04")
    assert policy.confirmation_method == "override"


def test_fcff_readiness_uses_selected_complete_valuation_base_period():
    rows = complete_fcff_rows() + [
        row("pnl", "revenue", "Revenue", "2026", 2_000_000),
        row("pnl", "depreciation", "Depreciation", "2026", -80_000),
        row("bs", "trade_debtors", "Trade debtors", "2026", 220_000),
        row("bs", "inventory", "Inventory", "2026", 160_000),
        row("bs", "trade_creditors", "Trade creditors", "2026", 100_000),
    ]

    from valuation_inputs import derive_fcff_assumption_readiness
    readiness = derive_fcff_assumption_readiness(rows)

    assert readiness["depreciation"]["source_period"] == "2025"
    assert readiness["depreciation"]["rate"] == Decimal("0.03")
    assert readiness["operating_nwc"]["source_period"] == "2025"
    assert readiness["operating_nwc"]["rate"] == Decimal("0.13")


def test_fcff_requires_approved_nwc_components_forecast_wacc_and_terminal_spread():
    rows = [item for item in complete_fcff_rows() if item["row_key"] != "inventory"]
    assert_error("missing_operating_nwc", rows, complete_fcff_frozen())

    frozen = complete_fcff_frozen()
    del frozen["intake_answers"]["fcff_assumptions"]["forecast"]
    assert_error("missing_forecast_assumptions", complete_fcff_rows(), frozen)

    frozen = complete_fcff_frozen()
    del frozen["approved_wacc_assumption_set"]
    assert_error("missing_wacc_approval", complete_fcff_rows(), frozen)

    frozen = complete_fcff_frozen()
    frozen["intake_answers"]["fcff_assumptions"]["forecast"]["terminal_growth_rate"] = "0.09"
    assert_error("invalid_terminal_spread", complete_fcff_rows(), frozen)


@pytest.mark.parametrize(
    ("unit", "factor"),
    [("whole", 1), ("thousands", 1_000), ("millions", 1_000_000)],
)
def test_supported_units_are_converted_to_whole_currency_units(unit, factor):
    rows = base_rows()
    for item in rows:
        item["unit"] = unit
        item["value"] /= factor

    inputs = build_valuation_inputs(rows)

    assert inputs.revenue.value == 1_000_000
    assert inputs.revenue.provenance[0].original_unit == unit
    assert inputs.revenue.provenance[0].normalised_value == 1_000_000


def test_unsupported_unit_fails_before_arithmetic():
    rows = base_rows()
    rows[0]["unit"] = "000s"
    assert_error("unsupported_unit", rows)


def test_currency_must_be_one_well_formed_iso_style_code():
    assert build_valuation_inputs(base_rows()).currency == "NZD"

    rows = base_rows()
    rows[-1]["currency"] = "AUD"
    assert_error("mixed_currency", rows)

    rows = base_rows()
    rows[0]["currency"] = "$NZ"
    assert_error("mixed_currency", rows)


@pytest.mark.parametrize("period", ["2025", "FY2025", "FY 2025", "2025-12-31"])
def test_supported_period_forms(period):
    inputs = build_valuation_inputs(base_rows(period))
    assert inputs.base_period.fiscal_year == 2025
    assert inputs.base_period.end_date.isoformat() == "2025-12-31"


def test_latest_complete_pnl_period_is_selected_chronologically():
    rows = base_rows("2024") + base_rows("2025")
    inputs = build_valuation_inputs(rows)
    assert inputs.base_period.fiscal_year == 2025
    assert inputs.revenue.value == 1_000_000


def test_unsupported_and_incompatible_periods_fail_closed():
    rows = base_rows()
    rows[0]["period"] = "Q4 2025"
    assert_error("unsupported_period", rows)

    assert_error("incompatible_balance_sheet_period", base_rows("2025", "2024"))


def test_equivalent_period_spellings_are_ambiguous():
    rows = base_rows()
    rows.append(row("pnl", "revenue", "Sales", "FY2025", 1_000_000))
    assert_error("ambiguous_base_period", rows)


def test_duplicate_canonical_input_is_rejected():
    rows = base_rows()
    rows.append(row("pnl", "revenue", "Sales", "2025", 1_000_000, document_id=8))
    assert_error("duplicate_financial_input", rows)


def test_missing_revenue_differs_from_reported_zero():
    assert_error("missing_revenue", [item for item in base_rows() if item["row_key"] != "revenue"])

    rows = base_rows()
    rows[0]["value"] = 0
    assert build_valuation_inputs(rows).revenue.value == 0


def test_reported_ebitda_including_zero_takes_priority():
    rows = base_rows()
    rows[1]["value"] = 0
    rows.extend([
        row("pnl", "ebit", "Operating profit", "2025", 150_000),
        row("pnl", "depreciation", "Depreciation", "2025", 30_000),
    ])
    inputs = build_valuation_inputs(rows)
    assert inputs.ebitda.value == 0
    assert inputs.ebitda.provenance[0].transformation == "reported_ebitda"


def test_ebitda_falls_back_to_same_period_ebit_plus_depreciation():
    rows = [item for item in base_rows() if item["row_key"] != "ebitda"]
    rows.extend([
        row("pnl", "ebit", "Operating profit", "2025", 150_000),
        row("pnl", "depreciation_amortisation", "D&A", "2025", 30_000),
    ])
    inputs = build_valuation_inputs(rows)
    assert inputs.ebitda.value == 180_000
    assert len(inputs.ebitda.provenance) == 2
    assert {p.transformation for p in inputs.ebitda.provenance} == {
        "ebit_before_depreciation_addback",
        "absolute_depreciation_added_to_ebit",
    }


def test_negative_depreciation_is_added_back_using_its_absolute_value():
    rows = [item for item in base_rows() if item["row_key"] != "ebitda"]
    rows.extend([
        row("pnl", "ebit", "Operating profit", "2025", 150_000),
        row("pnl", "depreciation", "Depreciation", "2025", -30_000),
    ])

    inputs = build_valuation_inputs(rows)

    assert inputs.ebitda.value == 180_000
    depreciation = next(p for p in inputs.ebitda.provenance if p.row_key == "depreciation")
    assert depreciation.normalised_value == 30_000
    assert depreciation.transformation == "absolute_depreciation_added_to_ebit"


def test_npat_plus_depreciation_is_not_an_ebitda_fallback():
    rows = [item for item in base_rows() if item["row_key"] != "ebitda"]
    rows.extend([
        row("pnl", "net_profit", "NPAT", "2025", 100_000),
        row("pnl", "depreciation", "Depreciation", "2025", 30_000),
    ])
    assert_error("missing_ebitda", rows)


@pytest.mark.parametrize(
    ("key", "label"),
    [
        ("short_term_debt", "Current bank loan"),
        ("long_term_debt", "Bank loan"),
        ("bank_debt", "Bank debt"),
        ("overdraft", "Bank overdraft"),
        ("finance_lease", "Finance lease liability"),
        ("hire_purchase", "Hire purchase liability"),
        ("shareholder_loan", "Shareholder loan"),
        ("director_loan", "Director loan"),
    ],
)
def test_approved_debt_categories_are_interest_bearing(key, label):
    rows = [item for item in base_rows() if item["statement"] != "bs"]
    rows.extend([
        row("bs", "cash_and_bank", "Cash at bank", "2025", 0),
        row("bs", key, label, "2025", 75_000),
    ])
    inputs = build_valuation_inputs(rows)
    assert inputs.interest_bearing_debt.value == 75_000
    assert inputs.net_debt.value == 75_000


def test_missing_debt_or_cash_does_not_silently_become_zero():
    rows = base_rows()
    assert_error("missing_debt", [item for item in rows if "debt" not in item["row_key"]])
    assert_error("missing_cash", [item for item in rows if item["row_key"] != "cash_and_bank"])


def test_total_liability_rows_are_not_treated_as_interest_bearing_debt():
    rows = [item for item in base_rows() if item["row_key"] != "long_term_debt"]
    rows.append(row("bs", "long_term_debt", "Total non current liabilities", "2025", 500_000))
    assert_error("ambiguous_debt_classification", rows)


def test_combined_cash_and_investment_rows_require_clarification():
    rows = base_rows()
    rows[2]["row_label"] = "Cash and short-term investments"
    rows[2]["source_text"] = "Cash and short-term investments"
    assert_error("ambiguous_cash_classification", rows)


def test_debt_heavy_and_net_cash_cases():
    debt_heavy = build_valuation_inputs(base_rows())
    assert debt_heavy.interest_bearing_debt.value == 120_000
    assert debt_heavy.net_debt.value == 70_000

    rows = base_rows()
    rows[2]["value"] = 200_000
    assert build_valuation_inputs(rows).net_debt.value == -80_000


def test_combined_or_unclear_debt_rows_fail_closed():
    rows = base_rows()
    rows.append(row("bs", "other_current_liab", "Trade creditors and bank debt", "2025", 90_000))
    assert_error("ambiguous_debt_classification", rows)


def test_only_clearly_unrestricted_cash_is_deducted():
    assert build_valuation_inputs(base_rows()).unrestricted_cash.value == 50_000

    for label in ("Restricted cash", "Cash held in trust"):
        rows = base_rows()
        rows[2]["row_label"] = label
        rows[2]["source_text"] = label
        assert_error("ambiguous_cash_classification", rows)


def test_surplus_assets_default_to_zero_or_require_explicit_approval():
    inputs = build_valuation_inputs(base_rows())
    assert inputs.surplus_assets.value == 0
    assert inputs.surplus_assets.provenance[0].transformation == "explicitly_absent"

    frozen = {
        "approved_surplus_assets": {
            "amount": 25_000,
            "rationale": "Unused investment property approved by reviewer",
            "approved": True,
            "source_text": "Reviewer approval SA-1",
        }
    }
    inputs = build_valuation_inputs(base_rows(), frozen)
    assert inputs.surplus_assets.value == 25_000
    assert inputs.surplus_assets.provenance[0].source_text == "Reviewer approval SA-1"

    frozen["approved_surplus_assets"]["approved"] = False
    assert_error("invalid_normalisation", base_rows(), frozen)


def test_normalisations_are_validated_preserved_and_applied():
    frozen = {
        "ebitda_adjustments": [
            {"label": "Owner wage", "amount": 20_000, "rationale": "Adjustment to market salary"},
            {"label": "One-off legal cost", "amount": -5_000, "rationale": "Non-recurring settlement reversal"},
        ]
    }
    inputs = build_valuation_inputs(base_rows(), frozen)
    assert [item.label for item in inputs.normalisations] == ["Owner wage", "One-off legal cost"]
    assert inputs.normalised_ebitda.value == 215_000
    assert len(inputs.normalised_ebitda.provenance) == 3

    for adjustment in (
        "invalid",
        {"label": "", "amount": 1, "rationale": "Reason"},
        {"label": "Owner wage", "amount": None, "rationale": "Reason"},
        {"label": "Owner wage", "amount": 1, "rationale": ""},
    ):
        assert_error("invalid_normalisation", base_rows(), {"ebitda_adjustments": [adjustment]})


def test_confirmed_intake_normalisations_take_precedence_over_legacy_adjustments():
    frozen = {
        "intake_answers": {
            "normalisations": [
                {"label": "Confirmed wage", "amount": 12_000, "rationale": "Confirmed by customer"},
            ]
        },
        "ebitda_adjustments": [
            {"label": "Legacy wage", "amount": 20_000, "rationale": "Legacy profile value"},
        ],
    }

    inputs = build_valuation_inputs(base_rows(), frozen)

    assert [item.label for item in inputs.normalisations] == ["Confirmed wage"]
    assert inputs.normalised_ebitda.value == 212_000


def test_explicitly_empty_intake_normalisations_do_not_restore_legacy_adjustments():
    frozen = {
        "intake_answers": {"normalisations": []},
        "ebitda_adjustments": [
            {"label": "Legacy wage", "amount": 20_000, "rationale": "Legacy profile value"},
        ],
    }

    inputs = build_valuation_inputs(base_rows(), frozen)

    assert inputs.normalisations == ()
    assert inputs.normalised_ebitda.value == 200_000


def test_selected_and_derived_values_have_full_provenance_and_models_are_frozen():
    inputs = build_valuation_inputs(base_rows())
    provenance = inputs.revenue.provenance[0]
    assert provenance.document_id == 7
    assert provenance.statement == "pnl"
    assert provenance.row_key == "revenue"
    assert provenance.row_label == "Revenue"
    assert provenance.original_period == "2025"
    assert provenance.currency == "NZD"
    assert provenance.original_unit == "whole"
    assert provenance.original_value == 1_000_000
    assert provenance.normalised_value == 1_000_000
    assert provenance.source_text == "Revenue"
    assert provenance.confidence == 0.95
    assert provenance.transformation == "unit_to_whole"
    assert inputs.net_debt.provenance

    with pytest.raises(FrozenInstanceError):
        inputs.currency = "AUD"
