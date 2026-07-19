"""Pure validation and normalisation of frozen valuation inputs."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Any


_UNIT_FACTORS = {
    "whole": Decimal("1"),
    "thousands": Decimal("1000"),
    "millions": Decimal("1000000"),
}
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_YEAR_RE = re.compile(r"^(?:FY\s*)?(\d{4})$", re.IGNORECASE)
_DEPRECIATION_KEYS = {"depreciation", "depreciation_amortisation"}
_DEBT_KEYS = {
    "short_term_debt",
    "long_term_debt",
    "bank_debt",
    "bank_loan",
    "overdraft",
    "finance_lease",
    "finance_leases",
    "hire_purchase",
    "shareholder_loan",
    "shareholder_loans",
    "director_loan",
    "director_loans",
}
_DEBT_TERMS = (
    "bank debt",
    "bank loan",
    "borrowings",
    "overdraft",
    "finance lease",
    "hire purchase",
    "shareholder loan",
    "director loan",
)
_AMBIGUOUS_DEBT_TERMS = (
    "trade creditor",
    "trade payable",
    "accounts payable",
    "other liabilit",
    "total liabilities",
    "total current liabilities",
    "total non current liabilities",
    "total non-current liabilities",
    "tax",
    "accrual",
    "provision",
)
_RESTRICTED_CASH_TERMS = ("restricted", "held in trust", "escrow", "term deposit pledged")
_AMBIGUOUS_CASH_TERMS = (
    "investment",
    "term deposit",
    "marketable securit",
    "financial asset",
)


class ValuationInputError(ValueError):
    """A stable, customer-safe valuation input validation error."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


@dataclass(frozen=True)
class FiscalPeriod:
    original: str
    fiscal_year: int
    end_date: date


@dataclass(frozen=True)
class ValueProvenance:
    document_id: int | None
    statement: str | None
    row_key: str | None
    row_label: str | None
    original_period: str | None
    currency: str
    original_unit: str
    original_value: Decimal | None
    normalised_value: Decimal
    source_text: str | None
    confidence: float | None
    transformation: str


@dataclass(frozen=True)
class ValuationAmount:
    value: Decimal
    provenance: tuple[ValueProvenance, ...]


@dataclass(frozen=True)
class Normalisation:
    label: str
    amount: Decimal
    rationale: str
    provenance: ValueProvenance


@dataclass(frozen=True)
class ConfirmedForecastPolicy:
    revenue_ratio: Decimal | None
    annual_schedule: tuple[Decimal, ...]
    rationale: str
    confirmed: bool
    confirmation_method: str | None = None
    confirmation_source: str | None = None


@dataclass(frozen=True)
class ForecastAssumptions:
    horizon_years: int
    revenue_growth_rate: Decimal
    terminal_growth_rate: Decimal
    normalised_ebitda_margin: Decimal


@dataclass(frozen=True)
class TaxPolicy:
    rate: Decimal
    policy_version: str
    positive_ebit_only: bool
    loss_tax_shield: bool


@dataclass(frozen=True)
class FrozenWaccAssumptionSet:
    assumption_set_id: int
    name: str
    version: int
    risk_free_rate: Decimal
    equity_risk_premium: Decimal
    beta: Decimal
    beta_type: str
    cost_of_debt: Decimal
    target_debt_weight: Decimal
    target_equity_weight: Decimal
    additional_premium: Decimal
    scenario_spread: Decimal
    source_references: str
    publisher: str
    as_of_date: date
    rationale: str
    approved_at: str
    approved_by: str


