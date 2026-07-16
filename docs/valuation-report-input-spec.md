# AccountIQ Valuation Report and Input Specification

## Product outcome

AccountIQ should produce an indicative SME valuation with the depth and structure of the
Propellerhead and Marina Terrace examples while avoiding a long expert-style questionnaire.

The customer experience follows one rule:

> Research first, ask second.

AccountIQ should extract what it can from uploaded financial statements, research what it can
from credible public sources, and ask the customer only for private facts or judgments that could
materially change the valuation.

The valuation intake uses progressive disclosure:

1. Five quick private-fact answers
2. A separate earnings-adjustment review

Before the final submit action, the earnings-review step should reassure the customer that there
are no more required questions after this check. It should preview the work AccountIQ will now do:
public-source research trail, valuation modelling and browser/PDF report preparation.

The self-serve report picker is valuation-first. Valuation Advisory is the only active self-serve
journey for the MVP; other professional report families may remain visible as coming-soon roadmap
cards, but they should not route customers into unrelated questionnaires during the valuation
journey.

Moving backward must preserve both the five answers and any optional expert inputs. The customer
should never face the questions, adjustment editor and technical overrides as one long form.

The wizard waits for financial extraction to finish before showing the valuation questions. A
customer should see a plain-language "Reading your financial statements" state rather than being
allowed to generate against partial or empty figures.

## Source hierarchy

### Uploaded financial information

- Historical revenue, EBITDA, net profit and margins
- Balance sheet, cash, interest-bearing debt and operating fixed assets
- Working-capital trends
- Candidate normalisations and one-off expenditure
- Historical growth and ratio analysis

The financial performance section should include a compact "trading performance at a glance"
panel sourced from the uploaded-financials table. It should pull out the revenue bridge, EBITDA
bridge, EBITDA margin bridge and latest actual EBITDA so management and advisers can understand the
trading trend before reading the full schedule.
The historical ratio analysis section should include a compact "margin and growth at a glance"
panel sourced from the ratio table. It should highlight latest revenue growth and the gross,
EBITDA and net-profit margin bridges, so profitability quality is clear without adding another
customer question.
The normalisations section should include a compact "normalisation impact at a glance" panel
sourced from the normalisation schedule. It should show confirmed adjustment count, net EBITDA
adjustment, largest adjustment and normalised EBITDA so the maintainable earnings bridge is clear
without asking the customer to estimate valuation mechanics.
The same section should include a compact "normalised EBITDA bridge" visual sourced from the same
schedule. It should show uploaded EBITDA basis plus net normalisation adjustment equals normalised
EBITDA, so readers can see the maintainable earnings bridge before the detailed schedule.

### Public research

- Company background, services, locations and public milestones
- Sector conditions, competitors and regulatory context
- Comparable transactions and market multiple ranges
- RBNZ government bond yield and inflation data
- Damodaran equity risk premium and industry total beta
- Optional management-supplied public source hints, such as website pages, Companies Office records,
  LinkedIn pages or media links, used only to identify and corroborate the correct business

Every public fact used in the report must retain its source URL.
Management-supplied website and public-link hints that help identify the business should also be retained
in the sources table when they are not already present in the research-returned URLs, labelled as
management-supplied hints and explained as business-profile, company-fact or market-context corroboration.

The intake should make this visible before the customer submits: AccountIQ can use public online
avenues for business context, and the resulting report keeps the source trail so a reader can see
what supported the assumptions.

The market position section should include a compact "market context at a glance" panel sourced
from the public-source and comparable-evidence tables. It should show retained public source
count, benchmark evidence coverage, public-profile support and the comparability caveat, so the
market page is evidence-backed without asking the customer to research their own market.

### Management-confirmed private inputs

The required self-serve intake is limited to five quick answers:

1. Purpose of the valuation
2. Owner or key-person dependency
3. Largest-customer concentration
4. Revenue predictability (contracted, mixed or transactional)
5. Realistic revenue outlook for the next 12-24 months

The business overview section should include a compact "business context at a glance" panel
sourced from those management-confirmed private inputs as disclosed in the valuation assumptions table.
It should show owner or key-person dependency, customer concentration, revenue predictability and revenue
outlook, so management can see why the short questionnaire mattered without reading the full
assumption trail.
The report-letter and basis-of-preparation front matter should also disclose each of the five
answers in a management input trail with an explicit "management-confirmed private input" basis,
so the source hierarchy remains visible before the main report sections.

