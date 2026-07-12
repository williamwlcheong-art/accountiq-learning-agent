# AccountIQ Public Valuation Offer Page Design

**Date:** 2026-07-12  
**Status:** Approved design; pending written-spec review  
**Scope:** PVM-07 only

## Objective

Create a focused public page at `/valuation` that explains AccountIQ's first paid offer and sends qualified SME owners into the existing account flow. The page must establish trust without publishing an unapproved price, reviewer credential, turnaround promise, testimonial, or regulated-service claim.

The primary conversion action is **Get a Business Valuation**, linking to `/login`. Payment remains inside the authenticated workflow and the public CTA never links directly to Stripe.

## Audience and Promise

The page serves New Zealand and Australian SME owners, founders, directors, and shareholders seeking an initial valuation reference point before a sale, funding discussion, shareholder conversation, or deeper advisory engagement.

The core promise is:

> Upload recent financial statements and receive an indicative business valuation report prepared with software and reviewed before delivery.

The page uses a calm, professional, plain-English voice. AI is disclosed through the phrase “prepared with software” but is not the headline or primary value proposition.

## Chosen Approach

Build one complete offer page inside the existing Next.js application.

This approach provides enough explanation and trust for a financial service while keeping the feature bounded to one route. It is preferable to:

- a minimal teaser page, which would not answer the visitor's trust and limitation questions; or
- a full multi-page marketing site, which would expand into contact capture, analytics, legal pages, reviewer biographies, and other work blocked by unresolved launch inputs.

## Page Structure and Copy Contract

### Header

- AccountIQ wordmark.
- Anchor links to `What you get`, `How it works`, and `FAQ`.
- `Sign in` link to `/login`.
- Primary `Get a valuation` link to `/login`.

The mobile header may simplify the anchor navigation, but both authentication links must remain accessible without a menu script.

### Hero

- Eyebrow: `Fixed-fee business valuation reports`
- H1: `Know what your business may be worth`
- Supporting copy: `Upload recent financial statements and receive an indicative business valuation report prepared with software and reviewed before delivery.`
- Primary CTA: `Get a Business Valuation` → `/login`
- Supporting note: `Indicative only. Not financial advice. Reviewed before delivery.`

The hero is not placed inside a card and does not use abstract finance or novelty-AI imagery. A restrained report-summary visual built from semantic HTML may support the offer without representing a fabricated customer result.

### Trust Points

Show four concise commitments:

- Fixed fee confirmed before payment.
- Reviewed before delivery.
- Web report and PDF access.
- Built for New Zealand and Australian SMEs.

Do not claim upload validation, confidentiality guarantees, turnaround time, professional memberships, or named reviewer credentials until those launch inputs are approved and implemented.

### Use Cases

Explain the three main reasons to seek an indicative valuation:

1. Prepare for a possible business sale.
2. Support an early funding or capital conversation.
3. Establish a reference point for shareholder or succession planning.

The section positions AccountIQ as a practical first step, not a replacement for a full advisory engagement.

### What the Customer Gets

List the delivered report content without making unapproved methodology claims:

- business overview based on supplied information;
- historical financial performance summary;
- normalised earnings adjustments where provided;
- indicative valuation range and key assumptions;
- key risks and matters to consider;
- review before release; and
- web and PDF delivery.

### How It Works

Reflect the workflow that exists today:

1. Create an account.
2. Upload recent financial statements.
3. Complete the valuation questions.
4. See the fixed fee and pay securely.
5. AccountIQ prepares the report.
6. A reviewer checks the report before release.
7. Access the reviewed report from the account page.

Do not say the upload passes serviceability validation before payment until that launch gate is implemented.

### Human Review and Boundaries

Explain that software prepares the first draft and the report is checked before release. State clearly that:

- the report is indicative only;
- it is not financial advice;
- it is not a certified, court-standard, or official valuation; and
- complex or regulated matters require a separate professional engagement.

The page must not identify the reviewer or claim credentials that have not been approved for public use.

### Early-Access Pricing

Use the heading `Early-access fixed-fee offer` and the supporting copy `Your fixed fee is shown before payment.`

