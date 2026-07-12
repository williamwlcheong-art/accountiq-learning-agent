# AccountIQ Commercial MVP Roadmap Context

**Date:** 2026-07-01
**Status:** Reconciled with the implemented Next.js and paid-valuation foundation on 2026-07-12
**Purpose:** Capture the agreed commercial direction before writing implementation plans or changing code.

## Working Decision

Build the first public version as a **Commercial MVP** rather than a pure app refactor or pure marketing launch.

The first public offer should be:

> A fast, fixed-fee Business Valuation Report for SME owners, supported by AI report generation and reviewed by Todd, with forecasting/advisory consultation as the primary upsell.

The business goal is to prove the full commercial loop:

1. Visitor understands the offer.
2. Visitor trusts the service enough to start.
3. Visitor uploads financials.
4. Visitor sees a clear fixed-fee valuation product.
5. Visitor pays.
6. The report is generated, reviewed, and delivered.
7. The customer can return to their dashboard to see the report and purchase history.
8. Todd or the business can upsell consultation services where useful.

## Source of Truth and Launch Gates

The `.planning/` docs are the current project source of truth. Phase 1 security/auth, Phase 2 multi-user isolation, the Next.js frontend migration, the valuation-only self-serve picker, and the initial checkout gate are implemented. `.planning/BACKLOG.md` tracks the remaining paid-valuation slices.

Before the Commercial MVP accepts public users or money, these launch gates must be explicitly satisfied:

1. **Security and isolation verified:** auth, CORS, filename sanitisation, XSS controls, user data isolation, and paid report access are re-verified against the current codebase.
2. **Compliance go/no-go:** disclaimer wording, "reviewed by" wording, refund policy, privacy policy, CAANZ/logo entitlement, and financial-advice boundary are approved.
3. **Pre-payment extraction validation:** uploaded statements are machine-readable enough to proceed before the customer is asked to pay.
4. **Payment failure paths designed:** needs-clarification, failed extraction, failed generation, failed review, cancellation, void, and refund states are defined.
5. **Reviewer capacity defined:** Todd review scope, expected minutes per report, turnaround SLA, and reviewer backup/escalation path are written down.
6. **Database decision made:** choose Postgres before taking live Stripe payments, unless there is a deliberate written decision to accept SQLite risk for a private pilot only.
7. **Frontend production topology verified:** the Next.js app is the primary UI and FastAPI remains the backend of record; verify the same-origin proxy, cookies, uploads, and report links in the deployed topology.
8. **Analytics consent designed:** PostHog/CRM tracking, abandoned-start capture, and financial-document privacy consent are defined before tracking live users.

## Product Focus

Launch with **one paid self-serve product**, not all five report types.

Initial product and upsell path:

1. **Business Valuation Report** — hero product and primary paid conversion.
2. **Forecasting Consultation** — advisor-led upsell from valuation, especially when valuation depends on future performance assumptions.
3. **Funding Readiness / Bank Credit Paper** — defer self-serve sale until valuation quality and fulfillment are proven.

Do not lead with a broad "financial intelligence platform" message. Lead with the specific outcome: a credible business valuation report.

## Positioning Direction

Prefer customer-facing language like:

- "Fixed-fee business valuation reports"
- "Upload your financials and receive a professionally reviewed valuation report"
- "Reviewed by Todd before delivery"
- "Indicative valuation, not financial advice"
- "Optional forecasting and advisory consultation"

Open positioning decision:

- Whether to say "AI-generated with expert review" prominently, or mostly position it as a "fast, fixed-fee valuation service reviewed by Todd."

Current recommendation:

- Use AI honestly but do not make AI the hero. The hero should be speed, fixed fee, clarity, and professional review.
- Suggested wording: "Our software prepares the first draft, then a valuation specialist reviews it before delivery."

## Market Reference Notes

### BizVal Reference

BizVal screenshots suggest useful public-offer patterns:

- Public navigation: Home, Why, Our Service, Our Fees, FAQ, Case Studies, Contact Us, Order Now.
- Pricing cards with fixed fees.
- Trust signal in header: Chartered Accountants Australia + New Zealand.
- Fee-page promises: fixed rate, upfront pricing, no hidden surprises.
- Order flow that explains steps and requests recent financial statements.

Treat BizVal as a market reference, not final AccountIQ pricing or copy.

### Sybiz Reference

Sources checked: `https://sybiz.com/` and `https://sybiz.com/product/sybiz-vision`.

Sybiz is useful as a credibility and information-architecture reference:

- Long operating history and Australian-built trust positioning.
- Navigation by products, solutions, customers, about, and contact.
- Success stories and resources as social proof.
- Clear contact journey for prospects who need help choosing the right solution.

For AccountIQ, translate this into:

