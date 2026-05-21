"""
Valuation Advisory algorithm -- AccountIQ Phase 5.
All computation is deterministic Python. Claude receives the output dict and writes narrative only.
Source: Bayleys Business Valuations production model (2021 NZ baseline).
"""
from __future__ import annotations
import math
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SECTOR_STARTING_MULTIPLES: dict[str, float] = {
    "asset_heavy":         6.3,
    "services":            4.7,
    "manufacturing":       5.0,
    "import_distribution": 6.0,
    "retail":              4.2,
}

# Sector weights: list of 23 floats, index 0 = Q1 ... index 22 = Q23
# Columns: asset_heavy, services, manufacturing, import_distribution, retail
# Source: 05-VALUATION-ALGORITHM.md sector weights table
SECTOR_WEIGHTS: dict[str, list[float]] = {
    "asset_heavy":         [0.7, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 1.0, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7],
    "services":            [0.7, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.7, 0.7, 0.7, 1.0, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7],
    "manufacturing":       [0.7, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.7, 0.7, 1.0, 1.0, 1.0, 1.0, 0.7, 0.7, 0.7, 0.7, 0.7],
    "import_distribution": [0.7, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.7, 0.7, 0.7, 0.7, 1.0, 1.0, 1.0, 1.0, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7],
    "retail":              [0.7, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.7, 1.0, 0.7, 1.0, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 1.0, 0.7, 0.7, 0.7],
}

# Questions with only 3 meaningful answer options (Low/Medium/High -> 5/3/1)
# Q6: seasonality, Q8: GP% consistency, Q9: staff dependence (1-indexed)
_THREE_OPTION_QUESTIONS = {6, 8, 9}

# Minimum resultant multiple floor (Known Limitations item 6 from VALUATION-ALGORITHM.md)
MINIMUM_MULTIPLE_FLOOR = 0.5

# ---------------------------------------------------------------------------
# EV/EBITDA multiples method
# ---------------------------------------------------------------------------

def compute_ev_ebitda_multiple(answers: list[int], sector: str) -> dict:
    """
    Compute the EV/EBITDA resultant multiple for the given sector and questionnaire answers.

    answers: list of 23 integers, each 1-5 (index 0 = Q1, index 22 = Q23)
    sector: one of SECTOR_STARTING_MULTIPLES keys
    returns: {
        'weighted_score': float,
        'max_possible': int,
        'resultant_multiple': float,
        'starting_multiple': float
    }

    Formula: resultant_multiple = (weighted_score / max_possible) x starting_multiple
    where weighted_score = sum(answer[i] x weight[sector][i] for i in 0..22)
    and max_possible = 5 x 23 = 115 (unweighted ceiling)
    """
    if sector not in SECTOR_STARTING_MULTIPLES:
        raise ValueError(
            f"Unknown sector: '{sector}'. Valid sectors: {list(SECTOR_STARTING_MULTIPLES)}"
        )
    if len(answers) != 23:
        raise ValueError(f"Expected 23 answers, got {len(answers)}")
    for i, score in enumerate(answers):
        if not (1 <= score <= 5):
            raise ValueError(f"Answer at index {i} (Q{i+1}) must be 1-5, got {score}")

    weights = SECTOR_WEIGHTS[sector]
    weighted_score = sum(answers[i] * weights[i] for i in range(23))
    max_possible = 5 * 23  # = 115
    starting_multiple = SECTOR_STARTING_MULTIPLES[sector]
    raw_multiple = (weighted_score / max_possible) * starting_multiple
    resultant_multiple = max(MINIMUM_MULTIPLE_FLOOR, raw_multiple)

    return {
        "weighted_score":     round(weighted_score, 4),
        "max_possible":       max_possible,
        "resultant_multiple": round(resultant_multiple, 4),
        "starting_multiple":  starting_multiple,
    }


# ---------------------------------------------------------------------------
# WACC calculation
# ---------------------------------------------------------------------------