Each judgement question offers a "Not sure" route where appropriate. If management is unsure about
the revenue outlook, AccountIQ derives a conservative assumption from uploaded historical revenue
(capped between -5% and 12%) and falls back to 2% when there is insufficient history.

One collapsed optional narrative field captures key contracts, signed pipeline, upcoming changes,
disputes, unusual risks or opportunities.

One optional public-links field lets the user paste helpful online sources without making source
research their job. These links are normalised and bounded at the API boundary, then passed into
the research loop as hints to corroborate rather than as standalone proof.

### Optional expert overrides

Advanced inputs remain available but collapsed by default:

- Replacement manager cost
- Interest-bearing debt at the valuation date
- Surplus or non-operating assets
- Specific supported annual revenue growth

If replacement manager cost is supplied, AccountIQ treats it as a management-supplied maintainable
earnings deduction and shows it as a separate negative row in the normalisation schedule. This
keeps the optional override transparent without asking the customer to complete an owner-salary
questionnaire.

The user should not be asked to choose a forecast horizon, WACC or terminal growth rate during the
normal flow. The model uses a five-year explicit forecast, derives WACC from public research and
anchors terminal growth to researched New Zealand inflation. All assumptions must be visible in
the finished report.

The valuation assumptions section must include an assumption/source trail table showing each
material input, the value used, the primary source and why it matters. At minimum this table must
distinguish uploaded financial data, management-confirmed private inputs and public research inputs.
It should also include an "assumption basis at a glance" panel sourced from the same table,
showing the maintainable earnings base, growth assumption and source mix before the detailed
assumption schedule, so readers do not have to decode a dense table to understand the valuation
basis.

## Valuation method

- Discounted cash flow is the primary valuation method.
- High, mid and low WACC scenarios create the valuation range.
- The Damodaran-derived private-company illiquidity discount is shown explicitly.
- The WACC section should include a compact "WACC build visual" sourced from the computed WACC
  table. It should show the mid-case risk-free rate, beta-adjusted risk premium, resulting WACC
  and separate illiquidity discount, making the discount-rate build transparent without asking
  the customer to choose technical capital-market inputs.
- Researched EV/EBITDA evidence is a cross-check range, not a single value selected by a customer
  scoring questionnaire.
- The market cross-check section should include a compact "implied multiple reconciliation"
  sourced from the computed DCF, valuation summary and multiples tables. It should show
  normalised EBITDA, the researched EV/EBITDA range, DCF-implied pre- and post-illiquidity
  multiple ranges, and any midpoint tension versus the market range, without adding another
  customer scoring question.
- Enterprise value is bridged to equity value using debt, cash and surplus assets.
  The bridge should distinguish uploaded balance-sheet debt/cash from management-supplied debt or
  surplus-asset overrides, so optional expert inputs are visible rather than blended into a
  generic source label.
- Free cash flow is computed as EBIT after tax plus depreciation, less maintenance capital
  expenditure and change in operating working capital.
- The DCF section includes a visible mid-case forecast cash-flow schedule showing annual revenue,
  EBITDA, EBIT, tax, maintenance capex, change in operating working capital, free cash flow to
  firm and discounted free cash flow. These numbers come from Python, not from customer estimates
  or language-model recalculation.
- The DCF section also includes a compact "DCF forecast bridge at a glance" panel sourced from
  the DCF table and mid-case cash-flow schedule. It shows the adjusted enterprise-value range,
  midpoint adjusted enterprise value, revenue progression and free-cash-flow progression so the
  reader can understand the forecast mechanics before reading every row of the schedules.
- The same section should include a compact "DCF value build visual" sourced from the same
  computed DCF table and mid-case cash-flow schedule. It should show present value of explicit
  forecast free cash flows, implied terminal value, enterprise value before illiquidity, the
  illiquidity discount and adjusted enterprise value, so the reader can see how forecast cash
  flow converts to the valuation conclusion without another management input.
- Maintenance capex defaults to extracted depreciation. Operating working capital is derived from
  receivables, inventory and other operating current assets less trade creditors and other
  operating current liabilities; its revenue ratio is capped between -10% and 30%.
- Python computes every valuation number; the language model writes narrative around those
  computed outputs.
