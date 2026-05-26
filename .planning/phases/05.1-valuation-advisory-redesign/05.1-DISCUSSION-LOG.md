# Phase 5.5: Valuation Advisory Redesign — Discussion Log

**Date:** 2026-05-26
**Areas discussed:** Questionnaire redesign, WACC & DCF model, Agentic research scope, Report structure

---

## Area 1: Questionnaire redesign

| Question | Options presented | Selected |
|----------|-------------------|----------|
| What should the intake capture? | Narrative risk inputs only / Financial assumptions only / Both | **Both** |
| Narrative areas to cover | Owner dependency / Customer concentration / Competitive position / Growth strategy | **All four** |
| Financial section: what user provides vs. extracted | Forecast assumptions only / Normalisations + forecast / Full WACC inputs + forecast | **Normalisations + forecast** |
| Normalisation table approach | Confirm + adjust existing only / Confirm + add new / Separate normalisation table | **Separate normalisation table** (pre-filled from Phase 3, fully editable, add new items) |
| Forecast growth rate format | Single growth rate / Year-by-year rates / Base-Bull-Bear | **Single growth rate (CAGR)** |

**Rationale:** The 23-question scoring model is being dropped because it produces a score-driven multiple, not the qualitative risk narrative needed for a Propellerhead-style report. The hybrid approach captures what the agent can't research (owner dependency, customer detail, growth plans) and what the financials don't specify (normalisation items, forecast assumptions).

---

## Area 2: WACC & DCF model

| Question | Options presented | Selected |
|----------|-------------------|----------|
| Drop EV/EBITDA multiples? | DCF-only / Keep both / Multiples as cross-check | **Multiples as cross-check** |
| WACC determination | Agent researches / User enters, agent validates / Hardcoded bands | **Agent researches WACC inputs** |
| WACC type | Real WACC (inflation-adjusted) / Nominal WACC with explicit terminal growth | **Nominal WACC, user enters terminal growth** |
| Illiquidity discount | Keep Damodaran formula / Simplified fixed discount / Drop it | **Keep Damodaran formula** |

**Rationale:** DCF is the professional standard for NZ SME valuations; multiples as a cross-check adds credibility without driving the conclusion. Agent-researched WACC removes the burden from business owners who don't know what a beta is. Nominal WACC chosen for simplicity.

---

## Area 3: Agentic research scope

| Question | Options presented | Selected |
|----------|-------------------|----------|
| Research categories | Company / Sector / WACC inputs / Comparable transactions | **Company + Sector + Comparable transactions** (WACC clarified separately) |
| WACC research | Agent searches / User enters manually | **Agent searches RBNZ + Damodaran** |
| RBNZ data to retrieve | Risk-free rate / ERP / Inflation | **All three** |
| Research architecture | Multi-step Claude with web_search / Orchestrated Python searches / Two-phase | **Multi-step Claude with web_search tool** |

**Key detail from user:** Beta input specifically references Damodaran's `totalbetaRest` dataset (published annually on damodaran.com). RBNZ is the source for risk-free rate, ERP, and inflation. Agent searches these sources dynamically.

---

## Area 4: Report structure

| Question | Options presented | Selected |
|----------|-------------------|----------|
| Section categories | Introduction / Business overview & market position / Financial tables / WACC & valuation tables | **All four** |
| Balance sheet summary | Include full BS summary / Net debt only / Skip | **Include full balance sheet summary** |
| Content storage format | JSON section storage / Mixed narrative + structured data / Markdown | **Keep JSON section storage** |

**New 12-section schema agreed:**
introduction → business_overview → market_position → financial_performance → normalisations_schedule → balance_sheet_summary → valuation_methodology → wacc_assumptions → dcf_analysis → valuation_summary → multiples_crosscheck → disclaimer

Sections containing tables use a `{narrative, table: {headers, rows}}` JSON structure within the section value.

---

## Deferred ideas

- Real WACC (inflation-adjusted) approach — user chose nominal; can add as toggle later
- Admin-uploaded Damodaran beta file fallback — if web search proves unreliable
- Bull/Bear revenue scenarios — belongs in Financial Forecast report type
