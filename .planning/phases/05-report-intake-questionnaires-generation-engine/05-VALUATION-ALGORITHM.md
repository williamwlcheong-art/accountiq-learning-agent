# Valuation Advisory — Algorithm Specification

**Source:** `2024.08.30 - Multiple Val Calc + EBIDTA multiple.xlsx` (Bayleys Business Valuations)
**Verified:** 2026-05-21 — all formulas reverse-engineered and confirmed against example outputs

---

## Overview

The Valuation Advisory report uses a two-method approach:
1. **EV/EBITDA Multiples** — scored questionnaire → sector multiple → enterprise value
2. **DCF (Discounted Cash Flow)** — WACC inputs → 5-year projections → terminal value → enterprise value

Both methods are computed by Python. Claude writes the narrative around the calculated outputs only.

---

## Method 1: EV/EBITDA Multiple (Beta Analysis Questionnaire)

### Step 1 — Select Sector

| Sector | Starting Multiple |
|--------|-----------------|
| Asset Heavy (manufacturing, property, capital-intensive) | 6.3x |
| Services (professional services, consulting, B2B services) | 4.7x |
| Manufacturing (production, fabrication) | 5.0x |
| Import / Distribution | 6.0x |
| Retail | 4.2x |

Starting multiples represent the theoretical ceiling for a business that scores perfectly in that sector. They reflect long-run NZ SME transaction data (2021 baseline — **update these annually**).

---

### Step 2 — Score 23 Questions

Questions are grouped into 8 categories. Each answer is scored 1–5 (5 = best outcome, 1 = worst). Each question has a sector-specific weight (1.0 = full weight, 0.7 = reduced weight for that sector).

**Sector weights table:** rows = questions, columns = sectors

| Q# | Category | Question | Asset Heavy | Services | Mfg | Import/Dist | Retail |
|----|----------|----------|-------------|----------|-----|-------------|--------|
| 1 | HISTORY | How long has business been established? | 0.7 | 0.7 | 0.7 | 0.7 | 0.7 |
| 2 | FINANCIAL | History of EBIT growth | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| 3 | FINANCIAL | What percentage of income is contracted? | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| 4 | FINANCIAL | CAPEX requirement (avg annual capex as % of depreciation) | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| 5 | FINANCIAL | Gross profit % | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| 6 | FINANCIAL | Level of seasonality in the business | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| 7 | FINANCIAL | Fixed assets as a percentage of sales | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| 8 | FINANCIAL | GP % consistency (trend) | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| 9 | PEOPLE | Business dependence on staff technical knowledge | 0.7 | 1.0 | 1.0 | 0.7 | 0.7 |
| 10 | PEOPLE | Average length of staff service | 0.7 | 1.0 | 1.0 | 0.7 | 1.0 |
| 11 | PEOPLE | How easy to hire / train staff | 0.7 | 1.0 | 1.0 | 0.7 | 0.7 |
| 12 | PEOPLE | Management team capable of running business without owner | 0.7 | 1.0 | 1.0 | 0.7 | 1.0 |
| 13 | SUPPLIERS | Supply chain vulnerability to disruption | 0.7 | 0.7 | 0.7 | 1.0 | 0.7 |
| 14 | SUPPLIERS | Contractual supply agreements or sole agencies | 0.7 | 0.7 | 0.7 | 1.0 | 0.7 |
| 15 | CUSTOMERS | % of turnover from B2B (wholesale) clients | 0.7 | 0.7 | 1.0 | 1.0 | 0.7 |
| 16 | CUSTOMERS | Top 5 customer retention across multiple periods | 1.0 | 1.0 | 1.0 | 1.0 | 0.7 |
| 17 | CUSTOMERS | Largest single customer % of turnover | 0.7 | 0.7 | 1.0 | 0.7 | 0.7 |
| 18 | CUSTOMERS | Ease of adding new customers | 0.7 | 0.7 | 1.0 | 0.7 | 0.7 |
| 19 | PREMISES | Premises suitability and lease security | 0.7 | 0.7 | 0.7 | 0.7 | 0.7 |
| 20 | COMPETITION | Level of competition in the market | 0.7 | 0.7 | 0.7 | 0.7 | 1.0 |
| 21 | COMPETITION | Barriers to entry for new competitors | 0.7 | 0.7 | 0.7 | 0.7 | 0.7 |
| 22 | GROWTH | Growth opportunities available to this business | 0.7 | 0.7 | 0.7 | 0.7 | 0.7 |
| 23 | GROWTH | Sector profile (declining → growing) | 0.7 | 0.7 | 0.7 | 0.7 | 0.7 |