- The sensitivity section includes a Python-computed 3x3 matrix: management-supplied or historically
  derived growth, plus or minus two percentage points, crossed with the high/mid/low WACC cases.
  This adds auditability without another customer question.
- The sensitivity section should include a compact "sensitivity takeaway at a glance" panel
  sourced from the Python-computed matrix and specific-risk-factor table. It should show the base
  sensitivity case, full quantified enterprise-value span, growth cases tested and number of
  specific risks covered, so management can understand what moved the range without extra
  valuation questions.
- The same section should include a compact "sensitivity spread visual" sourced from the same
  Python-computed matrix. It should show downside, base and upside adjusted enterprise value
  before the detailed grid, giving a quick risk-range picture without asking for extra management
  inputs.
- The same section includes a specific-risk-factor table derived from the short management intake:
  owner or key-person dependency, largest-customer concentration, revenue predictability, revenue outlook and
  optional private context. It is qualitative and must not be confused with the quantified
  WACC/growth sensitivity matrix.

## Report structure

1. Introduction
2. Executive summary
3. Overview
4. Market position
5. About business valuations
6. Valuation methodology adopted
7. Financial performance
8. Historical ratio analysis
9. Normalisations
10. Balance sheet summary
11. Valuation approach and assumptions
12. Weighted average cost of capital
13. Discounted cash flow analysis
14. Indicative valuation summary
15. Multiples cross-check
16. Sensitivity and specific risks
17. Comparable evidence appendix
18. Sources and references
19. Disclaimer
20. General principles
21. Glossary

The explanatory and appendix sections are generated from the same uploaded, researched and
computed evidence. They do not require additional customer questions.

The executive summary should include a compact "valuation conclusion at a glance" panel sourced
from the AccountIQ-computed executive valuation table. It should show the enterprise value range,
midpoint enterprise value, midpoint equity value and net-debt adjustment before the detailed
table, so the first substantive report page is immediately decision-useful.
The same executive summary should include a compact "valuation range visual" sourced from the
same computed high/mid/low rows. It should show the enterprise-value and indicative-equity-value
ranges with midpoint markers before the detailed table, so the reader can see the conclusion
visually without requiring any extra management inputs.

The indicative valuation summary section should include a compact "valuation range at a glance"
panel sourced from the DCF-versus-multiples summary table. It should show the primary DCF range,
midpoint equity value, market cross-check range and DCF-versus-multiple midpoint gap, so the
reader can understand the conclusion before studying every scenario row.

The valuation methodology section should include a compact "methodology at a glance" panel
sourced from the computed WACC, market-multiples and equity-bridge tables. It should identify the
primary DCF method, discount-rate range, market cross-check and equity bridge before the detailed
valuation mechanics begin.
The same methodology section should include a compact "valuation approach selection" panel showing
why DCF is adopted as the primary method, why EV/EBITDA is retained only as a reasonableness
cross-check, and why an asset/net-asset approach is not the primary basis for a going-concern SME
valuation. This panel should be sourced from existing computed DCF, multiples and balance-sheet
sections and must not add another customer question.

Core valuation mechanics pages should not read as table dumps. Where the WACC, market-multiples
cross-check and balance-sheet bridge tables are present, the browser report and PDF should add
compact interpretation panels sourced from those same tables. The WACC panel should explain how
the high/mid/low discount-rate cases drive the valuation range, the multiples panel should
explain how the EV/EBITDA range is used as a reasonableness cross-check rather than the primary
conclusion, the implied-multiple reconciliation should show how the DCF output translates back
to EV/EBITDA before and after the illiquidity adjustment, and the balance-sheet panel should
explain the midpoint enterprise-value-to-equity-value bridge. These panels must not introduce additional customer questions or language-model
recalculations.
The balance-sheet summary should also include a compact "enterprise-to-equity visual" sourced
from the same computed bridge table. It should show midpoint enterprise value, net debt, surplus
assets and midpoint equity value before the detailed rows, making the shareholder-value bridge
immediately visible without asking the customer for more valuation inputs.

The financial performance section should include a compact "financial trend visual" sourced from
the computed revenue and EBITDA rows in the financial-performance table. It should show the
period-by-period trading trend before the detailed table, giving readers an immediate view of
scale and operating earnings without asking the customer for additional valuation inputs.