@dataclass(frozen=True)
class ValuationInputs:
    currency: str
    base_period: FiscalPeriod
    revenue: ValuationAmount
    ebitda: ValuationAmount
    normalisations: tuple[Normalisation, ...]
    normalised_ebitda: ValuationAmount
    interest_bearing_debt: ValuationAmount
    unrestricted_cash: ValuationAmount
    approved_surplus_assets: ValuationAmount
    net_debt: ValuationAmount
    depreciation_and_amortisation: ValuationAmount | None = None
    operating_nwc_components: tuple[ValueProvenance, ...] = ()
    base_operating_nwc: ValuationAmount | None = None
    depreciation_policy: ConfirmedForecastPolicy | None = None
    capex_policy: ConfirmedForecastPolicy | None = None
    operating_nwc_policy: ConfirmedForecastPolicy | None = None
    forecast: ForecastAssumptions | None = None
    tax: TaxPolicy | None = None
    wacc_assumption_set: FrozenWaccAssumptionSet | None = None

    @property
    def surplus_assets(self) -> ValuationAmount:
        """Return approved surplus assets using the concise report-facing name."""
        return self.approved_surplus_assets

    @property
    def selected_currency(self) -> str:
        return self.currency

    @property
    def base_fiscal_period(self) -> FiscalPeriod:
        return self.base_period


@dataclass(frozen=True)
class _Row:
    raw: dict[str, Any]
    period: FiscalPeriod
    value: Decimal | None
    currency: str
    unit: str


def _fail(code: str, message: str, **details: Any) -> None:
    raise ValuationInputError(code, message, details)


def _decimal(value: Any, code: str, message: str, **details: Any) -> Decimal:
    if value is None or isinstance(value, bool):
        _fail(code, message, **details)
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        _fail(code, message, **details)
    if not result.is_finite():
        _fail(code, message, **details)
    return result


def _parse_period(value: Any) -> FiscalPeriod:
    original = str(value or "").strip()
    match = _YEAR_RE.fullmatch(original)
    if match:
        fiscal_year = int(match.group(1))
        return FiscalPeriod(original, fiscal_year, date(fiscal_year, 12, 31))
    try:
        end_date = date.fromisoformat(original)
    except ValueError:
        _fail(
            "unsupported_period",
            "A financial statement period is not in a supported year or full-date format.",
            period=original,
        )
    return FiscalPeriod(original, end_date.year, end_date)


def _prepare_rows(financial_rows: list[dict[str, Any]]) -> list[_Row]:
    prepared = []
    currencies = set()
    exact_inputs: set[tuple[str, str, str]] = set()
    canonical_inputs: dict[tuple[str, str, date], str] = {}

    for raw in financial_rows:
        statement = str(raw.get("statement") or "").strip().lower()
        row_key = str(raw.get("row_key") or "").strip().lower()
        original_period = str(raw.get("period") or "").strip()
        exact_key = (statement, row_key, original_period)
        if exact_key in exact_inputs:
            _fail(
                "duplicate_financial_input",
                "The financial statements contain a duplicate input for the same period.",
                statement=statement,
                row_key=row_key,
                period=original_period,
            )
        exact_inputs.add(exact_key)

        period = _parse_period(original_period)
        canonical_key = (statement, row_key, period.end_date)
        if canonical_key in canonical_inputs:
            _fail(
                "ambiguous_base_period",
                "Equivalent fiscal periods use conflicting period labels.",
                statement=statement,
                row_key=row_key,
                periods=[canonical_inputs[canonical_key], original_period],
            )
        canonical_inputs[canonical_key] = original_period

        unit = str(raw.get("unit") or "").strip().lower()
        if unit not in _UNIT_FACTORS:
            _fail(
                "unsupported_unit",
                "A financial statement uses an unsupported unit.",
                statement=statement,
                row_key=row_key,
                period=original_period,
                unit=unit,
            )

        currency = str(raw.get("currency") or "").strip().upper()
        if not _CURRENCY_RE.fullmatch(currency):
            _fail(
                "mixed_currency",
                "All valuation inputs must use one valid three-letter currency code.",
                currency=currency,
            )
        currencies.add(currency)

        raw_value = raw.get("value")
        value = None
        if raw_value is not None:
            value = _decimal(
                raw_value,
                "unsupported_unit",
                "A financial statement value is not a valid number.",
                statement=statement,
                row_key=row_key,
                period=original_period,
            ) * _UNIT_FACTORS[unit]
        prepared.append(_Row(raw, period, value, currency, unit))

    if len(currencies) != 1:
        _fail(
            "mixed_currency",
            "All valuation inputs must use one valid three-letter currency code.",
            currencies=sorted(currencies),
        )
    return prepared


