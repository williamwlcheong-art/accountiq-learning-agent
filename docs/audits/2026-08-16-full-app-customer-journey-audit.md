# AccountIQ full-app customer journey audit

Date: 16 August 2026  
Status: Read-only audit of the current local working tree  
Primary market assumed: New Zealand SME owners seeking an indicative, human-reviewed business valuation

## Executive verdict

AccountIQ has a credible valuation engine and a promising public offer page, but it is not ready for public acquisition or public Stripe payments. The main risk is not the visual design of the landing page. It is the continuity and trust of the whole journey around it.

The most serious functional defect is the real Stripe return path. The wizard redirects to Stripe before saving the report identifier, and it does not interpret the success or cancellation query parameters on return. A buyer can pay and then see the initial upload screen with no acknowledgement or reliable way back to the report.

The next biggest issue is product coherence. Google discovery, marketing, authentication, intake, payment, human review, delivery, and the returning-user experience feel like partially connected systems. The current `/account` page is useful purchase history, but it is not a dashboard. The current intake asks a business owner to make too many analyst-level decisions in one long, non-resumable form.

Recommendation: keep public checkout off. First make one complete valuation journey safe and trustworthy for a small invited NZ pilot. In parallel, establish the public-site, legal, proof, and measurement foundations. Scale SEO or paid search only after the pilot demonstrates that the journey converts and can be serviced reliably.

## Method

This audit combined:

- a live browser review at desktop and mobile sizes;
- a source review of public, authentication, wizard, payment, report, account, admin-review, email, and configuration paths;
- a review of the commercial assumptions, launch gates, backlog, and product scope;
- an independent UX assessment;
- an independent deterministic frontend detector and responsive-browser assessment;
- an independent SEO/GEO and acquisition assessment; and
- a read-only Cursor CLI review using Grok 4.6, with its findings checked against the source before inclusion.

Authenticated screens were assessed primarily from source because the audit did not create or mutate customer data. Production performance, rankings, Search Console data, field Core Web Vitals, and real Stripe behaviour were not exercised; those remain unverified.

## Current-state customer journey

| Stage | What exists now | Main gap | Recommended target |
|---|---|---|---|
| Discover | One public `/valuation` page with good semantic structure and a clear indicative-valuation proposition | `/` redirects anonymous visitors to `/login`; no sitemap, robots policy, canonical architecture, social metadata, Search Console, or content cluster | Make `/` the stable public commercial home, or make it explicitly route to the canonical offer; publish only approved public pages and submit a public-only sitemap |
| Evaluate | Clean hero, inclusions, process, FAQs, human-review and limitation language | No approved public price, GST, turnaround, reviewer identity, sample report, customer proof, company identity, privacy/security explanation, or contact path | Answer the purchase-critical questions before requesting files; add a redacted sample, named reviewer and credentials, approved policies, and a human fallback |
| Start | Repeated “Get a valuation” calls to action | Every CTA opens a sign-in-first screen, so new-user intent is lost | Send new prospects to `/signup?intent=business-valuation`; keep sign-in separate and preserve the next step through authentication |
| Register/sign in | Basic registration and sign-in with labelled fields and good password validation | No password reset, verification, visible account security, terms/privacy acknowledgement, or consistent marketing-to-product branding | Add recovery and account-security basics; retain offer context and trust copy at the account gate |
| Upload | Business name plus PDF/Excel/Word upload; safe filename handling; ingestion and readiness checks | Sensitive statements are requested before price/trust is established; no size cap; no data-use/retention reassurance; no save/resume | Add upload limits, privacy reassurance, file lifecycle details, support, and a persisted draft/order before upload begins |
| Serviceability | Extraction/readiness and authority-conflict logic can stop unsuitable cases before payment | The product tells some users an adviser must help but offers no adviser/contact route | Add a visible assisted-resolution path and capture these as qualified service leads |
| Product selection | Valuation Advisory is enabled | Four disabled future products make the MVP feel unfinished | Remove the picker for the one-product self-serve journey; introduce other services later as genuine adviser-led offers |
| Intake | Business context, derived financials, assumptions, normalisations, investment and risk ratings | A long single page exposes valuation jargon, 40 risk choices, weak progress feedback, and no draft persistence | Split into saved steps, translate terms, prefill recommendations, progressively disclose advanced inputs, and show time/progress |
| Confirm | Fee, source coverage, assumptions and human review are shown before payment; clarification is explicit that no payment was taken | No approved GST, turnaround, refund, terms or data-use acknowledgement | Present the complete commercial contract in plain language and link approved policies |
| Stripe | Checkout creation, idempotency, amount/currency checks and webhook state handling exist | The report ID is saved after the redirect branch; success/cancel returns are not handled; repeat starts can create another order | Persist the order before redirect, bind it to return URLs, render explicit return states, and offer resume/complete-payment actions |
| Generate/review | Paid valuation generation, status polling, human-review queue, draft viewing and approval exist | Reviewer can only approve; no checklist, notes UI, clarification/rejection/unserviceable/refund workflow, named owner or SLA | Add a review workbench, defined outcomes, customer messages, escalation/refund handling, owner and due time |
| Delivery | Ready email, HTML view, PDF download, retry/refund status copy | Email deep-link can produce an unauthenticated API error; no payment-received message or clear delivery time | Link email into an authenticated order page, acknowledge payment immediately, and show an honest timeline |
| Return | `/account` lists paid purchases and completed report actions | No active-order dashboard, unfinished drafts, company/document reuse, receipts/GST invoices, support, account security, deletion/export or repeat workflow | Build a lightweight order/report dashboard, not a financial-ratio dashboard |

