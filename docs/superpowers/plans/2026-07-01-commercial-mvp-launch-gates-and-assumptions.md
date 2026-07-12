# Commercial MVP Launch Gates And Assumptions Implementation Plan

**Execution status:** Completed planning artifact. The launch-gate, commercial-assumption, architecture-decision, and product-marketing files now exist. Do not re-run the guide replacement steps; use `.planning/BACKLOG.md` and the resulting documents as the current source of truth.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the non-code gates, commercial assumptions, and planning sequence required before AccountIQ accepts public users or live Stripe payments.

**Architecture:** This is a planning and governance phase, not an application-code phase. It turns the Commercial MVP context into launch gates, decision records, source-of-truth cleanup, and plan sequencing for the next implementation workstreams.

**Tech Stack:** Markdown planning docs, `.planning/` project source of truth, Next.js/FastAPI/Postgres/Stripe decisions for later implementation, official compliance references.

---

## Source Context

- Commercial MVP context: `docs/superpowers/specs/2026-07-01-commercial-mvp-roadmap-context.md`
- Public funnel backlog: `.planning/phases/999.1-public-facing-commercial-funnel-advisor-review/999.1-CONTEXT.md`
- Current roadmap source of truth: `.planning/ROADMAP.md`
- Current product source of truth: `.planning/PROJECT.md`
- Product marketing context: `.agents/product-marketing-context.md`

## External References To Check During Planning

- CA ANZ automated valuation and AI standards risk: `https://www.charteredaccountantsanz.com/news-and-analysis/insights/research-and-insights/could-automated-valuation-tools-and-ai-see-valuers-fall-foul-of-professional-standards`
- CA ANZ business valuation professional framework: `https://www.charteredaccountantsanz.com/member-services/technical/business-valuation`
- FMA AI in financial services governance and risk: `https://www.fma.govt.nz/news/all-releases/media-releases/understanding-artificial-intelligence-in-financial-services/`
- NZ Privacy Commissioner privacy principles: `https://www.privacy.org.nz/privacy-principles/`
- NZ Privacy Commissioner cross-border disclosure principle: `https://www.privacy.org.nz/privacy-principles/12/`
- Stripe Tax New Zealand GST support: `https://docs.stripe.com/tax/supported-countries/asia-pacific/collect-tax?tax-jurisdiction-asia-pacific=new-zealand`

## Gate Summary

The next roadmap should proceed in this order:

1. Source-of-truth cleanup.
2. Launch gates and compliance checklist.
3. Commercial assumptions and validation metrics.
4. Production infrastructure decision: Postgres, durable storage, hosting, backups, and deployed Next.js/FastAPI routing.
5. Marketing site and product-offer spec.
6. Customer dashboard and report-history spec.
7. Stripe and fulfillment state-machine plan.
8. Todd review queue plan.
9. Implementation.

No public launch or live Stripe payments should occur until gates 1-4 are complete.

---

### Task 1: Reconcile Source Of Truth

**Files:**

- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`
- Read: `.planning/PROJECT.md`
- Read: `.planning/ROADMAP.md`
- Read: `.planning/STATE.md`

- [ ] **Step 1: Confirm current phase state from `.planning/`**

Run:

```bash
sed -n '1,120p' .planning/ROADMAP.md
sed -n '1,90p' .planning/STATE.md
sed -n '1,120p' .planning/PROJECT.md
```

Expected: Phase 1 Security/Auth, Phase 2 Multi-User Isolation, and the Next.js migration are complete; `.planning/BACKLOG.md` tracks the paid Valuation Advisory MVP slices.

- [ ] **Step 2: Update guide files to remove stale "ready for Phase 1" language**

Replace any guide-file claims that the project is initialized or still missing authentication with current wording:

```markdown
**Current state:** The Next.js migration and initial paid-valuation checkout gate are implemented. Remaining commercial work is tracked in `.planning/BACKLOG.md`; public-funnel planning is captured in `docs/superpowers/specs/2026-07-01-commercial-mvp-roadmap-context.md`.
```

Expected: Future agents no longer read `CLAUDE.md` or `AGENTS.md` and conclude that authentication, CORS, path traversal, and XSS fixes are unbuilt.

- [ ] **Step 3: Add external-launch gates to the guide files**

Insert a short "Before Public Launch" section:

```markdown
## Before Public Launch

