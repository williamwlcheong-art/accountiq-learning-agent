# AccountIQ Marketing Site / Offer Spec

**Date:** 2026-07-01
**Status:** Draft spec for future implementation
**Depends on:** Commercial MVP architecture decisions and launch gates

## Purpose

Create the first public marketing surface for AccountIQ's Commercial MVP: a clear, trust-building homepage and offer page for a fixed-fee Business Valuation Report.

The site should convert qualified SME owners into the order flow without overclaiming, overexplaining AI, or implying a certified/regulated valuation product.

## Primary Offer

**Hero product:** Business Valuation Report.

**Positioning:** Fast, fixed-fee, professionally reviewed indicative business valuation report.

**Primary CTA:** Get a Business Valuation.

**Secondary CTA:** Talk to Us / Book a Consultation.

**Primary upsell:** Forecasting/advisory consultation after report review or delivery.

## Messaging Principle

Do not make AI the headline.

Preferred framing:

> Upload your financial statements and receive a fixed-fee indicative business valuation report, prepared with software and reviewed before delivery.

Supporting explanation:

> Our software prepares the first draft, then a valuation specialist reviews it before delivery.

Avoid:

- "Instant valuation"
- "Certified valuation"
- "Financial advice"
- "Guaranteed valuation"
- "Court-standard"
- "AI replaces your adviser"
- "Official valuation"

## Target Visitor

The first site is for SME owners, founders, directors, and shareholders who want to understand what their business may be worth before a sale, funding conversation, shareholder discussion, or deeper advisory engagement.

The visitor is likely anxious about:

- whether their financial data is safe;
- whether AI output is trustworthy;
- whether the report is credible enough to use;
- whether they will get trapped into a large advisory engagement;
- whether the process is clear and fixed-fee.

## Page Set

The Commercial MVP should start with a small public site:

1. **Homepage** — main conversion surface.
2. **Business Valuation Report** — optional dedicated detail page if homepage becomes too dense.
3. **How It Works** — can be a homepage section first.
4. **FAQ** — can be a homepage section first.
5. **Contact / Consultation** — simple lead capture.
6. **Legal pages** — privacy policy, terms/refund policy, disclaimer page once approved.

Do not build a broad multi-product marketing site yet. Defer separate pages for Bank Credit Paper, Information Memorandum, Capital Raising Document, advisor marketplace, and referral search.

## Homepage Structure

### 1. Header

Required nav:

- Business Valuation
- How It Works
- Pricing
- FAQ
- Contact
- Sign In
- Primary CTA: Get a Valuation

Keep nav concise. Do not include "Platform", "All Products", or broad SaaS language yet.

### 2. Hero

Goal: make the offer obvious within five seconds.

Recommended hero content:

- Eyebrow: Fixed-fee business valuation reports
- H1: Know what your business may be worth
- Supporting copy: Upload recent financial statements and receive an indicative valuation report prepared with software and reviewed before delivery.
- Primary CTA: Get a Business Valuation
- Secondary CTA: Talk to Us
- Trust note: Indicative only. Not financial advice. Reviewed before delivery.

Visual direction:

- Use real product/report imagery when available: sample report pages, report dashboard, valuation summary table.
- Do not use abstract finance stock imagery as the main proof.
- Do not put hero content in a card.

### 3. Trust / Proof Bar

Initial version may not have testimonials. It should still show credible proof elements:

- Reviewed before delivery.
- Fixed fee before payment.
- Upload validation before payment.
- Privacy-conscious handling of financial statements.
- Optional consultation after delivery.

Only use logos, professional memberships, or credentials where permission is clear.

### 4. Problem Section

Frame the customer pain:

- You need valuation clarity before a sale, funding conversation, or shareholder decision.
- Traditional advisory work can feel slow or expensive before you know where you stand.
- DIY calculators are fast but often too generic.
- AccountIQ gives you a practical first step.

### 5. Product / What You Get

Business Valuation Report inclusions:

- Business overview based on provided information.
- Historical financial performance summary.
- Normalised earnings / EBITDA adjustments where provided.
- DCF-style valuation analysis where supported.
- Valuation range and key assumptions.
- Indicative-only disclaimer.
- Reviewer check before delivery.
- PDF/web report delivery.

Need compliance review before publishing exact methodology claims.

### 6. How It Works

Use the real architecture flow:

1. Create account.
2. Upload financial statements.
3. We validate whether the files are usable.
4. Confirm fixed fee and pay securely.
5. Report is generated.
6. Todd/reviewer checks it before release.
7. Receive report and optional consultation prompt.

Important copy:

- If uploaded files are not serviceable, customer should see that before payment.
- If review requires clarification, customer sees that in the dashboard.

### 7. Pricing

Show pricing only if Todd/Dave approve final price.

Draft planning placeholder:

- Business Valuation Report: NZD 2,250 + GST

Pricing section should include:

- fixed fee;
- what is included;
- what is not included;
- refund/cancellation policy link once approved;
- consultation upsell as separate optional service.

If pricing is not approved, use:

> Early-access pricing available after upload validation.

Do not publish draft pricing as final.

### 8. Review / Human Oversight

This is a core trust section.

Explain:

- software prepares the first draft;
- a reviewer checks before delivery;
- the report is indicative, not a substitute for regulated advice or a certified valuation;
- complex cases may require clarification or a separate advisory engagement.

Need Todd-specific bio and credentials from Dave/Todd before final copy.

### 9. Sample Output

Use proof assets:

- anonymised sample report screenshot;
- sample valuation summary table;
- "from financial statements to report" example;
- disclaimer visible in sample.

Do not use fabricated customer cases.

### 10. FAQ

Initial FAQ questions:

- Is this financial advice?
- Is this a certified valuation?
- Who reviews the report?
- What documents do I need?
- What happens if my files cannot be processed?
- When do I pay?
- How long does it take?
- Is my financial data safe?
- Can I talk to someone after receiving the report?
- Do you support Australia and New Zealand?

### 11. Final CTA

Repeat the primary CTA:

- Get a Business Valuation

Secondary CTA:

- Book a Consultation

## CTA Destination

Primary CTA should eventually route to:

```text
/signup?intent=business-valuation
```

or, for signed-in users:

```text
/dashboard/new-valuation
```

The CTA must not route directly to Stripe. The customer must upload and pass serviceability validation before payment.

## Analytics Events

Allowed marketing-site events:

- `page_viewed`
- `valuation_cta_clicked`
- `secondary_consultation_cta_clicked`
- `pricing_viewed`
- `faq_opened`
- `sample_report_clicked`
- `contact_form_started`
- `contact_form_submitted`

Allowed properties:

- page path;
- CTA location;
- UTM source/medium/campaign;
- broad visitor type if selected by user;
- no financial data.

Forbidden properties:

- document text;
- uploaded filenames;
- company financial metrics;
- valuation values;
- report content;
- free-text form answers unless explicitly consented and necessary.

## Contact / CRM Capture

Minimum fields:

- name;
- email;
- business name;
- reason for enquiry;
- consent checkbox for contact.

Do not collect financial documents through the public contact form. Financial documents belong in authenticated upload flow with upload consent.

## Compliance Dependencies

Do not publish final site copy until these are resolved:

- indicative-only disclaimer;
- "reviewed by" wording;
- Todd bio/credential claims;
- CAANZ/logo usage permission;
- refund/cancellation policy;
- privacy policy and upload consent;
- AI/data-use disclosure;
- GST/pricing wording.

## Design Direction

The page should feel like a professional financial service, not a generic AI SaaS launch page.

Use:

- restrained color palette;
- report/table visuals;
- clear content hierarchy;
- modest confidence;
- direct language;
- visible process and safeguards.

Avoid:

- novelty AI visuals;
- exaggerated gradients;
- oversized startup hero copy;
- fake logos/testimonials;
- vague "transform your business" language.

## Out Of Scope

- Multi-product catalogue.
- Advisor marketplace.
- "Find your local accountant" search.
- Product Hunt launch page.
- Blog/resource library.
- Automated consultation booking/payment.
- All five report types.

## Open Inputs Needed

- Todd's exact public bio and credentials.
- Final product name: AccountIQ Business Valuation Report vs a valuation-specific brand.
- Final launch price and currency.
- Approved disclaimer/refund/privacy language.
- First sample report asset.
- First friendly-user proof source.

## Acceptance Criteria

- A visitor can understand the offer, price model, review promise, and limitations within one page.
- The primary CTA routes to signup/order intent, not directly to payment.
- The site reserves space for social proof without fabricating it.
- AI is disclosed honestly but not made the primary value proposition.
- The site avoids certified/regulated-advice claims unless separately approved.
- Analytics events avoid financial or sensitive content.