## What the dashboard should mean

The product plan deliberately excludes an automated financial-ratio dashboard. That remains sensible for the paid Valuation Advisory MVP. The missing dashboard is an operational customer home, not another analytics product.

A useful first dashboard should show:

1. the active valuation and its timeline: draft, awaiting payment, generating, human review, ready, clarification, refund or failed;
2. the next action, including resume intake, complete payment, answer a reviewer, or open/download the report;
3. previous reports and receipts/invoices;
4. saved company identity and explicitly reusable documents/assumptions;
5. support, account security, data export and deletion controls; and
6. a clear path to start a new valuation without losing the existing one.

It does not initially need charts, benchmarking, portfolio analytics, or a multi-product marketplace.

## Priority findings

### P0 — public-launch blockers

#### 1. Repair the paid Stripe return and recovery path

Persist the report/order identifier before leaving AccountIQ. Add the order or checkout session to both Stripe return URLs. On return, show “Payment received—confirming” or “Checkout cancelled—no charge,” restore the correct order, and give account-level actions for “Complete payment” and “View status.” Add a real Stripe integration test because the E2E mode bypasses the redirect branch that contains the defect.

#### 2. Keep public acquisition and payments disabled until launch gates close

The repository's launch-gate document says all eight gates remain open and public users/payments must not be accepted while any remains open. The gate areas are user isolation, professional boundaries, privacy/data use, serviceability, payment/refund/tax, reviewer capacity, production infrastructure, and measurement/consent. Some implementation details in the document are now stale after recent payment fixes, so re-audit and update each gate rather than treating the document as a timeless checklist.

#### 3. Approve the commercial and legal offer

Decide and document the public price, NZD/GST treatment, invoice/receipt behaviour, delivery target, human-review standard, refund/cancellation policy, serviceability handling, disclaimer, privacy policy, AI/offshore processing disclosure, retention/deletion policy, and support/escalation route. The code default is NZ$495, while the commercial assumptions contain a draft NZ$2,250 + GST figure. Neither should be promoted until the offer owner approves it.

#### 4. Replace prototype production dependencies

SQLite and local uploads/exports remain the system of record. Before public paid use, move to the approved production database and durable private object storage, define backup/restore and deletion procedures, and run same-origin cookie, CORS, authentication and file-isolation checks in the deployed environment.

#### 5. Close core security and data-handling gaps

Add a server-enforced upload-size limit, production-safe cookie defaults, startup rejection for empty/example JWT secrets, authentication rate limiting, generic server errors, private production API documentation, and non-sensitive health responses. Add password recovery, deletion/export, and explicit data-use consent. Remove production ability to write live provider secrets into a local `.env` file from the admin UI.

### P1 — make the invited pilot trustworthy and serviceable

#### 6. Freeze NZ market intelligence into each paid report input

The NZ market-intelligence package is useful: it is a registered, dated, cited quarterly snapshot that supplies controlled market context to the valuation. The recent work correctly fails closed for a new checkout when that snapshot is stale. However, generation still live-loads market intelligence later, and an already-open or reused pending Stripe session can cross the review date. Freeze the snapshot identifier, digest and content needed for the report at checkout; use that frozen version for a paid order while requiring fresh data only for new unpaid orders.

