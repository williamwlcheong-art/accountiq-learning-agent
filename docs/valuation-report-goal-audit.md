# AccountIQ valuation-report goal audit

Date: 2026-07-07

## User objective

Make the app output look and feel like the provided indicative valuation report examples, while asking the user the minimum practical number of valuation questions. The flow should feel user-friendly, use uploaded financials and online/public information where possible, and still capture enough private information to produce a professional valuation report.

This audit uses the current worktree as authoritative. It does not mark the goal complete; it identifies what is currently proven, what is partially proven, and what still needs stronger evidence before completion.

## Current completion verdict

Status: substantially implemented, but not yet completion-proven.

The current worktree strongly proves the valuation-first intake, five-answer private-fact flow, separate earnings review, public-source trail, Python-computed valuation tables, browser/PDF report pack, formal report-letter front matter, demo-mode safeguards, artifact quality gates, structural parity against the available example-report extracts, and a generated visual review pack for the current AccountIQ sample. The remaining evidence gaps are narrower but important:

- `docs/valuation-example-parity-checklist.md` now captures structural parity against the available Marina Terrace and Propellerhead extracts, and `output/html/valuation-visual-parity-review.html` links the current rendered AccountIQ pages to those criteria. The parity workflow now supports rendering selected pages from original example PDFs through `scripts/render_reference_pdf_pages.py`, then feeding the generated `reference-manifest.json` into the pack builder for true side-by-side review. No original example PDFs are currently stored as durable inputs, so no mapped reference images are currently supplied.
- A live provider-backed research/report smoke test has a harness, but has not been run in this environment because there is no real OpenAI API key configured.
- The full current frontend Playwright suite has now been rerun on alternate port 3001 and passed.
- Commercial launch pieces such as payment, admin review-before-release, purchase history, and public offer pages remain outside the proven report-output slice.

## Requirement-by-requirement audit

