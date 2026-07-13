# Public Valuation Offer Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public, conversion-focused `/valuation` page that explains AccountIQ's indicative valuation offer and directs qualified SME owners into the existing login flow without publishing unapproved commercial or compliance claims.

**Architecture:** Implement one static Next.js App Router server page with page-specific metadata and semantic HTML. Add only namespaced `.marketing-*` rules to the existing global stylesheet, keep all navigation as ordinary links, and verify the complete public offer through Playwright without adding backend, analytics, form, or client-state dependencies.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript 5, existing global CSS design tokens, Playwright 1.61, pnpm 10.33.

## Global Constraints

- Public route: `/valuation`; do not change the existing `/` authentication redirects.
- Primary and sign-in CTAs link to `/login`, never directly to Stripe.
- Pricing copy: `Early-access fixed-fee offer` and `Your fixed fee is shown before payment.`
- Do not publish `$495`, `NZD 2,250 + GST`, or another numeric amount.
- Required boundary: `Indicative only. Not financial advice. Reviewed before delivery.`
- Do not claim upload serviceability validation, confidentiality guarantees, turnaround time, reviewer credentials, professional memberships, testimonials, certified status, or regulated advice.
- Do not add analytics, consent handling, contact forms, legal pages, backend routes, dependencies, or client-side state.
- Use semantic landmarks, one H1, logical heading order, a skip link, visible focus states, and descriptive link names.
- Support 320px viewport width without horizontal overflow.
- Use pnpm only.

---

### Task 1: Build and verify the public valuation offer

**Files:**
- Create: `web/e2e/valuation.spec.ts`
- Create: `web/app/valuation/page.tsx`
- Modify: `web/app/globals.css`
- Modify: `.planning/BACKLOG.md`
- Modify: `.planning/STATE.md`
- Modify: `docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md`

**Interfaces:**
- Consumes: Next.js `Link`, Next.js `Metadata`, existing `/login` route, existing CSS variables from `web/app/globals.css`, and `expectNoHorizontalOverflow(page)` from `web/e2e/helpers.ts`. Repository inspection confirms the helper exists, root metadata uses a plain title without a template, `/` auth routing is page-local in `web/app/page.tsx`, and the wizard currently asks for PDF or Excel statements with the last two to three years preferred; the backend also accepts those formats.
- Produces: public `GET /valuation` page with ordinary `/login` and in-page anchor links; no exported runtime API.

- [x] **Step 1: Install the frontend dependencies with pnpm**

Run:

```bash
cd web
pnpm install --frozen-lockfile
```

Expected: installation succeeds from `pnpm-lock.yaml` without creating `package-lock.json`.

- [x] **Step 2: Verify the frontend baseline before changing behavior**

Run:

```bash
cd web
pnpm lint
pnpm typecheck
rg -n "expectNoHorizontalOverflow" e2e/helpers.ts
sed -n '1,20p' app/layout.tsx
sed -n '1,20p' app/page.tsx
rg -n "PDF or Excel - last 2-3 years preferred" components/wizard/wizard.tsx
rg -n 'allowed = .*"\.pdf".*"\.xlsx"' ../backend/main.py
```

Expected: lint and typecheck pass; the helper export exists; root metadata has no title template; authentication redirects are scoped to `app/page.tsx`; and the document guidance used by the public FAQ matches the current wizard.

- [x] **Step 3: Write the failing public-offer browser tests**

