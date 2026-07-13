# Paid Valuation MVP Implementation Plan

**Execution status:** In progress through small PRs. PVM-01 through PVM-03 are implemented on `main`; `.planning/BACKLOG.md` is authoritative for remaining slices and current status.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn AccountIQ from a general report-generation demo into a launch-ready paid valuation product: upload financials, complete valuation intake, pay, generate a reviewed indicative SME valuation, view it, and download a professional PDF.

**Architecture:** Keep FastAPI as the backend of record for auth, uploads, report jobs, payment webhooks, PDF rendering, and SQLite writes. Keep Next.js as the primary frontend for the wizard, account page, public valuation offer, and admin review queue. The first paid wedge is `valuation_advisory`; other report families remain present in code but are not sold self-serve until valuation quality and payment delivery are proven.

**Tech Stack:** FastAPI, SQLite/aiosqlite, Next.js App Router, React, TypeScript, Stripe Checkout/webhooks, WeasyPrint, Playwright, pytest.

---

## File Structure

- Modify `web/components/wizard/report-type-picker.tsx`: make Valuation Advisory the only selectable self-serve report and mark other report types as "Advisor pilot".
- Modify `web/components/wizard/wizard.tsx`: call a checkout endpoint for valuation instead of directly queueing generation.
- Modify `web/components/wizard/report-status-card.tsx`: show payment, review, and PDF download states.
- Modify `web/app/account/page.tsx`: replace the placeholder purchase-history copy with real report purchase history.
- Create `web/app/valuation/page.tsx`: public offer page for the valuation wedge.
- Modify `backend/db.py`: add `purchases`, report review fields, and PDF export fields.
- Modify `backend/main.py`: add checkout, webhook, account purchase history, admin review, and PDF endpoints.
- Create `backend/payments.py`: Stripe session/webhook helpers plus deterministic E2E payment shim.
- Create `backend/report_rendering.py`: HTML/PDF rendering helpers used by viewer and PDF endpoint.
- Modify `backend/report_email.py`: send email only after review approval for paid valuation reports.
- Modify `backend/requirements.txt`: add pinned Stripe and WeasyPrint dependencies.
- Modify `.env.example`: document Stripe, price, public URL, and review-gate settings.
- Add/modify tests in `tests/test_payments.py`, `tests/test_pdf_delivery.py`, `tests/test_admin_review.py`, `web/e2e/wizard.spec.ts`, `web/e2e/admin.spec.ts`, and `web/e2e/account.spec.ts`.

---

## Task 1: Narrow The Self-Serve Offer To Valuation

**Files:**
- Modify: `web/components/wizard/report-type-picker.tsx`
- Modify: `web/e2e/wizard.spec.ts`

- [ ] **Step 1: Update report-type metadata**

Replace `WIZARD_REPORT_TYPES` with metadata that keeps all report types visible but only enables `valuation_advisory`:

```ts
export const WIZARD_REPORT_TYPES = [
  {
    key: "valuation_advisory",
    name: "Valuation Advisory",
    desc: "Indicative SME valuation using researched WACC inputs, DCF scenarios, market multiples, and normalised EBITDA.",
    selfServe: true,
    badge: "Available now",
  },
  {
    key: "bank_credit_paper",
    name: "Bank Credit Paper",
    desc: "Structured credit submission covering business overview, financial performance, and lending rationale.",
    selfServe: false,
    badge: "Advisor pilot",
  },
  {
    key: "financial_forecast",
    name: "Financial Forecast",
    desc: "Three-year forward projections with base, bull, and bear scenarios derived from historical performance.",
    selfServe: false,
    badge: "Advisor pilot",
  },
  {
    key: "capital_raising",
    name: "Capital Raising Document",
    desc: "Investor-ready summary covering business model, financials, growth strategy, and use of funds.",
    selfServe: false,
    badge: "Advisor pilot",
  },
  {
    key: "information_memorandum",
    name: "Information Memorandum",
    desc: "Full sale document covering business overview, operations, financials, and growth opportunities.",
    selfServe: false,
    badge: "Advisor pilot",
  },
] as const;
```

- [ ] **Step 2: Disable non-valuation buttons**

In `ReportTypePicker`, render disabled buttons for `selfServe: false`, with an explanatory badge:

```tsx
<button
  key={reportType.key}
  type="button"
  disabled={!reportType.selfServe}
  className={[
    selected === reportType.key ? "report-type-card selected" : "report-type-card",
    reportType.selfServe ? "" : "disabled",
  ].filter(Boolean).join(" ")}
  onClick={() => {
    if (reportType.selfServe) onSelect(reportType.key);
  }}
>
  <span>{reportType.name}</span>
  <small>{reportType.desc}</small>
  <em>{reportType.badge}</em>
</button>
```

- [ ] **Step 3: Update Playwright coverage**

In `web/e2e/wizard.spec.ts`, change the happy path to select `Valuation Advisory`, and add:

```ts
await expect(page.getByRole("button", { name: /bank credit paper/i })).toBeDisabled();
await expect(page.getByText(/advisor pilot/i).first()).toBeVisible();
```

- [ ] **Step 4: Verify**

Run:

```bash
cd web
pnpm typecheck
pnpm lint
pnpm test:e2e -- e2e/wizard.spec.ts
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add web/components/wizard/report-type-picker.tsx web/e2e/wizard.spec.ts
git commit -m "feat(valuation): focus self-serve wizard on valuation"
```

---

## Task 2: Add Payment Job Model And Stripe Helpers

**Files:**
- Modify: `backend/db.py`
- Create: `backend/payments.py`
- Modify: `backend/requirements.txt`
- Modify: `.env.example`
- Add: `tests/test_payments.py`

- [ ] **Step 1: Write database migration tests**

Create `tests/test_payments.py`:

```python
import aiosqlite
import pytest

from db import DB_PATH, init_db


@pytest.mark.asyncio
async def test_payment_tables_exist(fresh_all_db):
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("PRAGMA table_info(purchases)") as cur:
            columns = {row[1] for row in await cur.fetchall()}
    assert {
        "id",
        "report_id",
        "user_id",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
        "amount_cents",
        "currency",
        "status",
        "paid_at",
    }.issubset(columns)
```

- [ ] **Step 2: Add migration**

In `backend/db.py`, inside `_migrate_db`, add:

```python
await db.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        stripe_checkout_session_id TEXT UNIQUE,
        stripe_payment_intent_id TEXT,
        amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL DEFAULT 'nzd',
        status TEXT NOT NULL DEFAULT 'pending',
        paid_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")
```

Also add indexes:

```python
await db.execute("CREATE INDEX IF NOT EXISTS idx_purchases_user ON purchases(user_id)")
await db.execute("CREATE INDEX IF NOT EXISTS idx_purchases_report ON purchases(report_id)")
await db.execute("CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases(status)")
```

- [ ] **Step 3: Add Stripe dependency**

In `backend/requirements.txt`, add:

```text
stripe==12.5.0
```

- [ ] **Step 4: Create payment helper**

Create `backend/payments.py`:

```python
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckoutConfig:
    price_cents: int
    currency: str
    success_url: str
    cancel_url: str


def checkout_config() -> CheckoutConfig:
    return CheckoutConfig(
        price_cents=int(os.getenv("ACCOUNTIQ_VALUATION_PRICE_CENTS", "49500")),
        currency=os.getenv("ACCOUNTIQ_CURRENCY", "nzd").lower(),
        success_url=os.getenv("ACCOUNTIQ_PAYMENT_SUCCESS_URL", "http://localhost:3000/wizard?payment=success"),
        cancel_url=os.getenv("ACCOUNTIQ_PAYMENT_CANCEL_URL", "http://localhost:3000/wizard?payment=cancelled"),
    )


def stripe_enabled() -> bool:
    return bool(os.getenv("STRIPE_SECRET_KEY", "").strip())
```

- [ ] **Step 5: Document env vars**

Add to `.env.example`:

```dotenv
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
ACCOUNTIQ_VALUATION_PRICE_CENTS=49500
ACCOUNTIQ_CURRENCY=nzd
ACCOUNTIQ_PAYMENT_SUCCESS_URL=http://localhost:3000/wizard?payment=success
ACCOUNTIQ_PAYMENT_CANCEL_URL=http://localhost:3000/wizard?payment=cancelled
ACCOUNTIQ_REQUIRE_ADMIN_REVIEW=true
```

- [ ] **Step 6: Verify**

Run:

```bash
/Users/davewilson/Code/Daves/william/accountiq-learning-agent/venv/bin/python -m pytest tests/test_payments.py
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add backend/db.py backend/payments.py backend/requirements.txt .env.example tests/test_payments.py
git commit -m "feat(payments): add valuation purchase model"
```

