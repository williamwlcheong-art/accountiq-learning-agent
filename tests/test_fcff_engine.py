from dataclasses import FrozenInstanceError
from decimal import Decimal, ROUND_DOWN, localcontext
import json

import pytest

from fcff_engine import (
    ENGINE_VERSION,
    FCFFCalculationError,
    calculate_fcff,
    canonical_calculation_payload,
    calculation_digest,
    report_prompt_payload,
)
from test_valuation_inputs import complete_fcff_frozen, complete_fcff_rows
from valuation_inputs import build_valuation_inputs


def calculate(overrides=None):
    frozen = complete_fcff_frozen()
    if overrides:
        overrides(frozen)
    return calculate_fcff(build_valuation_inputs(complete_fcff_rows(), frozen, require_fcff=True))


def test_report_prompt_payload_includes_explicit_equity_bridge_inputs():
    payload = report_prompt_payload(calculate())

    assert payload["bridge_inputs"] == {
        "interest_bearing_debt": "120000",
        "unrestricted_cash": "50000",
        "net_debt": "70000",
        "approved_surplus_assets": "0",
    }
    assert payload["base_period"] == "2025"
    assert payload["base_revenue"] == "1000000"
    assert payload["revenue_growth_rate"] == "0.06"
    assert payload["terminal_growth_rate"] == "0.025"
    assert payload["tax_rate"] == "0.28"
    assert payload["forecast_policies"]["operating_nwc"]["schedule_semantics"] == "revenue_ratio"
    assert payload["calculation_policies"]["tax"] == "positive-ebit-no-loss-shield-v1"


def test_calculates_approved_wacc_forecast_and_terminal_fcff():
    result = calculate()

    assert result.wacc.cost_of_equity == Decimal("0.123")
    assert result.wacc.after_tax_cost_of_debt == Decimal("0.0486")
    assert result.wacc.mid == Decimal("0.10068")
    expected = [
        (1, Decimal("1060000"), Decimal("212000"), Decimal("31800"), Decimal("180200"), Decimal("50456"), Decimal("129744"), Decimal("42400"), Decimal("137800"), Decimal("7800"), Decimal("111344")),
        (2, Decimal("1123600"), Decimal("224720"), Decimal("33708"), Decimal("191012"), Decimal("53483.36"), Decimal("137528.64"), Decimal("44944"), Decimal("146068"), Decimal("8268"), Decimal("118024.64")),
        (3, Decimal("1191016"), Decimal("238203.2"), Decimal("35730.48"), Decimal("202472.72"), Decimal("56692.3616"), Decimal("145780.3584"), Decimal("47640.64"), Decimal("154832.08"), Decimal("8764.08"), Decimal("125106.1184")),
        (4, Decimal("1262476.96"), Decimal("252495.392"), Decimal("37874.3088"), Decimal("214621.0832"), Decimal("60093.903296"), Decimal("154527.179904"), Decimal("50499.0784"), Decimal("164122.0048"), Decimal("9289.9248"), Decimal("132612.485504")),
        (5, Decimal("1338225.5776"), Decimal("267645.11552"), Decimal("40146.767328"), Decimal("227498.348192"), Decimal("63699.53749376"), Decimal("163798.81069824"), Decimal("53529.023104"), Decimal("173969.325088"), Decimal("9847.320288"), Decimal("140569.23463424")),
    ]
    assert len(result.forecast) == len(expected) == 5
    for year, values in zip(result.forecast, expected):
        assert (year.year, *(getattr(year, field) for field in (
            "revenue", "normalised_ebitda", "depreciation_and_amortisation",
            "ebit", "tax", "nopat", "capex", "closing_operating_nwc",
            "change_in_operating_nwc", "fcff",
        ))) == values
    terminal = result.terminal_forecast
    assert (
        terminal.year,
        terminal.revenue,
        terminal.normalised_ebitda,
        terminal.depreciation_and_amortisation,
        terminal.ebit,
        terminal.tax,
        terminal.nopat,
        terminal.capex,
        terminal.closing_operating_nwc,
        terminal.change_in_operating_nwc,
        terminal.fcff,
    ) == (
        6,
        Decimal("1371681.21704"),
        Decimal("274336.243408"),
        Decimal("41150.4365112"),
        Decimal("233185.8068968"),
        Decimal("65292.025931104"),
        Decimal("167893.780965696"),
        Decimal("54867.2486816"),
        Decimal("178318.5582152"),
        Decimal("4349.2331272"),
        Decimal("149827.735668096"),
    )


