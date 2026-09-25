---
name: AccountIQ marketing site
description: Warm paper, navy ink, a light serif with italic phrases, and a sample report as the main picture.
colors:
  paper: "#f5f1ea"
  white: "#fffdf9"
  line: "#e3ddd1"
  navy: "#1b1464"
  navy-deep: "#120d4a"
  text: "#3a3766"
  muted: "#666385"
  on-navy: "#ffffff"
  on-navy-soft: "#cfcbf3"
  red-tick: "#c8102e"
typography:
  display:
    fontFamily: "Newsreader, Georgia, serif"
    fontSize: "clamp(2.8rem, 5.4vw, 4.6rem)"
    fontWeight: 400
    lineHeight: 1.03
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Newsreader, Georgia, serif"
    fontSize: "clamp(2.1rem, 3.6vw, 3.1rem)"
    fontWeight: 400
    lineHeight: 1.08
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 600
rounded:
  card: "14px"
  sheet: "6px"
  pill: "999px"
spacing:
  container: "1120px"
  section: "clamp(72px, 9vw, 120px)"
components:
  button-primary:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.on-navy}"
    rounded: "{rounded.pill}"
    height: "56px"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.navy}"
    rounded: "{rounded.pill}"
    height: "56px"
  card:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.card}"
  footer:
    backgroundColor: "{colors.navy-deep}"
    textColor: "{colors.on-navy-soft}"
---

# Design System: AccountIQ marketing site

## Overview

Chosen on 24 September 2026 from four directions on the Claude Design canvas "AccountIQ home page ideas" (direction A, "The report you get"), then polished using Wallace Real Estate (wallacerealestate.co.nz) as the reference for how a premium New Zealand service site feels. Screenshots of Wallace are in `.impeccable/references/wallace/`, and 15 valuation sites are in `.impeccable/references/valuation-sites/`.

What we took from Wallace: one ink colour for all text on warm off-white, a light serif for headings with an italic phrase inside the heading, pill buttons with an arrow, a header that stays at the top as you scroll, a large centred statement between sections, figures set large in the serif above a hairline, and serif column headings in the footer. What we did not take: their typefaces (IvyPresto and Usual are paid Adobe fonts), their green, or their photography.

This covers the public marketing site: `web/app/(marketing)/*` and `web/components/marketing/*`. Tokens are scoped to `.marketing-page` in `web/components/marketing/marketing.css`. The other marketing pages (`/valuation`, `/blog`, the Markdown pages) share the header, footer, fonts and colours, but their bodies still use the older `marketing-*` classes in `web/app/globals.css`. The signed-in product is outside this system.

## Wordmark

`web/components/marketing/wordmark.tsx`. "AccountI" set in Instrument Sans at 650 weight, then a Q drawn in SVG whose tail is the reviewer's red tick. It says in the name what the product promises: every report is checked. The link around it carries the accessible name. The tick is the only red on the page apart from the tick on the sample report.

## Colours

- **Paper** `#f5f1ea`: the page. **White** `#fffdf9`: every other section band, so the page alternates paper and white.
- **Navy** `#1b1464`: headings, links, buttons, the closing band. **Deep navy** `#120d4a`: footer and button hover.
- **Text** `#3a3766` for body copy and **muted** `#666385` for labels and notes. Both pass 4.5 to 1 on paper and white.
- **Line** `#e3ddd1`: every hairline and card border.
- **Red** `#c8102e`: the tick in the wordmark and on the sample report. Nothing else.

## Typography

Newsreader (variable, optical sizes, with italics) for h1, h2, figures and card titles, always at 400 weight. Italic marks the phrase that carries the point, and only where there is one: the hero ("Know what your business is worth *before you talk to a buyer.*"), the centred statement, and "A chartered accountant *reads every report*". Section labels like "How it works" stay upright. Three italic phrases a page at most.

Instrument Sans for everything else: body at 1.0625rem (the 17px floor in PRODUCT.md), notes and captions at 1rem, small headings (h3) at 600, buttons and nav at 500. Only the text inside the sample report drawing goes smaller, because it is a picture of a document.

Both fonts load in `web/app/(marketing)/layout.tsx`, not the root layout, so the signed-in app does not download them.

## Layout

A 1120px container. Sections are `clamp(72px, 9vw, 120px)` tall at the top and bottom and alternate paper and white. Two patterns repeat:

- **Split:** heading and intro on the left (5 parts), content on the right (7 parts). On desktop the left side stays in view while the right scrolls.
- **Head and grid:** heading with intro on one line, then a grid of cards (report parts, steps, posts).

At 960px the hero and splits go to one column and the header nav folds into the menu. At 720px the grids go to one column and the side margins are 20px. At 400px the header tightens so the wordmark, the button and the menu still fit at 320px. The menu closes itself after a link is followed and on Escape (`menu-disclosure.tsx`).

## Components

- **Header:** sticky, paper at 88 percent with a blur behind it. A hairline and soft shadow fade in over the first 64px of scroll (CSS scroll timeline, with a plain hairline where that is not supported).
- **Buttons:** pills, 56px tall on the page and 44px in the header, with an arrow that moves 3px on hover. Primary is navy, quiet is a navy outline, light is white on the navy band.
- **Sample report:** a report front page with two sheets fanned behind it. The figures are for a made-up business and match how the real report works: each normalisation on its own line, normalised profit, a discounted cash flow in low, mid and high cases, and market multiples as a cross-check. Keep it in step with `backend/report_prompts.py` and `valuation_tables.py`. The "Where the number comes from" list repeats the same lines with the same figures, so the reader can match them.
- **Facts row:** fee, turnaround and "Every report" as large serif text between hairlines, under the hero.
- **Statement:** one centred serif sentence, the first half italic.
- **Cards:** paper on white (or the reverse), 14px corners, a hairline border, no shadow.
- **Price list:** each option with a bar scaled to its price. Ours is navy, the rest are grey.
- **Reviewer:** a split section with the review described in plain words and a signed line with the red tick. No placeholder image: William's photo, where he practises and years in practice go here once we have them.
- **What happens to your accounts:** four plain lines beside "Who this is not for". Each is true of the code today and must be signed off under Launch Gate 3 before launch.

## Motion

On load the report front rises into place, the sheets behind fan out, and the tick draws itself. All of it sits inside `prefers-reduced-motion: no-preference`. Buttons change colour and the arrow nudges on hover. Nothing else moves.

## Do and don't

- **Do** keep every figure on the sample report consistent with the real report's method.
- **Do** use one italic phrase per heading, not more.
- **Don't** add red anywhere except a reviewer's tick.
- **Don't** use shadows on cards. Only the sample report sheets cast shadows.
- **Don't** put stock photos or placeholder images on the page. Add William's real photo when we have it.
- **Don't** make a claim about data, fees or turnaround the code or PRODUCT.md does not support. The GST note covers other providers' prices only until the GST decision is made.