The comparable evidence appendix should include a compact "comparable evidence at a glance"
panel sourced from the comparable evidence table. It should show evidence-row count, retained
source URL count, whether market-multiple support is present and whether the comparability
caveat is visible, so the reader understands that public evidence supports a cross-check rather
than a direct private-company price.

The browser report cover and PDF cover are part of the professional report structure, not only
navigation chrome. Both should show:

- A compact report-basis strip showing uploaded financials, five private inputs, public-source
  trail and AccountIQ valuation model, so the short questionnaire feels deliberate rather than thin
- A compact valuation snapshot sourced from the computed executive-summary valuation table
- Prepared for
- Prepared by
- Preparer role
- Report channel
- Report type
- Report/reference number
- Valuation date
- Purpose
- Basis of value
- Reliance wording

The contents/body numbering starts with the formal report sections, but cover plus report-letter/
basis-of-preparation front matter should still make the evidence basis and reliance limitations clear.
The sources section should include a compact "source trail at a glance" panel sourced from the
structured sources table. It should show how many public URLs were retained and whether the table
supports discount-rate inputs, terminal-growth/inflation assumptions and business-context
evidence, before the detailed source table.
The disclaimer section should include a compact "reliance at a glance" panel sourced from the
existing disclaimer wording. It should summarise intended use, advice status, information
reliance, verification status and third-party reliance so the closing pages read like deliberate
professional report scope-setting rather than loose legal text. This panel must not introduce
additional customer questions.
The report-letter and basis-of-preparation front matter should include a compact, separate
report-letter positioning block plus a management input trail
showing each of the five private answers captured and how that answer is used in the report
scope, valuation assumptions or specific-risk commentary. This makes the short questionnaire feel
deliberate rather than thin. The PDF artifact audit should fail if the management input trail is
absent from a valuation report.
The same front matter should also state the information basis and scope exclusions, so the reader
understands that AccountIQ used uploaded financials, management-confirmed private inputs, public-source research
and valuation calculations, but did not perform an audit, assurance engagement, legal/tax review,
fairness opinion or buyer-specific synergy assessment.
The management input trail and the broader evidence/model basis should be visually separated in the
PDF front matter so the report reads as deliberate scope-setting rather than one long generated
table.

## Experience safeguards

- Explain why a private question matters before asking it.
- Show a live required-answer checklist on the valuation intake screen so the customer can see
  that only five private facts are required and optional research clues remain optional.
- Offer a clear "Not sure" answer where uncertainty is reasonable.
- Make it visible before the fields that "Not sure" is acceptable for uncertain private facts,
  so customers do not feel forced to guess precise customer, contract or forecast details.
- Keep technical assumptions out of the default customer flow.
- Keep public-source hints optional, collapsed by default, and clearly separate from the five
  required private-fact answers.
- Keep optional private valuation context collapsed by default, so the first valuation screen
  still reads as five required answers rather than a longer questionnaire.
- Pre-fill extracted adjustments and let the customer confirm, edit or remove them.
- If the customer keeps or adds an earnings adjustment, require a non-zero amount and a short
  rationale so the normalisation schedule can support a professional maintainable-earnings bridge.
  Blank adjustment rows should be ignored or removable rather than treated as extra required
  questions.
- In the earnings review, give plain-language examples of items that are usually worth adjusting
  and items that should usually be left alone, so users do not feel they need valuation training.
- Before the final "Research & prepare valuation" action, explain that no more required questions
  remain and that AccountIQ will prepare the research trail, valuation model outputs and
  browser/PDF report pack from the information already captured.
- Keep optional inputs collapsed.
- Enforce the same five required answers at both the browser and API boundaries.
- Reject unsupported non-empty valuation intake fields at the API boundary, so legacy risk scores,
  free-text questionnaire leftovers or accidental long-form fields cannot silently become part of
  the self-serve valuation journey.
- Require the selected financial upload to reach a completed extraction state before report
  generation can be queued.
- For live valuation reports, require extracted revenue plus an EBITDA/profit basis before queuing.
  A completed upload with no usable valuation figures should ask for clearer financial statements,
  not produce a thin professional-looking report.
- Check the live research connection before creating a report job so customers never wait for a
  queued report that is guaranteed to fail for a setup reason.
- Reject malformed, truncated, missing or placeholder report sections before marking a valuation
  complete; failed report attempts remain retryable and are never delivered as finished reports.
