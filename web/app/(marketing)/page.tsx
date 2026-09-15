import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";
import { listPosts } from "@/lib/content";
import { formatNzDate } from "@/lib/presentation";
import { REGISTER_PATH, SITE_URL, appUrl } from "@/lib/site";

export const metadata: Metadata = {
  title: "AccountIQ | Business valuation reports for New Zealand owners",
  description:
    "Upload your financial statements and get an indicative business valuation report for one fixed fee, reviewed by a person before it reaches you.",
  alternates: { canonical: SITE_URL },
};

const situations = [
  {
    heading: "You are thinking about selling",
    body: "Before you talk to a buyer or a broker, you want a number you can hold in your head and the reasoning behind it.",
  },
  {
    heading: "You are raising money or borrowing",
    body: "A lender or an investor will ask what the business is worth. It helps to have looked at that question first, on your own terms.",
  },
  {
    heading: "You are sorting out shareholding",
    body: "A partner is leaving, a family member is coming in, or a shareholder agreement needs a starting figure everyone can see.",
  },
];

const steps = [
  "Upload your last two to three years of financial statements",
  "Answer questions about the business and the assumptions behind the numbers",
  "See the fixed fee and pay securely",
  "AccountIQ prepares the report and a reviewer checks it",
  "Open the finished report from your account",
];

export default async function HomePage() {
  const user = await getCurrentUser();
  if (user?.is_admin) redirect("/admin");
  if (user) redirect("/reports");

  const posts = listPosts().slice(0, 3);

  return (
    <>
      <section className="marketing-hero">
        <div className="marketing-container marketing-home-hero">
          <h1>Business valuation reports for New Zealand owners</h1>
          <p className="marketing-hero-copy">
            AccountIQ turns your financial statements into an indicative valuation report. One fixed fee, and a
            person reviews every report before it reaches you.
          </p>
          <div className="marketing-actions">
            <Link className="marketing-cta" href={appUrl(REGISTER_PATH)}>
              Get a business valuation
            </Link>
            <Link className="marketing-secondary-cta" href="/valuation">
              See what is in the report
            </Link>
          </div>
          <p className="marketing-boundary">Indicative only. Not financial advice. Reviewed before delivery.</p>
        </div>
      </section>

      <section className="marketing-section">
        <div className="marketing-container">
          <h2>Most owners ask this question at a particular moment</h2>
          <div className="marketing-use-cases">
            {situations.map((situation) => (
              <div key={situation.heading}>
                <h3>{situation.heading}</h3>
                <p>{situation.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="marketing-section marketing-section-muted">
        <div className="marketing-container">
          <h2>How a report is made</h2>
          <ol className="marketing-steps">
            {steps.map((step, index) => (
              <li key={step}>
                <span aria-hidden="true">{index + 1}</span>
                <p>{step}</p>
              </li>
            ))}
          </ol>
          <p className="marketing-section-link">
            <Link href="/how-it-works">Read the process in full</Link>
          </p>
        </div>
      </section>

      <section className="marketing-section marketing-review-section">
        <div className="marketing-container marketing-review-copy">
          <h2>A person checks every report</h2>
          <div>
            <p>
              Software writes the first draft from the figures you supply and the answers you give. Nothing reaches
              you on that basis alone. A reviewer reads the draft, checks the assumptions against the statements, and
              releases it only when it holds up.
            </p>
            <p>
              The report is a starting point for a decision, not a substitute for advice. It is not a certified or
              court-standard valuation, and it says so plainly on the front page.
            </p>
          </div>
        </div>
      </section>

      {posts.length ? (
        <section className="marketing-section">
          <div className="marketing-container">
            <h2>Writing for business owners</h2>
            <ul className="marketing-post-list">
              {posts.map((post) => (
                <li key={post.slug}>
                  <Link href={`/blog/${post.slug}`}>
                    <h3>{post.title}</h3>
                    <p>{post.description}</p>
                    <time dateTime={post.date}>{formatNzDate(post.date, "long")}</time>
                  </Link>
                </li>
              ))}
            </ul>
            <p className="marketing-section-link">
              <Link href="/blog">Read more</Link>
            </p>
          </div>
        </section>
      ) : null}

      <section className="marketing-final-cta">
        <div className="marketing-container">
          <h2>Find out what your business may be worth</h2>
          <Link className="marketing-cta" href={appUrl(REGISTER_PATH)}>
            Get a business valuation
          </Link>
        </div>
      </section>
    </>
  );
}
