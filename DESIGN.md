---
name: AccountIQ marketing site
description: A white page, near-black text, one sans typeface, navy for the wordmark, links and buttons, and a sample report as the only picture.
colors:
  page: "#ffffff"
  line: "#e5e5ea"
  navy: "#1b1464"
  navy-deep: "#120d4a"
  ink: "#15151e"
  text: "#34353f"
  muted: "#62646f"
  on-navy: "#ffffff"
  red-tick: "#c8102e"
typography:
  display:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "clamp(2.25rem, 4.4vw, 3.25rem)"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "clamp(1.5rem, 2.4vw, 1.875rem)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 600
rounded:
  button: "8px"
  sheet: "8px"
spacing:
  container: "1120px"
  section: "clamp(56px, 7vw, 88px)"
components:
  button-primary:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.on-navy}"
    rounded: "{rounded.button}"
    height: "48px"
  button-quiet:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    rounded: "{rounded.button}"
    height: "48px"
  footer:
    backgroundColor: "{colors.page}"
    textColor: "{colors.text}"
---

# Design System: AccountIQ marketing site

## Overview

On 11 November 2026 Dave asked for the site to be toned back: a clean white page, simpler, with the look that reads as machine-made taken out. This replaces direction A from 24 September 2026 (warm paper, a serif with italic phrases, pill buttons with arrows, a fanned stack of report pages).

What was removed, so it does not come back: the cream background and alternating bands, the serif and its italic phrases, pill buttons and arrows, the fanned pages and their entrance animation, the row of large figures under the hero, the centred statement between sections, numbered cards, card boxes, price bars, the blurred header, the navy closing band and the navy footer.

This covers the public marketing site: `web/app/(marketing)/*` and `web/components/marketing/*`. Tokens are scoped to `.marketing-page` in `web/components/marketing/marketing.css`. The signed-in product is outside this system.

## Wordmark

`web/components/marketing/wordmark.tsx`. "AccountI" set in Instrument Sans at 650 weight, then a Q drawn in SVG whose tail is the reviewer's red tick. It says in the name what the product promises: every report is checked. The link around it carries the accessible name.

## Colours

- **Page** `#ffffff`: every section and the footer.
- **Ink** `#15151e` for headings, **text** `#34353f` for body copy, **muted** `#62646f` for notes. All pass 4.5 to 1 on white.
- **Navy** `#1b1464`: the wordmark, buttons, links in articles and the band on the sample report. **Deep navy** `#120d4a`: button hover.
- **Line** `#e5e5ea`: every hairline and border.
- **Red** `#c8102e`: the tick in the wordmark and on the sample report. Nothing else.

## Typography

Instrument Sans for everything. Headings (h1, h2) at 600 weight with tight tracking, small headings (h3) at 600 and body size, body at 1.0625rem (the 17px floor in PRODUCT.md), notes at 1rem. No italics for emphasis. Only the text inside the sample report goes smaller, because it is a picture of a document.

The font loads in `web/app/(marketing)/layout.tsx`, not the root layout, so the signed-in app does not download it.

## Layout

A 1120px container. Each section starts with a hairline and has `clamp(56px, 7vw, 88px)` of space above and below. Sections use one pattern: the heading and any intro on the left (4 parts), the content on the right (8 parts). The content is a plain list of rows (a label, then the explanation), a list, or a paragraph.

At 960px the two columns stack and the header nav folds into the menu; the hero keeps the report beside the copy down to 720px. At 720px the hero goes to one column and the side margins are 20px. Below 375px the header tightens so the wordmark, the button and the menu still fit at 320px. The menu closes itself after a link is followed and on Escape (`menu-disclosure.tsx`).

## Components

- **Header:** sticky, white, with a hairline under it.
- **Buttons:** 8px corners, 48px tall on the page and 44px in the header, no icon. Primary is navy, quiet is white with a grey border.
- **Sample report:** one flat page with a hairline border. The figures are for a made-up business and match how the real report works: each normalisation on its own line, normalised profit, a discounted cash flow in low, mid and high cases, and market multiples as a cross-check. Keep it in step with `backend/report_prompts.py` and `valuation_tables.py`. The "Where the number comes from" list repeats the same lines with the same figures, so the reader can match them.
- **Rows:** `.home-glosses`. A label on the left and the explanation on the right, with a hairline between rows. The steps use the same rows with a number in front, because their order matters.
- **Price list:** name, price and a one-line note. Ours is in bold.
- **Reviewer:** the review described in plain words. William's photo, where he practises and years in practice go here once we have them.
- **What happens to your accounts:** four plain lines. Each is true of the code today and must be signed off under Launch Gate 3 before launch.
- **Post cards:** the one place a box is used, because each is a link.

## Motion

Buttons and links change colour on hover. Nothing else moves.

## Do and don't

- **Do** keep every figure on the sample report consistent with the real report's method.
- **Do** add a new section in the same pattern: hairline, heading on the left, content on the right.
- **Don't** add red anywhere except a reviewer's tick.
- **Don't** add shadows, gradients, tinted backgrounds, a second typeface, icons in buttons or entrance animation.
- **Don't** put stock photos or placeholder images on the page. Add William's real photo when we have it.
- **Don't** make a claim about data, fees or turnaround the code or PRODUCT.md does not support. The GST note covers other providers' prices only until the GST decision is made.
