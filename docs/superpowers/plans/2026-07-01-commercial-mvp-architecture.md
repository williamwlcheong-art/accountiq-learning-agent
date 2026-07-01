# Commercial MVP Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define the production architecture for AccountIQ's Commercial MVP before writing the marketing site, payment flow, customer dashboard, or reviewer queue implementation plans.

**Architecture:** Use a strangler architecture. Next.js owns the public site and customer/admin app shell; FastAPI remains the backend of record for auth, uploads, extraction, valuation/report generation, reviewer workflow, payments, and durable data writes. Local development can keep SQLite, but live paid launch should use Postgres plus durable file storage.

**Tech Stack:** Next.js App Router, React, TypeScript, FastAPI, Python, Postgres, Railway, Stripe Checkout/Webhooks, PostHog, existing pytest suite, future Playwright E2E.

---

## Architecture Decision

Recommended Commercial MVP architecture:

```text
Browser
  |
  | public marketing pages, login, dashboard, order flow
  v
Next.js app in web/
  |
  | /api/backend/* rewrite/proxy in development and production
  | same customer journey and auth surface
  v
FastAPI backend
  |
  | auth, uploads, extraction, report generation,
  | Stripe webhooks, reviewer queue, PDF/report delivery
  v
Postgres for durable records
  +
Durable file storage for uploaded financials and generated PDFs
```

Do not migrate ingestion, OCR, valuation, AI calls, report generation, PDF rendering, or payment webhooks into Next.js during the Commercial MVP.

## Primary Decisions

1. **Next.js owns presentation and routing.** Marketing pages, login, customer dashboard, report history, and admin/reviewer screens should live in `web/`.
2. **FastAPI remains system of record.** It owns every durable state change and all financial/report processing.
3. **Postgres is required for live paid launch.** SQLite can remain for local development and private pilot only.
4. **Stripe fulfillment is webhook-driven.** Client redirect is never authoritative for report generation or delivery.
5. **Uploads must validate before payment.** Customers should not pay until files are accepted and serviceable enough to proceed.
6. **Generated reports require approval.** Paid valuation reports should enter `awaiting_review` before delivery.
7. **Analytics must be privacy-constrained.** PostHog can track funnel events, but not document text, report content, financial values, or sensitive form fields.

## External References

- Next.js rewrites can proxy an incoming path to another destination while keeping the visible URL unchanged: `https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites`
- Railway documents FastAPI deployment from templates, GitHub repositories, CLI, or Dockerfile: `https://docs.railway.com/guides/fastapi`
- Railway provides Postgres as a database service: `https://docs.railway.com/databases/postgresql`
- Railway provides persistent volumes and S3-compatible storage options for files: `https://docs.railway.com/data-storage` and `https://docs.railway.com/volumes`
- Stripe recommends webhook-based fulfillment for Checkout: `https://docs.stripe.com/checkout/fulfillment` and `https://docs.stripe.com/webhooks`
- PostHog supports controlling data collection and disabling/filtering autocapture: `https://posthog.com/docs/privacy/data-collection`

## Scope Boundary

This plan decides and sequences architecture. It does not implement application code. After this plan, write separate implementation plans for:

1. Marketing Site / Offer
2. Customer Dashboard + Report History
3. Stripe + Fulfillment State Machine
4. Todd Review Queue
5. Production Deployment + Postgres/File Storage
6. Privacy-Safe Analytics + CRM

---

### Task 1: Confirm Existing Backend Surface

**Files:**

- Read: `backend/main.py`
- Read: `backend/auth.py`
- Read: `backend/db.py`
- Read: `backend/ingestion.py`
- Read: `backend/report_email.py`
- Read: `backend/valuation.py`
- Read: `tests/`

- [ ] **Step 1: Confirm the route inventory**

Run with the backend running on port `8765`:

```bash
curl -sS http://127.0.0.1:8765/openapi.json > /tmp/accountiq-openapi.json
python3 - <<'PY'
import json
spec = json.load(open('/tmp/accountiq-openapi.json'))
ops = sorted((method.upper(), path) for path, methods in spec["paths"].items() for method in methods)
print(len(ops))
for method, path in ops:
    print(method, path)
PY
```

Expected: route count matches the current backend surface and includes:

```text
POST /wizard/upload
POST /wizard/report/generate
GET /wizard/report/{report_id}/status
GET /wizard/report/{report_id}/view
```

- [ ] **Step 2: Confirm auth cookie assumptions**

Run:

