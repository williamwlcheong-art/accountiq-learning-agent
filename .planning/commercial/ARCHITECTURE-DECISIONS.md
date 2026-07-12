# Commercial MVP Architecture Decisions

**Last updated:** 2026-07-12
**Status:** Frontend and backend-boundary decisions implemented; production infrastructure decisions remain launch gates.

## ADR-001: Frontend Shell

**Decision:** Use a Next.js App Router application in `web/` for the public marketing site, login/register entry, customer dashboard, report history, order flow, and reviewer/admin screens.

**Reasoning:**

- The primary product UI has migrated to `web/`; `frontend/index.html` is an opt-in legacy fallback.
- Next.js provides route-level ownership for marketing pages, customer app, account area, and reviewer/admin screens.
- Existing FastAPI endpoints can remain stable while the UI migrates.

**Rejected alternatives:**

- Keep all public/commercial UI in `frontend/index.html`: too hard to maintain and test.
- Move FastAPI logic into Next.js route handlers: risky because ingestion, OCR, valuation, AI calls, SQLite/Postgres access, and background jobs are Python-centric.

**Status:** Implemented for the current product UI.

## ADR-002: Same-Origin API Strategy

**Decision:** Use the same-origin `/api/backend/*` Route Handler proxy so browser requests, cookies, and CORS stay predictable.

**Local target:**

- Next.js dev server: `http://localhost:3000`
- FastAPI backend: `http://127.0.0.1:8765`
- Next.js Route Handler: `/api/backend/:path*` -> `http://127.0.0.1:8765/:path*`

**Production target:**

- One public site domain for customers.
- Path-based routing or reverse proxy sends app pages to Next.js and API/upload/report routes to FastAPI.
- If separate subdomains are used temporarily, cookie, CORS, CSRF, and SameSite behaviour must be tested before launch.

**Risk:** Rewrites/proxies and Set-Cookie behaviour must be browser-tested. Do not assume auth works until login/logout/report-view flows pass in production-like deployment.

**Status:** Implemented locally; production-like deployment verification remains required.

## ADR-003: File Upload Routing

**Decision:** Financial statement uploads should terminate at FastAPI, not at a serverless Next.js handler.

**Reasoning:**

- Existing upload, file sanitisation, ingestion, extraction, and background processing are in FastAPI.
- Large files and long-running processing are better owned by the Python backend.
- Marketing/app UI can call FastAPI through the same-origin proxy.

**Status:** Accepted for planning.

## ADR-004: Production Database

**Decision:** Use Postgres for live paid/public launch. SQLite remains acceptable for local development and private pilot only.

**Reasoning:**

- Purchases, Stripe webhook events, report states, reviewer decisions, and paid access records are durable commercial records.
- Migrating after live payment data accumulates is riskier than choosing Postgres before launch.
- Railway provides a managed Postgres service suitable for the first commercial deployment.

**Implementation implication:**

- Add a database abstraction/migration plan before enabling live Stripe payments.
- Keep async database access.
- Preserve tests that can run against isolated disposable DB paths or test Postgres.

**Status:** Accepted for planning.

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

## ADR-006: Backups And Recovery

**Decision:** Launch readiness requires a written backup/restore check for Postgres and durable file storage.

**Minimum evidence:**

- A recent database backup can be restored into a non-production environment.
- File storage has a documented backup/export path.
- Report PDFs can be re-downloaded after service restart/redeploy.

**Status:** Open until deployment plan.

## Commercial MVP Domain Entities

The implementation plans should introduce or verify these durable entities.

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

## Implementation Plan Order

Write and execute implementation plans in this order:

1. **Marketing Site / Offer**
   - Homepage, valuation offer, proof blocks, FAQ, CTA, privacy-safe analytics events.
2. **Customer Dashboard + Report History**
   - Account home, order status, report history, paid/unpaid states, viewer link.
3. **Pre-Payment Validation**
   - Upload validation result, customer status, supported/unsupported cases before Stripe.
4. **Stripe + Fulfillment State Machine**
   - Checkout, webhook, purchase records, paid access, refund/cancel paths.
5. **Todd Review Queue**
   - Review states, approval, clarification, refund-needed, internal notes, consultation flag.
6. **Production Deployment**
   - Railway/FastAPI, Postgres, file storage, secrets, backups, domain/cookies, Stripe webhook endpoint.
7. **Privacy-Safe Analytics + CRM**
   - PostHog event taxonomy, autocapture restrictions, contact/consultation lead capture.

## Stop Condition

Do not start public launch or ad spend until:

- Launch gates are passed or explicitly waived for private pilot.
- Architecture decisions are reviewed.
- Payment/refund state machine is planned.
- Todd review SLA is written.
- Privacy/analytics consent is written.
