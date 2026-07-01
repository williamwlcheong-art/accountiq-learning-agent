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