def compute_wacc(inputs: dict) -> dict:
    """
    Compute WACC using CAPM cost of equity and post-tax cost of debt.

    inputs keys (all values as decimals, e.g. 0.05 for 5%):
        risk_free_rate              -- nominal risk-free rate (10-year govt bond yield)
        equity_market_risk_premium  -- ERP (market return over risk-free)
        beta                        -- sector/business beta
        cost_of_debt_pretax         -- weighted average borrowing rate (pre-tax)
        corp_tax_rate               -- corporate tax rate (NZ default 0.28, AU default 0.30)
        weight_equity               -- proportion of equity funding (long-run)
        weight_debt                 -- proportion of debt funding; defaults to (1 - weight_equity)

    Formulas:
        cost_of_equity = risk_free_rate + beta x equity_market_risk_premium   (CAPM)
        cost_of_debt_post_tax = cost_of_debt_pretax x (1 - corp_tax_rate)
        wacc_post_tax = weight_equity x cost_of_equity + weight_debt x cost_of_debt_post_tax

    returns: {'cost_of_equity': float, 'cost_of_debt_post_tax': float, 'wacc_post_tax': float}
    """
    rf       = inputs["risk_free_rate"]
    erp      = inputs["equity_market_risk_premium"]
    beta     = inputs["beta"]
    kd_pre   = inputs.get("cost_of_debt_pretax", 0.0)
    tax      = inputs["corp_tax_rate"]
    we       = inputs.get("weight_equity", 1.0)
    wd       = inputs.get("weight_debt", 1.0 - we)

    cost_of_equity    = rf + beta * erp
    cost_of_debt_post = kd_pre * (1 - tax)
    wacc_post_tax     = we * cost_of_equity + wd * cost_of_debt_post

    return {
        "cost_of_equity":        round(cost_of_equity, 6),
        "cost_of_debt_post_tax": round(cost_of_debt_post, 6),
        "wacc_post_tax":         round(wacc_post_tax, 6),
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
    wacc:            post-tax WACC as decimal (from compute_wacc)
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


# ---------------------------------------------------------------------------
# Orchestrator: compute_valuation
# ---------------------------------------------------------------------------

def compute_valuation(
    questionnaire_answers: list[int],
    sector: str,
    dcf_inputs: dict,
    financial_data: dict,
) -> dict:
    """
    Orchestrate all valuation methods and return the complete output dict passed to Claude.

    questionnaire_answers: list of 23 integers 1-5 (index 0 = Q1)
    sector: one of SECTOR_STARTING_MULTIPLES keys
    dcf_inputs: {
        risk_free_rate:             float,   # decimal
        equity_market_risk_premium: float,   # decimal
        beta:                       float,
        cost_of_debt_pretax:        float,   # decimal, optional (default 0.0)
        corp_tax_rate:              float,   # decimal (NZ: 0.28, AU: 0.30)
        weight_equity:              float,   # decimal, optional (default 1.0)
        weight_debt:                float,   # decimal, optional (default 1 - weight_equity)
        revenue_growth_rate:        float,   # decimal
        terminal_growth_rate:       float,   # decimal
        forecast_years:             int,     # optional (default 5)
        capex_per_year:             float,   # optional (default 0.0)
    }
    financial_data: {
        normalised_ebitda: float,   # from Phase 3 ebitda_adjustments + extracted EBITDA
        revenues:          float,   # annual revenues for illiquidity discount
        is_profitable:     bool,    # True if NPBT > 0 (optional, derived from ebitda if absent)
        cash:              float,   # cash & bank balance from balance sheet (optional, default 0)
        net_debt:          float,   # net debt from balance sheet (optional, default 0)
    }

    Returns the output dict structure described in VALUATION-ALGORITHM.md SS Outputs Passed to Claude.
    """
    norm_ebitda   = financial_data["normalised_ebitda"]
    revenues      = financial_data.get("revenues", 0.0)
    is_profitable = financial_data.get("is_profitable", norm_ebitda > 0)
    cash          = financial_data.get("cash", 0.0)
    net_debt      = financial_data.get("net_debt", 0.0)

    # ------------------------------------------------------------------
    # Step 1: EV/EBITDA multiples
    # ------------------------------------------------------------------
    multiples_result  = compute_ev_ebitda_multiple(questionnaire_answers, sector)
    ev_multiples_raw  = norm_ebitda * multiples_result["resultant_multiple"]

    # ------------------------------------------------------------------
    # Step 2: WACC
    # ------------------------------------------------------------------
    wacc_inputs = {
        "risk_free_rate":             dcf_inputs["risk_free_rate"],
        "equity_market_risk_premium": dcf_inputs["equity_market_risk_premium"],
        "beta":                       dcf_inputs["beta"],
        "cost_of_debt_pretax":        dcf_inputs.get("cost_of_debt_pretax", 0.0),
        "corp_tax_rate":              dcf_inputs["corp_tax_rate"],
        "weight_equity":              dcf_inputs.get("weight_equity", 1.0),
        "weight_debt":                dcf_inputs.get("weight_debt", 1.0 - dcf_inputs.get("weight_equity", 1.0)),
    }
    wacc_result = compute_wacc(wacc_inputs)

    # ------------------------------------------------------------------
    # Step 3: DCF
    # ------------------------------------------------------------------
    dcf_result = compute_dcf(
        ebitda         = norm_ebitda,
        wacc           = wacc_result["wacc_post_tax"],
        growth_rate    = dcf_inputs["revenue_growth_rate"],
        tax_rate       = dcf_inputs["corp_tax_rate"],
        years          = int(dcf_inputs.get("forecast_years", 5)),
        terminal_growth = dcf_inputs["terminal_growth_rate"],
        capex_per_year  = dcf_inputs.get("capex_per_year", 0.0),
    )

    # ------------------------------------------------------------------
    # Step 4: Illiquidity discount
    # Use average of both EV methods as initial estimate (handles circular dependency)
    # ------------------------------------------------------------------
    ev_avg_raw = (ev_multiples_raw + dcf_result["enterprise_value_dcf"]) / 2
    illiquidity_rate = compute_illiquidity_discount(
        revenues, is_profitable, cash, ev_avg_raw
    )

    # ------------------------------------------------------------------
    # Step 5: Fair value range (net of illiquidity discount and net debt)
    # ------------------------------------------------------------------
    def _fair_value(ev_raw: float) -> float:
        return ev_raw * (1 - illiquidity_rate) - net_debt

    ev_low_raw  = min(ev_multiples_raw, dcf_result["enterprise_value_dcf"])
    ev_high_raw = max(ev_multiples_raw, dcf_result["enterprise_value_dcf"])

    # ------------------------------------------------------------------
    # Step 6: Identify key risk factors from low-scoring questions (score <= 2)
    # ------------------------------------------------------------------
    question_labels = [
        "Business tenure",            # Q1
        "EBIT growth history",        # Q2
        "% contracted income",        # Q3
        "CAPEX vs depreciation",      # Q4
        "Gross profit %",             # Q5
        "Seasonality",                # Q6
        "Fixed assets as % of sales", # Q7
        "GP% consistency",            # Q8
        "Staff technical dependence", # Q9
        "Avg staff tenure",           # Q10
        "Ease to hire/train",         # Q11
        "Management without owner",   # Q12
        "Supply chain vulnerability", # Q13
        "Supply contracts",           # Q14
        "% B2B turnover",             # Q15
        "Top-5 customer retention",   # Q16
        "Largest customer % of turnover", # Q17
        "Ease of new customers",      # Q18
        "Premises & lease security",  # Q19
        "Competition level",          # Q20
        "Barriers to entry",          # Q21
        "Growth opportunities",       # Q22
        "Sector profile",             # Q23
    ]
    key_risk_factors = []
    for i, score in enumerate(questionnaire_answers):
        if score <= 2:
            key_risk_factors.append(
                f"{question_labels[i]} (Q{i+1} scored {score}/5)"
            )

    # ------------------------------------------------------------------
    # Assemble output dict (matches VALUATION-ALGORITHM.md SS Outputs Passed to Claude)
    # ------------------------------------------------------------------
    return {
        "method_used":         "both",
        "normalised_ebitda":   round(norm_ebitda, 2),
        "questionnaire_score": {
            "raw":      sum(questionnaire_answers),
            "weighted": round(multiples_result["weighted_score"], 2),
            "max":      multiples_result["max_possible"],
        },
        "sector": sector,
        "ev_multiples": {
            "multiple":         multiples_result["resultant_multiple"],
            "enterprise_value": round(ev_multiples_raw, 2),
        },
        "ev_dcf": {
            "cumulative_dcf":     dcf_result["cumulative_dcf"],
            "terminal_value_npv": dcf_result["terminal_value_npv"],
            "enterprise_value":   dcf_result["enterprise_value_dcf"],
        },
        "illiquidity_discount": {
            "rate":   illiquidity_rate,
            "amount": round(ev_avg_raw * illiquidity_rate, 2),
        },
        "concluded_range": {
            "low":  round(_fair_value(ev_low_raw), 2),
            "mid":  round(_fair_value(ev_avg_raw), 2),
            "high": round(_fair_value(ev_high_raw), 2),
        },
        "net_debt": net_debt,
        "wacc":     wacc_result,
        "key_risk_factors": key_risk_factors[:5],  # top 5 only for Claude narrative
    }