- Reject generated valuation reports that read like an unfinished questionnaire or follow-up
  request. A report must not ask the user to provide more documents, more answers or technical
  valuation assumptions after the five private facts and earnings-adjustment review are complete.
- Reject generated valuation reports that do not contain the Python-computed DCF, WACC, multiples,
  equity bridge and sensitivity figures in the relevant valuation tables. The language model may
  write narrative, but it must not drift away from the computed valuation outputs.
- Reject generated valuation reports that omit the Python-computed mid-case forecast cash-flow
  schedule or drift from its yearly free-cash-flow bridge.
- Reject generated valuation reports whose valuation-assumptions section does not visibly
  distinguish uploaded financial data, management-confirmed private inputs and public research inputs.
- Reject generated valuation reports whose sensitivity-and-specific-risks section omits the
  specific risk factor table covering owner or key-person dependency, customer concentration, revenue
  predictability and revenue outlook.
- Require every comparable-evidence table row to include the public source URL that supports the
  evidence, not just a source name. The separate sources section is a structured table with source
  name, URL and a short description of what each source supports.
- Reject sources-section rows whose support/use description is only a generic label such as
  "website" or "source"; every retained URL should tell the reader what assumption, benchmark,
  company fact or market context it supports.
- In the browser report viewer, render public source URLs as safe clickable links and wrap long
  source text cleanly so evidence is easy to inspect.
- In the PDF, right-align financial figure columns but keep qualitative evidence, source,
  rationale and risk-treatment columns left-aligned so long text remains readable.
- Label every demo-mode report view, PDF cover, PDF page and filename as demo data that is not for
  reliance. Simulated research or valuation figures must never be mistaken for client work.
- Disclose demo mode during financial processing and before the five private questions. Demo
  wording must say that extraction, research and valuation inputs are simulated rather than
  promising live online research.
- Demo mode must be explicit (`ACCOUNTIQ_DEMO_MODE=true`, or E2E test mode) rather than an
  automatic fallback when the live provider key is missing. This lets local users continue without
  an Anthropic key while preventing production deployments from silently delivering simulated
  reports.
- Local no-key testing can use `scripts/start-demo-backend.sh`, which starts FastAPI with
  `ACCOUNTIQ_DEMO_MODE=true` without resetting the normal development database.
- Live provider-backed quality checks can use `scripts/run_live_valuation_smoke.py` once a real
  Anthropic key is configured. The script keeps demo mode off, verifies the live research
  connection, asks the live model for strict valuation-report JSON around AccountIQ-computed
  inputs, runs the same report validators as the app and can render a PDF artifact under
  `output/pdf/`.
- Visual PDF review can use `scripts/render_valuation_pdf_preview.py` to render the cover,
  contents, report-letter/basis-of-preparation, assumptions, DCF, sensitivity, risk, comparable-evidence and
  sources pages to PNGs for fast inspection.
- After the five answers and earnings review are submitted, the status screen should explain that
  AccountIQ is combining the upload, private answers, market research, valuation modelling and PDF
  formatting, including report-letter front matter, so the customer understands the work being done
  while they wait.
- Once the report is ready, the same screen should switch to completion language: the pack has been
  prepared, the customer can review it online or download the PDF, and the basis/source sections
  explain what the conclusion relies on. Do not keep using waiting-state wording after the report is
  ready.
- The ready screen should briefly explain the two delivery actions: use the browser report to review
  the valuation snapshot, report letter, basis of preparation and source trail; use the PDF as the
  print-ready professional pack for adviser, lender, board or owner discussions.
- Never invent missing company facts, transactions, financial figures or source URLs.
- Distinguish management-confirmed private inputs, extracted financial data and public research in the report.
- Present the report in a print-ready A4 layout with a cover, contents, report-letter/basis
  front matter, section hierarchy and professional financial tables.
- The browser report cover and PDF cover should include a compact valuation snapshot sourced from
  the computed report table, so the high/mid/low valuation output is visible before the detailed
  sections.
- The browser report cover and PDF cover should include professional front-cover detail fields:
  prepared for, prepared by, report type, reference, valuation date, purpose, basis of value and
  reliance wording. The PDF artifact audit should fail if these fields are absent.
- Number the report sections consistently in the browser viewer, contents page and PDF body so
  the output reads like a formal valuation pack and can be cross-referenced.
