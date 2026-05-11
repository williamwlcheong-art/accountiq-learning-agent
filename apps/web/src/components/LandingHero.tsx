import Link from "next/link";

export function LandingHero() {
  return (
    <section className="hero">
      <div>
        <div className="eyebrow">Financial statement intelligence</div>
        <h1>Turn messy statements into usable numbers.</h1>
        <p className="hero-copy">
          AccountIQ extracts profit and loss, balance sheet, confidence signals,
          and narrative context from PDFs and Excel files so accountants,
          lenders, brokers, and operators can review faster.
        </p>
        <div className="actions">
          <Link href="/upload" className="button">
            Upload a statement
          </Link>
          <Link href="/preview/demo" className="button secondary">
            View sample preview
          </Link>
        </div>
      </div>
      <div className="card">
        <div className="eyebrow">Preview report</div>
        <h2>Extract. Check. Unlock.</h2>
        <div className="metric-grid">
          <div className="metric">
            <strong>3 min</strong>
            <p>Typical statement preview time</p>
          </div>
          <div className="metric">
            <strong>42</strong>
            <p>Canonical rows across P&L and balance sheet</p>
          </div>
          <div className="metric">
            <strong>0.91</strong>
            <p>Sample extraction confidence</p>
          </div>
        </div>
      </div>
    </section>
  );
}
