"""Deterministic Decimal free-cash-flow-to-firm valuation engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import json
from typing import Any

from valuation_inputs import (
    ConfirmedForecastPolicy,
    ValuationInputs,
    approved_wacc_rates,
)


ENGINE_VERSION = "fcff-decimal-v1"
TERMINAL_SCHEDULE_POLICY_VERSION = "terminal-schedule-growth-v1"
DLOM_POLICY_VERSION = "damodaran-private-volume-zero-iterative-v1"
SCENARIO_ORDER = (
    ("high_wacc_low_value", "high"),
    ("mid_wacc_mid_value", "mid"),
    ("low_wacc_high_value", "low"),
)
_ONE = Decimal("1")
_ZERO = Decimal("0")


class FCFFCalculationError(ValueError):
    """A stable deterministic-calculation failure."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class WaccResult:
    assumption_set_id: int
    assumption_set_name: str
    assumption_set_version: int
    beta_type: str
    source_references: str
    publisher: str
    as_of_date: date
    rationale: str
    approved_at: str
    approved_by: str
    risk_free_rate: Decimal
    equity_risk_premium: Decimal
    beta: Decimal
    additional_premium: Decimal
    pre_tax_cost_of_debt: Decimal
    target_debt_weight: Decimal
    target_equity_weight: Decimal
    scenario_spread: Decimal
    cost_of_equity: Decimal
    after_tax_cost_of_debt: Decimal
    mid: Decimal
    high: Decimal
    low: Decimal


@dataclass(frozen=True, slots=True)
class ForecastYear:
    year: int
    revenue: Decimal
    normalised_ebitda: Decimal
    depreciation_and_amortisation: Decimal
    ebit: Decimal
    tax: Decimal
    nopat: Decimal
    capex: Decimal
    closing_operating_nwc: Decimal
    change_in_operating_nwc: Decimal
    fcff: Decimal


@dataclass(frozen=True, slots=True)
class DiscountedYear:
    year: int
    fcff: Decimal
    discount_factor: Decimal
    present_value: Decimal


@dataclass(frozen=True, slots=True)
class ValuationScenario:
    name: str
    wacc: Decimal
    discounted_years: tuple[DiscountedYear, ...]
    explicit_forecast_present_value: Decimal
    terminal_value: Decimal
    terminal_discount_factor: Decimal
    terminal_present_value: Decimal
    enterprise_value: Decimal
    net_debt: Decimal
    approved_surplus_assets: Decimal
    pre_dlom_equity_value: Decimal
    dlom_policy_version: str
    dlom_revenue: Decimal
    dlom_profitable: bool
    dlom_private_company_monthly_trading_volume: Decimal
    dlom_iterations: int
    dlom_rate: Decimal
    dlom_amount: Decimal
    equity_value: Decimal
    reconciliation_difference: Decimal


@dataclass(frozen=True, slots=True)
class ForecastPolicyResult:
    kind: str
    schedule_semantics: str
    revenue_ratio: Decimal | None
    annual_schedule: tuple[Decimal, ...]


@dataclass(frozen=True, slots=True)
class FCFFResult:
    engine_version: str
    currency: str
    base_period: str
    base_revenue: Decimal
    normalised_ebitda_margin: Decimal
    revenue_growth_rate: Decimal
    terminal_growth_rate: Decimal
    tax_rate: Decimal
    base_operating_nwc: Decimal
    interest_bearing_debt: Decimal
    unrestricted_cash: Decimal
    net_debt: Decimal
    approved_surplus_assets: Decimal
    depreciation_policy: ForecastPolicyResult
    capex_policy: ForecastPolicyResult
    operating_nwc_policy: ForecastPolicyResult
    wacc: WaccResult
    forecast: tuple[ForecastYear, ...]
    terminal_forecast: ForecastYear
    scenarios: tuple[ValuationScenario, ...]


def _fail(code: str, message: str, **details: Any) -> None:
    raise FCFFCalculationError(code, message, details)


