# AccountIQ valuation example-report parity checklist

Date: 2026-07-07

## Purpose

This checklist compares the current AccountIQ deterministic valuation sample against the available local extracts from the user-provided indicative valuation examples.

Available reference material in the current workspace:

- `tmp/pdfs/marina.txt` — usable extracted text for the Marina Terrace indicative company valuation report.
- `tmp/pdfs/propellerhead.txt` — sparse extracted headings only; useful for confirming broad section spine, not page-level presentation or detailed wording.
- `output/html/accountiq-demo-sample-indicative-valuation.html` and `output/pdf/accountiq-demo-sample-indicative-valuation.pdf` — current AccountIQ deterministic demo artifacts.
- `output/html/valuation-visual-parity-review.html` — generated visual review pack linking the current rendered AccountIQ PDF pages to the parity criteria in this checklist.

This is a structural and content-parity checklist. It is not a final visual side-by-side QA against the original PDF pages because the original reference PDFs are not stored as durable source artifacts in the repo.

## Reference spine observed

The Marina Terrace extract shows a professional indicative valuation pack with:

- Cover/title page and prepared-for party.
- Contents.
- Formal introductory letter and reliance wording.
- Introduction covering client, instructing party, purpose, valuation date, sources of information, basis of valuation, liability/confidentiality and compliance.
- Overview.
- About business valuations.
- Valuation methodology adopted.
- Financial performance and normalisations.
- Valuation approach and assumptions.
- Weighted average cost of capital.
- Sensitivity analysis.
- Multiples cross-check and observed comparable transaction discussion.
- Appendix.
- Disclaimer.
- General principles.
- Glossary.

The Propellerhead extract is thin, but its headings corroborate the same broad report shape: contents, introduction, executive summary, overview, about business valuations, valuation methodology, financial performance, valuation approach and assumptions, key differences, disclaimer, general principles and glossary.

## Parity checklist

| Reference expectation | AccountIQ current sample | Verdict | Notes / next improvement |
|---|---|---:|---|
| Professional cover/title page | Browser and PDF cover include report title, prepared for, prepared by, report type, reference, valuation date, purpose, basis of value, reliance and valuation snapshot. | Pass | AccountIQ also includes a report-basis strip explaining uploaded financials, five private inputs, public-source trail and valuation model. |
| Contents | AccountIQ includes a contents page with numbered sections 01-21. | Pass | Stronger than the reference extract because section numbering is explicit and validated in browser/PDF audits. |
| Formal introduction and reliance framing | AccountIQ now includes report-letter front matter with prepared-for, prepared-by, preparer role, organisation, report channel, report type, reference, purpose/reliance, information relied upon, work performed and important limitation rows. Section 01 then covers client/report purpose, valuation date/basis, sources of information, liability/confidentiality/compliance-style reliance wording. | Pass | AccountIQ includes a default AccountIQ valuation-team identity; optional named adviser/contact-person letterhead remains a branding/product decision rather than a report-logic gap. |
| Scope, sources and information basis | AccountIQ adds basis-of-preparation front matter before section 01, with report letter, scope exclusions, information basis, management input trail, evidence/model basis and derived technical assumptions. | Pass | This is a deliberate adaptation for self-serve use: it makes the short questionnaire and evidence hierarchy visible before the report body. |
| Overview | AccountIQ section 03 covers business overview and includes “Business context at a glance”. | Pass | Uses five private answers rather than asking a long business-description questionnaire. |
| Market/business context | AccountIQ adds section 04 Market Position with “Market context at a glance”. | Pass | Reference examples include market/context discussion; AccountIQ makes public-source evidence traceable. |
| About business valuations | AccountIQ section 05 explains business value, enterprise/equity value and why a range is used. | Pass | Matches the educational purpose of the examples. |
| Valuation methodology adopted | AccountIQ section 06 states DCF as primary and EV/EBITDA as cross-check, with methodology-at-a-glance and approach-selection panels. | Pass | Stronger guardrail than examples because it rejects customer-selected scoring mechanics. |
| Financial performance | AccountIQ section 07 includes a financial table, trading performance panel and financial trend visual. | Pass | Reference has financial-performance schedules; AccountIQ adds compact reader guidance to reduce table-dump feel. |
| Ratio/margin analysis | AccountIQ section 08 includes historical ratio analysis and margin/growth panel. | Pass | This expands the reference spine in a useful professional-report direction. |
| Normalisations | AccountIQ section 09 includes normalisation schedule, impact panel and normalised EBITDA bridge. | Pass | Aligns with reference normalisation discussion while keeping the customer interaction to a separate earnings review. |
| Balance sheet and equity bridge | AccountIQ section 10 includes balance-sheet summary and enterprise-to-equity bridge/visual. | Pass | Reference examples discuss valuation value and assumptions; AccountIQ makes debt/cash/surplus bridge explicit. |
| Valuation approach and assumptions | AccountIQ section 11 includes forecast assumptions, long-term/reinvestment assumptions, management context and a detailed assumption/source trail. | Pass | Strong improvement for auditability: uploaded data, management private inputs, public research and model conventions are separated. |
| Weighted average cost of capital | AccountIQ section 12 includes WACC assumptions and WACC build visual. | Pass | Mirrors the Marina Terrace WACC topic while deriving inputs from public research/model assumptions instead of customer entry. |
| Discounted cash flow analysis | AccountIQ section 13 includes DCF detail, DCF bridge, DCF value build and mid-case cash-flow schedule. | Pass | This is more explicit than the reference extract and is computed in Python. |
| Indicative valuation conclusion | AccountIQ executive summary and section 14 show high/mid/low enterprise and equity value. | Pass | The cover also shows the valuation snapshot before the detailed sections. |
| Multiples cross-check | AccountIQ section 15 includes market cross-check, implied multiple reconciliation and detailed multiples table. | Pass | AccountIQ requires source URLs and frames multiples as a reasonableness cross-check, not a direct private-company price. |
| Specific comparable evidence | AccountIQ section 17 includes comparable evidence appendix and source-backed rows. | Partial pass | The sample uses broad public benchmark evidence. It intentionally avoids named transaction claims unless supported; live reports should include named transaction evidence only when the research/source trail supports it. |
| Sensitivity | AccountIQ section 16 includes a Python-computed sensitivity matrix, sensitivity takeaway, sensitivity spread visual and specific risk factors. | Pass | The risk table uses the short intake answers, so sensitivity is professional without adding more user questions. |
| Appendix/source trail | AccountIQ has section 17 Comparable Evidence Appendix and section 18 Sources and References with URLs and support descriptions. | Pass | This directly supports the user’s point that business information can come from online avenues. |
| Disclaimer | AccountIQ section 19 has reliance-at-a-glance plus disclaimer wording. | Pass | The audit rejects live reports missing reliance context or demo reports without demo labels. |
| General principles | AccountIQ section 20 covers basis of value and timing/information principles. | Pass | Matches the professional-report close of the examples. |
| Glossary | AccountIQ section 21 defines DCF, enterprise value, equity value, EBITDA, maintainable earnings, normalisation, terminal value, WACC, illiquidity discount and FMCA. | Pass | Matches the examples’ glossary pattern. |
| Professional visual polish | Current sample PDF has 29 pages and passed the valuation PDF artifact audit. Preview PNGs exist under `tmp/pdfs/valuation-preview/`, and `scripts/build_valuation_visual_parity_pack.py` generated `output/html/valuation-visual-parity-review.html` with 20 rendered pages and 20 automatic report targets. The pack can now also accept mapped original-report page images through an optional reference manifest. | Partial pass | A final side-by-side visual review against the original reference PDF pages is still recommended when those PDFs are available as durable inputs. |