Create `web/e2e/valuation.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

import { expectNoHorizontalOverflow } from "./helpers";

test("public valuation page explains the bounded early-access offer", async ({ page }) => {
  await page.goto("/valuation");

  await expect(page).toHaveURL(/\/valuation$/);
  await expect(page.getByRole("heading", { level: 1, name: "Know what your business may be worth" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Early-access fixed-fee offer" })).toBeVisible();
  await expect(page.getByText("Your fixed fee is shown before payment.")).toBeVisible();
  await expect(page.getByText("Indicative only. Not financial advice. Reviewed before delivery.").first()).toBeVisible();
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("contentinfo")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);

  const sectionNavigation = page.getByRole("navigation", { name: "Valuation page sections" });
  await expect(sectionNavigation).toBeVisible();
  await expect(sectionNavigation.getByRole("link", { name: "What you get" })).toHaveAttribute("href", "#inclusions");
  await expect(sectionNavigation.getByRole("link", { name: "How it works" })).toHaveAttribute("href", "#process");
  await expect(sectionNavigation.getByRole("link", { name: "FAQ" })).toHaveAttribute("href", "#faq");

  const headingLevels = await page.getByRole("heading").evaluateAll((headings) =>
    headings.map((heading) => Number(heading.tagName.slice(1))),
  );
  for (let index = 1; index < headingLevels.length; index += 1) {
    expect(headingLevels[index]).toBeLessThanOrEqual(headingLevels[index - 1] + 1);
  }

  const primaryCta = page.getByRole("link", { name: "Get a Business Valuation" }).first();
  await expect(primaryCta).toHaveAttribute("href", "/login");
  await expect(page.getByRole("link", { name: "Sign in" }).first()).toHaveAttribute("href", "/login");

  const externalPaymentLinks = page.locator('a[href*="stripe"], a[href*="checkout"]');
  await expect(externalPaymentLinks).toHaveCount(0);

  const bodyText = (await page.locator("body").textContent()) ?? "";
  expect(bodyText).not.toMatch(/\$495|2,250/);
  expect(bodyText).toMatch(/not financial advice/i);
  expect(bodyText).toMatch(/not a certified, official, or court-standard valuation/i);
  expect(bodyText).toContain("Recent PDF or Excel financial statements covering the last two to three years are preferred.");
  expect(bodyText).toContain("Software prepares the first draft, and a human reviewer checks the report before it is released to your account.");

  // Smoke-check known positive marketing phrases. The explicit negative copy above
  // is the primary contract because a generic blacklist cannot understand negation.
  for (const forbiddenPositiveClaim of [
    /get an instant valuation/i,
    /guaranteed valuation/i,
    /certified valuation service/i,
    /official valuation service/i,
  ]) {
    expect(bodyText).not.toMatch(forbiddenPositiveClaim);
  }
});

test("public valuation page remains usable at 320px", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 780 });
  await page.goto("/valuation");

  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const mobileHeader = page.getByRole("banner");
  await expect(mobileHeader.getByRole("link", { name: "Sign in" })).toBeVisible();
  await expect(mobileHeader.getByRole("link", { name: "Get a valuation" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Get a Business Valuation" }).first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
```

- [x] **Step 4: Run the focused test and verify the red state**

Run:

```bash
cd web
pnpm exec playwright test e2e/valuation.spec.ts
```

Expected: FAIL because `/valuation` does not exist and the required H1 is absent. If the URL assertion fails because of an authentication redirect, confirm whether the gate is still page-local in `web/app/page.tsx` or has moved to middleware, and adjust only the gate's scope so `/valuation` remains public without changing `/` behavior. If port 3000 is occupied, create a temporary ignored Playwright config using an unused port; do not kill an unrelated process.

- [x] **Step 5: Implement the static valuation page**

Create `web/app/valuation/page.tsx`:

```tsx
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Indicative Business Valuation Reports | AccountIQ",
  description:
    "Understand what your business may be worth with a fixed-fee indicative valuation report reviewed before delivery.",
};

const trustPoints = [
  "Fixed fee confirmed before payment",
  "Reviewed before delivery",
  "Web report and PDF access",
  "Built for New Zealand and Australian SMEs",
];

const useCases = [
  {
    title: "Prepare for a possible sale",
    body: "Establish a practical valuation reference point before speaking with buyers or beginning a full advisory engagement.",
  },
  {
    title: "Plan a funding conversation",
    body: "Understand the assumptions and business factors likely to shape an early debt or capital discussion.",
  },
  {
    title: "Support shareholder planning",
    body: "Give shareholders or successors a shared starting point for a structured conversation about value.",
  },
];

const inclusions = [
  "Business overview based on the information you provide",
  "Historical financial performance summary",
  "Normalised earnings adjustments where provided",
  "Indicative valuation range and key assumptions",
  "Key risks and matters to consider",
  "Review before release",
  "Web report and PDF delivery",
];

const steps = [
  "Create your AccountIQ account",
  "Upload recent financial statements",
  "Complete the valuation questions",
  "See the fixed fee and pay securely",
  "AccountIQ prepares the report",
  "A reviewer checks the report before release",
  "Access the reviewed report from your account",
];

const faqs = [
  {
    question: "Is this financial advice?",
    answer: "No. The report is an indicative decision-support document and is not financial advice.",
  },
  {
    question: "Is this a certified valuation?",
    answer:
      "No. It is not a certified, official, or court-standard valuation. Those needs require a separate professional engagement.",
  },
  {
    question: "What documents do I need?",
    answer: "Recent PDF or Excel financial statements covering the last two to three years are preferred.",
  },
  {
    question: "When do I pay?",
    answer: "Your fixed fee is shown before payment, after you create an account and complete the valuation information.",
  },
  {
    question: "Who reviews the report?",
    answer:
      "Software prepares the first draft, and a human reviewer checks the report before it is released to your account.",
  },
];

export default function ValuationPage() {
  return (
    <div className="marketing-page">
      <a className="marketing-skip-link" href="#main-content">
        Skip to main content
      </a>

      <header className="marketing-header">
        <div className="marketing-container marketing-header-inner">
          <Link className="marketing-wordmark" href="/valuation" aria-label="AccountIQ valuation home">
            AccountIQ
          </Link>
          <nav className="marketing-nav" aria-label="Valuation page sections">
            <a href="#inclusions">What you get</a>
            <a href="#process">How it works</a>
            <a href="#faq">FAQ</a>
          </nav>
          <div className="marketing-header-actions">
            <Link className="marketing-text-link" href="/login">
              Sign in
            </Link>
            <Link className="marketing-cta marketing-cta-small" href="/login">
              Get a valuation
            </Link>
          </div>
        </div>
      </header>

      <main id="main-content">
        <section className="marketing-hero">
          <div className="marketing-container marketing-hero-grid">
            <div>
              <p className="marketing-eyebrow">Fixed-fee business valuation reports</p>
              <h1>Know what your business may be worth</h1>
              <p className="marketing-hero-copy">
                Upload recent financial statements and receive an indicative business valuation report prepared with
                software and reviewed before delivery.
              </p>
              <div className="marketing-actions">
                <Link className="marketing-cta" href="/login">
                  Get a Business Valuation
                </Link>
                <Link className="marketing-secondary-cta" href="/login">
                  Sign in
                </Link>
              </div>
              <p className="marketing-boundary">Indicative only. Not financial advice. Reviewed before delivery.</p>
            </div>

            <aside className="marketing-report-preview" aria-hidden="true">
              <div className="marketing-preview-header">
                <span>AccountIQ</span>
                <small>Report structure preview</small>
              </div>
              <p className="marketing-preview-title">Business Valuation Report</p>
              <dl>
                <div>
                  <dt>Valuation range</dt>
                  <dd>Key assumptions shown</dd>
                </div>
                <div>
                  <dt>Financial performance</dt>
                  <dd>Historical summary</dd>
                </div>
                <div>
                  <dt>Normalised earnings</dt>
                  <dd>Adjustments explained</dd>
                </div>
                <div>
                  <dt>Key risks</dt>
                  <dd>Matters to consider</dd>
                </div>
              </dl>
              <p>Reviewed before delivery</p>
            </aside>
          </div>
        </section>

        <section className="marketing-trust" aria-label="Offer commitments">
          <div className="marketing-container marketing-trust-grid">
            {trustPoints.map((point) => (
              <p key={point}>{point}</p>
            ))}
          </div>
        </section>

        <section className="marketing-section">
          <div className="marketing-container">
            <p className="marketing-eyebrow">A practical first step</p>
            <h2>Valuation clarity before the bigger decision</h2>
            <div className="marketing-card-grid">
              {useCases.map((useCase) => (
                <article className="marketing-card" key={useCase.title}>
                  <h3>{useCase.title}</h3>
                  <p>{useCase.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="marketing-section marketing-section-muted" id="inclusions">
          <div className="marketing-container marketing-two-column">
            <div>
              <p className="marketing-eyebrow">What you get</p>
              <h2>A clear report, with its assumptions visible</h2>
              <p>
                Use the report as an indicative reference point for planning and decide whether deeper professional
                advice is needed.
              </p>
            </div>
            <ul className="marketing-check-list">
              {inclusions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className="marketing-section" id="process">
          <div className="marketing-container">
            <p className="marketing-eyebrow">How it works</p>
            <h2>From financial statements to reviewed report</h2>
            <ol className="marketing-steps">
              {steps.map((step, index) => (
                <li key={step}>
                  <span aria-hidden="true">{index + 1}</span>
                  <p>{step}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="marketing-section marketing-review-section">
          <div className="marketing-container marketing-two-column">
            <div>
              <p className="marketing-eyebrow">Human review before release</p>
              <h2>Software speed, with a review checkpoint</h2>
            </div>
            <div>
              <p>
                AccountIQ prepares the first draft from the information supplied. A human reviewer checks the report
                before it is released to your account.
              </p>
              <p>
                The report is indicative only and is not financial advice. It is not a certified, official, or
                court-standard valuation, and it is not a substitute for a regulated professional engagement.
              </p>
            </div>
          </div>
        </section>

        <section className="marketing-section">
          <div className="marketing-container marketing-pricing-panel">
            <div>
              <h2>Early-access fixed-fee offer</h2>
              <p>Your fixed fee is shown before payment.</p>
            </div>
            <Link className="marketing-cta" href="/login">
              Get a Business Valuation
            </Link>
          </div>
        </section>

        <section className="marketing-section marketing-section-muted" id="faq">
          <div className="marketing-container marketing-faq-layout">
            <div>
              <p className="marketing-eyebrow">FAQ</p>
              <h2>Important questions before you begin</h2>
            </div>
            <div className="marketing-faq-list">
              {faqs.map((faq) => (
                <details key={faq.question}>
                  <summary>{faq.question}</summary>
                  <p>{faq.answer}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="marketing-final-cta">
          <div className="marketing-container">
            <p className="marketing-eyebrow">Start with a clearer reference point</p>
            <h2>Understand what your business may be worth</h2>
            <Link className="marketing-cta" href="/login">
              Get a Business Valuation
            </Link>
            <p>
              Already have an account? <Link href="/login">Sign in</Link>
            </p>
          </div>
        </section>
      </main>

      <footer className="marketing-footer">
        <div className="marketing-container">
          <strong>AccountIQ</strong>
          <p>Indicative only. Not financial advice.</p>
        </div>
      </footer>
    </div>
  );
}
```