def test_schedule_policies_are_amounts_and_nwc_is_a_closing_balance():
    def schedules(frozen):
        assumptions = frozen["intake_answers"]["fcff_assumptions"]
        assumptions["depreciation"] = {"annual_schedule": [10, 20, 30, 40, 50], "confirmed": True, "rationale": "Schedule"}
        assumptions["capex"] = {"annual_schedule": [100, 200, 300, 400, 500], "confirmed": True, "rationale": "Schedule"}
        assumptions["operating_nwc"] = {"annual_schedule": [140000, 150000, 160000, 170000, 180000], "confirmed": True, "rationale": "Schedule"}

    result = calculate(schedules)

    assert result.forecast[0].depreciation_and_amortisation == 10
    assert result.forecast[0].capex == 100
    assert result.forecast[0].closing_operating_nwc == 140000
    assert result.forecast[0].change_in_operating_nwc == 10000
    assert result.forecast[1].change_in_operating_nwc == 10000
    assert result.terminal_forecast.depreciation_and_amortisation == Decimal("51.250")
    assert result.terminal_forecast.capex == Decimal("512.500")
    assert result.terminal_forecast.closing_operating_nwc == Decimal("184500.000")
    assert result.terminal_forecast.change_in_operating_nwc == Decimal("4500.000")


def test_tax_is_only_charged_on_positive_ebit_and_zero_policies_are_exact():
    def zero(frozen):
        assumptions = frozen["intake_answers"]["fcff_assumptions"]
        assumptions["depreciation"] = {"rate": "0", "confirmed": True, "rationale": "None", "confirmation_method": "override"}
        assumptions["capex"] = {"rate": "0", "confirmed": True, "rationale": "None"}
        assumptions["operating_nwc"] = {"rate": "0", "confirmed": True, "rationale": "None", "confirmation_method": "override"}

    assert calculate(zero).forecast[0].tax > 0

    def loss(frozen):
        frozen["intake_answers"]["normalisations"] = [{"label": "Loss", "amount": -250000, "rationale": "Normalised loss"}]
        zero(frozen)
        frozen["approved_wacc_assumption_set"]["scenario_spread"] = "0"

    loss_result = calculate(loss)
    assert loss_result.forecast[0].ebit < 0
    assert loss_result.forecast[0].tax == 0

    def break_even(frozen):
        frozen["intake_answers"]["normalisations"] = [{"label": "Break even", "amount": -200000, "rationale": "Normalised break even"}]
        zero(frozen)
        frozen["approved_wacc_assumption_set"]["scenario_spread"] = "0"

    assert calculate(break_even).forecast[0].ebit == 0
    assert calculate(break_even).forecast[0].tax == 0


