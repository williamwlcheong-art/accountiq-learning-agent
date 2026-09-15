# Marketing site design

Date: 2026-09-16
Status: approved, ready for planning

## Why this exists

AccountIQ has one public page. The root address redirects signed-out visitors to
`/valuation`, the offer page, and nothing else exists. A visitor cannot read
what the company is, what a report costs, who is behind it, or what the terms
are. That is workable while every visitor arrives from a link someone sent them.
It stops working the moment the address is shared publicly, an ad runs, or
anyone looks for the company before buying a report.

This spec covers a marketing site built inside the existing Next.js app, with
content written as Markdown files in the repo.

## Decisions already made

| Question | Decision |
|---|---|
| Who publishes content | William edits Markdown in the repo. Publishing is a commit. No CMS. |
| Where it is built | Inside the existing Next.js app in `web/`, not a separate site. |
| Audience | Business owners first, with one page for accountants and advisors. |
| Geography | New Zealand now. Australia mentioned as coming, not promised. |
| Brand | The wordmark, navy and type the app already uses. A brand pass is separate later work. |
| Domain | Marketing site at the root domain, portal under `app.`, hostname held in one config value. |
| Blog at launch | Five posts drafted with the marketing and SEO skills, published under William's name after he reviews them. |

## Site structure

Pages, all under one `(marketing)` route group with its own layout:

| URL | Source | Purpose |
|---|---|---|
| `/` | React page | Home. What AccountIQ is, who it is for, one call to action. |
| `/valuation` | React page (exists) | The offer page. Unchanged except for its place in the nav. |
| `/pricing` | Markdown | The fixed fee, what is included, what is not. |
| `/how-it-works` | Markdown | The process in depth, including the review step. |
| `/about` | Markdown | William's background and why the product exists. |
| `/for-advisors` | Markdown | How a firm orders or refers. |
| `/contact` | Markdown | Email address and response expectation. No form. |
| `/terms` | Markdown | Terms of use. Needs legal review before publishing. |
| `/privacy` | Markdown | Privacy statement. Needs legal review before publishing. |
| `/blog` | React page | Post index, newest first. |
| `/blog/[slug]` | Markdown | One post. |
| `/blog/tag/[tag]` | React page | Posts carrying one tag. |

Home and the offer page stay as React because their layout is bespoke. Every
other page is Markdown so William can edit it without touching code.

`/login`, `/reports`, `/wizard`, `/account` and `/admin` are untouched. The root
route keeps redirecting signed-in customers to `/reports` and admins to
`/admin`; only the signed-out branch changes, from a redirect to the home page.

### Shell

One header across the marketing pages: wordmark, five links (Valuation, How it
works, Pricing, Blog, About), a Sign in link, and one call to action. Below
860px the links collapse into a menu button, matching the breakpoint the offer
page already uses.

One footer: company line, contact email, For advisors, Terms, Privacy, and the
sentence about the report being indicative only.

### Domain split

Today both the site and the app run on one host. When the split happens, the
`(marketing)` group serves the root domain and everything else moves under
`app.`. Sign-in links and calls to action read the app origin from a single
config value so the change is one variable, not a search through the markup.

## Content system

Two dependencies are added to `web/`: `gray-matter` for front matter and
`remark` with `remark-html` for the body. Both are small and maintained. No MDX,
so a post never contains code.

Content lives in `web/content/`:

```
web/content/
  pages/*.md     pricing, how-it-works, about, for-advisors, contact, terms, privacy
  posts/*.md     one file per blog post, filename becomes the slug
```

Front matter on every file:

| Field | Required | Use |
|---|---|---|
| `title` | yes | Page heading and meta title |
| `description` | yes | Meta description and blog card text |
| `date` | posts | Published date |
| `updated` | no | Shows as a last reviewed line. Valuation content dates quickly. |
| `author` | posts | Defaults to William |
| `tags` | posts | Drives the tag pages |
| `image` | no | Social card image, from `web/public/blog/` |
| `draft` | no | Visible in local development, left out of the build |

