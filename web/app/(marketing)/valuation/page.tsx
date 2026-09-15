import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Indicative Business Valuation Reports | AccountIQ",
  description:
    "Understand what your business may be worth with a fixed-fee indicative valuation report reviewed before delivery.",
};

const trustPoints = [
  "Fixed fee confirmed before payment",
  "Reviewed before delivery",
  "Web report and PDF access",
  "Built for New Zealand and Australian SMEs",
];

const useCases = [
  {
    title: "Prepare for a possible sale",
    body: "Establish a practical valuation reference point before speaking with buyers or beginning a full advisory engagement.",
  },
  {
    title: "Plan a funding conversation",
    body: "Understand the assumptions and business factors likely to shape an early debt or capital discussion.",
  },
  {
    title: "Support shareholder planning",
    body: "Give shareholders or successors a shared starting point for a structured conversation about value.",
  },
];

const inclusions = [
  "Business overview based on the information you provide",
  "Historical financial performance summary",
  "Normalised earnings adjustments where provided",
  "Indicative valuation range and key assumptions",
  "Key risks and matters to consider",
  "Review before release",
  "Web report and PDF delivery",
];

const reportSections = [
  "Business overview",
  "Market position",
  "Financial performance",
  "Normalisations schedule",
  "Balance sheet summary",
  "Valuation methodology",
  "WACC assumptions",
  "DCF analysis",
  "Valuation summary",
  "Multiples cross-check",
];

const steps = [
  "Create your account and upload recent financial statements",
  "Complete the valuation questions",
  "See the fixed fee and pay securely",
  "AccountIQ prepares the report and a reviewer checks it before release",
  "Open the reviewed report from your account",
];

const faqs = [
  {
    question: "Is this financial advice?",
    answer: "No. The report is an indicative decision-support document and is not financial advice.",
  },
  {
    question: "Is this a certified valuation?",
    answer:
      "No. It is not a certified, official, or court-standard valuation. Those needs require a separate professional engagement.",
  },
  {
    question: "What documents do I need?",
    answer: "Recent PDF or Excel financial statements covering the last two to three years are preferred.",
  },
  {
    question: "When do I pay?",
    answer: "Your fixed fee is shown before payment, after you create an account and complete the valuation information.",
  },
  {
    question: "Who reviews the report?",
    answer:
      "Software prepares the first draft, and a human reviewer checks the report before it is released to your account.",
  },
];

export default function ValuationPage() {
  return (
    <>
        <section className="marketing-hero">
          <div className="marketing-container marketing-hero-grid">
            <div>
              <h1>Know what your business may be worth</h1>
              <p className="marketing-hero-copy">
                Upload recent financial statements and receive an indicative valuation report for one fixed fee,
                reviewed before delivery.
              </p>
              <div className="marketing-actions">
                <Link className="marketing-cta" href="/login?mode=register">
                  Get a business valuation
                </Link>
                <Link className="marketing-secondary-cta" href="/login">
                  Sign in
                </Link>
              </div>
              <p className="marketing-boundary">Indicative only. Not financial advice. Reviewed before delivery.</p>
            </div>

            <aside className="marketing-report-contents" aria-labelledby="report-contents-heading">
              <h2 id="report-contents-heading">Inside the report</h2>
              <ol>
                {reportSections.map((section) => (
                  <li key={section}>{section}</li>
                ))}
              </ol>
            </aside>
          </div>
        </section>

        <section className="marketing-trust" aria-label="Offer commitments">
          <div className="marketing-container marketing-trust-grid">
            {trustPoints.map((point) => (
              <p key={point}>{point}</p>
            ))}
          </div>
        </section>

        <section className="marketing-section">
          <div className="marketing-container">
            <h2>Valuation clarity before the bigger decision</h2>
            <div className="marketing-use-cases">
              {useCases.map((useCase) => (
                <div key={useCase.title}>
                  <h3>{useCase.title}</h3>
                  <p>{useCase.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="marketing-section marketing-section-muted" id="inclusions">
          <div className="marketing-container marketing-two-column">
            <div>
              <h2>A clear report, with its assumptions visible</h2>
              <p>
                Use the report as an indicative reference point for planning and decide whether deeper professional
                advice is needed.
              </p>
            </div>
            <ul className="marketing-check-list">
              {inclusions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className="marketing-section" id="process">
          <div className="marketing-container">
            <h2>From financial statements to reviewed report</h2>
            <ol className="marketing-steps">
              {steps.map((step, index) => (
                <li key={step}>
                  <span aria-hidden="true">{index + 1}</span>
                  <p>{step}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="marketing-section marketing-review-section">
          <div className="marketing-container marketing-review-copy">
            <h2>Software speed, with a review checkpoint</h2>
            <div>
              <p>
                AccountIQ prepares the first draft from the information supplied. A human reviewer checks the report
                before it is released to your account.
              </p>
              <p>
                The report is indicative only and is not financial advice. It is not a certified, official, or
                court-standard valuation, and it is not a substitute for a regulated professional engagement.
              </p>
            </div>
          </div>
        </section>

        <section className="marketing-section">
          <div className="marketing-container marketing-pricing-panel">
            <div>
              <h2>Early-access fixed-fee offer</h2>
              <p>Your fixed fee is shown before payment.</p>
            </div>
            <Link className="marketing-cta" href="/login?mode=register">
              Get a business valuation
            </Link>
          </div>
        </section>

        <section className="marketing-section marketing-section-muted" id="faq">
          <div className="marketing-container marketing-faq-layout">
            <h2>Important questions before you begin</h2>
            <div className="marketing-faq-list">
              {faqs.map((faq) => (
                <details key={faq.question}>
                  <summary>{faq.question}</summary>
                  <p>{faq.answer}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="marketing-final-cta">
          <div className="marketing-container">
            <h2>Understand what your business may be worth</h2>
            <Link className="marketing-cta" href="/login?mode=register">
              Get a business valuation
            </Link>
            <p>
              Already have an account? <Link href="/login">Sign in</Link>
            </p>
          </div>
        </section>
    </>
  );
}