def test_each_scenario_discounts_terminal_value_and_reconciles_equity_after_dlom():
    result = calculate()

    assert [scenario.name for scenario in result.scenarios] == [
        "high_wacc_low_value", "mid_wacc_mid_value", "low_wacc_high_value"
    ]
    high, mid, low = result.scenarios
    assert high.enterprise_value < mid.enterprise_value < low.enterprise_value
    expected = {
        "high_wacc_low_value": {
            "present_values": (
                "100248.4964166096445420823279432419778874203190838",
                "95674.187166066034514538181672341715490209185569951",
                "91308.602294117114367243915954804460708414427831732",
                "87142.217769082130973168285115508272725644914378251",
                "83165.944138029908552921077378217640624827681457257",
            ),
            "explicit_pv": "457539.44778390483294995378806411406743651652832099",
            "terminal_value": "1748689.7253512605042016806722689075630252100840336",
            "terminal_pv": "1034589.3423388210951945715952327327244592235565968",
            "enterprise_value": "1492128.7901227259281445253832968467918957400849178",
            "pre_dlom": "1422128.7901227259281445253832968467918957400849178",
            "dlom_rate": "0.098286699129025495940323363081947252742067686421642",
            "dlom_amount": "139776.34451751740879563334513800100228022704647319",
            "equity_value": "1282352.4456052085193488920381588457896155130384446",
        },
        "mid_wacc_mid_value": {
            "present_values": (
                "101159.28335210960497147218083366646073336482901479",
                "97420.54035072517104858861038965589306371217679587",
                "93819.977442825054794766805077802128363861346988791",
                "90352.487634366535307675994278509881224055154820764",
                "87013.152680550684509699961782916446285476672702338",
            ),
            "explicit_pv": "469765.44146057705063220355236255080967047018032255",
            "terminal_value": "1979753.3782782241014799154334038054968287526427061",
            "terminal_pv": "1225478.5581083241023078222345698379675481846676044",
            "enterprise_value": "1695243.999568901152940025786932388777218654847927",
            "pre_dlom": "1625243.999568901152940025786932388777218654847927",
            "dlom_rate": "0.098364628080801402403495263061222047999256015016186",
            "dlom_amount": "159866.52155814911669074960674370861220142716787197",
            "equity_value": "1465377.478010752036249276180188680165017227680055",
        },
        "low_wacc_high_value": {
            "present_values": (
                "102086.77155535995892470752191293504969376902482855",
                "99215.148209082000641975623673039894997061618731672",
                "96424.301446461767594981260400321165416882418175425",
                "93711.959083552896954817302989273146424153155156371",
                "91075.912851217653915086314197225157891959460580329",
            ),
            "explicit_pv": "482514.09314567427803156802317279441442382567747234",
            "terminal_value": "2281177.461450913520097442143727161997563946406821",
            "terminal_pv": "1477992.8212446768546095931656838234719004191439881",
            "enterprise_value": "1960506.9143903511326411611888566178863242448214604",
            "pre_dlom": "1890506.9143903511326411611888566178863242448214604",
            "dlom_rate": "0.098441198446355181085732378840383413419698829375784",
            "dlom_amount": "186103.76632370716125438715099062810212548314378379",
            "equity_value": "1704403.1480666439713867740378659897841987616776766",
        },
    }
    assert len(result.scenarios) == 3
    for scenario in result.scenarios:
        values = expected[scenario.name]
        assert len(scenario.discounted_years) == len(result.forecast) == 5
        assert tuple(item.present_value for item in scenario.discounted_years) == tuple(
            Decimal(value) for value in values["present_values"]
        )
        assert scenario.explicit_forecast_present_value == Decimal(values["explicit_pv"])
        assert scenario.terminal_value == Decimal(values["terminal_value"])
        assert scenario.terminal_present_value == Decimal(values["terminal_pv"])
        assert scenario.enterprise_value == Decimal(values["enterprise_value"])
        assert scenario.net_debt == Decimal("70000")
        assert scenario.approved_surplus_assets == Decimal("0")
        assert scenario.pre_dlom_equity_value == Decimal(values["pre_dlom"])
        assert scenario.dlom_rate == Decimal(values["dlom_rate"])
        assert scenario.dlom_amount == Decimal(values["dlom_amount"])
        assert scenario.equity_value == Decimal(values["equity_value"])
        assert scenario.reconciliation_difference == 0


