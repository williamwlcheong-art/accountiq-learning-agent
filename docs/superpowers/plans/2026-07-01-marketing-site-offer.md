# Marketing Site / Offer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first public AccountIQ marketing surface for the Business Valuation Report offer, with clear positioning, trust-building proof sections, privacy-safe analytics, and CTAs into the customer order flow.

**Architecture:** Implement in the future Next.js `web/` app. The marketing page is presentation-only except for privacy-safe analytics and a contact/consultation lead form; financial document upload remains behind authentication in FastAPI.

**Tech Stack:** Next.js App Router, React, TypeScript, CSS modules or existing app styling convention once `web/` exists, PostHog with restricted explicit events, FastAPI for authenticated order/upload flow.

---

## Preconditions

Do not execute this plan until:

- `web/` Next.js foundation exists.
- Same-origin API strategy is working or stubbed.
- Product/legal copy is still allowed to be draft, or approved copy has been provided.
- Launch gates are understood: `.planning/commercial/LAUNCH-GATES.md`.

Reference docs:

- Offer spec: `docs/superpowers/specs/2026-07-01-marketing-site-offer-spec.md`
- Product context: `.agents/product-marketing-context.md`
- Architecture ADR: `.planning/commercial/ARCHITECTURE-DECISIONS.md`

## File Structure

Future files to create after `web/` exists:

```text
web/app/page.tsx
web/app/contact/page.tsx
web/app/legal/disclaimer/page.tsx
web/components/marketing/Header.tsx
web/components/marketing/Hero.tsx
web/components/marketing/TrustBar.tsx
web/components/marketing/ProblemSection.tsx
web/components/marketing/ProductInclusions.tsx
web/components/marketing/HowItWorks.tsx
web/components/marketing/PricingPanel.tsx
web/components/marketing/ReviewPromise.tsx
web/components/marketing/SampleOutput.tsx
web/components/marketing/Faq.tsx
web/components/marketing/FinalCta.tsx
web/components/marketing/ContactLeadForm.tsx
web/lib/analytics.ts
web/lib/marketingCopy.ts
web/types/marketing.ts
web/e2e/marketing.spec.ts
```

Keep marketing copy in `web/lib/marketingCopy.ts` so legal/compliance wording can be reviewed without hunting through component internals.

---

### Task 1: Add Marketing Copy Model

**Files:**

- Create: `web/types/marketing.ts`
- Create: `web/lib/marketingCopy.ts`
- Test: `web/lib/marketingCopy.test.ts` if unit test tooling exists; otherwise validate through E2E in Task 7.

- [ ] **Step 1: Create marketing types**

Create `web/types/marketing.ts`:

```ts
export type Cta = {
  label: string;
  href: string;
  eventName: string;
  location: string;
};

export type FaqItem = {
  question: string;
  answer: string;
};

export type PricingMode = "approved" | "early_access";

export type MarketingCopy = {
  hero: {
    eyebrow: string;
    headline: string;
    body: string;
    trustNote: string;
    primaryCta: Cta;
    secondaryCta: Cta;
  };
  trustPoints: string[];
  problemBullets: string[];
  inclusions: string[];
  howItWorks: string[];
  pricing: {
    mode: PricingMode;
    headline: string;
    priceLabel: string;
    notes: string[];
  };
  reviewPromise: {
    headline: string;
    body: string;
    bullets: string[];
  };
  faq: FaqItem[];
};
```

- [ ] **Step 2: Create draft marketing copy**

Create `web/lib/marketingCopy.ts`:

```ts
import type { MarketingCopy } from "@/types/marketing";

export const marketingCopy: MarketingCopy = {
  hero: {
    eyebrow: "Fixed-fee business valuation reports",
    headline: "Know what your business may be worth",
    body:
      "Upload recent financial statements and receive an indicative valuation report prepared with software and reviewed before delivery.",
    trustNote: "Indicative only. Not financial advice. Reviewed before delivery.",
    primaryCta: {
      label: "Get a Business Valuation",
      href: "/signup?intent=business-valuation",
      eventName: "valuation_cta_clicked",
      location: "hero",
    },
    secondaryCta: {
      label: "Talk to Us",
      href: "/contact",
      eventName: "secondary_consultation_cta_clicked",
      location: "hero",
    },
  },
  trustPoints: [
    "Fixed fee before payment",
    "Upload validation before payment",
    "Reviewed before delivery",
    "Optional consultation after delivery",
  ],
  problemBullets: [
    "You need valuation clarity before a sale, funding conversation, or shareholder decision.",
    "Traditional advisory work can feel slow or expensive before you know where you stand.",
    "DIY calculators are fast but often too generic to trust.",
  ],
  inclusions: [
    "Business overview based on provided information",
    "Historical financial performance summary",
    "Normalised earnings and EBITDA adjustments where provided",
    "Valuation range and key assumptions",
    "Indicative-only disclaimer",
    "Reviewer check before delivery",
    "Web report and PDF delivery",
  ],
  howItWorks: [
    "Create an account",
    "Upload financial statements",
    "We validate whether the files are usable",
    "Confirm fixed fee and pay securely",
    "Your report is generated",
    "A reviewer checks it before release",
    "Receive your report and optional consultation prompt",
  ],
  pricing: {
    mode: "early_access",
    headline: "Clear fixed-fee pricing",
    priceLabel: "Early-access pricing available after upload validation",
    notes: [
      "Final pricing, GST wording, and refund policy must be approved before public launch.",
      "Consultation is optional and quoted separately.",
    ],
  },
  reviewPromise: {
    headline: "Software speed with human review",
    body:
      "Our software prepares the first draft, then a valuation specialist reviews the report before delivery.",
    bullets: [
      "Complex cases may require clarification",
      "The report is indicative, not financial advice",
      "Reviewer notes and approval are part of the delivery workflow",
    ],
  },
  faq: [
    {
      question: "Is this financial advice?",
      answer:
        "No. The report is intended as an indicative valuation and decision-support document. It is not financial advice.",
    },
    {
      question: "Is this a certified valuation?",
      answer:
        "No. Customers needing court-standard, certified, or regulated valuation work should use a separate professional engagement.",
    },
    {
      question: "When do I pay?",
      answer:
        "Payment happens after upload and validation, before report generation and delivery.",
    },
    {
      question: "What happens if my files cannot be processed?",
      answer:
        "If files are not serviceable, the flow stops before payment and shows a contact-us path.",
    },
    {
      question: "Can I speak with someone after the report?",
      answer:
        "Yes. Forecasting and advisory consultation can be requested after review or delivery.",
    },
  ],
};
```

- [ ] **Step 3: Verify forbidden marketing claims are absent**

Run:

```bash
rg -n "certified|guaranteed|official valuation|instant valuation|court-standard|AI replaces|financial advice" web/lib/marketingCopy.ts
```

Expected: only allowed disclaimer/FAQ lines appear; no positive claim that the report is certified, instant, guaranteed, court-standard, official, or financial advice.

### Task 2: Add Privacy-Safe Analytics Helper

**Files:**

- Create: `web/lib/analytics.ts`

- [ ] **Step 1: Create analytics allowlist helper**

Create `web/lib/analytics.ts`:

```ts
const allowedEvents = new Set([
  "page_viewed",
  "valuation_cta_clicked",
  "secondary_consultation_cta_clicked",
  "pricing_viewed",
  "faq_opened",
  "sample_report_clicked",
  "contact_form_started",
  "contact_form_submitted",
]);

type MarketingEventProperties = {
  path?: string;
  ctaLocation?: string;
  faqQuestion?: string;
  utmSource?: string;
  utmMedium?: string;
  utmCampaign?: string;
};

export function trackMarketingEvent(
  eventName: string,
  properties: MarketingEventProperties = {},
) {
  if (!allowedEvents.has(eventName)) {
    return;
  }

  if (typeof window === "undefined") {
    return;
  }

  const posthog = (
    window as typeof window & {
      posthog?: {
        capture: (eventName: string, properties?: MarketingEventProperties) => void;
      };
    }
  ).posthog;
  posthog?.capture(eventName, properties);
}
```