The public page also claims support for New Zealand and Australian SMEs, while the current market-intelligence and tax-policy path is NZ-specific. Launch as NZ-first unless a separate Australian methodology, compliance review and evidence package are approved.

#### 7. Turn review into an operational workflow

Keep Approve, but add Request clarification, Reject/unserviceable, Regenerate and Refund needed outcomes. Use the existing review notes/customer-message data fields in the UI, require a checklist, identify the reviewer, track due time, and preserve an audit trail. A bad paid draft must not remain “under review” indefinitely.

#### 8. Replace the giant intake with a saved, guided flow

Split business context, financial adjustments, forecast assumptions and risk questions into short steps. Show total progress and expected completion time. Explain terms such as CAGR, terminal growth, normalisations, capex, operating working capital and WACC at the point of use. Prefill system recommendations, hide optional advanced work until needed, and autosave each step server-side.

#### 9. Establish trust before asking for files

Publish the approved price/GST, turnaround, named reviewer, review standard, privacy/security/data-use summary, retention/deletion terms, refund rules, and support contact before upload. Add an anonymised sample report and real proof from the controlled pilot when permission is available.

#### 10. Add a lightweight customer dashboard

Make the active order the first thing a returning customer sees. Support draft resume, payment resume, timeline/status, reviewer messages, delivery actions and purchase history. Add company/document reuse only with clear confirmation of reporting period and assumptions.

### P2 — build the public acquisition foundation

#### 11. Fix public information architecture and acquisition intent

Recommended lean public structure after compliance approval:

| URL | Purpose |
|---|---|
| `/` | Canonical NZ business-valuation offer |
| `/pricing` | Price, GST, inclusions, exclusions, delivery and refunds |
| `/sample-business-valuation-report` | Anonymised proof asset and methodology preview |
| `/how-it-works` | Documents, validation, human review and delivery |
| `/methodology` | Valuation approaches, assumptions and limitations |
| `/about` | Company and named reviewer identity/credentials |
| `/security-and-data` | Storage, access, AI vendors, retention and deletion |
| `/contact` | Human fallback and assisted serviceability |
| `/privacy`, `/terms`, `/refunds`, `/disclaimer` | Approved trust/legal content |

Keep private routes out of the index. Use a dedicated registration route that preserves `business-valuation` intent.

#### 12. Add technical SEO and GEO basics

Add a public-only sitemap, a deliberate robots policy, canonical URLs, `en-NZ`, private-route `noindex`, Open Graph/Twitter metadata and a share image. Add `Organization`, `WebSite`, `Service` and approved `Offer` structured data; use reviewer `Person/ProfilePage` and breadcrumbs where appropriate. Do not expect FAQ rich results from a commercial page. A useful `llms.txt` may be added later, but attributable expertise, citations, proof and clear source pages matter more.

#### 13. Instrument a privacy-safe funnel

Track only allowlisted events such as offer viewed, CTA clicked by placement, registration started/completed, upload started/completed/serviceability failed, intake started/completed, pricing viewed, checkout started/completed, report approved/delivered, and consultation requested. Never send filenames, business names, document text, financial metrics, valuation outputs or free-text answers. Configure consent, UTM persistence, Search Console, Bing Webmaster Tools and a funnel dashboard before acquiring traffic.

#### 14. Build evidence-led content, not content volume

After launch approval, start with a sample report and methodology page, then a few expert-reviewed NZ guides: how to value a business, what an indicative valuation can and cannot do, which financial statements are needed, and how normalised earnings work. Avoid thin city/industry doorway pages. The strongest positioning is between a free calculator and a formal certified engagement: more credible and reviewed than the former, faster and lighter than the latter.

### P3 — refine and expand after evidence

- Unify marketing, authentication and product visual language; the current journey feels like a polished offer attached to a legacy internal shell.
- Fix the 4px mobile overflow on the auth card and enlarge small header/login touch targets.
- Remove or defer the four “coming later” products until each has a real proposition and fulfilment path.
- Add repeat-valuation and adviser-led upsell paths only after the core valuation journey performs reliably.
- Use pilot objections, Search Console queries and funnel evidence to decide new pages and experiments.

## UX heuristic scorecard

Dual-agent method: Assessment A was an independent browser/source heuristic review; Assessment B independently ran the deterministic detector once and performed responsive browser checks. Assessment A completed before Assessment B findings were combined.