---

## Task 3: Gate Valuation Generation Behind Checkout

**Files:**
- Modify: `backend/db.py`
- Modify: `backend/main.py`
- Modify: `backend/payments.py`
- Modify: `web/components/wizard/wizard.tsx`
- Modify: `web/components/wizard/report-status-card.tsx`
- Add/modify: `tests/test_payments.py`
- Modify: `web/e2e/wizard.spec.ts`

- [ ] **Step 1: Add backend checkout endpoint tests**

In `tests/test_payments.py`, add a test that posts to `/wizard/report/checkout` in E2E mode and asserts the report queues without Stripe:

```python
@pytest.mark.asyncio
async def test_e2e_checkout_creates_queued_report(client, fresh_all_db, monkeypatch):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    await client.post("/auth/register", data={"email": "buyer@example.com", "password": "password123"})
    upload = await client.post(
        "/wizard/upload",
        data={"business_name": "Paid Valuation Ltd"},
        files={"file": ("sample.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    company_id = upload.json()["company_id"]
    res = await client.post("/wizard/report/checkout", json={
        "company_id": company_id,
        "report_type": "valuation_advisory",
        "intake_answers": {
            "forecast_horizon": 3,
            "revenue_growth_cagr": 8,
            "terminal_growth_rate": 3,
            "rq_revenue_quality": 3,
            "rq_owner_dependency": 3,
            "rq_ebitda_growth": 3,
            "rq_customer_concentration": 3,
            "rq_gross_margin": 3,
            "rq_competitive_barriers": 3,
            "rq_growth_outlook": 3,
            "rq_management_depth": 3,
        },
    })
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "queued"
    assert body["checkout_url"] is None
```

- [ ] **Step 2: Add `/wizard/report/checkout`**

In `backend/main.py`, add a new endpoint that:

1. Validates `report_type == "valuation_advisory"`.
2. Creates `reports.status = 'pending_payment'`.
3. Stores `report_intake`.
4. In `E2E_MODE`, marks purchase `paid`, updates report to `queued`, and starts `_generate_report`.
5. In real mode, creates a Stripe Checkout session and returns `checkout_url`.

The endpoint response shape must be:

```python
return {
    "report_id": report_id,
    "status": status,
    "checkout_url": checkout_url,
}
```

- [ ] **Step 3: Add webhook endpoint**

Add `POST /payments/stripe/webhook` that:

1. Verifies `STRIPE_WEBHOOK_SECRET`.
2. Accepts `checkout.session.completed`.
3. Finds purchase by `stripe_checkout_session_id`.
4. Updates purchase `status='paid'`, `paid_at=datetime('now')`.
5. Updates report `status='queued'`.
6. Queues `_generate_report`.

- [ ] **Step 4: Update wizard client**

In `web/components/wizard/wizard.tsx`, change valuation generation to post to `/wizard/report/checkout`. If `checkout_url` is present, assign `window.location.href = checkout_url`; otherwise continue to status polling with `report_id`.

- [ ] **Step 5: Verify**

Run:

```bash
/Users/davewilson/Code/Daves/william/accountiq-learning-agent/venv/bin/python -m pytest tests/test_payments.py tests/test_wizard_endpoints.py
cd web && pnpm test:e2e -- e2e/wizard.spec.ts
```

Expected: all pass.

Verified on 2026-07-04:

```bash
/Users/davewilson/Code/Daves/william/accountiq-learning-agent/venv/bin/python -m pytest tests/test_admin_review.py tests/test_payments.py tests/test_wizard_endpoints.py
# 17 passed

/Users/davewilson/Code/Daves/william/accountiq-learning-agent/venv/bin/python -m pytest
# 131 passed, 1 skipped

cd web && pnpm lint
cd web && pnpm typecheck
cd web && pnpm build
# all passed

cd web && pnpm test:e2e -- e2e/admin.spec.ts e2e/wizard.spec.ts e2e/report-viewer.spec.ts
# 4 passed

cd web && pnpm test:e2e
# 10 passed
```

- [x] **Step 6: Commit**

```bash
git add backend/main.py backend/payments.py web/components/wizard/wizard.tsx web/components/wizard/report-status-card.tsx tests/test_payments.py web/e2e/wizard.spec.ts
git commit -m "feat(payments): gate valuation generation behind checkout"
```

---

## Task 4: Add Admin Review Before Delivery

