import Link from "next/link";

import { visibleLinks } from "@/components/marketing/site-header";
import { Wordmark } from "@/components/marketing/wordmark";
import { CONTACT_EMAIL, FOOTER_LINKS, MAIN_NAV } from "@/lib/site";

export function SiteFooter() {
  const site = visibleLinks(MAIN_NAV);
  const company = visibleLinks(FOOTER_LINKS);

  return (
    <footer className="marketing-footer">
      <div className="marketing-container marketing-footer-inner">
        <div className="marketing-footer-brand">
          <Link className="marketing-wordmark" href="/" aria-label="AccountIQ home">
            <Wordmark />
          </Link>
          <p>Indicative business valuation reports for New Zealand businesses.</p>
        </div>

        <nav className="marketing-footer-column" aria-labelledby="footer-valuations">
          <h2 id="footer-valuations">Valuations</h2>
          {site.map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>

        {company.length ? (
          <nav className="marketing-footer-column" aria-labelledby="footer-company">
            <h2 id="footer-company">Company</h2>
            {company.map((item) => (
              <Link key={item.href} href={item.href}>
                {item.label}
              </Link>
            ))}
          </nav>
        ) : null}

        <div className="marketing-footer-column">
          <h2>Contact</h2>
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        </div>
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