- [x] **Step 6: Add namespaced responsive marketing styles**

Append the following to `web/app/globals.css`:

```css
/* Public valuation offer */
.marketing-page {
  --marketing-navy: #1b1464;
  --marketing-ink: #172033;
  --marketing-muted: #5e6878;
  --marketing-line: #dfe3ea;
  min-height: 100vh;
  background: #ffffff;
  color: var(--marketing-ink);
}

.marketing-container {
  width: min(1120px, calc(100% - 40px));
  margin-inline: auto;
}

.marketing-skip-link {
  position: fixed;
  z-index: 100;
  top: 12px;
  left: 12px;
  transform: translateY(-160%);
  border-radius: 6px;
  padding: 10px 14px;
  background: #ffffff;
  color: var(--marketing-navy);
  box-shadow: 0 8px 24px rgba(23, 32, 51, 0.18);
}

.marketing-skip-link:focus {
  transform: translateY(0);
}

.marketing-header {
  border-bottom: 1px solid var(--marketing-line);
  background: rgba(255, 255, 255, 0.98);
}

.marketing-header-inner,
.marketing-header-actions,
.marketing-nav,
.marketing-actions {
  display: flex;
  align-items: center;
}

.marketing-header-inner {
  min-height: 72px;
  justify-content: space-between;
  gap: 24px;
}

.marketing-wordmark {
  color: var(--marketing-navy);
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  text-decoration: none;
}

.marketing-nav,
.marketing-header-actions,
.marketing-actions {
  gap: 18px;
}

.marketing-nav a,
.marketing-text-link,
.marketing-secondary-cta {
  color: var(--marketing-ink);
  font-weight: 700;
  text-decoration: none;
}

.marketing-page a:focus-visible,
.marketing-page summary:focus-visible {
  outline: 3px solid var(--marketing-navy);
  outline-offset: 3px;
  box-shadow: 0 0 0 6px #ffffff;
}

.marketing-cta,
.marketing-secondary-cta {
  display: inline-flex;
  min-height: 48px;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  padding: 12px 18px;
  font-weight: 800;
  text-decoration: none;
}

.marketing-cta {
  background: var(--marketing-navy);
  color: #ffffff;
}

.marketing-secondary-cta {
  border: 1px solid var(--marketing-line);
  background: #ffffff;
}

.marketing-cta-small {
  min-height: 40px;
  padding: 9px 14px;
}

.marketing-hero {
  padding: 88px 0 72px;
}

.marketing-hero-grid,
.marketing-two-column,
.marketing-faq-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(320px, 0.92fr);
  gap: clamp(40px, 7vw, 88px);
  align-items: center;
}

.marketing-eyebrow {
  margin: 0 0 14px;
  color: var(--marketing-navy);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.marketing-hero h1 {
  max-width: 680px;
  margin: 0;
  color: var(--marketing-navy);
  font-size: clamp(2.55rem, 6vw, 4.7rem);
  letter-spacing: -0.055em;
  line-height: 0.98;
}

.marketing-hero-copy {
  max-width: 650px;
  margin: 26px 0;
  color: var(--marketing-muted);
  font-size: 1.18rem;
  line-height: 1.65;
}

.marketing-boundary {
  margin: 18px 0 0;
  color: var(--marketing-muted);
  font-size: 0.88rem;
  font-weight: 700;
}

.marketing-report-preview {
  border: 1px solid var(--marketing-line);
  border-top: 8px solid var(--marketing-navy);
  border-radius: 8px;
  padding: 30px;
  background: #ffffff;
  box-shadow: 0 24px 60px rgba(27, 20, 100, 0.13);
}

.marketing-preview-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  color: var(--marketing-navy);
  font-weight: 800;
}

.marketing-preview-header small {
  color: var(--marketing-muted);
  font-weight: 600;
}

.marketing-preview-title {
  margin: 32px 0 20px;
  color: var(--marketing-navy);
  font-size: 1.5rem;
  font-weight: 800;
}

.marketing-report-preview dl,
.marketing-report-preview dl div {
  display: grid;
  gap: 8px;
}

.marketing-report-preview dl {
  margin: 0;
}

.marketing-report-preview dl div {
  grid-template-columns: 1fr auto;
  padding: 13px 0;
  border-bottom: 1px solid var(--marketing-line);
}

.marketing-report-preview dt {
  font-weight: 800;
}

.marketing-report-preview dd {
  margin: 0;
  color: var(--marketing-muted);
  text-align: right;
}

.marketing-report-preview > p {
  margin: 22px 0 0;
  color: var(--marketing-navy);
  font-weight: 800;
}

.marketing-trust {
  border-block: 1px solid var(--marketing-line);
  background: #f8f9fc;
}

.marketing-trust-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.marketing-trust-grid p {
  margin: 0;
  padding: 24px 20px;
  border-right: 1px solid var(--marketing-line);
  color: var(--marketing-navy);
  font-size: 0.9rem;
  font-weight: 800;
  text-align: center;
}

.marketing-trust-grid p:last-child {
  border-right: 0;
}

.marketing-section {
  padding: 84px 0;
  scroll-margin-top: 24px;
}

.marketing-section-muted {
  background: #f6f7fb;
}

.marketing-section h2,
.marketing-final-cta h2 {
  max-width: 720px;
  margin: 0 0 24px;
  color: var(--marketing-navy);
  font-size: clamp(2rem, 4vw, 3rem);
  letter-spacing: -0.035em;
  line-height: 1.08;
}

.marketing-section p,
.marketing-final-cta p {
  color: var(--marketing-muted);
  line-height: 1.7;
}

.marketing-card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  margin-top: 34px;
}

.marketing-card {
  border: 1px solid var(--marketing-line);
  border-radius: 8px;
  padding: 28px;
  background: #ffffff;
}

.marketing-card h3 {
  margin: 0 0 12px;
  color: var(--marketing-navy);
}

.marketing-check-list {
  display: grid;
  gap: 14px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.marketing-check-list li {
  position: relative;
  padding: 15px 18px 15px 48px;
  border: 1px solid var(--marketing-line);
  border-radius: 7px;
  background: #ffffff;
}

.marketing-check-list li::before {
  position: absolute;
  top: 14px;
  left: 17px;
  color: var(--marketing-navy);
  content: "✓" / "";
  font-weight: 900;
}

.marketing-steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin: 34px 0 0;
  padding: 0;
  list-style: none;
}

.marketing-steps li {
  min-height: 156px;
  border-top: 3px solid var(--marketing-navy);
  padding: 20px 4px 0;
}

.marketing-steps span {
  display: inline-grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: 50%;
  background: #eeecfa;
  color: var(--marketing-navy);
  font-weight: 900;
}

.marketing-steps p {
  color: var(--marketing-ink);
  font-weight: 700;
}

.marketing-review-section {
  background: var(--marketing-navy);
  color: #ffffff;
}

.marketing-review-section .marketing-eyebrow,
.marketing-review-section h2,
.marketing-review-section p {
  color: #ffffff;
}

.marketing-pricing-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  border: 1px solid var(--marketing-line);
  border-radius: 10px;
  padding: 38px;
  background: #f8f9fc;
}

.marketing-pricing-panel h2 {
  margin-bottom: 10px;
}

.marketing-pricing-panel p:last-child {
  margin-bottom: 0;
}

.marketing-faq-layout {
  align-items: start;
}

.marketing-faq-list details {
  border-bottom: 1px solid var(--marketing-line);
  padding: 18px 0;
}

.marketing-faq-list summary {
  color: var(--marketing-navy);
  cursor: pointer;
  font-weight: 800;
}

.marketing-faq-list p {
  margin-bottom: 0;
}

.marketing-final-cta {
  padding: 90px 0;
  text-align: center;
}

.marketing-final-cta h2 {
  margin-inline: auto;
}

.marketing-final-cta p:last-child {
  margin-bottom: 0;
}

.marketing-footer {
  border-top: 1px solid var(--marketing-line);
  padding: 30px 0;
  background: #f8f9fc;
}

.marketing-footer .marketing-container {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.marketing-footer strong {
  color: var(--marketing-navy);
}

.marketing-footer p {
  margin: 0;
  color: var(--marketing-muted);
  font-size: 0.88rem;
}

@media (max-width: 860px) {
  .marketing-nav {
    display: none;
  }

  .marketing-hero-grid,
  .marketing-two-column,
  .marketing-faq-layout {
    grid-template-columns: 1fr;
  }

  .marketing-trust-grid,
  .marketing-card-grid,
  .marketing-steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .marketing-trust-grid p:nth-child(2) {
    border-right: 0;
  }
}

@media (max-width: 560px) {
  .marketing-container {
    width: min(100% - 28px, 1120px);
  }

  .marketing-header-inner {
    min-height: 64px;
    gap: 12px;
  }

  .marketing-header-actions {
    gap: 10px;
  }

  .marketing-header-actions .marketing-cta-small {
    padding-inline: 10px;
    font-size: 0.78rem;
  }

  .marketing-hero {
    padding: 58px 0 48px;
  }

  .marketing-hero h1 {
    font-size: clamp(2.4rem, 15vw, 3.4rem);
  }

  .marketing-actions,
  .marketing-pricing-panel,
  .marketing-footer .marketing-container {
    align-items: stretch;
    flex-direction: column;
  }

  .marketing-cta,
  .marketing-secondary-cta {
    width: 100%;
  }

  .marketing-report-preview {
    padding: 22px;
  }

  .marketing-report-preview dl div {
    grid-template-columns: 1fr;
  }

  .marketing-report-preview dd {
    text-align: left;
  }

  .marketing-trust-grid,
  .marketing-card-grid,
  .marketing-steps {
    grid-template-columns: 1fr;
  }

  .marketing-trust-grid p {
    border-right: 0;
    border-bottom: 1px solid var(--marketing-line);
  }

  .marketing-trust-grid p:last-child {
    border-bottom: 0;
  }

  .marketing-section {
    padding: 62px 0;
  }

  .marketing-pricing-panel {
    padding: 28px;
  }
}
```

