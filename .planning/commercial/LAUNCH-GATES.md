# Commercial MVP Launch Gates

**Last updated:** 2026-07-01
**Status:** Draft gates. Not legal, accounting, tax, or financial advice.

## Rule

AccountIQ should not accept public users or live Stripe payments until every Launch Gate is either passed or explicitly waived for a private pilot.

## Gate 1: Security And User Isolation

**Why it matters:** Paid reports and financial statements are sensitive. Access control failures would be severe.

**Must verify:**

- Auth/session cookies work through the implemented Next.js same-origin proxy.
- CORS is restricted for write endpoints.
- Uploaded filenames are sanitised with `Path(filename).name`.
- Frontend renders user/AI text safely.
- User A cannot access User B companies, documents, purchases, reports, PDFs, or reviewer messages.
- Non-admin users cannot access admin routes.

**Evidence required:**

- Test command and passing result.
- Manual browser smoke for login, logout, dashboard, upload, report view.
- Route inventory showing protected routes.

**Status:** Open.

## Gate 2: Compliance And Professional Boundary

**Why it matters:** Business valuation output, AI assistance, and professional-review claims create accounting/professional-standards risk.

**Must decide:**

- Is the first product an indicative valuation only?
- Does any output risk being regulated financial advice?
- What can "reviewed by Todd" legally and professionally mean?
- Can CAANZ or other logos/credentials be used?
- What disclaimer appears on site, checkout, report viewer, PDF, and email?
- What records must Todd keep to show professional judgement over AI output?

**Evidence required:**

- Written disclaimer approved by a qualified reviewer.
- Decision on CAANZ/logo usage.
- Written review checklist for Todd.
- Refund/cancellation policy approved before Stripe launch.

**Status:** Open.

## Gate 3: Privacy, Confidentiality, And Data Use

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

**Status:** Open.

## Gate 4: Pre-Payment Serviceability Validation

**Why it matters:** Customers should not pay before the app knows uploaded financials are likely usable.

**Must verify before Stripe:**

- File type accepted.
- File has extractable text/tables or OCR result.
- Minimum recent period data is present.
- Business name and fiscal period can be inferred or confirmed.
- Unsupported cases are stopped before payment with a contact-us path.

**Evidence required:**

- Validation status in dashboard.
- Validation failure copy.
- Test fixtures for valid PDF, scanned PDF, Excel, Word, and unsupported upload.

**Status:** Open.

## Gate 5: Payment And Refund State Machine

**Why it matters:** Stripe must be authoritative and paid access must survive retries, failures, and review holds.

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

- State transition diagram.
- Webhook handling plan.
- Refund/void decision for post-payment unserviceable orders.
- GST/tax handling decision.

**Status:** Open.

## Gate 6: Reviewer Capacity And SLA

**Why it matters:** "Fast" and "reviewed by Todd" create a delivery promise that must match real capacity.

**Must decide:**

- Does Todd review every valuation before delivery?
- Target review time per report.
- Target customer turnaround.
- What happens after 5, 10, or 20 concurrent paid orders?
- Who can be a backup reviewer?
- What internal checklist is required before approval?

**Evidence required:**

- Reviewer checklist.
- SLA wording for website and checkout.
- Admin queue fields for assignment and status.

**Status:** Open.

## Gate 7: Production Infrastructure

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

**Status:** Open.

## Gate 8: Measurement And CRM Consent

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

**Status:** Open.

## Reference Notes

- CA ANZ cautions that members should not unquestioningly rely on automated valuation tools and should critically evaluate outputs and document judgement.
- CA ANZ business valuation resources point to APES 225 in Australia and AES-2 in New Zealand for valuation engagements.
- FMA AI materials emphasise governance, risk management, documentation, data quality, and customer outcomes.
- NZ Privacy Commissioner guidance requires clear purpose, secure handling, appropriate use/disclosure, and cross-border safeguards for personal information.
- Stripe Tax supports GST calculations for New Zealand, but tax registration and product tax treatment must be decided before launch.