Do not publish `$495`, `NZD 2,250 + GST`, or any other amount. The repository currently contains conflicting planning figures, and neither has been approved as public marketing copy. Consultation may be described as optional but must not include an unapproved rate or booking promise.

### FAQ

Include concise answers to:

- Is this financial advice?
- Is this a certified valuation?
- What documents do I need?
- When do I pay?
- Who reviews the report?

Answers must repeat the indicative-only boundary, avoid named credentials, and avoid promising serviceability checks or turnaround times that are not yet implemented.

### Final CTA

Repeat `Get a Business Valuation` linking to `/login`, with a nearby `Already have an account? Sign in` link to the same destination.

## Architecture and Files

The feature is presentation-only and does not add backend routes, persistence, analytics, forms, or client-side state.

Expected implementation files:

- Create `web/app/valuation/page.tsx` for semantic page markup and page-specific metadata.
- Modify `web/app/globals.css` for namespaced `.marketing-*` styles and responsive layout.
- Create `web/e2e/valuation.spec.ts` for public-route, messaging, CTA, forbidden-claim, and responsive checks.
- Update planning state and backlog files when the PR opens and merges.

Keep the copy with the page for this bounded slice. A separate marketing-copy model and component library would add indirection before a second marketing page exists.

The existing `/` behavior remains unchanged: unauthenticated users are redirected to `/login`, and authenticated users are routed to their application surface. PVM-07 introduces `/valuation` without changing authentication routing.

## Visual Direction

- Professional financial-service character rather than generic AI SaaS styling.
- Restrained navy, blue, white, and soft neutral palette using existing design tokens where practical.
- Strong typographic hierarchy with a readable maximum line length.
- Semantic report/table motif as the primary visual proof device.
- Moderate spacing and modest headline scale.
- No gradients, stock photography, fabricated logos, fake testimonials, or decorative financial charts presented as customer evidence.

The page must remain usable from 320px width and must not introduce horizontal overflow.

## Accessibility

- One H1 and logical heading order.
- Semantic `header`, `main`, `section`, `nav`, and `footer` landmarks.
- Skip link to main content.
- Visible keyboard focus states.
- Sufficient color contrast.
- Anchor targets receive scroll margin so headings are not obscured.
- Decorative report imagery is hidden from assistive technology; meaningful content remains text.
- Links use descriptive accessible names.

## Error Handling and Degraded Behavior

The page has no data dependency, so it renders without FastAPI, Stripe, analytics, or JavaScript. All navigation uses ordinary links. If authentication is unavailable after a CTA click, the existing login/authentication flow owns that error state.

## Testing

Playwright must verify:

- `/valuation` is publicly accessible without redirecting to `/login`;
- the H1, early-access pricing language, indicative-only boundary, and review promise are visible;
- primary and sign-in links resolve to `/login` and no CTA points to Stripe;
- no unapproved numeric price is published;
- the page does not positively claim the report is certified, guaranteed, official, instant, court-standard, or financial advice;
- the key page landmarks and heading hierarchy are present; and
- the page has no horizontal overflow at a mobile viewport.

Run frontend lint, typecheck, production build, the focused valuation test, and the full Playwright suite before merge.

## Explicitly Out of Scope

- Replacing the authenticated `/` redirect behavior.
- Contact or consultation forms.
- Analytics or consent management.
- PostHog integration.
- Legal, privacy, refund, or terms pages.
- Publishing a final price or GST treatment.
- Reviewer biography, credentials, memberships, or logos.
- Sample-report downloads or fabricated report results.
- Pre-payment serviceability validation.
- Changes to Stripe checkout.
- A broader multi-product marketing site.

## Acceptance Criteria

- A first-time visitor can understand the offer, intended use, review step, pricing model, and limitations on one page.
- The primary CTA enters the existing account flow rather than payment.
- The page contains no unapproved price, proof, credential, timing, privacy, or regulatory claim.
- The current authenticated application routes remain unchanged.
- The implementation is accessible, responsive, static, and covered by browser tests.
