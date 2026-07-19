from dataclasses import FrozenInstanceError

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


def assert_error(code, rows, frozen_inputs=None):
    with pytest.raises(ValuationInputError) as exc:
        build_valuation_inputs(rows, frozen_inputs)
    assert exc.value.code == code
    assert exc.value.message
    assert isinstance(exc.value.details, dict)
    return exc.value


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