def _require_inputs(inputs: ValuationInputs) -> None:
    required = {
        "depreciation_policy": inputs.depreciation_policy,
        "capex_policy": inputs.capex_policy,
        "operating_nwc_policy": inputs.operating_nwc_policy,
        "forecast": inputs.forecast,
        "tax": inputs.tax,
        "wacc_assumption_set": inputs.wacc_assumption_set,
        "base_operating_nwc": inputs.base_operating_nwc,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        _fail("incomplete_inputs", "Complete frozen FCFF inputs are required.", missing=missing)


def _policy_value(
    policy: ConfirmedForecastPolicy,
    revenue: Decimal,
    index: int,
) -> Decimal:
    if policy.revenue_ratio is not None:
        return revenue * policy.revenue_ratio
    return policy.annual_schedule[index]


def _forecast_year(
    *,
    year: int,
    revenue: Decimal,
    margin: Decimal,
    depreciation: Decimal,
    capex: Decimal,
    closing_nwc: Decimal,
    previous_nwc: Decimal,
    tax_rate: Decimal,
) -> ForecastYear:
    ebitda = revenue * margin
    ebit = ebitda - depreciation
    tax = ebit * tax_rate if ebit > _ZERO else _ZERO
    nopat = ebit - tax
    change_nwc = closing_nwc - previous_nwc
    fcff = nopat + depreciation - capex - change_nwc
    return ForecastYear(
        year, revenue, ebitda, depreciation, ebit, tax, nopat, capex,
        closing_nwc, change_nwc, fcff,
    )


def _dlom_rate(revenue: Decimal, profitable: bool, cash: Decimal, equity: Decimal) -> Decimal:
    if equity <= _ZERO:
        return _ZERO
    current_equity = equity
    discount = _ZERO
    log_revenue = revenue.ln() if revenue > _ZERO else _ZERO
    for _ in range(2):
        cash_ratio = cash / current_equity if current_equity > _ZERO else _ZERO
        discount = (
            Decimal("0.145")
            - Decimal("0.0022") * log_revenue
            - Decimal("0.015") * (_ONE if profitable else _ZERO)
            - Decimal("0.016") * cash_ratio
        )
        discount = max(_ZERO, min(discount, Decimal("0.50")))
        current_equity = equity * (_ONE - discount)
    return discount


def calculate_fcff(inputs: ValuationInputs) -> FCFFResult:
    """Calculate the common forecast and all approved WACC scenarios exactly."""
    _require_inputs(inputs)
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        forecast = inputs.forecast
        tax_policy = inputs.tax
        assumptions = inputs.wacc_assumption_set
        approved = approved_wacc_rates(assumptions, tax_policy)
        wacc = WaccResult(
            assumptions.assumption_set_id,
            assumptions.name,
            assumptions.version,
            assumptions.beta_type,
            assumptions.source_references,
            assumptions.publisher,
            assumptions.as_of_date,
            assumptions.rationale,
            assumptions.approved_at,
            assumptions.approved_by,
            assumptions.risk_free_rate,
            assumptions.equity_risk_premium,
            assumptions.beta,
            assumptions.additional_premium,
            assumptions.cost_of_debt,
            assumptions.target_debt_weight,
            assumptions.target_equity_weight,
            assumptions.scenario_spread,
            approved.cost_of_equity,
            approved.after_tax_cost_of_debt,
            approved.mid,
            approved.high,
            approved.low,
        )
        if wacc.low - forecast.terminal_growth_rate < Decimal("0.01"):
            _fail(
                "invalid_terminal_spread",
                "WACC must exceed terminal growth by at least one percentage point in every scenario.",
                low_wacc=str(wacc.low),
                terminal_growth_rate=str(forecast.terminal_growth_rate),
            )

        years = []
        revenue = inputs.revenue.value
        previous_nwc = inputs.base_operating_nwc.value
        for index in range(forecast.horizon_years):
            revenue *= _ONE + forecast.revenue_growth_rate
            depreciation = _policy_value(inputs.depreciation_policy, revenue, index)
            capex = _policy_value(inputs.capex_policy, revenue, index)
            closing_nwc = _policy_value(inputs.operating_nwc_policy, revenue, index)
            year = _forecast_year(
                year=index + 1,
                revenue=revenue,
                margin=forecast.normalised_ebitda_margin,
                depreciation=depreciation,
                capex=capex,
                closing_nwc=closing_nwc,
                previous_nwc=previous_nwc,
                tax_rate=tax_policy.rate,
            )
            years.append(year)
            previous_nwc = closing_nwc

        terminal_growth_factor = _ONE + forecast.terminal_growth_rate
        terminal_revenue = revenue * terminal_growth_factor
        terminal_depreciation = (
            terminal_revenue * inputs.depreciation_policy.revenue_ratio
            if inputs.depreciation_policy.revenue_ratio is not None
            else years[-1].depreciation_and_amortisation * terminal_growth_factor
        )
        terminal_capex = (
            terminal_revenue * inputs.capex_policy.revenue_ratio
            if inputs.capex_policy.revenue_ratio is not None
            else years[-1].capex * terminal_growth_factor
        )
        terminal_nwc = (
            terminal_revenue * inputs.operating_nwc_policy.revenue_ratio
            if inputs.operating_nwc_policy.revenue_ratio is not None
            else years[-1].closing_operating_nwc * terminal_growth_factor
        )
        terminal = _forecast_year(
            year=forecast.horizon_years + 1,
            revenue=terminal_revenue,
            margin=forecast.normalised_ebitda_margin,
            depreciation=terminal_depreciation,
            capex=terminal_capex,
            closing_nwc=terminal_nwc,
            previous_nwc=years[-1].closing_operating_nwc,
            tax_rate=tax_policy.rate,
        )

        scenarios = []
        for name, rate_name in SCENARIO_ORDER:
            rate = getattr(wacc, rate_name)
            discounted = tuple(
                DiscountedYear(
                    item.year,
                    item.fcff,
                    _ONE / ((_ONE + rate) ** item.year),
                    item.fcff / ((_ONE + rate) ** item.year),
                )
                for item in years
            )
            explicit_pv = sum((item.present_value for item in discounted), _ZERO)
            terminal_value = terminal.fcff / (rate - forecast.terminal_growth_rate)
            terminal_factor = _ONE / ((_ONE + rate) ** forecast.horizon_years)
            terminal_pv = terminal_value * terminal_factor
            enterprise_value = explicit_pv + terminal_pv
            pre_dlom = enterprise_value - inputs.net_debt.value + inputs.approved_surplus_assets.value
            dlom_rate = _dlom_rate(
                terminal.revenue,
                terminal.ebit > _ZERO,
                inputs.unrestricted_cash.value,
                pre_dlom,
            )
            dlom_amount = pre_dlom * dlom_rate
            equity = pre_dlom - dlom_amount
            reconciliation = equity - (enterprise_value - inputs.net_debt.value + inputs.approved_surplus_assets.value - dlom_amount)
            if reconciliation != _ZERO:
                _fail("failed_reconciliation", "The equity bridge did not reconcile exactly.", scenario=name)
            scenarios.append(ValuationScenario(
                name, rate, discounted, explicit_pv, terminal_value, terminal_factor,
                terminal_pv, enterprise_value, inputs.net_debt.value,
                inputs.approved_surplus_assets.value, pre_dlom,
                DLOM_POLICY_VERSION, terminal.revenue, terminal.ebit > _ZERO,
                _ZERO, 2, dlom_rate, dlom_amount, equity, reconciliation,
            ))

        enterprise_values = tuple(item.enterprise_value for item in scenarios)
        if assumptions.scenario_spread > _ZERO:
            if not enterprise_values[0] < enterprise_values[1] < enterprise_values[2]:
                _fail("failed_monotonicity", "WACC scenario values are not strictly ordered.")
        elif len(set(enterprise_values)) != 1:
            _fail("failed_monotonicity", "Zero-spread WACC scenario values are not equal.")

        return FCFFResult(
            ENGINE_VERSION,
            inputs.currency,
            inputs.base_period.original,
            inputs.revenue.value,
            forecast.normalised_ebitda_margin,
            forecast.revenue_growth_rate,
            forecast.terminal_growth_rate,
            tax_policy.rate,
            inputs.base_operating_nwc.value,
            inputs.interest_bearing_debt.value,
            inputs.unrestricted_cash.value,
            inputs.net_debt.value,
            inputs.approved_surplus_assets.value,
            ForecastPolicyResult(
                "ratio" if inputs.depreciation_policy.revenue_ratio is not None else "schedule",
                inputs.depreciation_policy.schedule_semantics or "revenue_ratio",
                inputs.depreciation_policy.revenue_ratio,
                inputs.depreciation_policy.annual_schedule,
            ),
            ForecastPolicyResult(
                "ratio" if inputs.capex_policy.revenue_ratio is not None else "schedule",
                inputs.capex_policy.schedule_semantics or "revenue_ratio",
                inputs.capex_policy.revenue_ratio,
                inputs.capex_policy.annual_schedule,
            ),
            ForecastPolicyResult(
                "ratio" if inputs.operating_nwc_policy.revenue_ratio is not None else "schedule",
                inputs.operating_nwc_policy.schedule_semantics or "revenue_ratio",
                inputs.operating_nwc_policy.revenue_ratio,
                inputs.operating_nwc_policy.annual_schedule,
            ),
            wacc,
            tuple(years),
            terminal,
            tuple(scenarios),
        )


def _plain_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _serialise(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _plain_decimal(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_serialise(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {key: _serialise(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _serialise(item) for key, item in value.items()}
    return value


def canonical_calculation_payload(result: FCFFResult) -> dict[str, Any]:
    """Return the digest authority payload, excluding its own digest."""
    payload = _serialise(result)
    payload["policies"] = {
        "engine": ENGINE_VERSION,
        "terminal_schedule_extrapolation": TERMINAL_SCHEDULE_POLICY_VERSION,
        "dlom": DLOM_POLICY_VERSION,
        "tax": "positive-ebit-no-loss-shield-v1",
        "operating_nwc_schedule": "closing-balance-v1",
    }
    return payload


def calculation_digest(result: FCFFResult) -> str:
    encoded = json.dumps(
        canonical_calculation_payload(result),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def report_prompt_payload(result: FCFFResult) -> dict[str, Any]:
    """Return deterministic strings for narrative generation, not report tables."""
    canonical = canonical_calculation_payload(result)
    return {
        "engine_version": result.engine_version,
        "calculation_digest": calculation_digest(result),
        "instruction": "Copy these deterministic numeric strings without recalculation.",
        "currency": result.currency,
        "base_period": canonical["base_period"],
        "base_revenue": canonical["base_revenue"],
        "normalised_ebitda_margin": canonical["normalised_ebitda_margin"],
        "revenue_growth_rate": canonical["revenue_growth_rate"],
        "terminal_growth_rate": canonical["terminal_growth_rate"],
        "tax_rate": canonical["tax_rate"],
        "base_operating_nwc": canonical["base_operating_nwc"],
        "forecast_policies": {
            "depreciation": canonical["depreciation_policy"],
            "capex": canonical["capex_policy"],
            "operating_nwc": canonical["operating_nwc_policy"],
        },
        "calculation_policies": canonical["policies"],
        "bridge_inputs": {
            "interest_bearing_debt": canonical["interest_bearing_debt"],
            "unrestricted_cash": canonical["unrestricted_cash"],
            "net_debt": canonical["net_debt"],
            "approved_surplus_assets": canonical["approved_surplus_assets"],
        },
        "forecast": canonical["forecast"],
        "terminal_forecast": canonical["terminal_forecast"],
        "wacc": canonical["wacc"],
        "scenarios": canonical["scenarios"],
    }
