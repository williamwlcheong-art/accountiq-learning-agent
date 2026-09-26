# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

New Zealand business owners, roughly 45 to 65, with turnover between about
$500,000 and $10 million. Manufacturing, trades, services, franchise sites. Not
finance people.

They arrive because something has already happened: a buyer has made an
approach, a shareholder wants out, the bank has asked for a number, a
relationship has ended. They want to know what the business is worth and why,
before they talk to anyone with an interest in the answer. They are wary of
uploading their annual accounts to a website they have not heard of.

Accountants and business brokers are a second audience, served by one page.

## Product Purpose

The owner uploads two to three years of annual financial statements, answers
questions about the business, pays one fixed fee, and receives an indicative
business valuation report as a web report and PDF. Software prepares the draft;
a person reviews every report against the statements before it is released.

Success is an owner who pays because the site made the report, the person
behind it and the price all believable, and who then uses the report in a real
conversation with a buyer, bank or shareholder.

## Positioning

It reads the owner's actual statements, which a $60 comparable-sales report
(Bizstats) does not, and it comes back in days at a published price, where an
accountant-prepared report (Bizval, $2,250 to $5,200) takes 7 to 21 working days
and a certified valuation (Fealty, $4,900 to $9,900) takes weeks. Competitor
prices were read from their own sites on 2026-09-16.

It is indicative only. Not financial advice, not a certified or court-standard
valuation. Court, IRD, Family Court and formal disputes need a registered
valuer, and the product says so.

## Operating Context

Owners typically read on a laptop at the office after hours, or on a phone
between jobs. The report is handed to buyers, lenders, co-shareholders and
accountants, so it has to look like a document a professional would stand
behind.

The product app lives in the same Next.js codebase (`web/`); the marketing site
shares its header, footer and brand with the signed-in portal.

## Capabilities and Constraints

- Upload of PDF or Excel statements, extraction, valuation questions, Stripe
  checkout, admin review before release, web report and WeasyPrint PDF.
- All eight launch gates in `.planning/commercial/LAUNCH-GATES.md` are open.
  The product must not take public payments until they close.
- **Placeholder, confirmed for design use only (2026-09-23):** fee of $1,200;
  turnaround of 3 working days; William Cheong named as a chartered accountant
  who reviews every report, with no CA ANZ logo. All three need William's sign-off
  before launch.
- GST treatment of the fee is undecided.
- There is no refund path in the code yet.
- Report sections: business overview, market position, financial performance,
  normalisations, balance sheet summary, valuation methodology, WACC
  assumptions, DCF analysis, valuation summary, multiples cross-check.

## Brand Commitments

- The AccountIQ wordmark.
- New Zealand English. Plain, straight-talking voice: a chartered accountant
  talking to an owner across a table. No em dashes, no consultant-speak.
- Say New Zealand, not "New Zealand and Australia". Australia is not available.

## Evidence on Hand

- No real sample report. The PDFs in `data/` are test output with placeholder
  text and must not be shown.
- No testimonials, customer count, logos, or photograph of William.
- Competitor prices above, verified on their own pages.
- One drafted blog post: `web/content/posts/what-is-my-business-worth.md`.
- Any sample report shown on the site must be for a made-up company and labelled
  as a sample. Do not invent customers, quotes or counts.

## Product Principles

1. Show the document. The product is a report; the site shows it rather than
   describing it.
2. Numbers in the open. Price, turnaround and what alternatives cost are stated,
   not hinted at.
3. A named person, not "a reviewer".
4. Say who it is not for. The limits are part of the pitch, not small print.
5. Plain words an owner uses about their own business.

## Accessibility & Inclusion

WCAG AA contrast, visible focus states, usable at 320 pixels wide. Older
readers: body text no smaller than 17px on marketing pages.
