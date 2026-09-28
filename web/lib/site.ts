/**
 * Marketing site configuration.
 *
 * SITE_URL and APP_ORIGIN are the two values that change when the domain is
 * registered and the portal moves to its own subdomain. Everything else in the
 * marketing pages reads them from here rather than hard-coding a host.
 */

export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://accountiq.co.nz").replace(/\/$/, "");

/** Where the signed-in product lives. Empty string means "same host as the site". */
export const APP_ORIGIN = (process.env.NEXT_PUBLIC_APP_ORIGIN || "").replace(/\/$/, "");

/** Confirm with William before launch. */
export const CONTACT_EMAIL = "hello@accountiq.co.nz";

/**
 * Placeholders for design, agreed 2026-09-23 and not yet signed off by William.
 * Launch Gates 2, 5 and 6 decide the real values: what the review claim may
 * say, the fee and its GST treatment, and a turnaround reviewers can keep.
 */
export const FEE = { amount: 1200, display: "$1,200" };
export const TURNAROUND = "3 working days";
export const REVIEWER = { name: "William Cheong", credential: "CA" };

/*
 * What happens to an owner's accounts. Each line is true of the code today:
 * documents and reports are checked against the signed-in user (backend/main.py),
 * the draft is prepared with an AI model, and nothing contacts third parties.
 * Launch Gate 3 (privacy) must sign these off, and add storage and deletion
 * terms, before public launch.
 */
export const PRIVACY_LINES = [
  "Your statements are used for one thing: preparing your report.",
  `They sit in your own account. Other customers cannot open them, and ${REVIEWER.name} sees them only to check your report.`,
  "Software, including an AI model, reads them to prepare the first draft.",
  "We never contact a buyer, your bank or anyone else about your business. The report is yours to share, or not.",
];

export const REGISTER_PATH = "/login?mode=register";
export const SIGN_IN_PATH = "/login";

export function appUrl(path: string): string {
  return APP_ORIGIN ? `${APP_ORIGIN}${path}` : path;
}

export const MAIN_NAV = [
  { href: "/valuation", label: "Valuation" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/pricing", label: "Pricing" },
  { href: "/blog", label: "Blog" },
  { href: "/about", label: "About" },
] as const;

export const FOOTER_LINKS = [
  { href: "/for-advisors", label: "For advisors" },
  { href: "/contact", label: "Contact" },
  { href: "/terms", label: "Terms" },
  { href: "/privacy", label: "Privacy" },
] as const;
