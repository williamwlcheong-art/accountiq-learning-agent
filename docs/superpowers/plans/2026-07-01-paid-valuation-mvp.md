# Paid Valuation MVP Implementation Plan

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
npm run typecheck
npm run lint
npm run test:e2e -- e2e/wizard.spec.ts
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
cd web && npm run test:e2e -- e2e/wizard.spec.ts
```

Expected: all pass.

- [ ] **Step 6: Commit**

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

- [ ] **Step 1: Add backend tests**

Create `tests/test_admin_review.py` with tests for:

```python
async def test_completed_paid_valuation_enters_awaiting_review(...):
    ...

async def test_admin_can_approve_report_and_user_can_view(...):
    ...

async def test_regular_user_cannot_approve_report(...):
    ...
```

Use direct DB inserts for the draft report row to keep tests deterministic.

- [ ] **Step 2: Change generation final status**

In `_generate_report`, after storing content for `valuation_advisory`, set:

```python
next_status = "awaiting_review" if os.getenv("ACCOUNTIQ_REQUIRE_ADMIN_REVIEW", "true").lower() == "true" else "done"
```

Only send report-ready email when `next_status == "done"`.

- [ ] **Step 3: Add admin report routes**

Add:

```python
@app.get("/admin/reports/pending")
async def admin_pending_reports(...):
    ...

@app.post("/admin/reports/{report_id}/approve")
async def admin_approve_report(...):
    ...
```

Approval sets `status='done'`, `completed_at=datetime('now')`, and sends the report-ready email.

- [ ] **Step 4: Add admin UI**

Add an Admin nav link `Reports`. The page lists `awaiting_review` reports with company name, report type, created date, `Open draft`, and `Approve`.

- [ ] **Step 5: Verify**

Run:

```bash
/Users/davewilson/Code/Daves/william/accountiq-learning-agent/venv/bin/python -m pytest tests/test_admin_review.py
cd web && npm run test:e2e -- e2e/admin.spec.ts
```

Expected: all pass.

- [ ] **Step 6: Commit**

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

- [ ] **Step 1: Add dependency**

Add to `backend/requirements.txt`:

```text
weasyprint==62.3
jinja2==3.1.6
```

- [ ] **Step 2: Add renderer module**

Create `backend/report_rendering.py` with:

```python
from __future__ import annotations

import html
from pathlib import Path

from weasyprint import HTML


def report_pdf_path(export_dir: Path, report_id: int) -> Path:
    return export_dir / f"report-{report_id}.pdf"


def render_report_html(company_name: str, report_type: str, sections: dict, generated_at: str) -> str:
    escaped_company = html.escape(company_name)
    body = [f"<h1>{html.escape(report_type.replace('_', ' ').title())}</h1>"]
    body.append(f"<p>{escaped_company} · {html.escape(generated_at or '')}</p>")
    for key, value in sections.items():
        body.append(f"<section><h2>{html.escape(key.replace('_', ' ').title())}</h2>")
        if isinstance(value, dict):
            body.append(f"<p>{html.escape(str(value.get('narrative', '')))}</p>")
        else:
            body.append(f"<p>{html.escape(str(value))}</p>")
        body.append("</section>")
    return "<!doctype html><html><body>" + "".join(body) + "</body></html>"


def write_pdf(html_text: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_text).write_pdf(str(output_path))
```

- [ ] **Step 3: Add PDF endpoint**

Add `GET /wizard/report/{report_id}/pdf` that:

1. Requires report owner.
2. Requires `status='done'`.
3. Renders and stores PDF if missing.
4. Returns `FileResponse` with `application/pdf`.

- [ ] **Step 4: Update status card**

When report status is done, show:

```tsx
<a className="button button-secondary" href={`/api/backend/wizard/report/${reportId}/pdf`}>
  Download PDF
</a>
```

- [ ] **Step 5: Verify**

Run:

```bash
/Users/davewilson/Code/Daves/william/accountiq-learning-agent/venv/bin/python -m pytest tests/test_pdf_delivery.py
cd web && npm run test:e2e -- e2e/wizard.spec.ts
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/report_rendering.py backend/main.py backend/requirements.txt tests/test_pdf_delivery.py web/components/wizard/report-status-card.tsx
git commit -m "feat(delivery): add valuation PDF export"
```

---

## Task 6: Add Purchase History And Public Offer Page

**Files:**
- Modify: `backend/main.py`
- Modify: `web/app/account/page.tsx`
- Create: `web/app/valuation/page.tsx`
- Add: `web/e2e/account.spec.ts`

- [ ] **Step 1: Add purchase history endpoint**

Add `GET /account/purchases` returning current user's purchases joined to reports and companies:

```python
{
    "report_id": row["report_id"],
    "company_name": row["company_name"],
    "report_type": row["report_type"],
    "status": row["status"],
    "amount_cents": row["amount_cents"],
    "currency": row["currency"],
    "paid_at": row["paid_at"],
}
```

- [ ] **Step 2: Render purchase history**

In `web/app/account/page.tsx`, fetch `/account/purchases` server-side and render rows with `Open report` and `Download PDF` links for `done` reports.

- [ ] **Step 3: Add public valuation page**

Create `web/app/valuation/page.tsx` with headline `Indicative SME Valuation Report`, price `$495 launch price`, three use cases, and a `Start valuation` link to `/login`.

- [ ] **Step 4: Verify**

Run:

```bash
cd web
npm run typecheck
npm run lint
npm run test:e2e
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py web/app/account/page.tsx web/app/valuation/page.tsx web/e2e/account.spec.ts
git commit -m "feat(valuation): add purchase history and offer page"
```

---

## Final Verification

Run the full suite:

```bash
/Users/davewilson/Code/Daves/william/accountiq-learning-agent/venv/bin/python -m pytest
cd web
npm run lint
npm run typecheck
npm run build
npm run test:e2e
npm run test:e2e:prod
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