- [x] **Step 7: Run the focused test and verify the green state**

Run:

```bash
cd web
pnpm exec playwright test e2e/valuation.spec.ts
```

Expected: both valuation tests pass.

- [x] **Step 8: Run all frontend regression gates**

Run:

```bash
cd web
pnpm lint
pnpm typecheck
pnpm build
pnpm test:e2e
pnpm test:e2e:prod
```

Expected: lint, typecheck, production build, development-server Playwright, and production-server Playwright all pass. The build output includes `/valuation` as a static route.

- [x] **Step 9: Update the paid-MVP planning records**

Apply these exact state changes:

- `.planning/BACKLOG.md`: mark PVM-07 `In review` with `PR pending`; note that the static public offer uses early-access pricing without a numeric amount and links to `/login`. The actual PR number is added in Step 11 immediately after the PR is opened.
- `.planning/STATE.md`: set current status to `PVM-07 public valuation offer in review`, record the verification results, and set PVM-08 live report UAT as next.
- `docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md`: mark Task 7 implementation and verification steps complete, reference this focused plan, and preserve the separation between PVM-07 and PVM-08.

Do not mark PVM-07 `Done` until the PR has passed final review and is about to merge.

- [x] **Step 10: Commit the verified implementation**

Run:

```bash
git add web/app/valuation/page.tsx web/app/globals.css web/e2e/valuation.spec.ts .planning/BACKLOG.md .planning/STATE.md docs/superpowers/plans/2026-07-01-paid-valuation-mvp.md docs/superpowers/plans/2026-07-13-public-valuation-offer.md
git commit -m "feat(valuation): add public offer page"
```