One loader module, `web/lib/content.ts`, with three functions: list posts, get a
post by slug, get a page by slug. Nothing else reads the folder. Pages and posts
are static at build time, with the post and tag routes generated from the folder
listing. Rendered body text gets one `.prose` block in the stylesheet.

Not in scope at launch: comments, search, and RSS. RSS is a small addition once
there are posts worth subscribing to.

## Pages

**Home.** Left-aligned hero saying what AccountIQ is in one sentence and who it
is for, with one call to action to the valuation page. Then four sections: the
situations owners are in when they need a number, how the report is made, why
the review step matters, and the three most recent posts. No statistics, no
customer logos and no testimonials until there are real ones.

**Pricing.** The fixed fee in New Zealand dollars with GST stated, what is
included, what is not (no certified valuation, no financial advice), when
payment is taken, and refund terms in one paragraph. William supplies the
number. The page is not published without it.

**How it works.** What the customer needs ready before starting, what happens at
each stage, and what the reviewer checks. Turnaround time is added once William
commits to one he can keep.

**About.** William's background and why the product exists, in first person if
he is comfortable with that.

**For advisors.** How a firm orders for a client or refers one, what the review
step means for their own risk, Australia as coming, and an email call to action
rather than a form.

**Contact.** Email address and how quickly someone replies. No form, which
avoids spam handling and any backend work.

**Terms and privacy.** Drafted from standard New Zealand SaaS terms and the
Privacy Act 2020 principles, and clearly flagged for William's lawyer before
publishing.

## SEO

- Per-page titles and descriptions from front matter, canonical URLs, Open Graph
  and Twitter cards with a default image.
- `sitemap.xml` and `robots.txt` generated by Next from the content folder.
  Drafts are excluded and the app routes are disallowed.
- JSON-LD: `Organization` on every page, `Service` on the valuation and pricing
  pages, `Article` on posts, `FAQPage` on the offer page questions,
  `BreadcrumbList` on posts. These are schema.org type names and keep their US
  spelling.
- One primary search term per page, chosen by the SEO skills before any copy is
  written, using New Zealand phrasing.
- One `h1` per page and no skipped heading levels. The Playwright check on the
  offer page already asserts this and extends to the new pages.
- Image alt text is required by the loader rather than optional.
- Every post links to the offer page at least once.

## Copy production

1. **Positioning brief** from the product marketing skill: who the owner is, the
   moment they start looking for a number, what they are afraid of, and the one
   promise AccountIQ can keep. Every headline traces back to this brief.
2. **Keywords** from the SEO skills: one primary term per page and five post
   topics drawn from what New Zealand owners actually search for. Likely topics
   include what a small business is worth, what buyers look at first, why profit
   and value differ, how to prepare accounts before a sale, and what an
   indicative valuation can and cannot tell you.
3. **Drafting** with the copywriting skill against the brief and the keyword.
   Plain English, New Zealand spelling, and no claim the product cannot keep. No
   price until William supplies one and no turnaround time until he commits to
   one.
4. **Anti-AI pass** with both the `ai-copywriter` and `de-ai-ify` skills before
   anything is committed. The writing hook re-checks every Markdown file as it
   is written.
5. **Review.** Every page and post ships with `draft: true`. William reads,
   edits, and flips the flag. Legal pages carry a note that they need his
   lawyer.

## Testing

- One Playwright spec that walks the home page, each navigation link, a blog
  post and a tag page, and confirms the call to action lands on registration.
- The existing `/valuation` spec keeps its assertions about no price and the
  required disclaimers.
- A build-time check that every content file carries the required front matter
  and that no published post is still marked as a draft.
- The signed-in redirect tests stay as they are, with one added for the
  signed-out root now rendering the home page instead of redirecting.

## Rollout

This ships as its own pull request after PR #26 merges (it adds the NZ market
intelligence layer, payment hardening, auth polish and the customer portal),
because both touch the root route.

Estimated three days: one for the shell, pages and content system, one for copy
and posts, one for SEO, tests and review fixes.

## Open items for William

- The fixed fee, with GST treatment.
- A turnaround time he can keep.
- Whether the about page is written in his own voice.
- Legal review of the terms and privacy pages.
- The domain, once registered.
