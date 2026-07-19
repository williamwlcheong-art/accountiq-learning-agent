# Commercial MVP Launch Gates

**Last updated:** 2026-07-20
**Status:** All eight gates are open. This is not legal, accounting, tax, or financial advice.

## Rule

AccountIQ must not accept public users or public Stripe payments while any Launch Gate is open. Implementation evidence shows what the application currently does. It does not complete a gate. Each gate needs its listed evidence and sign-off by the designated qualified reviewer, or a documented, time-bounded private-pilot waiver.

## Current implementation evidence and gaps

The current implementation has a checkout-gated valuation flow. A valuation report is created as `pending_payment`, and its purchase is created as `pending`. A confirmed payment moves the purchase to `paid` and the report to `queued`. Generation uses `queued`, `generating`, and `researching`, then moves a valuation report to `awaiting_review`. Reviewer approval changes the report to `done` and the review to `approved`; the PDF route only permits a `done` report.

The checkout endpoint can return `needs_clarification` when valuation inputs are incomplete, but this is a response state, not a persisted report or purchase status. Reports can also be `failed`. The database has no implemented `cancelled`, `refund_needed`, or `refunded` purchase or report path. There is no cancellation or refund workflow, and no GST or other tax calculation, recording, invoice, or tax-treatment path. These are implementation gaps and do not satisfy Gate 5.

The unmerged `feature/fcff-assumptions` branch proposes an active approved WACC set and complete FCFF assumptions as checkout requirements. No PR exists yet. These controls cannot be treated as current merged implementation or gate evidence until a PR is opened, reviewed, merged, and freshly verified.

## Gate 1: Security and user isolation

**Why it matters:** Paid reports and financial statements are sensitive. Access-control failures would be severe.

**Must verify:**

- Auth/session cookies work through the implemented Next.js same-origin proxy.
- CORS is restricted for write endpoints.
- Uploaded filenames are sanitised with `Path(filename).name`.
- Frontend renders user/AI text safely.
- User A cannot access User B companies, documents, purchases, reports, PDFs, or reviewer messages.
- Non-admin users cannot access admin routes.

**Evidence required:**

- Test command and passing result.
- Manual browser smoke for login, logout, dashboard, upload, and report view.
- Route inventory showing protected routes.
- Designated qualified reviewer sign-off.

**Status:** Open.

## Gate 2: Compliance and professional boundary

**Why it matters:** Business valuation output, AI assistance, and professional-review claims create accounting and professional-standards risk.

**Must decide:**

- Is the first product an indicative valuation only?
- Does any output risk being regulated financial advice?
- What can a qualified-review claim legally and professionally mean?
- Can CAANZ or other logos or credentials be used?
- What disclaimer appears on site, checkout, report viewer, PDF, and email?
- What records must the designated qualified reviewer keep to show professional judgement over AI output?

**Evidence required:**

- Written disclaimer approved by the designated qualified reviewer.
- Decision on CAANZ/logo usage.
- Written review checklist for the designated qualified reviewer.
- Refund and cancellation policy approved before Stripe launch.
- Designated qualified reviewer sign-off.

**Status:** Open.

## Gate 3: Privacy, confidentiality, and data use

**Why it matters:** Customers upload financial statements and business information. AI vendors, analytics tools, and CRM tools may process sensitive data.

**Must decide:**

- What data is collected and why.
- Whether uploaded financial statements are sent to offshore AI providers.
- What consent is shown before upload.
- How long uploaded files, extracted rows, generated reports, and logs are retained.
- Whether customers can request deletion.
- Whether PostHog captures only product events or any document/report content.
- Whether CRM receives only lead/contact data, not financial documents.

**Evidence required:**

- Privacy policy draft.
- Upload consent language.
- Vendor/data-flow list.
- Analytics event schema with prohibited properties.
- Designated qualified reviewer sign-off.

**Status:** Open.

## Gate 4: Pre-payment serviceability validation

**Why it matters:** Customers should not pay before the app knows uploaded financials are likely usable.

**Must verify before Stripe:**

- File type accepted.
- File has extractable text/tables or OCR result.
- Minimum recent period data is present.
- Business name and fiscal period can be inferred or confirmed.
- Unsupported cases are stopped before payment with a contact-us path.
- An active approved WACC set and complete FCFF assumptions are required before valuation checkout.

**Evidence required:**

- Validation status in dashboard.
- Validation failure copy.
- Test fixtures for valid PDF, scanned PDF, Excel, Word, and unsupported upload.
- Test evidence for missing WACC or FCFF assumptions.
- Designated qualified reviewer sign-off.