def test_net_cash_surplus_assets_and_zero_spread_reconcile():
    rows = complete_fcff_rows()
    next(item for item in rows if item["row_key"] == "cash_and_bank")["value"] = 200000
    frozen = complete_fcff_frozen(approved_surplus_assets={
        "amount": 25000, "rationale": "Approved", "approved": True, "source_text": "SA-1"
    })
    frozen["approved_wacc_assumption_set"]["scenario_spread"] = "0"
    result = calculate_fcff(build_valuation_inputs(rows, frozen, require_fcff=True))

    assert result.net_debt == Decimal("-80000")
    assert result.approved_surplus_assets == Decimal("25000")
    assert len({scenario.enterprise_value for scenario in result.scenarios}) == 1
    assert all(s.pre_dlom_equity_value - s.enterprise_value == Decimal("105000") for s in result.scenarios)


def test_terminal_spread_one_point_boundary_is_accepted():
    def boundary(frozen):
        frozen["intake_answers"]["fcff_assumptions"]["forecast"]["terminal_growth_rate"] = "0.08068"

    result = calculate(boundary)
    assert result.wacc.low - result.terminal_growth_rate == Decimal("0.01")


def test_results_are_immutable_and_ignore_ambient_decimal_context():
    baseline = calculate()
    with pytest.raises(FrozenInstanceError):
        baseline.currency = "AUD"

    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        changed_context = calculate()
    assert changed_context == baseline


def test_canonical_payload_digest_and_prompt_serialisation_are_stable_and_decimal_only():
    result = calculate()
    payload = canonical_calculation_payload(result)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = calculation_digest(result)

    assert payload["wacc"]["assumption_set_id"] == 4
    assert payload["wacc"]["assumption_set_name"] == "NZ SME services"
    assert payload["wacc"]["assumption_set_version"] == 2
    assert payload["wacc"]["beta_type"] == "industry_unlevered_relevered"
    assert payload["wacc"]["source_references"] == "Approved research file"
    assert payload["wacc"]["publisher"] == "AccountIQ valuation team"
    assert payload["wacc"]["as_of_date"] == "2026-07-01"
    assert payload["wacc"]["rationale"] == "Pilot assumptions"
    assert payload["wacc"]["approved_at"] == "2026-07-02 10:00:00"
    assert payload["wacc"]["approved_by"] == "reviewer@example.com"
    assert payload["wacc"]["risk_free_rate"] == "0.0425"
    assert digest == "3677853337f49c493832742a8cb32ce4fa6a09db5f16e37065ee33d733b983dc"
    assert len(digest) == 64
    assert "e+" not in encoded.lower()
    assert not any(isinstance(value, float) for value in _walk(payload))
    prompt = report_prompt_payload(result)
    assert prompt["bridge_inputs"] == {
        "interest_bearing_debt": "120000",
        "unrestricted_cash": "50000",
        "net_debt": "70000",
        "approved_surplus_assets": "0",
    }
    assert prompt["calculation_digest"] == digest
    assert prompt["instruction"] == "Copy these deterministic numeric strings without recalculation."
    assert [item["name"] for item in prompt["scenarios"]] == [s.name for s in result.scenarios]

    def changed_metadata(frozen):
        frozen["approved_wacc_assumption_set"]["version"] = 3
    assert calculation_digest(calculate(changed_metadata)) != digest

    def changed(frozen):
        frozen["intake_answers"]["fcff_assumptions"]["forecast"]["revenue_growth_rate"] = "0.061"
    assert calculation_digest(calculate(changed)) != digest


def test_incomplete_inputs_and_invalid_terminal_spread_have_stable_errors():
    inputs = build_valuation_inputs(complete_fcff_rows())
    with pytest.raises(FCFFCalculationError) as exc:
        calculate_fcff(inputs)
    assert exc.value.code == "incomplete_inputs"
    assert exc.value.details

    frozen = complete_fcff_frozen()
    frozen["intake_answers"]["fcff_assumptions"]["forecast"]["terminal_growth_rate"] = "0.08069"
    with pytest.raises(Exception) as input_exc:
        build_valuation_inputs(complete_fcff_rows(), frozen, require_fcff=True)
    assert input_exc.value.code == "invalid_terminal_spread"


def _walk(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)
    else:
        yield value
