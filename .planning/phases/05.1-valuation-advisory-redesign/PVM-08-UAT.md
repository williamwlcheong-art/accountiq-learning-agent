# PVM-08 valuation UAT

## Status

The no-network synthetic service rehearsal passed on 2026-07-22 against snapshot schema `2`, engine `fcff-decimal-v1`, and all six Python-owned valuation tables. It left the paid fixture report in `awaiting_review`, rendered private HTML/PDF, and recorded immutable evidence outside the repository. Live Anthropic UAT has not run and still requires separate explicit approval. A rehearsal is implementation evidence only; it does not authorise live UAT or complete a launch gate.

## Purpose

This procedure is for one paid Valuation Advisory draft through the existing research, calculation, Claude generation and report-rendering boundaries. It uses a synthetic fixture and leaves the report in `awaiting_review`. It must not approve, release, email, refund, or otherwise deliver a report.

The focused automated suite runs the real deterministic generation pipeline with fixed synthetic substitutes at both external AI boundaries and mocks PDF conversion. Running tests never calls Anthropic.

## Safety requirements

Run this only from a trusted development machine after explicit approval for the specific live run. This approval is a procedural checkpoint recorded outside the repository. The runner does not verify the approval record; `--confirm-live-uat` only confirms the operator's intent. No live Anthropic call or web search is allowed without both the approval and confirmation flag. Do not take any Stripe, SMTP, approval, release, or production action.

The runner enforces the following technical conditions before importing the backend application:

- `ACCOUNTIQ_UAT_MODE=true`
- `ACCOUNTIQ_DB_PATH` points to a new, disposable SQLite file outside the repository whose name contains `uat`, `disposable` or `tmp`
- `APP_BASE_URL` is a loopback origin with an explicit port
- `ACCOUNTIQ_E2E_MODE=false`
- `ACCOUNTIQ_REQUIRE_ADMIN_REVIEW=true`
- the fixture is synthetic, unless its use has been expressly authorised
- the fixture email ends in `.invalid`
- Stripe and SMTP variables are absent
- `ANTHROPIC_API_KEY` is required only for an explicitly confirmed live UAT
- the command selects exactly one mode: `--synthetic-rehearsal` or `--confirm-live-uat`

The database path must not exist before the run. This prevents reuse of an earlier database and makes each run auditable. Keep all evidence, the disposable database, HTML, PDF, and review notes outside the repository.

## Valuation preflight

The synthetic fixture and runner now implement and verify all of the following:

- Extend `tests/fixtures/valuation_uat/synthetic_nz_sme.json` with complete confirmed FCFF assumptions, including D&A, capex, operating NWC, forecast horizon, growth, EBITDA margin, tax treatment, and any zero-value rationale.
- Extend `scripts/run_live_valuation_uat.py` to seed and activate exactly one approved synthetic WACC assumption set before creating the snapshot.
- Extend the runner's assertions and immutable evidence to record and verify snapshot schema `2`, engine `fcff-decimal-v1`, Decimal FCFF reconciliation, and Python-owned deterministic valuation tables.
- Keep the UAT evidence-document schema version distinct from the report-input snapshot schema and document both explicitly.

The 2026-07-22 synthetic rehearsal verified the following and recorded the results outside the repository:

- Exactly one active, approved WACC assumption set is selected, with its source references, publisher, as-of date, rationale, approver, and approval time frozen in the snapshot.
- Complete FCFF assumptions are present before checkout or any external call.
- The report input snapshot uses schema `2` and engine `fcff-decimal-v1`.
- Python produces deterministic valuation tables from frozen inputs, and the tables reconcile to the Decimal FCFF calculation.

Do not substitute a missing preflight result with a live Anthropic call, web search, manual database edit, or reviewer approval.

## Run the deterministic checks first

From the repository root:

```bash
venv/bin/python -m pytest tests/test_valuation_uat.py -q
```

These tests substitute fixed outputs only at the external research and report-generation boundaries and mock PDF conversion. They cover unsafe configuration refusals, fixture restrictions, the real snapshot/Decimal/table pipeline, report invariants, import safety, private rendering, and immutable evidence.

## Run the no-network synthetic rehearsal

Prepare a new disposable database and evidence root outside the repository, keep payment and delivery settings absent, and leave `ANTHROPIC_API_KEY` unset or empty. Then run:

```bash
unset STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET
unset SMTP_HOST SMTP_USER SMTP_PASSWORD FROM_EMAIL ANTHROPIC_API_KEY
export ACCOUNTIQ_UAT_MODE=true
export ACCOUNTIQ_E2E_MODE=false
export ACCOUNTIQ_REQUIRE_ADMIN_REVIEW=true
UAT_PRIVATE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/accountiq-valuation-uat-XXXXXX")"
chmod 700 "$UAT_PRIVATE_ROOT"
export ACCOUNTIQ_DB_PATH="$UAT_PRIVATE_ROOT/disposable-valuation-uat.db"
export APP_BASE_URL="http://127.0.0.1:9876"
venv/bin/python scripts/run_live_valuation_uat.py \
  --synthetic-rehearsal \
  --evidence-root "$UAT_PRIVATE_ROOT/evidence"
```

This mode exercises the real snapshot, Decimal FCFF, deterministic table, persistence, review-state, HTML, PDF, and immutable-evidence boundaries. Fixed synthetic research and narrative outputs replace the two external AI calls. The evidence must record `external_ai_calls_performed: false`.

## Prepare an authorised live run

The technical preconditions and synthetic rehearsal are complete. A live run remains blocked until explicit approval for the specific live UAT. After that approval, clear all payment and delivery settings from the shell. Do not replace them with dummy values because the preflight rejects configured values.

```bash
unset STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET
unset SMTP_HOST SMTP_USER SMTP_PASSWORD FROM_EMAIL
export ACCOUNTIQ_UAT_MODE=true
export ACCOUNTIQ_E2E_MODE=false
export ACCOUNTIQ_REQUIRE_ADMIN_REVIEW=true
UAT_PRIVATE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/accountiq-valuation-uat-XXXXXX")"
chmod 700 "$UAT_PRIVATE_ROOT"
export ACCOUNTIQ_DB_PATH="$UAT_PRIVATE_ROOT/disposable-valuation-uat.db"
export APP_BASE_URL="http://127.0.0.1:9876"
export ANTHROPIC_API_KEY="..."
```

Confirm that `ACCOUNTIQ_DB_PATH` is new and is not `data/accountiq_learning.db`. The supplied fixture is:

`tests/fixtures/valuation_uat/synthetic_nz_sme.json`

It contains invented people, business details and financial figures. Do not substitute customer data unless its use has been expressly authorised and the fixture records `"authorised_for_uat": true` with a `.invalid` UAT email.

## Explicit live command

This is the only step that can call Anthropic or perform permitted research. It can incur API cost. Do not run it without explicit confirmation for the live UAT.

```bash
venv/bin/python scripts/run_live_valuation_uat.py \
  --confirm-live-uat \
  --evidence-root "$UAT_PRIVATE_ROOT/evidence"
```

Importing the script does nothing. Without the confirmation flag or any safety setting, it exits before database initialisation or network work.

## Expected result

If an authorised run succeeds:

1. It initialises only the configured disposable database.
2. It seeds the synthetic SME, financial history, management, adjustments, paid fixture purchase and queued report.
3. It verifies and records the frozen WACC and FCFF assumptions, report-input snapshot schema and engine, Decimal reconciliation, and deterministic valuation-table authority.
4. It invokes the existing valuation generator.
5. It requires the final report and review record to remain `awaiting_review`.
6. It rejects missing sections, empty narratives, generation placeholders, missing required tables and an incomplete disclaimer.
7. It renders a private HTML file and PDF without calling approval or email code.
8. It creates a new timestamped directory beneath the private `--evidence-root`, outside the repository.

The evidence JSON is created once with read-only permissions. It contains hashes, section keys, deterministic check results, and the configured model and research tool type. Current production boundaries do not expose returned model metadata, so the evidence must not claim which model Anthropic returned. Generated report prose and likely secrets are excluded or hashed.

HTML and PDF contain the private draft and use owner-only file permissions. They are review artefacts, not customer deliverables.

## Qualified reviewer checklist and cleanup

A designated qualified reviewer reviews the private HTML or PDF for:

- WACC provenance, approval, source material, as-of date, and frozen snapshot values
- Decimal FCFF arithmetic and reconciliation from assumptions through valuation outputs
- the enterprise-value-to-equity bridge, including debt, unrestricted cash, approved surplus assets, and equity-level DLOM treatment
- Python-owned deterministic tables and agreement with the frozen inputs and Decimal FCFF outputs
- professional structure, first-draft usefulness, indicative-only, financial-advice, FMCA and reliance wording
- rendering quality, tables, and page disclaimer

Record review notes outside the immutable machine evidence. Do not use an admin approval endpoint, change the report to `done`, send a report-ready email, create a Stripe session, process a webhook, refund, cancel, or release any report.

After evidence and review notes are retained in the agreed private location, remove the disposable database, its `-wal` and `-shm` files, and private HTML/PDF copies that are no longer required. Never copy the UAT database into the default data path.