- [ ] **Step 2: Verify no broad payload escape hatch**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

source = Path("web/lib/analytics.ts").read_text().lower()
for forbidden in ["document", "financial", "revenue", "ebitda", "filename", "report narrative"]:
    if forbidden in source:
        raise SystemExit(f"Forbidden analytics property found: {forbidden}")
PY
```

Expected: no forbidden analytics property names are present.

### Task 3: Build Marketing Components

**Files:**

- Create: `web/components/marketing/Header.tsx`
- Create: `web/components/marketing/Hero.tsx`
- Create: `web/components/marketing/TrustBar.tsx`
- Create: `web/components/marketing/ProblemSection.tsx`
- Create: `web/components/marketing/ProductInclusions.tsx`
- Create: `web/components/marketing/HowItWorks.tsx`
- Create: `web/components/marketing/PricingPanel.tsx`
- Create: `web/components/marketing/ReviewPromise.tsx`
- Create: `web/components/marketing/SampleOutput.tsx`
- Create: `web/components/marketing/Faq.tsx`
- Create: `web/components/marketing/FinalCta.tsx`

- [ ] **Step 1: Build components from `marketingCopy`**

Each component should:

- receive explicit props or import `marketingCopy`;
- avoid `dangerouslySetInnerHTML`;
- use semantic HTML;
- use buttons/links with clear accessible names;
- expose CTA locations for analytics.

Example CTA implementation:

```tsx
"use client";

import Link from "next/link";
import { trackMarketingEvent } from "@/lib/analytics";
import type { Cta } from "@/types/marketing";

export function MarketingCta({ cta }: { cta: Cta }) {
  return (
    <Link
      href={cta.href}
      onClick={() =>
        trackMarketingEvent(cta.eventName, {
          ctaLocation: cta.location,
          path: window.location.pathname,
        })
      }
    >
      {cta.label}
    </Link>
  );
}
```

- [ ] **Step 2: Build FAQ with explicit event tracking**

FAQ open action should call:

```ts
trackMarketingEvent("faq_opened", {
  faqQuestion: item.question,
  path: window.location.pathname,
});
```

- [ ] **Step 3: Keep sample output honest**

Until a real sample report asset exists, `SampleOutput` should show a clearly labelled placeholder:

```tsx
<p>Sample anonymised report preview coming soon.</p>
```

Do not fabricate a testimonial or customer case.

### Task 4: Build Homepage

**Files:**

- Create or modify: `web/app/page.tsx`

- [ ] **Step 1: Compose homepage sections in order**

`web/app/page.tsx` should render:

```tsx
import { Header } from "@/components/marketing/Header";
import { Hero } from "@/components/marketing/Hero";
import { TrustBar } from "@/components/marketing/TrustBar";
import { ProblemSection } from "@/components/marketing/ProblemSection";
import { ProductInclusions } from "@/components/marketing/ProductInclusions";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { PricingPanel } from "@/components/marketing/PricingPanel";
import { ReviewPromise } from "@/components/marketing/ReviewPromise";
import { SampleOutput } from "@/components/marketing/SampleOutput";
import { Faq } from "@/components/marketing/Faq";
import { FinalCta } from "@/components/marketing/FinalCta";