| Requirement | Current evidence | Status | Remaining caveat / next check |
|---|---|---:|---|
| Output should resemble the provided professional indicative valuation examples | `docs/valuation-report-input-spec.md` translates the examples into a formal target structure referencing Propellerhead and Marina Terrace. `docs/valuation-example-parity-checklist.md` compares the current sample to the available reference extracts. `output/html/valuation-visual-parity-review.html` shows the current rendered AccountIQ pages against the parity criteria and can include original-report images through `--reference-manifest`. `scripts/render_reference_pdf_pages.py` can now render supplied original PDFs into that manifest workflow. `backend/report_prompts.py` asks the live report generator to match that standard. Generated sample artifacts exist at `output/html/accountiq-demo-sample-indicative-valuation.html` and `output/pdf/accountiq-demo-sample-indicative-valuation.pdf`. | Partially proven | Structural parity and AccountIQ visual review are captured; final visual side-by-side awaits supplied original PDFs/page images. |
| User should not face a long expert questionnaire | `web/components/wizard/intake-form.tsx` shows “Only five answers are required”, a 5-answer checklist, “Not sure is an acceptable answer”, collapsed optional source/private fields, and collapsed advanced valuation overrides. `web/e2e/wizard.spec.ts` verifies this flow and asserts legacy risk/technical questions are absent. | Proven | Keep protecting this in E2E when adding paid/admin surfaces. |
| Ask enough information to support the valuation | Required intake is limited to purpose, owner/key-person dependency, customer concentration, revenue predictability, and revenue outlook in `docs/valuation-report-input-spec.md`; the UI maps each answer to its report use, and the report basis page includes a management input trail. | Proven | The live-model prompt still depends on the report validators to prevent drift. |
| Research first, ask second | The spec requires uploaded extraction and public research before asking only private facts. The intake UI says AccountIQ researches the business, sector, comparable transactions, discount-rate inputs, and NZ inflation. | Proven for UX and deterministic flow | Live online research is not proven without a real OpenAI key and live smoke run. |
| Business information can be sourced from online avenues | Optional public links are visible as source hints, are treated as clues, and are retained when used. `tests/test_wizard_endpoints.py` covers public URL normalisation and rejection of invalid/private URLs. The report audits require public HTTP(S) URLs, safe clickable links, non-generic support descriptions, and no non-public source URLs. | Proven for validation and artifacts | Live retrieval quality still needs provider-backed smoke once a key exists. |
| Wizard waits for extraction before valuation questions | `docs/valuation-report-input-spec.md` requires the “Reading your financial statements” state; `tests/test_wizard_endpoints.py` covers extraction/report-generation readiness, selected-upload readiness, and live core-financial-row checks. The full current frontend E2E suite also passed on alternate port 3001. | Proven | None currently for deterministic/demo flow. |
| Moving backward preserves required and optional answers | `web/e2e/wizard.spec.ts` verifies moving back preserves the five answers, optional public links, private context, normalisation rows, and optional expert overrides. | Proven | None currently. |
| Earnings adjustment review is separate and reassuring | `web/components/wizard/intake-form.tsx` has a separate earnings review stage with “This is a review, not a finance test”, “No extra required answers”, adjustment examples, non-zero amount/rationale validation, and “No more required answers after this check”. | Proven | None currently. |
| Keep technical valuation assumptions out of normal flow | The UI does not ask for WACC, terminal growth, or forecast horizon. Advanced overrides are collapsed and limited to replacement manager cost, debt, surplus assets, and supported growth. E2E asserts terminal-growth inputs are absent and advanced fields are hidden by default. | Proven | None currently. |
| Derive conservative growth when revenue outlook is “Not sure” | `backend/valuation.py` implements the not-sure revenue-growth route and tests in `tests/test_valuation.py` cover conservative-history, sparse-history, fallback, and override behaviour. | Proven | None currently. |
| Python computes DCF, WACC, valuation bridge, sensitivity, and risk tables | `backend/valuation.py` computes WACC scenarios, DCF, sensitivity matrix, assumptions/source trail, and specific risk factors. `backend/main.py` wires these computed outputs into report generation. `tests/test_report_generation_validation.py` rejects reports that drop or drift from core Python-computed rows. | Proven | Continue treating the model as narrative-only around computed values. |
| Report includes the requested professional structure | `backend/report_quality.py` requires cover, contents, report-letter/basis-of-preparation front matter, numbered sections 01-21, valuation snapshot, at-a-glance panels, WACC, DCF, multiples cross-check, sensitivity, specific risks, sources, disclaimer, principles, and glossary. Current deterministic PDF audit passed with 29 pages. | Proven for deterministic artifact | Formal visual parity review against the original examples should still be captured. |
| Browser report and PDF are first-class review/delivery surfaces | `backend/main.py` exposes the browser report review route and PDF download. `tests/test_report_viewer.py` and `tests/test_pdf_delivery.py` cover browser/PDF delivery, audit failures, report framing, download action, and A4 print CSS. | Proven | Production paid delivery is not complete. |
| Source hierarchy is visible | The report quality audit requires uploaded financials, management-confirmed private inputs, public research, and AccountIQ calculations to be distinguished. The generated sample basis page and assumptions table show management input trail and assumption/source trail. | Proven | None currently. |
| Management-input trail appears before report body | Browser/PDF tests and `backend/report_quality.py` require report letter, scope exclusions, management input trail, evidence/model basis, derived technical assumptions, and questions intentionally not asked before section 01. | Proven | None currently. |
| No invented facts, figures, URLs, or unfinished-questionnaire report language | `backend/report_quality.py` rejects placeholder text, draft language, raw intake keys, unsafe markup, unfinished follow-up language, non-public URLs, thin source descriptions, demo leakage into live reports, and live reports missing reliance wording. `tests/test_report_generation_validation.py` rejects unsupported figures and claims. | Proven for deterministic/report-validation paths | Live provider smoke still needed to prove the real model obeys these gates end-to-end. |
| Demo/no-key usage is safe and explicit | `.env.example`, `scripts/start-demo-backend.sh`, `backend/main.py`, `README.md`, and tests under `tests/test_local_demo_config.py`, `tests/test_admin_gate.py`, and `tests/test_wizard_endpoints.py` require explicit demo mode and reject silent simulated reports in live mode without a key. | Proven | None currently for local/no-key operation. |
| Generated artifacts pass current quality audits | Fresh commands run on 2026-07-07: `venv/bin/python scripts/generate_sample_valuation_html.py` and `venv/bin/python scripts/generate_sample_valuation_pdf.py` regenerated the deterministic artifacts and passed their built-in structured/rendered audits. The PDF audit passed with 29 pages, 6 URLs, 0 non-public URLs, and 29/29 demo-labelled pages. The sample generators audit structured report content before rendering and rendered HTML/PDF after writing, so a broken sample build fails before being accepted as valid output. | Proven | These are deterministic demo artifacts, not live-provider artifacts. |
| Browser flow still works end-to-end | Focused wizard command passed with 4 tests, and the full frontend E2E command passed: `PLAYWRIGHT_BASE_URL=http://localhost:3001 PLAYWRIGHT_FRONTEND_URL=http://localhost:3001 PLAYWRIGHT_FRONTEND_COMMAND='npx next dev --port 3001' npm run test:e2e` -> 12 passed. | Proven for current frontend E2E suite | Production/live-provider smoke remains separate. |
| Visual parity review pack is reproducible | `scripts/render_valuation_pdf_preview.py` renders the AccountIQ PDF pages; `scripts/render_reference_pdf_pages.py` can render selected pages from supplied original example PDFs and write `reference-manifest.json`; `scripts/build_valuation_visual_parity_pack.py` builds `output/html/valuation-visual-parity-review.html` from the AccountIQ preview manifest and optional reference manifest. Focused verification passed: `venv/bin/python -m pytest tests/test_pdf_preview_renderer.py -q --tb=short` -> 11 passed. | Proven for current AccountIQ rendered-page review and future reference-PDF mapping | Still needs original reference PDFs/images for true side-by-side visual parity. |