**Files:**
- Modify: `backend/main.py`
- Modify: `web/components/admin/admin-nav.tsx` or existing admin layout component
- Create: `web/app/admin/reports/page.tsx`
- Create: `web/components/admin/reports-page.tsx`
- Add: `tests/test_admin_review.py`
- Modify: `web/e2e/admin.spec.ts`

- [x] **Step 1: Add backend tests**

Create `tests/test_admin_review.py` with tests for:

```python
async def test_completed_paid_valuation_enters_awaiting_review(...):
    ...

async def test_admin_can_approve_report_and_user_can_view(...):
    ...

async def test_regular_user_cannot_approve_report(...):
    ...

async def test_review_schema_supports_approval_audit(...):
    ...
```

Use direct DB inserts for the draft report row to keep tests deterministic.

- [x] **Step 2: Change generation final status**

In `_generate_report`, after storing content for `valuation_advisory`, set:

```python
next_status = "awaiting_review" if os.getenv("ACCOUNTIQ_REQUIRE_ADMIN_REVIEW", "true").lower() == "true" else "done"
```

Only send report-ready email when `next_status == "done"`.

- [x] **Step 3: Add admin report routes**

Add:

```python
@app.get("/admin/reports/pending")
async def admin_pending_reports(...):
    ...

@app.post("/admin/reports/{report_id}/approve")
async def admin_approve_report(...):
    ...
```

Approval sets `status='done'`, `completed_at=datetime('now')`, records the reviewer identity and approval time in `reviews`, and sends the report-ready email.

- [x] **Step 4: Add admin UI**

Add an Admin nav link `Reports`. The page lists `awaiting_review` reports with company name, report type, created date, `Open draft`, and `Approve`.

- [x] **Step 5: Verify**

Run:

```bash
/Users/davewilson/Code/Daves/william/accountiq-learning-agent/venv/bin/python -m pytest tests/test_admin_review.py
cd web && pnpm test:e2e -- e2e/admin.spec.ts
```

Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add backend/main.py web/app/admin/reports/page.tsx web/components/admin/reports-page.tsx tests/test_admin_review.py web/e2e/admin.spec.ts
git commit -m "feat(reports): add admin review gate"
```

---

## Task 5: Add Professional PDF Export

**Files:**
- Create: `backend/report_rendering.py`
- Modify: `backend/main.py`
- Modify: `backend/requirements.txt`
- Add: `tests/test_pdf_delivery.py`
- Modify: `web/components/wizard/report-status-card.tsx`
- Modify: `web/components/wizard/wizard.tsx`
- Modify: `web/app/globals.css`
- Modify: `web/e2e/wizard.spec.ts`

- [x] **Step 1: Add dependency**

Add to `backend/requirements.txt`:

```text
weasyprint==69.0
```

The renderer uses Python's escaping and lightweight structured-content helpers directly, so Jinja is not required.

- [x] **Step 2: Add renderer module**

Create `backend/report_rendering.py` with safe narrative, heading, bullet, bold-text, and table rendering; AccountIQ navy branding; an A4 cover; a per-page page counter/disclaimer; and atomic PDF writes. Import WeasyPrint inside `write_pdf` so importing the API does not eagerly load the rendering runtime.

- [x] **Step 3: Add PDF endpoint**

Add `GET /wizard/report/{report_id}/pdf` that:

1. Requires report owner.
2. Requires `status='done'`.
3. Renders and stores PDF if missing.
4. Returns `FileResponse` with `application/pdf`.
5. Runs synchronous rendering in an executor and atomically caches the artifact.

- [x] **Step 4: Update status card**

When report status is done, show:

```tsx
<a className="button button-secondary" href={`/api/backend/wizard/report/${reportId}/pdf`}>
  Download PDF
</a>
```

Persist the active report ID under a user-specific browser key and restore the status screen after reload. Clear it when the customer selects `Upload another`.

- [x] **Step 5: Verify**

Run:

```bash
/Users/davewilson/Code/Daves/william/accountiq-learning-agent/venv/bin/python -m pytest tests/test_pdf_delivery.py
cd web && pnpm test:e2e -- e2e/wizard.spec.ts
```

Expected: all pass.

Verified on 2026-07-12:

```bash
PYTHONPATH=/tmp/accountiq-test-deps:/tmp/accountiq-pdf-deps python3 -m pytest tests/ -q
# 136 passed, 1 skipped

