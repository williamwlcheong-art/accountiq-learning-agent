import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  BarChart3,
  FileText,
  ShieldCheck,
  UserCheck,
} from "lucide-react";

const products = [
  {
    name: "Business Valuation Report",
    price: "Fixed fee from NZ$2,250 + GST",
    copy: "Fixed-fee valuation report for SME owners, advisers, and planning conversations.",
    featured: true,
  },
  {
    name: "Bank Credit Paper",
    price: "Pilot product",
    copy: "A lender-ready credit summary built from uploaded financial statements.",
  },
  {
    name: "Advisory Consultation",
    price: "Quoted after review",
    copy: "Todd-led next-step support once the valuation findings are clear.",
  },
];

export default function HomePage() {
  return (
    <main>
      <section className="home-hero">
        <nav className="site-nav">
          <Link className="brand" href="/">
            <span className="brand-mark">a</span>
            <span>AccountIQ</span>
          </Link>
          <div className="site-nav-links">
            <a href="#pricing">Pricing</a>
            <a href="#proof">Proof</a>
            <Link href="/login">Sign in</Link>
          </div>
        </nav>

        <div className="hero-content">
          <div className="hero-copy">
            <p className="eyebrow">Fixed-fee valuation reports</p>
            <h1>Fixed-fee business valuations, reviewed before delivery.</h1>
            <p className="lede">
              AccountIQ turns uploaded financial statements into structured valuation reports for business
              owners, with human review before anything goes to the client.
            </p>
            <div className="button-row">
              <Link className="primary-button" href="/login">
                Get a business valuation
                <ArrowRight aria-hidden="true" size={18} />
              </Link>
              <a className="secondary-button" href="#pricing">
                View products
              </a>
            </div>
          </div>

          <div className="report-preview" aria-label="Report preview">
            <div className="preview-header">
              <FileText aria-hidden="true" size={20} />
              <span>Valuation Advisory</span>
            </div>
            <div className="metric-row">
              <span>Revenue</span>
              <strong>NZ$1.25m</strong>
            </div>
            <div className="metric-row">
              <span>EBITDA</span>
              <strong>NZ$235k</strong>
            </div>
            <div className="valuation-band">
              <span>Indicative range</span>
              <strong>NZ$1.8m - NZ$2.4m</strong>
            </div>
            <div className="review-strip">
              <UserCheck aria-hidden="true" size={18} />
              Todd review step
            </div>
          </div>
        </div>
      </section>

      <section className="section-band proof-band" id="proof">
        <div className="proof-grid">
          <div>
            <h2>Built for buyers who have never met us.</h2>
          </div>
          <div className="proof-list">
            <span>
              <ShieldCheck aria-hidden="true" size={18} />
              Clear disclaimer and advice boundary
            </span>
            <span>
              <BadgeCheck aria-hidden="true" size={18} />
              Adviser review before release
            </span>
            <span>
              <BarChart3 aria-hidden="true" size={18} />
              Transparent fixed-fee offer
            </span>
          </div>
        </div>
      </section>

      <section className="section-band products-band" id="pricing">
        <div className="section-heading">
          <h2>Start with three products, keep the buying decision simple.</h2>
        </div>
        <div className="product-grid">
          {products.map((product) => (
            <article className={`product-card${product.featured ? " product-card-featured" : ""}`} key={product.name}>
              <h3>{product.name}</h3>
              <strong>{product.price}</strong>
              <p>{product.copy}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
