import Link from "next/link";

import { visibleLinks } from "@/components/marketing/site-header";
import { CONTACT_EMAIL, FOOTER_LINKS } from "@/lib/site";

export function SiteFooter() {
  const links = visibleLinks(FOOTER_LINKS);

  return (
    <footer className="marketing-footer">
      <div className="marketing-container marketing-footer-inner">
        <div>
          <strong>AccountIQ</strong>
          <p>Indicative business valuation reports for New Zealand businesses.</p>
        </div>

        <nav className="marketing-footer-links" aria-label="Footer">
          {links.map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        </nav>
      </div>

      <div className="marketing-container marketing-footer-note">
        <p>
          Reports are indicative only and are not financial advice. They are not certified, official, or
          court-standard valuations. Every report is reviewed before delivery.
        </p>
      </div>
    </footer>
  );
}