The current `.planning/` docs say Phase 1 security/auth and Phase 2 user isolation are complete, but these must still be re-verified before any public launch or live Stripe payments.

Commercial MVP launch gates:
- Re-verify auth, CORS, filename sanitisation, XSS controls, user data isolation, and paid report access.
- Complete compliance review for disclaimer wording, "reviewed by" wording, refund policy, privacy policy, CAANZ/logo entitlement, and financial-advice boundary.
- Validate uploaded statements before payment.
- Define failed extraction, failed generation, needs-clarification, cancellation, void, and refund states.
- Define Todd/reviewer capacity and turnaround SLA.
- Decide Postgres vs SQLite for live paid launch.
- Verify the implemented Next.js/FastAPI split in the production deployment topology.
- Define analytics consent before PostHog/CRM tracking.
```

- [ ] **Step 4: Verify guide cleanup**

Run:

```bash
rg -n "Initialized|ready for Phase 1|No authentication|Wildcard CORS|Unsanitised filename|XSS via innerHTML" CLAUDE.md AGENTS.md
```

Expected: no stale "Phase 1 still unbuilt" claims remain.

### Task 2: Complete Launch Gates Checklist

**Files:**

- Create: `.planning/commercial/LAUNCH-GATES.md`
- Read: `docs/superpowers/specs/2026-07-01-commercial-mvp-roadmap-context.md`

- [ ] **Step 1: Create launch-gates directory**

Run:

```bash
mkdir -p .planning/commercial
```

- [ ] **Step 2: Write `.planning/commercial/LAUNCH-GATES.md` with this structure**

```markdown
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
```

- [ ] **Step 3: Verify no gate has a fake pass**

Run:

```bash
rg -n "Status: Passed|Status: Complete|Status: Done" .planning/commercial/LAUNCH-GATES.md
```

Expected: no output. Gates start open until evidence exists.

### Task 3: Complete Commercial Assumptions

**Files:**

- Create: `.planning/commercial/COMMERCIAL-ASSUMPTIONS.md`
- Read: `.agents/product-marketing-context.md`

- [ ] **Step 1: Write `.planning/commercial/COMMERCIAL-ASSUMPTIONS.md` with this structure**

```markdown
# Commercial MVP Assumptions

**Last updated:** 2026-07-01
**Status:** Draft assumptions for validation.

## Offer

**Hero product:** Business Valuation Report.
**Primary upsell:** Forecasting/advisory consultation.
**Deferred products:** Bank Credit Paper, Capital Raising Document, Information Memorandum, advisor marketplace, local accountant referral search.

## Positioning

Lead with a fast, fixed-fee, professionally reviewed valuation service.

Do not make AI the headline. Use transparent supporting language:

> Our software prepares the first draft, then a valuation specialist reviews it before delivery.

## Initial Pricing Assumption

Pricing is not final. Use this as a planning placeholder until Todd/Dave approve actual pricing:

| Product | Draft price | Notes |
|---------|-------------|-------|
| Business Valuation Report | NZD 2,250 + GST | Anchored to BizVal-style market pricing, not final |
| Forecasting/advisory consultation | NZD 350-500 + GST per hour or fixed package | Manual upsell, not self-serve MVP |

## Unit Economics To Validate

| Metric | Draft assumption | Owner |
|--------|------------------|-------|
| AI/report generation cost per valuation | Under NZD 50 | Dave |
| Todd review time per normal report | 30-45 minutes | Todd |
| Manual support time per normal order | 15-30 minutes | Dave/Todd |
| Clarification rate | Under 25% | To measure |
| Refund/unserviceable rate | Under 10% | To measure |
| Gross margin before ad spend | Above 70% | Dave/Todd |
| Max early CAC test | Under 25% of gross margin | Dave |

## Validation Threshold

Commercial MVP is validated when:

- 10 paid valuation orders come from non-friend users.
- At least 7 are delivered without manual rescue beyond Todd review.
- At least 2 customers request a consultation conversation.
- No unresolved refund, privacy, security, or compliance incident remains open.
- Customer acquisition source is known for at least 8 of 10 orders.

## First Launch Motion

Use a controlled early-access launch rather than open ads immediately:

1. Internal/friendly review with sample files.
2. Invite 3-5 friendly business owners or advisers.
3. Offer early-access pricing or manual invoice if Stripe is not ready.
4. Collect objections, clarification frequency, and review time.
5. Only then run small paid traffic tests with PostHog attribution.

## Paid Ads Guardrail

Do not scale ads until:

- Launch gates 1-8 are passed or explicitly waived for private pilot.
- PostHog/source attribution is live.
- Stripe/payment tracking is live or manual invoice tracking is reliable.
- The landing page has at least one credible proof asset.
- Review capacity can handle expected order volume.

## Social Proof Plan

Initial proof assets:

- Todd profile and credentials.
- Sample anonymised valuation report.
- "How review works" process section.
- Before/after example from financial statements to report output.
- Early-access case study after permission.

Do not use fabricated testimonials, customer logos, or CAANZ marks without permission.

## Known Risks

| Risk | Mitigation |
|------|------------|
| AI trust risk | Lead with professional review and transparent AI role |
| Professional standards risk | Compliance gate and Todd review checklist |
| Payment before serviceability risk | Pre-payment extraction validation |
| Refund/review failure risk | Explicit state machine and refund policy |
| Single reviewer bottleneck | Capacity assumptions and future reviewer assignment field |
| Privacy risk | Consent language, data-flow map, analytics restrictions |
| Infrastructure durability risk | Postgres before live payments |
```

- [ ] **Step 2: Verify assumptions are labelled as draft**

Run:

```bash
rg -n "Draft|not final|To measure|not legal" .planning/commercial/COMMERCIAL-ASSUMPTIONS.md
```

Expected: output shows price and metrics are not final promises.

### Task 4: Create Product Marketing Context

**Files:**

- Create: `.agents/product-marketing-context.md`

- [ ] **Step 1: Confirm context exists**

Run:

```bash
test -f .agents/product-marketing-context.md && sed -n '1,260p' .agents/product-marketing-context.md
```

Expected: context captures product overview, target audience, personas, pain points, differentiation, objections, customer language, voice, proof points, and goals.

- [ ] **Step 2: Review missing fields with Dave/Todd**

Ask for corrections to:

- Todd credentials and exact public bio.
- Whether pricing should be NZD, AUD, or both.
- Whether Business Valuation Report is sold under AccountIQ or a valuation-specific brand.
- First friendly users or anonymised proof sources.
- Exact consultation upsell offer.

### Task 5: Decide Next Implementation Plan Order

**Files:**

- Read: `.planning/commercial/LAUNCH-GATES.md`
- Read: `.planning/commercial/COMMERCIAL-ASSUMPTIONS.md`
- Read: `docs/superpowers/specs/2026-07-01-commercial-mvp-roadmap-context.md`

- [ ] **Step 1: Confirm plan order**

Use this implementation-plan order unless Dave explicitly changes it:

1. `2026-07-01-marketing-site-offer.md`
2. Customer dashboard and report history slice from `.planning/BACKLOG.md`
3. Pre-payment serviceability validation plan
4. Remaining Stripe failure/refund state-machine work
5. Todd review queue plan

- [ ] **Step 2: Stop before code**

Do not implement application code until Dave approves the launch gates and commercial assumptions.

### Task 6: Verification And Commit

**Files:**

- Verify: `CLAUDE.md`
- Verify: `AGENTS.md`
- Verify: `.agents/product-marketing-context.md`
- Verify: `.planning/commercial/LAUNCH-GATES.md`
- Verify: `.planning/commercial/COMMERCIAL-ASSUMPTIONS.md`
- Verify: `docs/superpowers/plans/2026-07-01-commercial-mvp-launch-gates-and-assumptions.md`

- [ ] **Step 1: Check Markdown whitespace**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 2: Confirm changed files**

Run:

```bash
git status --short
```

Expected changed files are only planning/guide/context files.

- [ ] **Step 3: Commit**

Run:

```bash
git add CLAUDE.md AGENTS.md .agents/product-marketing-context.md .planning/commercial/LAUNCH-GATES.md .planning/commercial/COMMERCIAL-ASSUMPTIONS.md docs/superpowers/plans/2026-07-01-commercial-mvp-launch-gates-and-assumptions.md
git commit -m "docs: define commercial mvp launch gates"
```