Expected: the commit contains only PVM-07 implementation, tests, and planning updates.

- [ ] **Step 11: Review, merge, and clean the completed worktree**

Run the repository's normal PR workflow:

```bash
git push -u origin codex/pvm-07-public-offer
gh pr create --base main --head codex/pvm-07-public-offer \
  --title "PVM-07: add public valuation offer" \
  --body $'## Summary\n- add a public, static valuation offer page\n- use early-access fixed-fee language without an unapproved numeric amount\n- route every conversion CTA through the existing login flow\n\n## Verification\n- pnpm lint\n- pnpm typecheck\n- pnpm build\n- focused Playwright suite\n- pnpm test:e2e\n- pnpm test:e2e:prod'
```

After `gh pr create` returns the PR number, use `apply_patch` to replace `PR pending` in the PVM-07 backlog row with that number, then commit and push the bookkeeping update:

```bash
git add .planning/BACKLOG.md
git commit -m "docs(planning): link PVM-07 pull request"
git push
```

Before merge:

- review `origin/main...HEAD` for correctness, accessibility, truthful marketing claims, and scope;
- run the requested read-only `claude-fable-5` review and independently triage every finding;
- rerun any gate affected by a patch;
- mark PVM-07 `Done` and PVM-08 next immediately before merge; and
- merge only when the PR is clean and mergeable.

After merge, remove the worktree and any `.next`, `node_modules`, temporary Playwright configuration, test output, or disposable dependency environment associated with it.