- social proof and case-study slots, even if early ones start as anonymised examples;
- a clear "what you get" product section;
- professional/team credibility;
- educational resources that build trust before a purchase;
- a conversion path that supports both self-serve and "talk to us."

## Commercial MVP Customer Flow

Recommended flow:

1. Visitor lands on the marketing homepage.
2. Visitor sees the Business Valuation Report offer, price, inclusions, sample/report preview, Todd/reviewer credibility, FAQ, and CTA.
3. Visitor clicks **Get a Business Valuation**.
4. Visitor creates an account or signs in.
5. Visitor uploads financial statements.
6. Visitor selects **Business Valuation Report**.
7. App performs a pre-payment validation pass: file accepted, text/tables extractable, minimum required periods present, and no obvious unsupported case.
8. Visitor sees price, inclusions, turnaround, disclaimer, review promise, and what happens if the report needs clarification.
9. Visitor pays via Stripe.
10. App creates a purchase/report record visible in their dashboard.
11. Report generation runs.
12. Todd/reviewer reviews the generated report.
13. Reviewer either approves delivery, requests clarification, marks the order unserviceable/refundable, or flags a consultation opportunity.
14. Customer receives report in web viewer and PDF delivery once approved.
15. Customer sees consultation upsell where relevant.

Payment should happen **after upload/product confirmation** and **before full generation/delivery**.

Avoid:

- requiring payment before the customer sees the upload/product flow;
- generating a complete paid report before payment;
- charging before confirming uploaded files are usable enough to proceed;
- relying on email alone without an in-app dashboard record.

## Roadmap Tracks

### Track 1: Marketing Site and Offer

Goal: Create the public demand-capture surface.

Scope:

- Homepage.
- Pricing / "what you get" section.
- Business Valuation Report product page or homepage section.
- Social proof slots: testimonials, anonymised examples, sample report screenshots, Todd credentials.
- FAQ: process, data security, turnaround, report limitations, GST/pricing, refunds, review process.
- Contact / consultation CTA.
- "Get a Business Valuation" primary CTA.

First version can be thin on real social proof, but it must reserve space for proof and avoid looking empty.

### Track 2: Customer App Loop

Goal: Improve the post-signup experience so customers understand where they are.

Scope:

- Better signup/sign-in entry from marketing site.
- Customer dashboard after login.
- Upload flow for financial statements.
- Product selection limited to initial products.
- Report status timeline.
- Report history and purchase history.
- Viewer link for completed reports.

### Track 3: Payment and Fulfillment

Goal: Make payment authoritative and visible.

Scope:

- Stripe Checkout or PaymentIntent flow.
- Server-side webhook confirms payment.
- Purchase record stored against user/report.
- Report generation begins only after confirmed payment.
- Paid report access enforced server-side.
- Email notification on completion.
- Explicit states for `uploaded`, `validated`, `awaiting_payment`, `paid`, `generating`, `awaiting_review`, `needs_clarification`, `approved`, `delivered`, `failed`, `cancelled`, and `refunded`.
- GST/tax handling and Stripe tax configuration decision.

Keep the security rule: never unlock paid report output based only on client-side payment return.

### Track 4: Advisor Review and Upsell

Goal: Make Todd's review operational, not just marketing copy.

Scope:

- Internal reviewer queue.
- Reviewer status: awaiting generation, awaiting review, needs clarification, approved, delivered.
- Reviewer notes.
- Request-clarification action.
- Approve-for-delivery action.
- Mark-unserviceable/refund-needed action.
- Consultation opportunity flag.
- Customer-facing consultation CTA after approval/delivery.

This track is central to trust and future revenue. It also prevents the product from becoming "AI sends financial reports without human review."

The first reviewer spec must include a capacity assumption. Example assumptions to validate:

- Todd reviews every paid valuation report before delivery.
- Target turnaround is one business day after successful generation for normal cases.
- If review requires clarification, the customer sees a dashboard hold state and receives a clear request.
- If the upload/report is not serviceable after payment, the order is cancelled or refunded through a documented process.
- The data model should allow future reviewer assignment, even if Todd is the only reviewer at launch.

### Track 5: Infrastructure and Measurement

Goal: Make the commercial loop deployable and measurable.

Scope:

- Extend the implemented Next.js app with the public site and commercial account surfaces.
- Keep FastAPI for ingestion, report generation, valuation logic, and durable backend work.
- Decide deployment path: Railway is likely acceptable for app/server/database management.
- Decide database path: SQLite for local/dev, Postgres likely for hosted commercial use.
- Add PostHog or equivalent analytics:
  - traffic source and UTM capture;
  - CTA clicks;
  - signup starts/completes;
  - upload starts/completes;
  - payment starts/completes;
  - report delivered;
  - consultation CTA clicks.
- Add CRM/lead capture:
  - contact form leads;
  - consultation requests;
  - abandoned starts where consent/privacy allows.