| Nielsen heuristic | Score (0–4) | Main observation |
|---|---:|---|
| Visibility of system status | 2 | Phase labels and polling help; there is no total-step progress, draft state, delivery estimate or reliable payment-return state |
| Match with the real world | 2 | Marketing is plain; intake exposes valuation/accounting terminology without enough translation |
| User control and freedom | 2 | Back actions exist, but pre-checkout work and Stripe returns cannot be reliably resumed |
| Consistency and standards | 2 | Marketing, auth and product shell have visibly different maturity; acquisition CTA opens sign-in |
| Error prevention | 3 | Strong file/type checks, constrained inputs, confirmation and idempotency; no upload-size cap or autosave |
| Recognition rather than recall | 2 | Derived figures are shown, but the long form requires too much context to be held in memory |
| Flexibility and efficiency | 1 | No saved company, reusable documents, duplicate valuation, draft/resume or returning-user shortcut |
| Aesthetic and minimalist design | 2 | Landing is clean; disabled products and the long intake add noise |
| Error recovery | 3 | Clarification, retry and refund copy are strong; payment return and swallowed polling errors are exceptions |
| Help and documentation | 1 | FAQ exists, but contextual help, support, privacy and task guidance are absent |
| **Total** | **20/40** | **A credible base with material end-to-end continuity and trust gaps** |

### Design specificity and strengths

The first `/valuation` viewport feels authored: the large valuation-specific headline, restrained navy palette, report-structure motif, human-review message and disciplined limitation language are appropriate. The product becomes more category-interchangeable after that. The report preview is schematic rather than proof, later sections use generic SaaS cards and checklists, and login/product surfaces visually fall back to a generic/legacy shell.

Strengths worth preserving:

- clear “indicative, not advice/certified” boundaries;
- explicit pre-payment confirmation of fee, sources, assumptions and review;
- strong clarification copy that states no payment was taken;
- human-readable generation, failure, refund and delivery states;
- semantic landing-page structure, working skip link, native FAQ controls and visible keyboard focus;
- responsive valuation landing page with no observed content overflow.

### Detector and responsive findings

The deterministic detector reported two warnings in `globals.css`: generic Arial typography and a top accent border on a rounded report-preview card. The typography warning is a fair distinctiveness signal. The rounded-card warning appears to be a false positive because the accent reads as an intentional report-cover motif.

At 390px, the auth card extends roughly 4px beyond the viewport because `max-width: 95vw` does not account for its padded grid container. The valuation page itself did not overflow at 320px or 390px. The mobile header sign-in link and CTA are smaller than the recommended 44px touch target. The visible report preview is `aria-hidden`, although much of its information is repeated later.

### Persona red flags

- First-time owner: clicks “Get a valuation,” sees a sign-in form, then five product choices with four disabled, followed by unfamiliar valuation terminology and no total time estimate.
- Distracted mobile owner: encounters a slightly clipped auth card, a very long risk-rating flow, and loses work if interrupted before checkout.
- Stressed paid buyer: returns from Stripe to the upload screen, cannot tell whether payment succeeded, and can accidentally start another order.
- Privacy-conscious owner: is asked to upload P&L and balance-sheet data without a public privacy, retention, deletion or reviewer-access explanation.
- Reviewer: can approve but cannot ask a question, reject, flag an unserviceable case, record a structured decision or initiate a refund path.

### Minor observations

- Business name should be marked required in the rendered control.
- Non-auth status-polling errors should be shown, not silently swallowed.
- Form errors should link/focus the affected fields, not only appear at the top.
- Registration needs terms/privacy acknowledgement and password recovery.
- Footer needs legal, privacy, contact and company identity.
- Report-ready email should link to an authenticated order page rather than a cookie-gated API endpoint.
- Public API documentation and database-path health output should be disabled in production.
- Partial refunds need an explicit policy/state; they should not be silently ignored.
- Refunded report PDFs should be removed from durable delivery storage under the approved retention policy.

## SEO and acquisition health

Provisional score: **36/100**. This is a local pre-launch score, not a measurement of Google performance.

| Area | Assessment |
|---|---|
| Technical SEO | Weak: root redirect, no sitemap/robots/canonicals/private noindex |
| On-page | Promising: good title, one H1, semantic structure and clear offer boundaries |
| Trust/E-E-A-T | Weak for a financial offer: no named expert, proof, policies, contact or governance |
| Structured data | Absent |
| Content | Thin but focused; important purchase and risk questions are unanswered |
| Performance/CWV | Low obvious landing-page risk, but production field data is unavailable |
| AI-search readiness | Weak: little attributable expertise, source evidence, original proof or entity linkage |
| Measurement | Absent: rankings, indexing, traffic and conversion are unverified |