**Status:** Open.

## Gate 5: Payment, cancellation, refund, and tax state machine

**Why it matters:** Stripe must be authoritative and paid access must survive retries, failures, review holds, cancellation, refunds, and tax handling.

**Required states:**

- `uploaded`
- `validating`
- `validation_failed`
- `validated`
- `awaiting_payment`
- `paid`
- `generating`
- `generation_failed`
- `awaiting_review`
- `needs_clarification`
- `approved`
- `delivered`
- `cancelled`
- `refund_needed`
- `refunded`

**Evidence required:**

- State transition diagram mapping the required states to persisted report and purchase states.
- Webhook handling plan and retry evidence.
- Implemented cancellation and refund paths, including post-payment unserviceable orders.
- GST/tax handling decision, implementation evidence, and customer record requirements.
- Designated qualified reviewer sign-off.

**Status:** Open.

## Gate 6: Reviewer capacity and SLA

**Why it matters:** Fast delivery and a qualified-review claim create a delivery promise that must match real capacity.

**Must decide:**

- Does the designated qualified reviewer review every valuation before delivery?
- Target review time per report.
- Target customer turnaround.
- What happens after 5, 10, or 20 concurrent paid orders?
- Who can be a backup qualified reviewer?
- What internal checklist is required before approval?

**Evidence required:**

- Reviewer checklist.
- SLA wording for website and checkout.
- Admin queue fields for assignment and status.
- Designated qualified reviewer sign-off.

**Status:** Open.

## Gate 7: Production infrastructure

**Why it matters:** Payment, report, and reviewer state are durable business records.

**Must decide:**

- Production routing for the implemented Next.js public site/app shell and FastAPI backend.
- FastAPI deployment target.
- Postgres before live payments.
- File storage path for uploaded financials and PDFs.
- Backup/restore plan.
- Environment/secrets plan.

**Evidence required:**

- Architecture decision record.
- Deployment checklist.
- Postgres migration plan or written private-pilot SQLite waiver.
- Designated qualified reviewer sign-off.

**Status:** Open.

## Gate 8: Measurement and CRM consent

**Why it matters:** Paid acquisition is wasteful without attribution, but financial-document users need privacy-safe tracking.

**Must decide:**

- Which PostHog events are tracked.
- Which properties are forbidden.
- UTM/source attribution model.
- Contact form and consultation request routing.
- Abandoned-start capture consent.

**Evidence required:**

- Analytics event taxonomy.
- CRM field list.
- Cookie/privacy consent language.
- Designated qualified reviewer sign-off.

**Status:** Open.

## Restricted private-pilot path

A restricted private pilot may proceed only under a written, time-bounded waiver for the specific open gates. It is not a public launch and must not enable public Stripe payments.

- Use named, invited pilot participants only. Record each invitee and the permitted scope outside the repository.
- Complete a synthetic rehearsal first. Do not use customer data in the rehearsal unless it is expressly authorised.
- The designated qualified reviewer controls each release and must approve the pilot report before any delivery.
- Record the waiver owner, affected gates, reason, controls, start and end dates, and review date. Expired waivers do not continue by default.
- Keep Stripe and SMTP absent for rehearsal. If a later pilot payment or delivery action is proposed, obtain separate written approval and reassess the relevant gates before that action.

## First-sale blockers

Public first sale remains blocked because all eight gates are open. In particular, public Stripe must remain disabled until serviceability validation, cancellation/refund paths, GST/tax treatment, production durability, privacy/consent, security evidence, qualified reviewer capacity, and professional boundary decisions are complete and signed off. Valuation readiness also requires opening, reviewing, and merging the 3A branch; implementing PR 3B Decimal FCFF and PR 3C deterministic tables; completing a synthetic service rehearsal; and separately approving live UAT.

## Reference notes

- CA ANZ cautions that members should not unquestioningly rely on automated valuation tools and should critically evaluate outputs and document judgement.
- CA ANZ business valuation resources point to APES 225 in Australia and AES-2 in New Zealand for valuation engagements.
- FMA AI materials emphasise governance, risk management, documentation, data quality, and customer outcomes.
- NZ Privacy Commissioner guidance requires clear purpose, secure handling, appropriate use/disclosure, and cross-border safeguards for personal information.
- Stripe Tax supports GST calculations for New Zealand, but tax registration and product tax treatment must be decided before launch.