def _provenance(row: _Row, transformation: str) -> ValueProvenance:
    original_value = None
    if row.raw.get("value") is not None:
        original_value = Decimal(str(row.raw["value"]))
    return ValueProvenance(
        document_id=row.raw.get("document_id"),
        statement=str(row.raw.get("statement") or ""),
        row_key=str(row.raw.get("row_key") or ""),
        row_label=str(row.raw.get("row_label") or ""),
        original_period=str(row.raw.get("period") or ""),
        currency=row.currency,
        original_unit=row.unit,
        original_value=original_value,
        normalised_value=row.value if row.value is not None else Decimal("0"),
        source_text=row.raw.get("source_text"),
        confidence=row.raw.get("confidence"),
        transformation=transformation,
    )


def _period_rows(rows: list[_Row], statement: str, end_date: date) -> list[_Row]:
    return [
        row for row in rows
        if str(row.raw.get("statement") or "").lower() == statement
        and row.period.end_date == end_date
    ]


def _find(rows: list[_Row], key: str) -> _Row | None:
    return next(
        (row for row in rows if str(row.raw.get("row_key") or "").lower() == key and row.value is not None),
        None,
    )


def _select_base_period(rows: list[_Row]) -> tuple[FiscalPeriod, _Row, tuple[_Row, ...]]:
    pnl_dates = sorted({row.period.end_date for row in rows if str(row.raw.get("statement") or "").lower() == "pnl"}, reverse=True)
    incomplete = []
    for end_date in pnl_dates:
        period_rows = _period_rows(rows, "pnl", end_date)
        revenue = _find(period_rows, "revenue")
        reported_ebitda = _find(period_rows, "ebitda")
        ebit = _find(period_rows, "ebit")
        depreciation = next((_find(period_rows, key) for key in _DEPRECIATION_KEYS if _find(period_rows, key)), None)
        if revenue and (reported_ebitda or (ebit and depreciation)):
            if reported_ebitda:
                return revenue.period, revenue, (reported_ebitda,)
            return revenue.period, revenue, (ebit, depreciation)
        incomplete.append({"period": end_date.isoformat(), "missing_revenue": revenue is None})

    if any(not item["missing_revenue"] for item in incomplete):
        _fail("missing_ebitda", "A complete EBITDA input is required for valuation.", periods=incomplete)
    _fail("missing_revenue", "A complete revenue input is required for valuation.", periods=incomplete)


