---
name: AccountIQ
description: Fixed-fee SME valuation reports with clear status, payment, and human review.
colors:
  ink: "#13202f"
  muted: "#607084"
  line: "#d8e1eb"
  paper: "#ffffff"
  wash: "#f4f7fa"
  valuation-blue: "#126a9f"
  valuation-blue-deep: "#0a3d62"
  review-green: "#9bc83d"
  review-green-deep: "#557a14"
  review-green-hero: "#cfef78"
  review-green-hover: "#acd94c"
  advisory-gold: "#d69e2e"
  danger: "#b42318"
  danger-bg: "#fff1f0"
  danger-line: "#f5c2bd"
  cta-ink: "#142208"
typography:
  display:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "clamp(2.55rem, 5vw, 5.2rem)"
    fontWeight: 800
    lineHeight: 0.98
    letterSpacing: "0"
  headline:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "clamp(1.8rem, 3vw, 3.1rem)"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "0"
  title:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "1.1rem"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "0"
  body:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "0"
  label:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "0.08em"
rounded:
  sm: "6px"
  md: "7px"
  lg: "8px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "14px"
  lg: "24px"
  section: "72px"
components:
  button-primary:
    backgroundColor: "{colors.review-green}"
    textColor: "{colors.cta-ink}"
    rounded: "{rounded.md}"
    padding: "0 18px"
    height: "46px"
  button-primary-hover:
    backgroundColor: "{colors.review-green-hover}"
    textColor: "{colors.cta-ink}"
    rounded: "{rounded.md}"
    padding: "0 18px"
    height: "46px"
  card-panel:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "24px"
  text-field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "46px"
---

# Design System: AccountIQ

## 1. Overview

**Creative North Star: "The Reviewed Ledger"**

AccountIQ should feel like a calm working file that has already passed through a careful professional's hands. The interface is direct, legible, and commercially credible; it leads with the fixed-fee valuation outcome and then proves the workflow, review step, compliance boundary, and customer status.

The visual system rejects broad SaaS platform language, generic finance stock imagery, abstract AI-first positioning, purple/blue gradient startup tropes, and decorative glassmorphism. Blue is allowed because it is the brand and trust base, but it must be paired with white space, ledger-like structure, and a measured green review accent so the product does not become another startup gradient.

**Key Characteristics:**
- Calm commercial confidence, not hype.
- High-trust information density with readable spacing.
- Human review as a visible product step.
- Fixed-fee clarity before payment or document upload.
- Compliance boundaries treated as product clarity, not fine print.

## 2. Colors

The palette is a professional trust system: deep valuation blue for brand and structure, review green for primary action and reviewed status, and quiet neutrals for the working surfaces.

