# PVM-08 valuation UAT

## Purpose

This procedure runs one paid Valuation Advisory draft through the existing research, calculation, Claude generation and report-rendering boundaries. It uses synthetic data and leaves the report in `awaiting_review`. It does not approve or release the report.

The automated test suite mocks generation and PDF conversion. Running tests never calls Anthropic.

## Safety requirements

Run this only from a trusted development machine. The runner stops before importing the application unless every condition is met:

- `ACCOUNTIQ_UAT_MODE=true`
- `ACCOUNTIQ_DB_PATH` points to a new, disposable SQLite file outside the repository whose name contains `uat`, `disposable` or `tmp`
- `APP_BASE_URL` is a loopback origin with an explicit port
- `ACCOUNTIQ_E2E_MODE=false`
- the fixture is synthetic or expressly authorised
- the fixture email ends in `.invalid`
- Stripe and SMTP variables are absent
- `ANTHROPIC_API_KEY` is present
- the command includes `--confirm-live-uat`

The database path must not exist before the run. This prevents reuse of an earlier database and makes each run auditable.

## Run the mocked checks first

From the repository root:

```bash
venv/bin/python -m pytest tests/test_valuation_uat.py -q
```

These tests mock the existing generation and PDF boundaries. They cover unsafe configuration refusals, fixture restrictions, report invariants, import safety, private rendering and immutable evidence.

## Prepare an authorised live run

Clear all payment and delivery settings from the shell. Do not replace them with dummy values because the preflight rejects configured values.

```bash
unset STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET
unset SMTP_HOST SMTP_USER SMTP_PASSWORD FROM_EMAIL
export ACCOUNTIQ_UAT_MODE=true
export ACCOUNTIQ_E2E_MODE=false
UAT_PRIVATE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/accountiq-valuation-uat-XXXXXX")"
chmod 700 "$UAT_PRIVATE_ROOT"
export ACCOUNTIQ_DB_PATH="$UAT_PRIVATE_ROOT/disposable-valuation-uat.db"
export APP_BASE_URL="http://127.0.0.1:9876"
export ANTHROPIC_API_KEY="..."
# Optional. If omitted, the application's current default is used.
# export CLAUDE_MODEL="claude-sonnet-4-6"
```

Confirm that `ACCOUNTIQ_DB_PATH` is new and is not `data/accountiq_learning.db`. The supplied fixture is:

`tests/fixtures/valuation_uat/synthetic_nz_sme.json`

It contains invented people, business details and financial figures. Do not substitute customer data unless its use has been expressly authorised and the fixture records `"authorised_for_uat": true` with a `.invalid` UAT email.

## Explicit live command

This is the only step that can call Anthropic. It can make a research call and a report-generation call, which incur API cost.

```bash
venv/bin/python scripts/run_live_valuation_uat.py \
  --confirm-live-uat \
  --evidence-root "$UAT_PRIVATE_ROOT/evidence"
```

Importing the script does nothing. Without the confirmation flag or any safety setting, it exits before database initialisation or network work.

## Expected result

A successful run:

1. Initialises only the configured disposable database.
2. Seeds the synthetic SME, financial history, management, adjustments, paid fixture purchase and queued report.
3. Invokes the existing valuation generator.
4. Requires the final state and review record to remain `awaiting_review`.
5. Rejects missing sections, empty narratives, generation placeholders, missing required tables and an incomplete disclaimer.
6. Renders a private HTML file and PDF without calling approval or email code.
7. Creates a new timestamped directory beneath the required private `--evidence-root`, which must be outside the repository.

The evidence JSON is created once with read-only permissions. It contains hashes, section keys, deterministic check results, and the configured model and research tool type. Current production boundaries do not expose returned model metadata, so the evidence does not claim which model Anthropic returned. Generated report prose and likely secrets are excluded or hashed.

HTML and PDF contain the private draft and use owner-only file permissions. They are review artefacts, not customer deliverables.

## Review and cleanup

William reviews the private HTML or PDF for:

- financial assumptions and arithmetic presentation
- WACC, DCF, comparable multiple and illiquidity wording
- risk-score interpretation
- professional structure and first-draft usefulness
- indicative-only, financial-advice, FMCA and reliance wording
- tables, page disclaimer and rendering quality

Record review notes outside the immutable machine evidence. Do not use an admin approval endpoint, change the report to `done`, send a report-ready email, create a Stripe session or process a webhook.

After evidence and review notes are retained in the agreed private location, remove the disposable database, its `-wal` and `-shm` files, and private HTML/PDF copies that are no longer required. Never copy the UAT database into the default data path.