---

### Step 3 — Answer Options per Question

All scored 5 (best) → 1 (worst):

| Q# | Score 5 | Score 4 | Score 3 | Score 2 | Score 1 |
|----|---------|---------|---------|---------|---------|
| 1 | 10yrs+ | 5–10 yrs | 3–5 yrs | 1–3 yrs | < 1 yr |
| 2 | Strong growth | Growing | Steady | Weak | Declining |
| 3 | >80% contracted | 60–80% | 40–60% | 20–40% | <20% |
| 4 | <20% of depreciation | 20–40% | 40–60% | 60–80% | >80% |
| 5 | >50% GP | 40–50% | 30–40% | 20–30% | <20% |
| 6 | Low seasonality | — | Medium | — | High |
| 7 | High fixed asset base | — | Medium | — | Low fixed asset base |
| 8 | GP% improving | — | Steady | — | Declining |
| 9 | Low staff dependence | — | Average | — | Highly dependent on key staff |
| 10 | > 7 yrs avg tenure | 5–7 yrs | 3–5 yrs | 1–3 yrs | < 1 yr |
| 11 | Very easy to hire/train | Easy | OK | Hard | Very hard |
| 12 | Fully managed (no owner dependency) | Semi-managed | Could be managed | Hard to manage without owner | Totally owner-dependent |
| 13 | Not vulnerable | Slightly | Steady | Very vulnerable | Extremely vulnerable |
| 14 | All supply contracted | Plenty | Some | A few | None |
| 15 | >80% B2B | 60–80% | 40–60% | 20–40% | <20% B2B |
| 16 | All top 5 retained | Most | Some | Few | None same |
| 17 | Largest customer ≤10% | 11–20% | 21–30% | 31–40% | >40% |
| 18 | Easy to add customers | Quite easy | Average | Hard | Very hard |
| 19 | Secure long-term lease, growth-ready | Comfortable, decent term | OK for 4+ yrs | Must relocate < 3 yrs | Must relocate < 2 yrs |
| 20 | Hardly any competition | Some | Average | A lot | Highly competitive |
| 21 | Very hard to set up in competition | Hard | Possible | Easy | Very easy |
| 22 | Lots of growth opportunity | Good opportunities | Some | Small | None |
| 23 | Strong sector growth | Good | Steady | Weak | Declining sector |

**Note on Q7:** "High fixed asset base" scores 5 because in the source model, high fixed assets = more defensible/investable. This is appropriate for asset-heavy sectors but may be counterintuitive for services. The sector weighting (all 1.0) means this applies equally across sectors — consider reviewing.

---

### Step 4 — Calculate Resultant Multiple

```
weighted_score = sum(answer_score[i] × sector_weight[sector][i] for i in 1..23)
max_possible   = 5 × 23 = 115

resultant_multiple = (weighted_score / max_possible) × starting_multiple[sector]
```

**Example (Services, score 69.3/115):** 69.3 / 115 × 4.7 = **2.83x**