For paid/public launch, default to Postgres for payment, purchase, report, and reviewer-state durability. SQLite can remain for local development and private testing.

## Explicit Deferrals

Defer these until the valuation product sells:

- A broad marketplace/referral network for local accountants and advisers.
- "Find your nearest advisor" or realestate.co.nz-style search.
- All five report types as public self-serve products.
- White-label/advisor reseller mode.
- Sophisticated CRM automation beyond first lead capture.
- Complex ad experimentation before attribution and conversion events exist.

The local accountant/adviser referral concept is attractive, but it is a second business model. Capture it as a future expansion once demand and fulfillment are proven.

## Unit Economics and Validation Metrics

Before pricing and Stripe copy are finalised, write a one-page assumption set:

- target valuation report price and whether it includes GST;
- estimated AI/report-generation cost per order;
- estimated Todd review minutes per normal report;
- expected clarification/refund rate;
- target gross margin before ad spend;
- maximum acceptable customer acquisition cost for first experiments;
- definition of Commercial MVP validation.

Suggested initial validation threshold:

> 10 paid valuation orders from non-friend users, at least 7 delivered without manual rescue beyond Todd review, at least 2 consultation conversations requested, and no unresolved refund/compliance incidents.

This threshold can change, but the plan needs a measurable target before ad spend scales.

## Upsell Model

Forecasting/advisory should be treated as a manual service upsell in the MVP, not as a fully automated product unless separately planned.

Initial upsell moments:

- after valuation review identifies forecast sensitivity;
- after delivery, with "Book a valuation/forecasting consultation";
- when the reviewer marks a report as needing discussion;
- when the customer asks about funding, sale readiness, or growth planning.

Do not count upsell revenue in MVP economics until there is a priced consultation offer and a booking/payment path.

## Social Proof Plan

Social proof is likely the biggest marketing gap for a new service.

Initial proof options:

- Todd profile and credentials.
- Professional review process explanation.
- Sample anonymised valuation report.
- Before/after example: messy financial statements to clear report output.
- Case-study placeholders that can become real once early users complete reports.
- Trust badges only where permission is clear.
- Transparent limitations and disclaimers, which can increase trust for a financial product.

Avoid fabricated testimonials or implied logos/credentials without permission.

## Open Decisions

1. **AI positioning:** lead with expert-reviewed service, or explicitly lead with AI-assisted delivery?
2. **Initial product count:** settled for MVP as valuation only; forecasting remains an advisor-led upsell.
3. **Pricing:** one fixed valuation price, tiered by company size, or tiered by report depth?
4. **Payment model:** Stripe Checkout upfront after upload, card authorization then delayed capture, or invoice/manual payment for first customers?
5. **Review scope:** Todd reviews every report before delivery, only valuation reports, or exception cases only?
6. **Infrastructure:** choose the production host and complete the Postgres migration before accepting live payments; SQLite remains local/private-pilot only.
7. **Social proof source:** who are the first friendly users or anonymised case studies?
8. **Brand:** remain AccountIQ, create a valuation-specific brand, or make Todd the visible brand anchor?
9. **Commercial validation:** what paid-order threshold proves the MVP enough to scale ads?
10. **Guide reconciliation:** completed for the Next.js architecture; keep guides and `.planning/BACKLOG.md` current as commercial slices land.

## Recommended Immediate Next Plans

Use these planning artifacts and implement the remaining slices in backlog order:

1. **Commercial MVP Architecture Plan** — completed planning artifact
   - Next.js/FastAPI boundaries are decided; production database, storage, and deployment remain gated.

2. **Launch Gates / Compliance Checklist**
   - Security/isolation verification, compliance wording, refund policy, privacy/analytics consent, Postgres decision, frontend architecture decision.

3. **Unit Economics and Validation Metrics**
   - Price, GST, review cost, generation cost, target conversion, CAC guardrail, validation threshold.

4. **Marketing Site / Offer Spec**
   - Homepage sections, product/pricing copy, proof blocks, CTA flow, FAQ, analytics events.

5. **Customer Dashboard + Report History Spec**
   - What a customer sees after login, report status, paid/unpaid states, purchase history.

6. **Stripe + Fulfillment Gate Plan**
   - Payment state machine, webhook handling, purchase records, access control, extraction validation, failed-review/refund paths.

7. **Todd Review Queue Spec**
   - Internal reviewer workflow, statuses, actions, customer communication, upsell prompts.

## Instructions for Peer Review

Please review this context as a senior product/engineering/marketing peer.

Prioritise:

- strategic sequencing risks;
- missing commercial assumptions;
- product/market clarity;
- payment and fulfillment pitfalls;
- trust/social-proof gaps;
- infrastructure risks;
- anything that would make the next implementation plans fragile.

Do not focus on copywriting polish. The goal is to decide what to plan next and what to defer.
