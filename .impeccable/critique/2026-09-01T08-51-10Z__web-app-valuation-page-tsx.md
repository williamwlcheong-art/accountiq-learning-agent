---
target: landing/login pages (/valuation + /login)
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 2
timestamp: 2026-09-01T08-51-10Z
slug: web-app-valuation-page-tsx
---
Method: dual-agent (A: design-review subagent · B: detector/browser subagent)

# Design critique: AccountIQ valuation landing (/valuation) + login (/login)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | "Working..." on submit is vague; no sense of place in the 7-step journey after a CTA click |
| 2 | Match System / Real World | 3 | Plain-English copy; "normalised earnings adjustments" assumes accountant literacy |
| 3 | User Control and Freedom | 2 | Register mode is client state only (refresh loses it); no path off the login card except one buried link |
| 4 | Consistency and Standards | 1 | Two brands: marketing navy #1b1464 vs app navy #1a2a40 + #2563eb button; CTA label drifts; paid CTA lands on "Sign in" |
| 5 | Error Prevention | 2 | Password length hint renders under the confirm field, not the password field, register mode only |
| 6 | Recognition Rather Than Recall | 3 | Sections self-labelled; login card gives no hint what follows sign-in |
| 7 | Flexibility and Efficiency | 1 | Login: no forgot-password, no show-password toggle, no remember-me (n/a for the Persuade landing itself) |
| 8 | Aesthetic and Minimalist Design | 3 | Disciplined and quiet; 7 steps orphan a 3-item row in a 4-col grid; disclaimer repeats 5 times |
| 9 | Error Recovery | 2 | Good role="alert" with specific messages, but "Incorrect email or password" is a dead end with no reset path |
| 10 | Help and Documentation | 3 | FAQ answers the real pre-purchase questions; best section on the page |
| **Total** | | **22/40** | **Acceptable** |

## Design Specificity Verdict

**LLM assessment:** Category-interchangeable SaaS boilerplate with unusually careful legal copy. Strip the word "valuation" and the template (eyebrow sections, 3-card grid, checklist, numbered steps, FAQ, centred final CTA) could sell payroll software. NZ presence is one trust-strip line and NZ spelling; the font stack is Arial/Helvetica; no named humans, no NZD price, no firm credentials. The hero report-preview card is the one genuinely product-specific artefact.

**Deterministic scan:** Zero static findings in the four TSX files. Runtime detector on /valuation: 6 console findings plus page-level extras, dominated by one deliberate convention (uppercase `marketing-eyebrow` kickers flagged 7 ways: treat as a single stylistic choice, largely false positive), plus real hits: `extreme-negative-tracking` on the hero H1 (-0.06em), `border-accent-on-rounded` + `gpt-thin-border-wide-shadow` on the report-preview aside, `cramped-padding` on the trust strip, and `monotonous-spacing` (one ~4px gap used 92% of the time). /login: `flat-type-hierarchy` (max ratio 1.5:1), which corroborates the brand-discontinuity finding. Detector and reviewer independently agreed on the hero tracking and the two-designs problem.

## Overall Impression

Honest, accessible, legally careful, and visually anonymous. The copy earns trust that the conversion mechanics then spend: every CTA lands a new buyer on a sign-in form, the "fixed fee" section shows no fee, and the brand changes clothes at the exact moment of commitment.

## What's Working

1. Honest scope-setting copy: FAQ and "Software speed, with a review checkpoint" preempt the objections an SME owner or their accountant would actually raise.
2. Real accessibility work: skip link, aria-hidden decorative preview, focus-visible outlines with halo, labelled nav regions, role="alert" errors.
3. The hero report-preview card shows the buyer the artefact they are buying, above the fold, stamped "Reviewed before delivery".

## Priority Issues

1. **[P0] Every acquisition CTA lands on sign-in, not registration.** All five "Get a (Business) Valuation" CTAs link to /login, which defaults to "Sign in to AccountIQ"; "Create account" is the last, smallest element on the card. This is the single conversion moment of the funnel. Fix: support /login?mode=register, point acquisition CTAs there, heading "Create your AccountIQ account". Suggested: /impeccable polish.
2. **[P0] No password recovery.** Paying customers return weeks later for their reviewed PDF; a forgotten password is a lost delivery. Fix: "Forgot password?" link by the password label, wired to a reset flow (mailto stopgap acceptable). Suggested: /impeccable harden.
3. **[P1] Brand discontinuity landing → auth.** Marketing #1b1464/white vs auth #1a2a40/#2563eb/grey; detector's flat-type-hierarchy on /login corroborates. The handoff at the moment of commitment reads as a different, cheaper product. Fix: one token set; restyle auth card and button in the marketing palette; carry the wordmark over. Suggested: /impeccable polish.
4. **[P1] Pricing section with no price, footer with no identity.** Fixed-fee promise with no number; footer has no legal entity, NZBN, contact, terms, or privacy links, and the named human reviewer trust claim shows zero humans. Fix: state the fee (or "from $X NZD") and build a real footer. Copy/product decision William owns. Suggested: /impeccable clarify.
5. **[P2] Mobile rough edges.** "Sign in" header link wraps at 375px; anchor nav disappears entirely below 860px; 7 steps orphan a 3-row in a 4-col grid; hero H1 tracking -0.06em reads crushed (detector agrees). Suggested: /impeccable adapt.

## Persona Red Flags

**Jordan (first-timer):** clicks "Get a Business Valuation" → greeted as an existing user; may attempt sign-in with fresh details and hit "Incorrect email or password". The "Learn about the valuation advisory" link sits above "Create account", looping back to the page just left.

**Casey (mobile):** header "Sign in" wraps; ~6,400px of scroll with no anchor shortcuts below 860px; pricing panel arrives with no number after the whole scroll.

**Riley (stress tester):** register mode lost on refresh (useState only); password hint under the wrong field; no per-page title on /login so the tab can't be found among several.

## Minor Observations

- Hero H1 letter-spacing -0.055em with line-height 0.98 in bold Arial: descenders nearly collide.
- Every interactive element on the landing resolves to /login; the nav is theatre.
- FAQ details elements use default triangle markers, unstyled next to the polish elsewhere.
- "Working..." should be "Signing in..." / "Creating account...".
- /login has no metadata export; the conversion page has no SEO identity while /valuation does.
- Auth card's 48px shadow is the only elevation in the design language (detector: thin-border-wide-shadow on the preview aside too).

## Questions to Consider

1. If the fee is genuinely fixed, why not print "NZ$X, confirmed before you pay" in the hero?
2. Would one named reviewer with a credential (CA, RBV) and a photo convert more than all five disclaimers combined?
3. Who is the page for: the owner or the owner's accountant? Choosing would resolve most of the genericness.