def _normalisations(frozen_inputs: dict[str, Any], currency: str) -> tuple[Normalisation, ...]:
    intake_answers = frozen_inputs.get("intake_answers")
    if isinstance(intake_answers, dict) and "normalisations" in intake_answers:
        items = intake_answers["normalisations"]
    else:
        items = frozen_inputs.get("ebitda_adjustments") or []
    if not isinstance(items, list):
        _fail(
            "invalid_normalisation",
            "Confirmed EBITDA normalisations must be a list.",
            field="normalisations",
        )

    result = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            _fail(
                "invalid_normalisation",
                "Every EBITDA normalisation must be an object.",
                index=index,
            )
        label = str(item.get("label") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        if not label or not rationale:
            _fail(
                "invalid_normalisation",
                "Every EBITDA normalisation needs a label, amount, and rationale.",
                index=index,
            )
        amount = _decimal(
            item.get("amount"),
            "invalid_normalisation",
            "Every EBITDA normalisation needs a valid numeric amount.",
            index=index,
        )
        provenance = ValueProvenance(
            document_id=None,
            statement=None,
            row_key="ebitda_adjustment",
            row_label=label,
            original_period=None,
            currency=currency,
            original_unit="whole",
            original_value=amount,
            normalised_value=amount,
            source_text=rationale,
            confidence=None,
            transformation="approved_normalisation",
        )
        result.append(Normalisation(label, amount, rationale, provenance))
    return tuple(result)


def _classify_balance_sheet(rows: list[_Row]) -> tuple[list[_Row], list[_Row]]:
    debt_rows = []
    cash_rows = []
    for row in rows:
        if row.value is None:
            continue
        key = str(row.raw.get("row_key") or "").lower()
        text = " ".join(
            str(value or "").lower()
            for value in (key, row.raw.get("row_label"), row.raw.get("source_text"))
        )
        has_debt_term = any(term in text for term in _DEBT_TERMS)
        has_non_debt_term = any(term in text for term in _AMBIGUOUS_DEBT_TERMS)
        if (key in _DEBT_KEYS and has_non_debt_term) or (has_debt_term and has_non_debt_term):
            _fail(
                "ambiguous_debt_classification",
                "A combined liability row cannot be classified safely as interest-bearing debt.",
                row_key=key,
                row_label=row.raw.get("row_label"),
                period=row.period.original,
            )
        if key in _DEBT_KEYS or has_debt_term:
            debt_rows.append(row)

        if key == "cash_and_bank" or "cash" in key:
            if any(term in text for term in _RESTRICTED_CASH_TERMS + _AMBIGUOUS_CASH_TERMS):
                _fail(
                    "ambiguous_cash_classification",
                    "Only clearly unrestricted cash can be deducted in the valuation.",
                    row_key=key,
                    row_label=row.raw.get("row_label"),
                    period=row.period.original,
                )
            cash_rows.append(row)
    return debt_rows, cash_rows


def _summed_amount(rows: list[_Row], transformation: str, currency: str) -> ValuationAmount:
    if rows:
        return ValuationAmount(
            sum((row.value for row in rows if row.value is not None), Decimal("0")),
            tuple(_provenance(row, transformation) for row in rows),
        )
    provenance = ValueProvenance(
        None, None, None, None, None, currency, "whole", Decimal("0"),
        Decimal("0"), None, None, "explicitly_absent",
    )
    return ValuationAmount(Decimal("0"), (provenance,))


def _surplus_assets(frozen_inputs: dict[str, Any], currency: str) -> ValuationAmount:
    item = frozen_inputs.get("approved_surplus_assets")
    if item in (None, {}):
        return _summed_amount([], "approved_surplus_assets", currency)
    rationale = str(item.get("rationale") or "").strip()
    source_text = str(item.get("source_text") or "").strip()
    if item.get("approved") is not True or not rationale or not source_text:
        _fail(
            "invalid_normalisation",
            "A non-zero surplus asset requires explicit approval, rationale, and provenance.",
            field="approved_surplus_assets",
        )
    amount = _decimal(
        item.get("amount"),
        "invalid_normalisation",
        "Approved surplus assets need a valid numeric amount.",
        field="approved_surplus_assets",
    )
    if amount < 0:
        _fail(
            "invalid_normalisation",
            "Approved surplus assets cannot be negative.",
            field="approved_surplus_assets",
        )
    provenance = ValueProvenance(
        None, None, "approved_surplus_assets", "Approved surplus assets", None,
        currency, "whole", amount, amount, source_text, None,
        "approved_surplus_assets",
    )
    return ValuationAmount(amount, (provenance,))


def derive_fcff_assumption_readiness(
    financial_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Derive safe FCFF ratios from the valuation-selected base period."""
    rows = _prepare_rows(financial_rows)
    base_period, revenue_row, _ = _select_base_period(rows)
    if revenue_row.value == 0:
        _fail("missing_revenue", "Revenue must be non-zero to derive FCFF assumptions.")

    pnl_rows = _period_rows(rows, "pnl", base_period.end_date)
    depreciation_row = next(
        (_find(pnl_rows, key) for key in _DEPRECIATION_KEYS if _find(pnl_rows, key)),
        None,
    )
    bs_rows = _period_rows(rows, "bs", base_period.end_date)
    component_keys = ("trade_debtors", "inventory", "trade_creditors")
    components = [_find(bs_rows, key) for key in component_keys]

    depreciation = None
    if depreciation_row is not None:
        depreciation = {
            "rate": abs(depreciation_row.value) / revenue_row.value,
            "source_period": revenue_row.period.original,
            "provenance": depreciation_row.raw.get("source_text") or depreciation_row.raw.get("row_label"),
        }

    operating_nwc = None
    if all(component is not None for component in components):
        nwc_value = components[0].value + components[1].value - components[2].value
        operating_nwc = {
            "rate": nwc_value / revenue_row.value,
            "source_period": revenue_row.period.original,
            "provenance": {
                "formula": "Trade debtors + Inventory - Trade creditors",
                "components": [
                    {
                        "document_id": component.raw.get("document_id"),
                        "row_key": component.raw.get("row_key"),
                        "row_label": component.raw.get("row_label"),
                        "period": component.period.original,
                        "currency": component.currency,
                        "original_unit": component.unit,
                        "original_value": component.raw.get("value"),
                        "normalised_value": component.value,
                        "source_text": component.raw.get("source_text"),
                    }
                    for component in components
                ],
            },
        }

    return {"depreciation": depreciation, "operating_nwc": operating_nwc}


def _fcff_policy(
    assumptions: dict,
    key: str,
    forecast_horizon: int,
    *,
    calculated_rate: Decimal | None = None,
    source_period: str | None = None,
) -> ConfirmedForecastPolicy:
    item = assumptions.get(key)
    if not isinstance(item, dict):
        _fail(f"missing_{key}", f"A confirmed {key.replace('_', ' ')} assumption is required.")
    rationale = str(item.get("rationale") or "").strip()
    confirmed = item.get("confirmed") is True
    confirmation_method = str(item.get("confirmation_method") or "").strip() or None
    confirmation_source = str(item.get("confirmation_source") or "").strip() or None
    schedule = item.get("annual_schedule")
    rate = item.get("rate")
    if not confirmed:
        _fail(f"missing_{key}", f"The {key.replace('_', ' ')} assumption must be confirmed.")
    if schedule is not None:
        if not isinstance(schedule, list) or not schedule:
            _fail(f"missing_{key}", f"The {key.replace('_', ' ')} schedule is invalid.")
        if len(schedule) != forecast_horizon:
            _fail(
                f"missing_{key}",
                f"The {key.replace('_', ' ')} schedule must match the forecast horizon.",
                expected_years=forecast_horizon,
                actual_years=len(schedule),
            )
        values = tuple(_decimal(value, f"missing_{key}", f"The {key.replace('_', ' ')} schedule is invalid.") for value in schedule)
        if any(value < 0 for value in values):
            _fail(f"missing_{key}", f"The {key.replace('_', ' ')} schedule cannot be negative.")
        if any(value == 0 for value in values) and not rationale:
            _fail(f"missing_{key}_rationale", f"A zero {key.replace('_', ' ')} assumption needs a rationale.")
        return ConfirmedForecastPolicy(
            None, values, rationale, confirmed, confirmation_method, confirmation_source
        )
    value = _decimal(rate, f"missing_{key}", f"A valid {key.replace('_', ' ')} revenue ratio is required.")
    if value < 0 or value > 1:
        _fail(f"missing_{key}", f"The {key.replace('_', ' ')} revenue ratio must be between zero and one.")
    if value == 0 and not rationale:
        _fail(f"missing_{key}_rationale", f"A zero {key.replace('_', ' ')} assumption needs a rationale.")
    if confirmation_method == "calculated" and calculated_rate is not None:
        submitted_period = str(item.get("source_period") or "").strip()
        if value != calculated_rate or submitted_period != source_period:
            _fail(
                f"invalid_calculated_{key}",
                f"The calculated {key.replace('_', ' ')} assumption must match its source period and derived value.",
                expected_rate=str(calculated_rate),
                actual_rate=str(value),
                expected_source_period=source_period,
                actual_source_period=submitted_period,
            )
        if confirmation_source != "financial_statements":
            _fail(
                f"invalid_calculated_{key}",
                f"The calculated {key.replace('_', ' ')} assumption must retain its financial statement source.",
            )
    elif calculated_rate is not None and confirmation_method != "override":
        _fail(
            f"invalid_calculated_{key}",
            f"Changes to the calculated {key.replace('_', ' ')} assumption require an override.",
        )
    if confirmation_method == "override" and not rationale:
        _fail(f"missing_{key}_rationale", f"An overridden {key.replace('_', ' ')} assumption needs a rationale.")
    return ConfirmedForecastPolicy(
        value, (), rationale, confirmed, confirmation_method, confirmation_source
    )


def _fcff_inputs(
    rows: list[_Row],
    base_period: FiscalPeriod,
    revenue: ValuationAmount,
    normalised_ebitda: ValuationAmount,
    frozen_inputs: dict[str, Any],
) -> tuple:
    intake = frozen_inputs.get("intake_answers")
    assumptions = intake.get("fcff_assumptions") if isinstance(intake, dict) else None
    if not isinstance(assumptions, dict):
        return (None, (), None, None, None, None, None, None, None)

    pnl_rows = _period_rows(rows, "pnl", base_period.end_date)
    depreciation_row = next((_find(pnl_rows, key) for key in _DEPRECIATION_KEYS if _find(pnl_rows, key)), None)
    if not depreciation_row:
        _fail("missing_depreciation", "Same-period depreciation and amortisation is required.")
    depreciation_value = abs(depreciation_row.value)
    depreciation_provenance = _provenance(depreciation_row, "absolute_depreciation_and_amortisation")
    depreciation_provenance = ValueProvenance(
        depreciation_provenance.document_id, depreciation_provenance.statement,
        depreciation_provenance.row_key, depreciation_provenance.row_label,
        depreciation_provenance.original_period, depreciation_provenance.currency,
        depreciation_provenance.original_unit, depreciation_provenance.original_value,
        depreciation_value, depreciation_provenance.source_text,
        depreciation_provenance.confidence, depreciation_provenance.transformation,
    )
    depreciation = ValuationAmount(depreciation_value, (depreciation_provenance,))

    bs_rows = _period_rows(rows, "bs", base_period.end_date)
    component_keys = ("trade_debtors", "inventory", "trade_creditors")
    components = [_find(bs_rows, key) for key in component_keys]
    if any(component is None for component in components):
        missing = [key for key, component in zip(component_keys, components) if component is None]
        _fail("missing_operating_nwc", "All approved same-period operating working-capital components are required.", missing=missing)
    component_provenance = tuple(
        _provenance(component, "operating_nwc_asset" if component.raw["row_key"] != "trade_creditors" else "operating_nwc_liability")
        for component in components
    )
    base_nwc_value = components[0].value + components[1].value - components[2].value
    base_nwc = ValuationAmount(base_nwc_value, component_provenance)

    forecast_item = assumptions.get("forecast")
    if not isinstance(forecast_item, dict) or forecast_item.get("confirmed") is not True:
        _fail("missing_forecast_assumptions", "Confirmed forecast assumptions are required.")
    horizon = forecast_item.get("horizon_years")
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 1 or horizon > 10:
        _fail("missing_forecast_assumptions", "Forecast horizon must be between one and ten years.")

    depreciation_policy = _fcff_policy(
        assumptions, "depreciation", horizon,
        calculated_rate=depreciation_value / revenue.value,
        source_period=base_period.original,
    )
    capex_policy = _fcff_policy(assumptions, "capex", horizon)
    operating_nwc_policy = _fcff_policy(
        assumptions, "operating_nwc", horizon,
        calculated_rate=base_nwc_value / revenue.value,
        source_period=base_period.original,
    )
    growth = _decimal(forecast_item.get("revenue_growth_rate"), "missing_forecast_assumptions", "A valid revenue growth rate is required.")
    terminal_growth = _decimal(forecast_item.get("terminal_growth_rate"), "missing_forecast_assumptions", "A valid terminal growth rate is required.")
    if revenue.value == 0:
        _fail("missing_forecast_assumptions", "Revenue must be non-zero to establish the EBITDA margin.")
    forecast = ForecastAssumptions(horizon, growth, terminal_growth, normalised_ebitda.value / revenue.value)
    tax = TaxPolicy(Decimal("0.28"), "nz-company-tax-2026-v1", True, False)

    raw_wacc = frozen_inputs.get("approved_wacc_assumption_set")
    if not isinstance(raw_wacc, dict):
        _fail("missing_wacc_approval", "An active adviser-approved WACC assumption set is required.")
    required_text = ("name", "beta_type", "source_references", "publisher", "as_of_date", "rationale", "approved_at", "approved_by")
    if any(not str(raw_wacc.get(field) or "").strip() for field in required_text):
        _fail("missing_wacc_approval", "The approved WACC assumption set is incomplete.")
    try:
        wacc_date = date.fromisoformat(str(raw_wacc["as_of_date"]))
        assumption_set_id = int(raw_wacc["id"])
        version = int(raw_wacc["version"])
    except (ValueError, TypeError):
        _fail("missing_wacc_approval", "The approved WACC assumption set is incomplete.")
    decimal_fields = {
        field: _decimal(raw_wacc.get(field), "missing_wacc_approval", "The approved WACC assumption set is incomplete.")
        for field in ("risk_free_rate", "equity_risk_premium", "beta", "cost_of_debt", "target_debt_weight", "target_equity_weight")
    }
    if decimal_fields["target_debt_weight"] + decimal_fields["target_equity_weight"] != 1:
        _fail("missing_wacc_approval", "Approved WACC debt and equity weights must total one.")
    additional = _decimal(raw_wacc.get("additional_premium", 0), "missing_wacc_approval", "The approved WACC assumption set is incomplete.")
    spread = _decimal(raw_wacc.get("scenario_spread", 0), "missing_wacc_approval", "The approved WACC assumption set is incomplete.")
    mid_wacc = (
        decimal_fields["risk_free_rate"]
        + decimal_fields["beta"] * decimal_fields["equity_risk_premium"]
        + additional
    ) * decimal_fields["target_equity_weight"] + (
        decimal_fields["cost_of_debt"] * (Decimal("1") - tax.rate)
    ) * decimal_fields["target_debt_weight"]
    if mid_wacc - spread - terminal_growth < Decimal("0.01"):
        _fail("invalid_terminal_spread", "WACC must exceed terminal growth by at least one percentage point in every scenario.")
    wacc = FrozenWaccAssumptionSet(
        assumption_set_id, str(raw_wacc["name"]), version,
        decimal_fields["risk_free_rate"], decimal_fields["equity_risk_premium"],
        decimal_fields["beta"], str(raw_wacc["beta_type"]), decimal_fields["cost_of_debt"],
        decimal_fields["target_debt_weight"], decimal_fields["target_equity_weight"],
        additional, spread, str(raw_wacc["source_references"]), str(raw_wacc["publisher"]),
        wacc_date, str(raw_wacc["rationale"]), str(raw_wacc["approved_at"]), str(raw_wacc["approved_by"]),
    )
    return (
        depreciation, component_provenance, base_nwc, depreciation_policy,
        capex_policy, operating_nwc_policy, forecast, tax, wacc,
    )


def build_valuation_inputs(
    financial_rows: list[dict[str, Any]],
    frozen_inputs: dict[str, Any] | None = None,
    *,
    require_fcff: bool = False,
) -> ValuationInputs:
    """Build immutable valuation inputs from snapshot-shaped rows and inputs."""
    rows = _prepare_rows(financial_rows)
    currency = rows[0].currency
    base_period, revenue_row, ebitda_rows = _select_base_period(rows)
    balance_sheet_rows = _period_rows(rows, "bs", base_period.end_date)
    if not balance_sheet_rows:
        available = sorted({row.period.original for row in rows if str(row.raw.get("statement") or "").lower() == "bs"})
        _fail(
            "incompatible_balance_sheet_period",
            "A balance sheet matching the selected fiscal year-end is required.",
            base_period=base_period.original,
            balance_sheet_periods=available,
        )

    revenue = ValuationAmount(revenue_row.value, (_provenance(revenue_row, "unit_to_whole"),))
    if len(ebitda_rows) == 1:
        ebitda = ValuationAmount(
            ebitda_rows[0].value,
            (_provenance(ebitda_rows[0], "reported_ebitda"),),
        )
    else:
        ebit_row, depreciation_row = ebitda_rows
        depreciation_value = abs(depreciation_row.value)
        depreciation_provenance = _provenance(
            depreciation_row, "absolute_depreciation_added_to_ebit"
        )
        depreciation_provenance = ValueProvenance(
            depreciation_provenance.document_id,
            depreciation_provenance.statement,
            depreciation_provenance.row_key,
            depreciation_provenance.row_label,
            depreciation_provenance.original_period,
            depreciation_provenance.currency,
            depreciation_provenance.original_unit,
            depreciation_provenance.original_value,
            depreciation_value,
            depreciation_provenance.source_text,
            depreciation_provenance.confidence,
            depreciation_provenance.transformation,
        )
        ebitda = ValuationAmount(
            ebit_row.value + depreciation_value,
            (
                _provenance(ebit_row, "ebit_before_depreciation_addback"),
                depreciation_provenance,
            ),
        )

    frozen_inputs = frozen_inputs or {}
    normalisations = _normalisations(frozen_inputs, currency)
    normalised_ebitda = ValuationAmount(
        ebitda.value + sum((item.amount for item in normalisations), Decimal("0")),
        ebitda.provenance + tuple(item.provenance for item in normalisations),
    )
    debt_rows, cash_rows = _classify_balance_sheet(balance_sheet_rows)
    if not debt_rows:
        _fail(
            "missing_debt",
            "A clearly classified interest-bearing debt balance is required, including a reported zero.",
            period=base_period.original,
        )
    if not cash_rows:
        _fail(
            "missing_cash",
            "A clearly classified unrestricted cash balance is required, including a reported zero.",
            period=base_period.original,
        )
    debt = _summed_amount(debt_rows, "interest_bearing_debt", currency)
    cash = _summed_amount(cash_rows, "unrestricted_cash", currency)
    surplus_assets = _surplus_assets(frozen_inputs, currency)
    net_debt = ValuationAmount(
        debt.value - cash.value,
        tuple(
            ValueProvenance(
                p.document_id, p.statement, p.row_key, p.row_label, p.original_period,
                p.currency, p.original_unit, p.original_value, p.normalised_value,
                p.source_text, p.confidence, "interest_bearing_debt_minus_unrestricted_cash",
            )
            for p in debt.provenance + cash.provenance
        ),
    )
    fcff_values = _fcff_inputs(
        rows, base_period, revenue, normalised_ebitda, frozen_inputs
    )
    if require_fcff and fcff_values[0] is None:
        _fail("missing_forecast_assumptions", "Complete FCFF assumptions are required before checkout.")
    return ValuationInputs(
        currency=currency,
        base_period=base_period,
        revenue=revenue,
        ebitda=ebitda,
        normalisations=normalisations,
        normalised_ebitda=normalised_ebitda,
        interest_bearing_debt=debt,
        unrestricted_cash=cash,
        approved_surplus_assets=surplus_assets,
        net_debt=net_debt,
        depreciation_and_amortisation=fcff_values[0],
        operating_nwc_components=fcff_values[1],
        base_operating_nwc=fcff_values[2],
        depreciation_policy=fcff_values[3],
        capex_policy=fcff_values[4],
        operating_nwc_policy=fcff_values[5],
        forecast=fcff_values[6],
        tax=fcff_values[7],
        wacc_assumption_set=fcff_values[8],
    )
