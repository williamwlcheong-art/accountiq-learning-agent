# AccountIQ Learning Agent

AccountIQ is a financial intelligence prototype for SME business owners. Users upload financial statements, complete business-profile intake, and generate first-draft professional reports such as valuation advisory, bank credit papers, financial forecasts, capital raising documents, and information memorandums.

## Architecture

- `backend/` - FastAPI backend, SQLite persistence, uploads, ingestion, valuation, report generation, and email.
- `web/` - Next.js App Router frontend for login, wizard, admin workflows, and E2E tests.
- `frontend/` - legacy vanilla SPA kept as an opt-in rollback/reference fallback.
- `.planning/` - project, roadmap, codebase, and phase planning docs.

FastAPI remains the backend of record. The Next.js frontend calls `/api/backend/*`, which is proxied at runtime to `FASTAPI_ORIGIN`.

## Current Development Status

As of 2026-07-02, the Next.js refactor has been merged into `main`. The primary app UI is `web/`; `frontend/` is kept only as a legacy rollback/reference surface.

The active commercial workstream is the valuation-first report experience: a user-friendly five-answer valuation intake, optional public-source/private-context hints, researched valuation narrative, browser report viewer, and print-ready PDF artifact. The output/input specification lives at `docs/valuation-report-input-spec.md`; the broader paid MVP plan lives at `docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md`.

Payment, admin review-before-release, purchase history, production legal/trust pages, and the public offer surface remain launch work. Keep `main` deployable and land feature work through small PRs rather than one large long-lived branch.

## Local Development

Create `.env` from `.env.example`, then start the two runtimes.

Backend:

```bash
source venv/bin/activate
cd backend
uvicorn main:app --reload --port 8765
```

In a linked git worktree that does not have its own `venv/`, use the parent checkout virtualenv, for example `source ../../venv/bin/activate`.

For local valuation-flow testing without an Anthropic key or login, use explicit
demo mode:

```bash
scripts/start-demo-backend.sh
```

This starts FastAPI with `ACCOUNTIQ_DEMO_MODE=true` and
`ACCOUNTIQ_AUTH_DISABLED=true` by default. Demo mode is labelled in the wizard,
browser report, PDF cover/pages, and sample filenames so simulated research or
valuation figures are not confused with client work. The auth bypass creates a
local `demo@accountiq.local` user so you can open `http://localhost:3000/wizard`
directly without registering.

To test demo mode while keeping login enabled, run:

```bash
ACCOUNTIQ_AUTH_DISABLED=false scripts/start-demo-backend.sh
```

Frontend:

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:3000`.

The legacy UI is available at `http://localhost:8765/app` only when `ACCOUNTIQ_SERVE_LEGACY_FRONTEND=true`.

## Valuation Report Artifacts

Generate deterministic sample artifacts without a live API key:

```bash
source venv/bin/activate
python scripts/generate_sample_valuation_html.py
python scripts/generate_sample_valuation_pdf.py
```

Both generators are quality-gated by default. The HTML generator audits the
structured valuation-report content before rendering and audits the rendered
browser report after writing. The PDF generator audits the same structured
content before rendering and audits the rendered PDF after writing. A failed
audit stops the generated artifact from being treated as valid sample output.

The default outputs are:

- `output/html/accountiq-demo-sample-indicative-valuation.html`
- `output/pdf/accountiq-demo-sample-indicative-valuation.pdf`

Audit existing artifacts explicitly when reviewing a saved report pack, a live
smoke output, or an artifact generated outside the default sample commands:

```bash
python scripts/audit_valuation_report.py --html output/html/accountiq-demo-sample-indicative-valuation.html --demo-mode
python scripts/audit_valuation_report.py --pdf output/pdf/accountiq-demo-sample-indicative-valuation.pdf --demo-mode
```

Render key PDF pages and build the visual parity review pack:

```bash
python scripts/render_valuation_pdf_preview.py --pdf output/pdf/accountiq-demo-sample-indicative-valuation.pdf --pages auto
python scripts/render_reference_pdf_pages.py --write-template
python scripts/build_valuation_visual_parity_pack.py --write-reference-template
python scripts/build_valuation_visual_parity_pack.py
```

The visual review pack is written to `output/html/valuation-visual-parity-review.html`.
It links rendered AccountIQ pages to the example-report parity checklist. It does
not replace a final side-by-side review against the original example PDFs. When
original PDFs are available, copy
`tmp/pdfs/reference-examples/reference-pdf-map.template.json` to
`reference-pdf-map.json`, fill in the PDF paths and reference page numbers, then run:

```bash
python scripts/render_reference_pdf_pages.py --spec tmp/pdfs/reference-examples/reference-pdf-map.json
python scripts/build_valuation_visual_parity_pack.py --reference-manifest tmp/pdfs/reference-examples/reference-manifest.json
```

If page images are already prepared, you can instead copy
`tmp/pdfs/reference-examples/reference-manifest.template.json` to
`reference-manifest.json`, fill in the image paths, and pass the same
`--reference-manifest` option.

For provider-backed smoke testing, configure a real `ANTHROPIC_API_KEY`, keep `ACCOUNTIQ_DEMO_MODE=false`, then run:

```bash
python scripts/run_live_valuation_smoke.py
```

## Tests

Backend:

```bash
python -m pytest tests -q
```

Focused valuation/report checks:

```bash
python -m pytest tests/test_report_rendering.py tests/test_report_quality.py tests/test_pdf_delivery.py tests/test_report_viewer.py tests/test_sample_html_generator.py tests/test_sample_pdf_generator.py -q
python -m pytest tests/test_report_prompts.py tests/test_report_generation_validation.py -q
python -m pytest tests/test_local_demo_config.py tests/test_admin_gate.py tests/test_wizard_endpoints.py -q
```

Frontend:

```bash
cd web
npm run typecheck
npm run lint
npm run build
npm run test:e2e
npm run test:e2e:prod
```

Playwright uses deterministic E2E mode through `scripts/start-e2e-backend.sh` and a disposable SQLite database at `data/accountiq_e2e.db`.

## Agent Notes

Coding-agent guidance lives in `AGENTS.md`. Next.js-specific warnings for the `web/` subtree live in `web/AGENTS.md`.