### Primary
- **Valuation Blue** (#126a9f): Used for the hero field, brand emphasis, valuation amounts, and product headings. It is the main credibility color, not a decorative wash.
- **Deep Valuation Blue** (#0a3d62): Used for the brand mark, hero depth, and high-contrast structural anchors.

### Secondary
- **Review Green** (#9bc83d): Used for primary CTAs, positive review states, and rare trust accents on dark or button surfaces.
- **Deep Review Green** (#557a14): Used for labels and review text on light backgrounds because it meets contrast where Review Green does not.
- **Hero Review Green** (#cfef78): Used only for green label text on the blue hero.
- **Hover Review Green** (#acd94c): Used only for primary button hover state.

### Tertiary
- **Advisory Gold** (#d69e2e): Reserved for future advisory, escalation, or premium consultation cues. It must stay rare until the consulting offer is real.
- **Danger Red** (#b42318): Used only for blocking errors, failed payment, failed extraction, or invalid form states.
- **Danger Surface** (#fff1f0): Used behind blocking error messages.
- **Danger Line** (#f5c2bd): Used as the border around blocking error messages.

### Neutral
- **Ledger Ink** (#13202f): Primary text and icon color.
- **Muted Slate** (#607084): Secondary copy, helper text, and low-emphasis metadata.
- **Ruled Line** (#d8e1eb): Borders, dividers, and quiet containment.
- **Paper** (#ffffff): Cards, forms, and report surfaces.
- **Soft Wash** (#f4f7fa): Page background and low-emphasis section bands.

### Named Rules

**The Review Accent Rule.** Review Green is a trust signal, not a theme. Use it for the primary action, review status, or a single proof cue; never wash whole sections in green.

**The No Unverified Proof Rule.** CAANZ logos, professional credentials, testimonials, and social proof are forbidden unless entitlement and permission are clear.

**The Blue With Air Rule.** Blue can carry the hero and brand, but every blue surface must be balanced by Paper, Soft Wash, or structured report UI nearby.

## 3. Typography

**Display Font:** Inter with system sans fallbacks.
**Body Font:** Inter with system sans fallbacks.
**Label/Mono Font:** Inter with system sans fallbacks.

**Character:** The type is plainspoken and contemporary, with enough weight to feel accountable. It should look like a professional report interface, not a consumer fintech app.

### Hierarchy
- **Display** (800, `clamp(2.55rem, 5vw, 5.2rem)`, 0.98): Used only for the homepage hero and major empty states.
- **Headline** (800, `clamp(1.8rem, 3vw, 3.1rem)`, 1.05): Used for public site section headings and major dashboard groupings.
- **Title** (800, `1.1rem`, 1.2): Used for product cards, panel titles, and report preview headings.
- **Body** (400, `1rem`, 1.6): Used for explanatory copy, product descriptions, and customer workflow text. Keep long-form body copy around 65-75 characters per line.
- **Label** (800, `0.78rem`, `0.08em`, uppercase only when rare): Used for one leading context label, not every section.

### Named Rules

**The One Eyebrow Rule.** A page may use one small uppercase label to orient the user. Repeating uppercase labels above every section is forbidden.

**The Report Voice Rule.** Headings must make concrete promises about workflow, price, review, or report status. Avoid vague category labels such as "Solutions" or "Platform".

## 4. Elevation

AccountIQ uses a hybrid of ruled-line containment and low ambient shadow. Surfaces should feel like report pages or working panels, not floating marketing cards. Depth is allowed only when it clarifies a task surface or separates the report preview from the hero.

### Shadow Vocabulary
- **Panel Lift** (`box-shadow: 0 6px 14px rgba(19, 32, 47, 0.08)`): Use for report previews, auth panels, and dashboard panels.
- **Selected Control** (`box-shadow: 0 4px 12px rgba(19, 32, 47, 0.1)`): Use only for selected segmented controls.
- **Featured Product Rule** (`box-shadow: inset 0 4px 0 #126a9f`): Use as an inset marker for the primary product, not as decorative depth.

### Named Rules

**The No Glass Rule.** Translucent cards, blur panels, frosted glass, and heavy ambient glow are prohibited.

**The Line Before Shadow Rule.** Use borders and section rhythm first. Add shadow only when a surface contains an active workflow or preview.

## 5. Components

### Buttons
- **Shape:** Gently squared professional corners (7px radius).
- **Primary:** Review Green background (#9bc83d) with Cta Ink text (#142208), 46px minimum height, 18px horizontal padding, and icon support.
- **Hover / Focus:** Hover brightens to #acd94c and lifts 1px. Focus must use the visible green 3px outline with 3px offset.
- **Secondary:** White or translucent surface with a 1px border. Use it for lower-risk navigation such as viewing products.

### Chips
- **Style:** AccountIQ does not currently have a separate chip system. Use proof-list rows or segmented controls instead of inventing pill-heavy UI.

### Cards / Containers
- **Corner Style:** Consistent 8px radius for panels and cards.
- **Background:** Paper (#ffffff) over Soft Wash (#f4f7fa) or the blue hero.
- **Shadow Strategy:** Use Panel Lift only for workflow surfaces; product cards should stay mostly flat.
- **Border:** 1px Ruled Line (#d8e1eb) on all panels and cards.
- **Internal Padding:** 22px for report previews, 24px for panels and product cards.

### Inputs / Fields
- **Style:** White field, 1px Ruled Line border, 7px radius, 46px minimum height.
- **Focus:** Keep the visible green focus outline. Do not rely on color-only border changes.
- **Error / Disabled:** Errors use Danger Red (#b42318) on a pale red surface with a clear border and text explanation.

### Navigation
- **Style:** Brand link and nav links use 44px minimum targets. Desktop nav is compact and direct; mobile wraps without hiding primary actions.
- **Typography:** 650-800 weight, no negative letter spacing.
- **States:** Visible focus is mandatory. Active marketing nav may use text color or subtle underline; do not create tab-like chrome in the hero nav.

### Report Preview

The report preview is the signature public component. It should show real business-report concepts such as revenue, EBITDA, indicative range, and review status. It must not imply a certified valuation, guaranteed value, financial advice, or instant automated output.

## 6. Do's and Don'ts

### Do:
- **Do** lead with the concrete customer outcome: a fixed-fee indicative business valuation report.
- **Do** build trust before asking for money or financial documents.
- **Do** show review, payment, validation, and status as plain workflow steps.
- **Do** use Deep Review Green (#557a14) for green text on light surfaces, and reserve Review Green (#9bc83d) for CTAs or dark-surface accents.
- **Do** keep controls at 44px minimum touch target size where possible.
- **Do** respect `prefers-reduced-motion` and keep animation to state feedback only.

### Don't:
- **Don't** use broad SaaS platform language.
- **Don't** use generic finance stock imagery.
- **Don't** use abstract AI-first positioning.
- **Don't** use purple/blue gradient startup tropes.
- **Don't** use decorative glassmorphism.
- **Don't** claim "instant valuation", "certified valuation", "financial advice", "guaranteed valuation", "court-standard", or "AI replaces your adviser".
- **Don't** use CAANZ logos, professional credentials, testimonials, or social proof unless permission and entitlement are clear.
- **Don't** let green body text sit below WCAG AA contrast on light backgrounds.