## Recommended 30/60/90-day sequence

### Days 0–30: make one paid journey safe

1. Keep public checkout and broad acquisition disabled.
2. Fix Stripe return, order persistence, status recovery and duplicate-purchase protection.
3. Re-audit and close the payment, privacy, security, serviceability, reviewer and infrastructure launch gates.
4. Decide price/GST, delivery, refund, reviewer and data-use policies.
5. Freeze NZ market intelligence per paid report.
6. Add upload limits, production auth/security defaults and essential account recovery/data controls.
7. Add reviewer outcomes and a lightweight active-order dashboard.
8. Split and persist the intake flow.
9. Run a production-like Stripe/webhook/email/review/PDF/refund UAT with synthetic data.
10. Invite 3–5 known NZ business owners only after a written pilot sign-off.

### Days 31–60: establish public trust and measurement

1. Make the canonical public homepage and direct-signup journey coherent.
2. Publish approved pricing, GST, turnaround, legal, privacy, security/data, refund, disclaimer and contact pages.
3. Publish a redacted sample report and named-reviewer/company proof.
4. Add robots, sitemap, canonical/noindex policy, metadata, social assets and structured data.
5. Add privacy-safe funnel analytics and configure Search Console/Bing tools.
6. Measure pilot completion, serviceability, review time, support demand, refund rate and customer comprehension.
7. Fix the highest-friction steps using observed pilot evidence.

### Days 61–90: earn and test acquisition

1. Publish a small set of expert-reviewed NZ valuation guides and methodology content.
2. Collect permissioned testimonials/case studies and anonymised process evidence.
3. Build accountant, broker, succession-adviser and commercial-lawyer referral relationships.
4. Use search and funnel data to test CTA, signup, price presentation, sample placement and consultation fallback.
5. Begin narrowly controlled exact-intent paid search only if launch gates are closed, reviewer capacity is stable and the funnel is measurable.
6. Add distinct use-case pages only when each has unique evidence and a real service path.

## Launch scorecard to use at weekly review

| Gate | Evidence required |
|---|---|
| Payment continuity | Real Stripe success, cancel, expiry, failure, retry and refund tests pass without losing order context |
| Customer trust | Approved public price/GST, delivery, reviewer, privacy, security/data, refund, disclaimer and support content is live |
| Serviceability | Unsupported/conflicted cases stop before payment or enter a defined assisted path |
| Reviewer operations | Every paid case has an owner, due time, checklist and approve/clarify/unserviceable/refund outcome |
| Data safety | Durable private storage, database migration, backups, restore test, upload cap, deletion/export and secret/cookie controls are verified |
| Product continuity | Draft intake, payment and report status all resume across reload/device/session where intended |
| Measurement | Consent and privacy-safe funnel events are live; no sensitive payloads are collected |
| Acquisition | Canonical public site, sitemap, index policy, Search Console and proof assets are in place |

## Decisions needed before implementation expands

1. Is the first commercial motion a controlled NZ pilot, a public self-serve launch, or the pilot followed by public launch? This audit recommends the third sequence.
2. What is the approved price and is it GST-inclusive or exclusive? Resolve the NZ$495 code default versus the NZ$2,250 + GST planning assumption.
3. Will the human reviewer be named publicly, and which qualifications/review standard may be claimed?
4. Is the desired customer relationship a one-off report purchase or an ongoing valuation workspace? This audit recommends a lightweight ongoing order/report workspace without broad analytics.
5. Is Australia genuinely in MVP scope? This audit recommends NZ-only positioning until Australian methodology and compliance are independently approved.

## Run notes

- Target slug: `web-app`.
- Assessment A remained independent of detector results.
- Assessment B ran the deterministic detector exactly once and found two warnings.
- Browser checks covered `/`, `/valuation`, `/login`, `/wizard`, and `/account` at desktop and mobile sizes; private routes redirected when unauthenticated.
- Browser console showed no warnings or errors during the reviewed public states.
- Browser overlay injection was unavailable; DOM inspection, screenshots, logs and source corroboration were used instead.
- No application code, data, account, Stripe object or external system was changed by this audit.

Questions are not blockers for the first safety work: Stripe continuity, launch-gate re-audit, data/security limits, and production-like UAT should proceed before acquisition regardless of the commercial choices above.