export default function HomePage() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <TrustBar />
        <ProblemSection />
        <ProductInclusions />
        <HowItWorks />
        <PricingPanel />
        <ReviewPromise />
        <SampleOutput />
        <Faq />
        <FinalCta />
      </main>
    </>
  );
}
```

- [ ] **Step 2: Add metadata**

Set metadata to:

```ts
export const metadata = {
  title: "AccountIQ | Fixed-fee business valuation reports",
  description:
    "Upload recent financial statements and receive an indicative business valuation report prepared with software and reviewed before delivery.",
};
```

### Task 5: Build Contact / Consultation Page

**Files:**

- Create: `web/app/contact/page.tsx`
- Create: `web/components/marketing/ContactLeadForm.tsx`

- [ ] **Step 1: Create contact form fields**

Fields:

- name;
- email;
- business name;
- reason for enquiry;
- consent checkbox.

Do not include financial-document upload on this page.

- [ ] **Step 2: Add submit placeholder if backend lead endpoint is not ready**

If the CRM/contact API is not implemented, the form should not fake success. Use:

```tsx
<p>
  Contact form backend is not connected yet. Please email us directly while early access is being prepared.
</p>
```

or hide submit behind a disabled early-access state until the backend exists.

### Task 6: Add Legal Placeholder Pages

**Files:**

- Create: `web/app/legal/disclaimer/page.tsx`
- Create: `web/app/legal/privacy/page.tsx`
- Create: `web/app/legal/terms/page.tsx`

- [ ] **Step 1: Add draft-status legal pages**

Each page must clearly say:

```tsx
<p>This page is a draft and must be reviewed before public launch.</p>
```

- [ ] **Step 2: Link to legal pages from footer/header**

Footer links:

- Privacy
- Terms
- Disclaimer

### Task 7: Add Marketing E2E Smoke

**Files:**

- Create: `web/e2e/marketing.spec.ts`

- [ ] **Step 1: Add Playwright checks**

Test:

```ts
import { expect, test } from "@playwright/test";

test("homepage presents valuation offer and safe CTAs", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /Know what your business may be worth/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Get a Business Valuation/i }).first()).toHaveAttribute(
    "href",
    /signup\\?intent=business-valuation/,
  );
  await expect(page.getByText(/Indicative only/i)).toBeVisible();
  await expect(page.getByText(/Reviewed before delivery/i)).toBeVisible();
});

test("homepage does not make forbidden claims", async ({ page }) => {
  await page.goto("/");
  const body = await page.locator("body").innerText();

  expect(body).not.toMatch(/we (provide|offer|deliver).{0,80}certified/i);
  expect(body).not.toMatch(/certified valuation report for your business/i);
  expect(body).not.toMatch(/guaranteed valuation/i);
  expect(body).not.toMatch(/instant valuation/i);
  expect(body).not.toMatch(/AI replaces/i);
});
```

### Task 8: Verification And Commit

**Files:**

- Verify all `web/` marketing files created by this plan.

- [ ] **Step 1: Run typecheck/build**

Run from `web/`:

```bash
npm run typecheck
npm run build
```

Expected: both pass.

- [ ] **Step 2: Run E2E smoke**

Run from `web/`:

```bash
npm run test:e2e -- marketing.spec.ts
```

Expected: marketing homepage tests pass.

- [ ] **Step 3: Run forbidden claim scan**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

patterns = [
    "guaranteed valuation",
    "instant valuation",
    "ai replaces",
    "official valuation",
    "certified valuation report for your business",
]
hits = []
for path in Path("web").rglob("*"):
    if path.is_file() and path.suffix in {".ts", ".tsx", ".md", ".mdx"}:
        text = path.read_text(errors="ignore").lower()
        for pattern in patterns:
            if pattern in text:
                hits.append(f"{path}: {pattern}")
if hits:
    print("\\n".join(hits))
    raise SystemExit(1)
PY
```

Expected: no positive forbidden marketing claims. Legal/FAQ disclaimers may mention terms only to say the product is not those things.

- [ ] **Step 4: Commit**

Run:

```bash
git add web
git commit -m "feat: add valuation marketing site"
```
