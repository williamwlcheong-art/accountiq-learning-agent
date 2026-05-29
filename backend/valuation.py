"""
Valuation Advisory algorithm -- AccountIQ Phase 05.1.

Refactored per D-W1/D-W2/D-W5/D-W6:
  - Scoring-based EV/EBITDA logic removed (compute_ev_ebitda_multiple, compute_wacc,
    compute_valuation, SECTOR_STARTING_MULTIPLES, SECTOR_WEIGHTS, etc.)
  - compute_wacc_scenarios() added for High/Mid/Low WACC from researched inputs
  - compute_dcf() and compute_illiquidity_discount() retained verbatim

All computation is deterministic Python. Claude receives the output dict and writes narrative only.
"""
from __future__ import annotations
import math
from typing import Optional


# ---------------------------------------------------------------------------
# WACC scenarios (D-W2, D-W6)
# ---------------------------------------------------------------------------

def compute_wacc_scenarios(
    risk_free_rate: float,
    industry_beta: float,
    erp: float,
) -> dict:
    """
    Compute High/Mid/Low WACC scenarios from researched inputs (D-W2, D-W6).

    Inputs are in PERCENT form (e.g. risk_free_rate=4.65 not 0.0465,
    erp=5.94 not 0.0594, industry_beta=1.08).

    Returns a dict {"high": float, "mid": float, "low": float} with values
    in PERCENT. Caller is responsible for dividing by 100 before passing
    to compute_dcf() which takes wacc as a decimal.

    Spread formula (per AI-SPEC Section 4b.1):
      mid  = risk_free_rate + (industry_beta * erp)
      high = mid + beta_spread * erp + erp_spread
      low  = mid - beta_spread * erp - erp_spread
    where beta_spread = 0.15 (±15% beta variation) and
          erp_spread  = 0.25 (±0.25 percentage point ERP variation).
    """
    beta_spread = 0.15
    erp_spread = 0.25
    mid = risk_free_rate + (industry_beta * erp)
    return {
        "high": round(mid + beta_spread * erp + erp_spread, 2),
        "mid":  round(mid, 2),
        "low":  round(mid - beta_spread * erp - erp_spread, 2),
    }


# ---------------------------------------------------------------------------
# DCF (Discounted Cash Flow)
# ---------------------------------------------------------------------------

def compute_dcf(
    ebitda: float,
    wacc: float,
    growth_rate: float,
    tax_rate: float,
    years: int,
    terminal_growth: float,
    capex_per_year: Optional[float] = None,
) -> dict:
    """
    Compute DCF enterprise value using FCFF projections and Gordon's Growth Model terminal value.

    ebitda:          normalised EBITDA (year 0 base, from Phase 3 ebitda_adjustments)
    wacc:            post-tax WACC as decimal (from compute_wacc_scenarios / 100)
    growth_rate:     annual EBITDA/revenue growth rate as decimal
    tax_rate:        corporate tax rate as decimal
    years:           forecast horizon (typically 3 or 5)
    terminal_growth: long-run sustainable CAGR as decimal (typically 0.02-0.04)
    capex_per_year:  annual capex; defaults to 0

    Formulas (per year):
        ebitda[yr]   = ebitda[yr-1] x (1 + growth_rate)
        tax[yr]      = ebitda[yr] x tax_rate
        fcff[yr]     = ebitda[yr] - tax[yr] - capex
        dcf[yr]      = fcff[yr] / (1 + wacc)^yr

    Terminal value (Gordon's Growth Model):
        terminal_value     = fcff[years] x (1 + terminal_growth) / (wacc - terminal_growth)
        terminal_value_npv = terminal_value / (1 + wacc)^years

    NOTE: caller must ensure wacc > terminal_growth to avoid division by zero.

    returns: {
        'yearly': list of per-year breakdowns,
        'cumulative_dcf': float,
        'terminal_value': float,
        'terminal_value_npv': float,
        'enterprise_value_dcf': float
    }
    """
    if wacc <= terminal_growth:
        raise ValueError(
            f"WACC ({wacc:.4f}) must be greater than terminal_growth ({terminal_growth:.4f}) "
            "to avoid division by zero in Gordon's Growth Model."
        )

    capex = capex_per_year if capex_per_year is not None else 0.0
    yearly = []
    current_ebitda = ebitda
    cumulative_dcf = 0.0

    for yr in range(1, years + 1):
        current_ebitda = current_ebitda * (1 + growth_rate)
        tax_charge     = current_ebitda * tax_rate
        fcff           = current_ebitda - tax_charge - capex
        discounted     = fcff / ((1 + wacc) ** yr)
        cumulative_dcf += discounted
        yearly.append({
            "year":   yr,
            "ebitda": round(current_ebitda, 2),
            "tax":    round(tax_charge, 2),
            "fcff":   round(fcff, 2),
            "dcf":    round(discounted, 2),
        })

    final_fcff     = yearly[-1]["fcff"]
    terminal_value = final_fcff * (1 + terminal_growth) / (wacc - terminal_growth)
    terminal_npv   = terminal_value / ((1 + wacc) ** years)
    enterprise_value_dcf = cumulative_dcf + terminal_npv

    return {
        "yearly":               yearly,
        "cumulative_dcf":       round(cumulative_dcf, 2),
        "terminal_value":       round(terminal_value, 2),
        "terminal_value_npv":   round(terminal_npv, 2),
        "enterprise_value_dcf": round(enterprise_value_dcf, 2),
    }


# ---------------------------------------------------------------------------
# Illiquidity discount (Damodaran bid-ask spread regression)
# ---------------------------------------------------------------------------

def compute_illiquidity_discount(
    revenues: float,
    is_profitable: bool,
    cash: float,
    ev: float,
    iterations: int = 2,
) -> float:
    """
    Compute illiquidity discount rate using Damodaran bid-ask spread regression formula.
    Returns discount as a decimal (e.g. 0.12 for 12%).

    Formula:
        illiquidity_discount = 0.145
            - 0.0022 x ln(annual_revenues)
            - 0.015  x is_profitable          (1 if NPBT > 0, else 0)
            - 0.016  x (cash / enterprise_value)
            - 0.11   x (monthly_trading_volume / enterprise_value)   [= 0 for private companies]

    For private SMEs: monthly_trading_volume = 0 (no public market).
    cash = cash and bank balance from extracted balance sheet.

    Circular dependency note (VALUATION-ALGORITHM.md Known Limitations #4):
    The discount depends on EV, but EV is what we're computing. Solved with `iterations`
    iterations starting from the initial EV estimate (typically the average of multiples and DCF).

    Result is clamped to [0%, 50%] to prevent nonsensical valuations.
    """
    if ev <= 0:
        return 0.0

    discount = 0.0
    current_ev = ev

    for _ in range(iterations):
        cash_ratio = cash / current_ev if current_ev > 0 else 0.0
        ln_rev     = math.log(revenues) if revenues > 0 else 0.0
        discount = (
            0.145
            - 0.0022 * ln_rev
            - 0.015  * (1 if is_profitable else 0)
            - 0.016  * cash_ratio
            # 0.11 * (trading_vol / ev) = 0 for private companies (no public market)
        )
        # Clamp to [0%, 50%] -- prevents negative concluded values from extreme discount rates
        discount    = max(0.0, min(discount, 0.50))
        current_ev  = ev * (1 - discount)

    return round(discount, 6)
