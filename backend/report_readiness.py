"""Report-specific financial readiness checks used by the self-serve wizard."""

from __future__ import annotations


_REVENUE_KEYS = {
    "revenue",
    "sales",
    "net_sales",
    "turnover",
}
_EARNINGS_KEYS = {
    "ebitda",
    "ebit",
    "operating_profit",
    "net_profit",
    "profit_after_tax",
}
_CASH_KEYS = {
    "cash",
    "cash_and_bank",
    "cash_and_equivalents",
}
_DEBT_KEYS = {
    "borrowings",
    "bank_debt",
    "short_term_debt",
    "long_term_debt",
    "current_debt",
    "non_current_debt",
}


def _periods_for_keys(rows: list[dict], statement: str, keys: set[str]) -> set[str]:
    periods: set[str] = set()
    for row in rows:
        if str(row.get("statement") or "").lower() != statement:
            continue
        key = str(row.get("row_key") or row.get("canonical_key") or "").lower()
        if key not in keys:
            continue
        period = str(row.get("period") or "").strip()
        if period:
            periods.add(period)
    return periods


def assess_credit_financial_readiness(rows: list[dict]) -> dict:
    """Describe whether the extracted statements can support a credit paper.

    The paper can include lender assumptions and conditions precedent, but it
    should not be queued when the upload has no usable P&L or balance sheet.
    The follow-up list is deliberately practical: these are the documents a
    lender would normally request to move from screening to committee.
    """
    revenue_periods = _periods_for_keys(rows, "pnl", _REVENUE_KEYS)
    earnings_periods = _periods_for_keys(rows, "pnl", _EARNINGS_KEYS)
    balance_sheet_periods = {
        str(row.get("period") or "").strip()
        for row in rows
        if str(row.get("statement") or "").lower() == "bs"
        and str(row.get("period") or "").strip()
    }
    cash_periods = _periods_for_keys(rows, "bs", _CASH_KEYS)
    debt_periods = _periods_for_keys(rows, "bs", _DEBT_KEYS)

    issues: list[str] = []
    warnings: list[str] = []
    if not revenue_periods:
        issues.append("revenue")
    if not earnings_periods:
        issues.append("EBITDA or profit")
    if not balance_sheet_periods:
        issues.append("a balance sheet")
    if not cash_periods:
        warnings.append("No cash balance was extracted; liquidity analysis will be limited.")
    if not debt_periods:
        warnings.append("No borrowings were extracted; existing-debt and leverage analysis will be limited.")
    if len(revenue_periods) == 1 or len(earnings_periods) == 1:
        warnings.append("Only one P&L period was extracted; trend and downside analysis will be limited.")

    follow_up_items = [
        {
            "label": "Current management accounts",
            "impact": "Tests trading since the last annual accounts and gives the lender a current earnings run-rate.",
        },
        {
            "label": "Debt schedule, payout letters and lender statements",
            "impact": "Confirms existing debt, refinance need, pricing, maturities and security priority.",
        },
        {
            "label": "Security schedule and current valuation evidence",
            "impact": "Supports collateral value, ownership, lien priority and the requested LVR.",
        },
        {
            "label": "AR, AP and stock ageing where relevant",
            "impact": "Tests working-capital quality, cash conversion and borrowing-base eligibility.",
        },
        {
            "label": "Borrower, ownership and guarantor details",
            "impact": "Confirms the legal borrower perimeter, support and parties granting security.",
        },
    ]

    if len(balance_sheet_periods) == 1:
        follow_up_items.insert(
            1,
            {
                "label": "A more recent balance sheet",
                "impact": "Improves the debt, cash, net tangible asset and liquidity view at the proposed facility date.",
            },
        )

    return {
        "ready": not issues,
        "issues": issues,
        "warnings": warnings,
        "revenue_periods": sorted(revenue_periods),
        "earnings_periods": sorted(earnings_periods),
        "balance_sheet_periods": sorted(balance_sheet_periods),
        "follow_up_items": follow_up_items,
    }


def report_follow_up_items(valuation_readiness: dict, credit_readiness: dict) -> dict[str, list[dict]]:
    """Return report-specific information prompts without changing hard gates."""
    valuation_items = [
        {
            "label": "The latest 3-4 years of financial statements",
            "impact": "Improves trend analysis and lets the model distinguish a current run-rate from a single-period result.",
        },
        {
            "label": "Evidence for unusual or one-off earnings items",
            "impact": "Supports the separate earnings review and makes maintainable EBITDA easier to defend.",
        },
        {
            "label": "Current debt, cash and surplus-asset details",
            "impact": "Improves the enterprise-value-to-equity-value bridge.",
        },
    ]
    if len(valuation_readiness.get("revenue_periods", [])) <= 1 or len(valuation_readiness.get("earnings_periods", [])) <= 1:
        valuation_items[0]["label"] = "Additional historical financial statements"
    return {
        "valuation_advisory": valuation_items,
        "bank_credit_paper": credit_readiness.get("follow_up_items", []),
    }


def credit_readiness_message(issues: list[str]) -> str:
    missing = ", ".join(issues)
    return (
        "We could not prepare a useful credit paper from the uploaded statements because they do not show "
        f"{missing}. Upload a complete profit and loss plus balance sheet, then try again."
    )