```bash
rg -n "accountiq_session|SameSite|httponly|set_cookie|delete_cookie" backend/auth.py backend/main.py
```

Expected: auth uses an HttpOnly session cookie and logout clears it.

- [ ] **Step 3: Confirm current tests before architecture implementation**

Run:

```bash
source venv/bin/activate
python -m pytest tests/ -q
```

Expected: all tests pass, or failures are classified as pre-existing before architecture work starts.

### Task 2: Decide The Frontend Deployment Shape

**Files:**

- Create: `.planning/commercial/ARCHITECTURE-DECISIONS.md`
- Read: `docs/superpowers/plans/2026-07-01-nextjs-refactor-final.md`

- [ ] **Step 1: Record the frontend decision**

Create `.planning/commercial/ARCHITECTURE-DECISIONS.md` with:

```markdown
# Commercial MVP Architecture Decisions

**Last updated:** 2026-07-01

## ADR-001: Frontend Shell

**Decision:** Use a Next.js App Router application in `web/` for the public marketing site, login/register entry, customer dashboard, report history, order flow, and reviewer/admin screens.

**Reasoning:**
- The current `frontend/index.html` is a large single-file app and is not the right long-term shell for a commercial funnel.
- Next.js gives route-level ownership for marketing pages, customer app, account area, and reviewer/admin screens.
- Existing FastAPI endpoints can remain stable while the UI migrates.

**Rejected alternatives:**
- Keep all public/commercial UI in `frontend/index.html`: too hard to maintain and test.
- Move FastAPI logic into Next.js route handlers: risky because ingestion, OCR, valuation, AI calls, SQLite/Postgres access, and background jobs are Python-centric.

**Status:** Accepted for planning.
```

- [ ] **Step 2: Decide same-domain strategy**

Append:

```markdown
## ADR-002: Same-Origin API Strategy

**Decision:** Prefer a same-origin `/api/backend/*` proxy/rewrite so browser requests, cookies, and CORS stay predictable.

**Local target:**
- Next.js dev server: `http://localhost:3000`
- FastAPI backend: `http://127.0.0.1:8765`
- Next.js rewrite: `/api/backend/:path*` -> `http://127.0.0.1:8765/:path*`

**Production target:**
- One public site domain for customers.
- Path-based routing or reverse proxy sends app pages to Next.js and API/upload/report routes to FastAPI.
- If separate subdomains are used temporarily, cookie, CORS, CSRF, and SameSite behaviour must be tested before launch.

**Risk:** Rewrites/proxies and Set-Cookie behaviour must be browser-tested. Do not assume auth works until login/logout/report-view flows pass in production-like deployment.

**Status:** Accepted for planning.
```

- [ ] **Step 3: Define upload routing rule**

Append:

```markdown
## ADR-003: File Upload Routing

**Decision:** Financial statement uploads should terminate at FastAPI, not at a serverless Next.js handler.

**Reasoning:**
- Existing upload, file sanitisation, ingestion, extraction, and background processing are in FastAPI.
- Large files and long-running processing are better owned by the Python backend.
- Marketing/app UI can call FastAPI through the same-origin proxy.

**Status:** Accepted for planning.
```

### Task 3: Decide Production Data Storage

**Files:**

- Modify: `.planning/commercial/ARCHITECTURE-DECISIONS.md`
- Read: `backend/db.py`
- Read: `.planning/commercial/LAUNCH-GATES.md`

- [ ] **Step 1: Record the Postgres decision**

Append:

```markdown
## ADR-004: Production Database

**Decision:** Use Postgres for live paid/public launch. SQLite remains acceptable for local development and private pilot only.

**Reasoning:**
- Purchases, Stripe webhook events, report states, reviewer decisions, and paid access records are durable commercial records.
- Migrating after live payment data accumulates is riskier than choosing Postgres before launch.
- Railway provides a managed Postgres service suitable for the first commercial deployment.

**Implementation implication:**
- Add a database abstraction/migration plan before Stripe implementation.
- Keep async database access.
- Preserve tests that can run against isolated disposable DB paths or test Postgres.

**Status:** Accepted for planning.
```

- [ ] **Step 2: Record file storage decision**

Append:

```markdown
## ADR-005: Uploaded Files And Generated PDFs

**Decision:** Do not rely on ephemeral container storage for production files. Use durable storage for uploaded financial statements and generated PDFs.

**Private pilot option:** Railway volume mounted to the FastAPI service.

**Public launch option:** Railway volume for simplest first deployment, or S3-compatible object storage if multi-service access, backups, or growth requirements make object storage cleaner.

**Required paths:**
- Uploaded source files.
- Extracted/OCR intermediate artefacts if retained.
- Generated report PDFs.
- Audit/reviewer attachments if added.

**Status:** Accepted for planning.
```

- [ ] **Step 3: Record backup expectation**

Append:

```markdown
## ADR-006: Backups And Recovery

**Decision:** Launch readiness requires a written backup/restore check for Postgres and durable file storage.

**Minimum evidence:**
- A recent database backup can be restored into a non-production environment.
- File storage has a documented backup/export path.
- Report PDFs can be re-downloaded after service restart/redeploy.

**Status:** Open until deployment plan.
```

### Task 4: Define Commercial MVP Domain Model

**Files:**

- Modify: `.planning/commercial/ARCHITECTURE-DECISIONS.md`
- Read: `backend/db.py`
- Read: `.planning/commercial/COMMERCIAL-ASSUMPTIONS.md`

- [ ] **Step 1: Add required entities**

Append:

```markdown
## Commercial MVP Domain Entities

The implementation plans should introduce or verify these durable entities:

### User

Existing auth user. Owns companies, documents, purchases, reports, and customer dashboard state.

### Company

Existing company/business record attached to a user.

### Document

Uploaded financial statement source file and extraction status.

### Validation Result

Pre-payment serviceability result for uploaded documents.

Required fields:
- `id`
- `company_id`
- `user_id`
- `status`: `pending`, `passed`, `failed`
- `failure_reason`
- `created_at`
- `updated_at`

### Product

Commercial product selection. First public product is `business_valuation_report`.

### Purchase

Payment record linked to user, company, product, and report.

Required fields:
- `id`
- `user_id`
- `company_id`
- `report_id`
- `product_key`
- `amount_cents`
- `currency`
- `tax_cents`
- `stripe_checkout_session_id`
- `stripe_payment_intent_id`
- `status`
- `created_at`
- `paid_at`
- `refunded_at`

### Report

Generated report object with customer-visible and internal state.

### Review

Human review workflow for report approval.

Required fields:
- `id`
- `report_id`
- `reviewer_user_id`
- `status`: `awaiting_review`, `needs_clarification`, `approved`, `unserviceable`
- `internal_notes`
- `customer_message`
- `created_at`
- `updated_at`
- `approved_at`

### Consultation Lead

Manual upsell/contact record created after review or delivery.
```

- [ ] **Step 2: Add report state machine**

Append:

```markdown
## Commercial MVP State Machine

Use these states for planning Stripe, dashboard, and reviewer flows:

1. `uploaded`
2. `validating`
3. `validation_failed`
4. `validated`
5. `awaiting_payment`
6. `paid`
7. `generating`
8. `generation_failed`
9. `awaiting_review`
10. `needs_clarification`
11. `approved`
12. `delivered`
13. `refund_needed`
14. `refunded`
15. `cancelled`

Rules:
- Stripe payment can only start after `validated`.
- Generation can only start after server-side payment confirmation.
- Customer delivery can only happen after `approved`.
- `needs_clarification` must be visible in the customer dashboard.
- `refund_needed` and `refunded` must remove or block paid report access.
```

### Task 5: Define Deployment Topology

**Files:**

- Modify: `.planning/commercial/ARCHITECTURE-DECISIONS.md`
- Read: `.planning/commercial/LAUNCH-GATES.md`

- [ ] **Step 1: Add local topology**

Append:

```markdown
## Local Development Topology

```text
localhost:3000  -> Next.js app in web/
localhost:8765  -> FastAPI backend in backend/
SQLite          -> local dev DB unless Postgres test mode is active
data/           -> local uploads/reports
```

Local environment variables:
- `FASTAPI_ORIGIN=http://127.0.0.1:8765`
- `NEXT_PUBLIC_API_BASE=/api/backend`
- `ACCOUNTIQ_DB_PATH=...` for isolated local/E2E DBs
```

- [ ] **Step 2: Add private pilot topology**

Append:

```markdown
## Private Pilot Topology

```text
Public domain or staging domain
  -> Next.js app
  -> /api/backend/* to FastAPI

FastAPI
  -> Postgres preferred
  -> Railway volume acceptable for pilot files
  -> Stripe test mode or manual invoice
```

Private pilot may waive some public launch gates only if the waiver is written in `.planning/commercial/LAUNCH-GATES.md`.
```

- [ ] **Step 3: Add public paid topology**

Append:

```markdown
## Public Paid Launch Topology

```text
Customer browser
  -> one public customer-facing site
  -> Next.js pages/app shell
  -> same-origin API/proxy to FastAPI

FastAPI service
  -> Postgres
  -> durable file storage
  -> Stripe webhook endpoint
  -> email provider
  -> AI provider

Admin/reviewer
  -> Next.js reviewer/admin screens
  -> FastAPI reviewer APIs
```

Public launch requires:
- Postgres.
- Durable file storage.
- HTTPS webhook endpoint for Stripe.
- Production cookie/auth test.
- Backup/restore evidence.
```

### Task 6: Define Analytics And Privacy Boundary

**Files:**

- Modify: `.planning/commercial/ARCHITECTURE-DECISIONS.md`
- Read: `.agents/product-marketing-context.md`

- [ ] **Step 1: Add analytics decision**

Append:

```markdown
## ADR-007: Analytics Boundary

**Decision:** Track funnel events, not financial content.

Allowed events:
- `page_viewed`
- `valuation_cta_clicked`
- `signup_started`
- `signup_completed`
- `upload_started`
- `upload_completed`
- `validation_passed`
- `validation_failed`
- `checkout_started`
- `checkout_completed`
- `report_generation_started`
- `report_awaiting_review`
- `report_delivered`
- `consultation_cta_clicked`

Forbidden properties:
- document text
- extracted financial line items
- revenue, EBITDA, profit, valuation values
- uploaded filenames if customer/company identifying
- report narrative
- customer free-text answers
- API keys, tokens, emails in event properties unless explicitly consented and required

Implementation note:
- Disable or tightly configure autocapture before production.
- Add explicit event capture for the funnel instead of broad form/input capture.

**Status:** Accepted for planning.
```

### Task 7: Decide Implementation Plan Order

**Files:**

- Modify: `.planning/commercial/ARCHITECTURE-DECISIONS.md`

- [ ] **Step 1: Add implementation sequence**

Append:

```markdown
## Implementation Plan Order

Write and execute implementation plans in this order:

1. **Next.js Foundation + E2E Backend Mode**
   - Scaffold `web/`, API proxy, auth smoke, deterministic E2E mode.

2. **Marketing Site / Offer**
   - Homepage, valuation offer, proof blocks, FAQ, CTA, privacy-safe analytics events.

3. **Customer Dashboard + Report History**
   - Account home, order status, report history, paid/unpaid states, viewer link.

4. **Pre-Payment Validation**
   - Upload validation result, customer status, supported/unsupported cases before Stripe.

5. **Stripe + Fulfillment State Machine**
   - Checkout, webhook, purchase records, paid access, refund/cancel paths.

6. **Todd Review Queue**
   - Review states, approval, clarification, refund-needed, internal notes, consultation flag.

7. **Production Deployment**
   - Railway/FastAPI, Postgres, file storage, secrets, backups, domain/cookies, Stripe webhook endpoint.

8. **Privacy-Safe Analytics + CRM**
   - PostHog event taxonomy, autocapture restrictions, contact/consultation lead capture.
```

- [ ] **Step 2: Add stop condition**

Append:

```markdown
## Stop Condition

Do not start public launch or ad spend until:

- Launch gates are passed or explicitly waived for private pilot.
- Architecture decisions are reviewed.
- Payment/refund state machine is planned.
- Todd review SLA is written.
- Privacy/analytics consent is written.
```

### Task 8: Verification And Commit

**Files:**

- Verify: `.planning/commercial/ARCHITECTURE-DECISIONS.md`
- Verify: `docs/superpowers/plans/2026-07-01-commercial-mvp-architecture.md`

- [ ] **Step 1: Check for forbidden placeholders**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

terms = [
    "TB" + "D",
    "TO" + "DO",
    "implement " + "later",
    "fill in " + "details",
    "Add " + "appropriate",
    "Write tests " + "for the above",
    "Similar " + "to Task",
]
files = [
    Path("docs/superpowers/plans/2026-07-01-commercial-mvp-architecture.md"),
    Path(".planning/commercial/ARCHITECTURE-DECISIONS.md"),
]
hits = []
for path in files:
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        if any(term in line for term in terms):
            hits.append(f"{path}:{lineno}:{line}")
if hits:
    print("\\n".join(hits))
    raise SystemExit(1)
PY
```

Expected: no output.

- [ ] **Step 2: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/superpowers/plans/2026-07-01-commercial-mvp-architecture.md .planning/commercial/ARCHITECTURE-DECISIONS.md
git commit -m "docs: define commercial mvp architecture"
```