cd web && pnpm lint && pnpm typecheck && pnpm build
# all passed

cd web && pnpm exec playwright test e2e/wizard.spec.ts --config .playwright-port3109.config.ts
# 2 passed
```

Also rendered and visually inspected a two-page A4 sample with WeasyPrint 69.0, including markdown headings/bullets/bold text, a branded table, disclaimer panel, and complete page footers.

- [ ] **Step 6: Commit**

```bash
git add backend/report_rendering.py backend/main.py backend/requirements.txt tests/test_pdf_delivery.py web/components/wizard/report-status-card.tsx web/components/wizard/wizard.tsx web/app/globals.css web/e2e/wizard.spec.ts
git commit -m "feat(delivery): add valuation PDF export"
```

---

## Task 6: Add Account Purchase History

**Files:**
- Modify: `backend/main.py`
- Modify: `web/app/account/page.tsx`
- Modify: `web/types/domain.ts`
- Add: `tests/test_purchase_history.py`
- Add: `web/e2e/account.spec.ts`

- [x] **Step 1: Add purchase history endpoint with TDD coverage**

Add `GET /account/purchases` returning only the current user's purchases joined to reports and companies. Return explicit `purchase_status` and `report_status` fields, and order newest first.

- [x] **Step 2: Render and test purchase history**

In `web/app/account/page.tsx`, fetch `/account/purchases` server-side and render payment and delivery status. Show `Open report` and `Download PDF` only for `done` reports. Cover awaiting-review and released states in Playwright.

- [x] **Step 3: Verify**

Run backend pytest, frontend lint/typecheck/build, and relevant Playwright coverage.

Verified on 2026-07-12:

```bash
PYTHONPATH=/tmp/accountiq-test-deps python3 -m pytest tests/ -q
# 138 passed, 1 skipped

cd web && pnpm lint && pnpm typecheck && pnpm build
# all passed

cd web && pnpm exec playwright test --config .playwright-port3110.config.ts
# 10 passed
```

- [x] **Step 4: Commit**

```bash
git add backend/main.py tests/test_purchase_history.py web/app/account/page.tsx web/types/domain.ts web/e2e/account.spec.ts
git commit -m "feat(account): add purchase history"
```

---

## Task 7: Add Public Valuation Offer Page

**Files:**
- Create: `web/app/valuation/page.tsx`
- Add: `web/e2e/valuation.spec.ts`

- [x] **Step 1: Add public valuation page**

Implemented through the focused, Fable-5-reviewed plan at `docs/superpowers/plans/2026-07-13-public-valuation-offer.md`. The static `/valuation` page uses the approved `Know what your business may be worth` headline, early-access fixed-fee language without a numeric amount, primary use cases, visible trust/compliance boundaries, and conversion links to `/login`.

- [x] **Step 2: Verify**

```bash
cd web
pnpm typecheck
pnpm lint
pnpm test:e2e -- e2e/valuation.spec.ts
```

Expected: all pass.

Verified 2026-07-13: focused valuation Playwright 2 passed; lint, typecheck, and production build passed; full development and production Playwright suites each passed 13 tests; `/valuation` is statically prerendered.

- [x] **Step 3: Commit**

```bash
git add web/app/valuation/page.tsx web/e2e/valuation.spec.ts
git commit -m "feat(valuation): add public offer page"
```

---

## Final Verification

Run the full suite:

```bash
/Users/davewilson/Code/Daves/william/accountiq-learning-agent/venv/bin/python -m pytest
cd web
pnpm lint
pnpm typecheck
pnpm build
pnpm test:e2e
pnpm test:e2e:prod
```

Expected:

- Backend pytest passes.
- Lint/typecheck/build pass.
- Dev Playwright passes.
- Standalone production Playwright passes.

Then push:

```bash
git push -u origin codex/paid-valuation-mvp
```

---

## Self-Review

- Spec coverage: The plan covers valuation focus, payment gating, admin review, PDF delivery, purchase history, and public offer surface.
- Deferred deliberately: Full self-serve Bank Credit Paper, Forecast, Capital Raising, and IM. These remain advisor-pilot/offline until the valuation wedge proves payment and report trust.
- Placeholder scan: No task uses TBD/TODO/implement-later language.
- Type consistency: The plan uses the existing `valuation_advisory` report key, existing `/wizard/report/{id}` URL family, and existing FastAPI/Next proxy pattern.
