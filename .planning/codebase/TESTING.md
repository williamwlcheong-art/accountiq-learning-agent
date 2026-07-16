---
last_mapped: 2026-07-05
---

# Testing

## Current State

The project has two active automated test layers:

- **Backend:** `pytest` tests in `tests/` cover auth, admin gates, data isolation, extraction, upload, business profile, valuation, report prompts, research loop behavior, deterministic E2E backend mode, local demo mode, valuation report validation, PDF rendering/delivery, and sample artifact generation.
- **Browser E2E:** Playwright tests in `web/e2e/` cover auth redirects, registration/login/logout, regular-user valuation wizard upload/report generation/viewing, admin company/upload/document/financial workflows, admin route protection, report viewer escaping, and mobile overflow smoke checks.

The Next.js app also has static verification:

- `npm run typecheck`
- `npm run lint`
- `npm run build`

## Backend Test Commands

Run from the repo root:

```bash
source venv/bin/activate
python -m pytest tests/ -q
```

Focused examples:

```bash
python -m pytest tests/test_auth.py -q
python -m pytest tests/test_admin_gate.py -q
python -m pytest tests/test_e2e_mode.py -q
python -m pytest tests/test_report_rendering.py tests/test_report_quality.py tests/test_pdf_delivery.py tests/test_report_viewer.py tests/test_sample_html_generator.py tests/test_sample_pdf_generator.py -q
python -m pytest tests/test_report_prompts.py tests/test_report_generation_validation.py -q
python -m pytest tests/test_local_demo_config.py tests/test_admin_gate.py tests/test_wizard_endpoints.py -q
```

## Frontend Static Checks

Run from `web/`:

```bash
npm run typecheck
npm run lint
npm run build
```

## Browser E2E

Run from `web/`:

```bash
npm run test:e2e
```

Playwright starts two web servers:

1. `../scripts/start-e2e-backend.sh`
2. `npm run dev`

The backend launcher:

- Deletes `data/accountiq_e2e.db`, `-wal`, and `-shm`
- Sets `ACCOUNTIQ_DB_PATH=data/accountiq_e2e.db`
- Sets `ACCOUNTIQ_E2E_MODE=true`
- Sets `OWNER_EMAIL=owner-e2e@example.com`
- Starts FastAPI on `127.0.0.1:8765`

This keeps E2E deterministic and independent from local development data, Anthropic, OCR, SMTP, and long-running background work.

## Valuation Artifact QA

Generate deterministic sample artifacts without a live Anthropic key:

```bash
source venv/bin/activate
python scripts/generate_sample_valuation_html.py
python scripts/generate_sample_valuation_pdf.py
```

The sample generators are part of the report QA gate, not just convenience
scripts. By default, they audit the structured valuation-report content before
rendering; the HTML generator then audits the rendered browser report, and the
PDF generator audits the rendered PDF after writing. If any required section,
source trail, demo label, DCF schedule, valuation snapshot, disclaimer, or safe
URL requirement fails, generation fails.

Audit existing browser/PDF artifacts explicitly when reviewing saved outputs,
live smoke results, or files produced outside the default generators:

```bash
python scripts/audit_valuation_report.py --html output/html/accountiq-demo-sample-indicative-valuation.html --demo-mode
python scripts/audit_valuation_report.py --pdf output/pdf/accountiq-demo-sample-indicative-valuation.pdf --demo-mode
```

For visual QA, render the key PDF pages and rebuild the parity review pack:

```bash
python scripts/render_valuation_pdf_preview.py --pdf output/pdf/accountiq-demo-sample-indicative-valuation.pdf --pages auto
python scripts/render_reference_pdf_pages.py --write-template
python scripts/build_valuation_visual_parity_pack.py --write-reference-template
python scripts/build_valuation_visual_parity_pack.py
```

Open `output/html/valuation-visual-parity-review.html` to inspect the current
rendered pages against the example-report parity criteria. This proves the
AccountIQ rendered-page review pack is current; it does not prove final
side-by-side visual parity unless the original example PDFs or page images are
available as durable QA inputs. If original PDFs are available, copy and fill
`tmp/pdfs/reference-examples/reference-pdf-map.template.json`, run
`python scripts/render_reference_pdf_pages.py --spec tmp/pdfs/reference-examples/reference-pdf-map.json`,
then rebuild with `--reference-manifest tmp/pdfs/reference-examples/reference-manifest.json`.
If page images are already prepared, map them directly through
`tmp/pdfs/reference-examples/reference-manifest.json`.

For live-provider smoke testing, configure a real `ANTHROPIC_API_KEY`, keep `ACCOUNTIQ_DEMO_MODE=false`, then run:

```bash
python scripts/run_live_valuation_smoke.py
```

## Production E2E Smoke

Run from `web/`:

```bash
npm run test:e2e:prod
```

This builds Next.js first, then runs Playwright with `PLAYWRIGHT_FRONTEND_COMMAND="npm run start"` so the browser suite exercises the standalone production server rather than the dev server.

## E2E Coverage Map

| Spec | Coverage |
|------|----------|
| `auth.spec.ts` | Login redirect, registration, logout, login, short-password error |
| `wizard.spec.ts` | Regular upload, valuation-first report picker, extraction gate, five-answer intake, optional detail preservation, report generation, viewer link |
| `admin.spec.ts` | Owner admin registration, company create, upload, documents, financials |
| `security.spec.ts` | Regular user redirected away from admin |
| `report-viewer.spec.ts` | Generated report escapes script-like payloads |
| `responsive.spec.ts` | Wizard has no horizontal overflow on desktop/mobile profiles |

## Expectations For Future Changes

- Backend route/data changes need focused pytest coverage.
- Frontend workflow changes need either a Playwright update or a clear reason the existing E2E path covers the behavior.
- Any change touching uploads, report generation, auth cookies, route guards, or report viewing should run the full command set before merging:

```bash
source venv/bin/activate && python -m pytest tests/ -q
cd web && npm run typecheck && npm run lint && npm run build
cd web && npm run test:e2e
cd web && npm run test:e2e:prod
```
