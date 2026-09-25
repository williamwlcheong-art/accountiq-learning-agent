import Link from "next/link";

import { Arrow } from "@/components/marketing/arrow";
import { MenuDisclosure } from "@/components/marketing/menu-disclosure";
import { Wordmark } from "@/components/marketing/wordmark";
import { listPageSlugs } from "@/lib/content";
import { MAIN_NAV, REGISTER_PATH, SIGN_IN_PATH, appUrl } from "@/lib/site";

/** Routes that exist as React pages rather than Markdown files. */
const BUILT_IN_ROUTES = new Set(["/valuation", "/blog"]);

/**
 * Links to Markdown pages are dropped while that page is still a draft, so the
 * nav never points at a page the build has left out.
 */
export function visibleLinks<T extends { href: string }>(links: readonly T[]): T[] {
  const published = new Set(listPageSlugs().map((slug) => `/${slug}`));
  return links.filter((link) => BUILT_IN_ROUTES.has(link.href) || published.has(link.href));
}

/**
 * One header for every marketing page. It stays at the top of the window as
 * the page scrolls. The narrow-screen menu is a native disclosure so the nav
 * needs no client-side JavaScript.
 */
export function SiteHeader() {
  const nav = visibleLinks(MAIN_NAV);

  return (
    <header className="marketing-header">
      <div className="marketing-container marketing-header-inner">
        <Link className="marketing-wordmark" href="/" aria-label="AccountIQ home">
          <Wordmark />
        </Link>

        <nav className="marketing-nav" aria-label="Main">
          {nav.map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="marketing-header-actions">
          <Link className="marketing-text-link" href={appUrl(SIGN_IN_PATH)}>
            Sign in
          </Link>
          <Link className="marketing-cta marketing-cta-small" href={appUrl(REGISTER_PATH)}>
            Start your valuation
            <Arrow />
          </Link>
        </div>

        <MenuDisclosure>
          <summary aria-label="Menu">
            <span aria-hidden="true" />
            Menu
          </summary>
          <nav className="marketing-menu-panel" aria-label="Main, narrow screen">
            {nav.map((item) => (
              <Link key={item.href} href={item.href}>
                {item.label}
              </Link>
            ))}
            <Link href={appUrl(SIGN_IN_PATH)}>Sign in</Link>
          </nav>
        </MenuDisclosure>
      </div>
    </header>
  );
}