## Product adaptations from the examples

AccountIQ should not copy the examples one-for-one. The current implementation makes three useful product adaptations:

1. It adds report-letter and basis-of-preparation front matter showing why five private answers are enough.
2. It retains online/public source URLs and describes what each source supports.
3. It uses Python-computed valuation outputs, with the language model limited to narrative around those outputs.

Those adaptations are aligned with the user objective: make the report feel professional like the examples, while reducing customer questionnaire burden.

## Remaining parity recommendations

1. Store the original example PDFs or sanctioned page images in a durable, ignored QA folder, then create a visual comparison pack against the AccountIQ cover, contents, introduction, valuation conclusion, methodology, WACC, DCF, sensitivity, sources, disclaimer and glossary pages.
2. Add optional white-label/adviser branding fields if the desired output should look like a Bayleys/adviser report rather than an AccountIQ-branded self-serve report.
3. When live research is configured, run `scripts/run_live_valuation_smoke.py` and confirm named market/comparable evidence is only included when backed by retained public source URLs.

## Visual review pack

The current visual review pack can be regenerated with:

```bash
python scripts/render_valuation_pdf_preview.py --pdf output/pdf/accountiq-demo-sample-indicative-valuation.pdf --pages auto
python scripts/build_valuation_visual_parity_pack.py
```

When original example-report PDFs are available, create a PDF/page map:

```bash
python scripts/render_reference_pdf_pages.py --write-template
cp tmp/pdfs/reference-examples/reference-pdf-map.template.json tmp/pdfs/reference-examples/reference-pdf-map.json
```

Then place the original PDFs in `tmp/pdfs/reference-examples/`, fill in the
copied map with each PDF path and the original page number that corresponds to
each AccountIQ target, and render the mapped reference pages:

```bash
python scripts/render_reference_pdf_pages.py --spec tmp/pdfs/reference-examples/reference-pdf-map.json
```

This writes the PNGs and `tmp/pdfs/reference-examples/reference-manifest.json`
for the visual parity pack.

If original example-report pages are already available as images, add a manifest
directly instead:

```bash
python scripts/build_valuation_visual_parity_pack.py --write-reference-template
cp tmp/pdfs/reference-examples/reference-manifest.template.json tmp/pdfs/reference-examples/reference-manifest.json
```

Then place original example-report page images in `tmp/pdfs/reference-examples/`
and fill in the copied manifest:

```json
{
  "references": [
    {
      "accountiq_target": "Cover valuation snapshot",
      "title": "Marina Terrace cover",
      "source": "Marina Terrace example",
      "path": "marina-cover.png",
      "notes": "Cover/title and prepared-for party"
    }
  ]
}
```

Then regenerate the pack with:

```bash
python scripts/render_valuation_pdf_preview.py --pdf output/pdf/accountiq-demo-sample-indicative-valuation.pdf --pages auto
python scripts/build_valuation_visual_parity_pack.py --reference-manifest tmp/pdfs/reference-examples/reference-manifest.json
```

Latest generated pack:

- `output/html/valuation-visual-parity-review.html`
- 20 rendered AccountIQ pages included
- 20 automatic report targets checked
- 0 mapped reference images currently supplied
- Reference PDF map template: `tmp/pdfs/reference-examples/reference-pdf-map.template.json`
- Reference manifest template: `tmp/pdfs/reference-examples/reference-manifest.template.json`
- Source manifest: `tmp/pdfs/valuation-preview/accountiq-demo-sample-indicative-valuation-preview-manifest.json`