**Python function signature:**
```python
def compute_ev_ebitda_multiple(answers: list[int], sector: str) -> dict:
    """
    answers: list of 23 integers, each 1–5
    sector: one of 'asset_heavy', 'services', 'manufacturing', 'import_distribution', 'retail'
    returns: {'weighted_score': float, 'max_possible': int, 'resultant_multiple': float, 'starting_multiple': float}
    """
```

---

### Step 5 — Apply to Normalised EBITDA

```
normalised_ebitda = extracted_ebitda + ebitda_addbacks   # from Phase 3 profile
enterprise_value_multiples = normalised_ebitda × resultant_multiple
```

Normalised EBITDA is the "EBITDA to working owner" figure — extracted EBITDA plus owner add-backs (from Phase 3's `ebitda_adjustments` table). Use the most recent full fiscal year.

---

## Method 2: DCF (Discounted Cash Flow)

### Inputs from Intake Questionnaire

| Input | Description | Default suggestion |
|-------|-------------|-------------------|
| Risk-free rate (nominal) | 10-year government bond yield | User enters; suggest current RBNZ/RBA rate |
| Equity Market Risk Premium | Market return over risk-free rate | 7–8% typical NZ/AU SME |
| Beta | Sector beta multiplier | Derived from questionnaire score OR user enters |
| Cost of debt (pre-tax) | Weighted average borrowing rate | From balance sheet or user enters |
| Corp tax rate | NZ default 28%, AU default 30% | User confirms |
| Weighting of equity | % equity funding (long-run) | 100% if no debt |
| Weighting of debt | % debt funding (long-run) | 0% if no debt |
| Terminal growth rate | Long-run sustainable CAGR | 2–4% typical |
| Forecast years | DCF projection horizon | 3 or 5 years |
| Revenue growth rate | Annual growth assumption | User enters (or derived from historical trend) |
| Replacement owner salary | Market-rate salary to replace working owner | User enters (EBITDA add-back context) |

### WACC Calculation

```
cost_of_equity   = risk_free_rate + beta × equity_market_risk_premium   # CAPM
cost_of_debt_post_tax = cost_of_debt_pretax × (1 - corp_tax_rate)

wacc_post_tax = (weight_equity × cost_of_equity) + (weight_debt × cost_of_debt_post_tax)
```

### DCF Projections (5 years)

```
# Year 0 = normalised EBITDA from Phase 3
# FCFF = Free Cash Flow to Firm

for year in 1..forecast_years:
    revenue[year]  = revenue[year-1] × (1 + growth_rate)
    ebitda[year]   = ebitda[year-1] × (1 + growth_rate)
    tax[year]      = ebitda[year] × corp_tax_rate
    capex[year]    = 0   # user can enter; default 0
    fcff[year]     = ebitda[year] - tax[year] - capex[year]
    dcf[year]      = fcff[year] / (1 + wacc_post_tax)^year

cumulative_dcf = sum(dcf[1..forecast_years])
```

### Terminal Value (Gordon's Growth Model)

```
final_year_cashflow = fcff[forecast_years]
terminal_value      = final_year_cashflow × (1 + terminal_growth_rate) / (wacc_post_tax - terminal_growth_rate)
terminal_value_npv  = terminal_value / (1 + wacc_post_tax)^forecast_years

enterprise_value_dcf = cumulative_dcf + terminal_value_npv
```

---

## Illiquidity Discount (Bid-Ask Spread Regression)

Applied to enterprise value to reflect the cost of illiquidity for a private company sale.

**Formula (Damodaran):**
```
illiquidity_discount = 0.145
    - 0.0022 × ln(annual_revenues)
    - 0.015  × is_profitable          # 1 if NPBT > 0, else 0
    - 0.016  × (cash / enterprise_value)
    - 0.11   × (monthly_trading_volume / enterprise_value)   # 0 for private companies
```

For private SMEs: `monthly_trading_volume = 0` (no public market).
`cash` = cash and bank balance from extracted balance sheet.

---

## Final Enterprise Value and Fair Value

```
# Take the average of both methods (or weight as appropriate)
ev_multiples = normalised_ebitda × resultant_multiple
ev_dcf       = cumulative_dcf + terminal_value_npv

enterprise_value = (ev_multiples + ev_dcf) / 2   # simple average; or report separately

discount_amount  = enterprise_value × illiquidity_discount
fair_value       = enterprise_value × (1 - illiquidity_discount) - net_debt

# Report low/mid/high range
ev_low  = min(ev_multiples, ev_dcf) × (1 - illiquidity_discount) - net_debt
ev_high = max(ev_multiples, ev_dcf) × (1 - illiquidity_discount) - net_debt
ev_mid  = fair_value
```

---

## Python Module Structure

```
backend/valuation.py
  ├── SECTOR_STARTING_MULTIPLES   # dict: sector → float
  ├── SECTOR_WEIGHTS              # dict: sector → list[float] (23 weights)
  ├── compute_ev_ebitda_multiple(answers, sector) → dict
  ├── compute_wacc(inputs) → dict
  ├── compute_dcf(ebitda, wacc, growth_rate, tax_rate, years, terminal_growth) → dict
  ├── compute_illiquidity_discount(revenues, is_profitable, cash, ev) → float
  └── compute_valuation(questionnaire_answers, dcf_inputs, financial_data) → ValuationResult
```

---

## Known Limitations and Improvement Notes

1. **Starting multiples are 2021 NZ baseline** — should be reviewed annually and configurable per jurisdiction (AU multiples differ). Store in config or DB rather than hardcoded.

2. **Q7 "Fixed assets" scoring** — "High fixed asset base" scores 5 across all sectors but this penalises asset-light services businesses. Consider inverting Q7 for Services and Retail sectors.

3. **Q6, Q8, Q9 three-option questions** — these have 3 meaningful options but use 5-3-1 scoring (skipping 4 and 2). The UI should show only 3 radio buttons (Low/Medium/High etc.) but map them to scores 5/3/1.

4. **Illiquidity discount uses firm value in denominator** — this creates a circular dependency (discount depends on EV, but EV is what we're computing). Solve with an initial EV estimate, then one iteration.

5. **Beta for CAPM** — the model accepts a direct beta input. A future improvement is to derive beta from the questionnaire score (higher-risk businesses → higher beta). For now, user enters beta manually.

6. **Minimum multiple floor** — add a floor of 0.5x resultant multiple to prevent nonsensical valuations for very low-scoring businesses.

7. **Normalised EBITDA** — pull directly from Phase 3's `ebitda_adjustments` table (sum of add-backs + extracted EBITDA). Do NOT ask the user to re-enter EBITDA.

8. **Multiple financial years** — the model uses the most recent fiscal year's EBITDA. A 3-year weighted average (most recent year weighted 60%, year-2 weighted 30%, year-3 weighted 10%) produces more stable results. Consider offering this as an option.

---

## Outputs Passed to Claude

Python computes and passes to Claude:

```json
{
  "method_used": "both" | "dcf_only" | "multiples_only",
  "normalised_ebitda": 420909,
  "questionnaire_score": {"raw": 81, "weighted": 69.3, "max": 115},
  "sector": "Services",
  "ev_multiples": {"multiple": 2.83, "enterprise_value": 1191173},
  "ev_dcf": {"cumulative_dcf": 1420000, "terminal_value_npv": 380000, "enterprise_value": 1800000},
  "illiquidity_discount": {"rate": 0.12, "amount": 215000},
  "concluded_range": {"low": 950000, "mid": 1200000, "high": 1450000},
  "net_debt": 0,
  "wacc": {"cost_of_equity": 0.18, "wacc_post_tax": 0.18},
  "key_risk_factors": ["Owner-dependent operations (Q12 scored 4/5)", "Limited contracted income (Q3 scored 1/5)"]
}
```

Claude receives this JSON and writes the narrative. Claude does NOT make up or adjust the numbers.