## Fresh command evidence

```text
venv/bin/python -m pytest tests/test_report_rendering.py tests/test_report_viewer.py tests/test_report_quality.py tests/test_sample_html_generator.py tests/test_sample_pdf_generator.py -q --tb=short
219 passed
```

```text
venv/bin/python scripts/audit_valuation_report.py --html output/html/accountiq-demo-sample-indicative-valuation.html --demo-mode
passed: true
artifact: valuation_report_html
issues: []
metadata: url_count 4; non_public_source_url_count 0; demo_mode true; text_length 41217
```

```text
venv/bin/python scripts/audit_valuation_report.py --pdf output/pdf/accountiq-demo-sample-indicative-valuation.pdf --demo-mode
passed: true
artifact: valuation_report_pdf
issues: []
metadata: page_count 29; url_count 6; non_public_source_url_count 0; demo_mode true; demo_labelled_page_count 29
```

```text
venv/bin/python scripts/render_valuation_pdf_preview.py --pdf output/pdf/accountiq-demo-sample-indicative-valuation.pdf --pages auto
selection_mode: auto
rendered_pages: 20
matched_targets: 20
```

```text
venv/bin/python scripts/render_reference_pdf_pages.py --write-template
template_path: tmp/pdfs/reference-examples/reference-pdf-map.template.json
reference_page_rows: 20
```

```text
venv/bin/python scripts/build_valuation_visual_parity_pack.py --write-reference-template
template_path: tmp/pdfs/reference-examples/reference-manifest.template.json
reference_rows: 20
```

```text
venv/bin/python scripts/build_valuation_visual_parity_pack.py
output_path: output/html/valuation-visual-parity-review.html
page_count: 20
target_count: 20
reference_count: 0
```

```text
venv/bin/python -m pytest tests/test_pdf_preview_renderer.py -q --tb=short
11 passed
```

```text
cd web
PLAYWRIGHT_BASE_URL=http://localhost:3001 PLAYWRIGHT_FRONTEND_URL=http://localhost:3001 PLAYWRIGHT_FRONTEND_COMMAND='npx next dev --port 3001' npm run test:e2e
12 passed
```

## Recommended next work

1. Store or reattach the original example PDFs as durable QA inputs, copy `tmp/pdfs/reference-examples/reference-pdf-map.template.json` to `reference-pdf-map.json`, fill in the PDF paths/page numbers, run `python scripts/render_reference_pdf_pages.py --spec tmp/pdfs/reference-examples/reference-pdf-map.json`, then regenerate `output/html/valuation-visual-parity-review.html` with `--reference-manifest tmp/pdfs/reference-examples/reference-manifest.json` for a true side-by-side review.
2. Once a real OpenAI API key is available, run `python scripts/run_live_valuation_smoke.py` with `ACCOUNTIQ_DEMO_MODE=false` and audit the resulting JSON/HTML/PDF.
3. Keep commercial launch work separate from this report-output goal: payment, admin review, purchase history and public offer surfaces remain launch gaps, not proof that the report-output experience is complete.
