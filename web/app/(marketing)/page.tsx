import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Arrow } from "@/components/marketing/arrow";
import { getCurrentUser } from "@/lib/auth";
import { listPosts } from "@/lib/content";
import { formatNzDate } from "@/lib/presentation";
import { FEE, REGISTER_PATH, REVIEWER, SITE_URL, TURNAROUND, appUrl } from "@/lib/site";

const reviewer = `${REVIEWER.name} ${REVIEWER.credential}`;

export const metadata: Metadata = {
  title: "AccountIQ | What is your business worth?",
  description: `An indicative valuation of your New Zealand business, worked out from your own financial statements and checked by ${reviewer}. ${FEE.display}, back in ${TURNAROUND}.`,
  alternates: { canonical: SITE_URL },
};

/*
 * Illustrative figures for a made-up business. The normalisations add up:
 * 182,400 + 38,000 + 12,500 - 9,800 = 223,100. The value range is the low and
 * high discounted cash flow scenarios with the mid case between them, which is
 * how the real report concludes (backend/report_prompts.py, valuation_tables.py).
 */
const sample = {
  low: 692_000,
  mid: 770_000,
  high: 848_000,
};
const scale = { from: 600_000, to: 940_000 };
const at = (value: number) => `${((value - scale.from) / (scale.to - scale.from)) * 100}%`;

/* The same lines, in the same order, as the sample report in the hero. */
const glosses = [
  {
    line: "Reported profit",
    figure: "$182,400",
    words: "What your annual accounts say the business made. It is the starting point, and rarely the number a buyer uses.",
  },
  {
    line: "Owner's salary",
    figure: "+$38,000",
    words: "You pay yourself more than a manager would cost. A buyer adds the difference back, because they would not pay it.",
  },
  {
    line: "One-off legal",
    figure: "+$12,500",
    words: "A legal bill that came once and will not come again, so a buyer leaves it out of the running costs.",
  },
  {
    line: "Rent to market",
    figure: "−$9,800",
    words: "You own the building and charge the business less than market rent. A buyer would pay full rent, so profit comes down.",
  },
  {
    line: "Normalised profit",
    figure: "$223,100",
    words: "What the business earns for whoever owns it. The valuation starts from this figure, not the first one.",
  },
];

const reportParts = [
  {
    title: "Your business and its market",
    words: "What the business does, and where it sits in its New Zealand industry, with the market evidence we used.",
  },
  {
    title: "Your profit, normalised",
    words: "Two to three years of results, each adjustment a buyer would make, and your debt and cash.",
  },
  {
    title: "The valuation",
    words: "A discounted cash flow in three scenarios, with the discount rate and every assumption shown.",
  },
  {
    title: "The cross-check",
    words: "Your range set against what similar businesses sell for, as a check on the answer.",
  },
];

/* Competitor fees are the lowest each publishes, NZD excluding GST, read on 16 September 2026. */
const prices = [
  { name: "Broker appraisal", price: "Free", amount: 0, note: "They are also hoping for your listing." },
  { name: "Comparable sales report", price: "from $60", amount: 60, note: "Never opens your accounts." },
  {
    name: "AccountIQ",
    price: FEE.display,
    amount: FEE.amount,
    note: `Reads your statements. Checked by ${reviewer}.`,
  },
  { name: "Accountant-prepared report", price: "from $2,250", amount: 2250, note: "Seven to twenty-one working days." },
  { name: "Certified valuation", price: "from $4,900", amount: 4900, note: "Three to eight weeks." },
];
const dearest = Math.max(...prices.map((item) => item.amount));

const steps = [
  {
    title: "Upload your statements",
    words: "Create an account, then upload your last two to three years of annual accounts, as PDF or Excel.",
  },
  { title: "Answer the questions", words: "What you pay yourself, what happened once, who your biggest customers are." },
  { title: "Pay the fixed fee", words: `${FEE.display}, through Stripe. The fee does not change after you upload.` },
  { title: `${REVIEWER.name} checks it`, words: "Every adjustment and the range, against your own statements." },
  { title: "Open your report", words: `Online and as a PDF, ${TURNAROUND} later.` },
];

/*
 * What happens to an owner's accounts. Each line is true of the code today:
 * documents and reports are checked against the signed-in user (backend/main.py),
 * the draft is prepared with an AI model, and nothing contacts third parties.
 * Launch Gate 3 (privacy) must sign these off, and add storage and deletion
 * terms, before public launch.
 */
const privacy = [
  "Your statements are used for one thing: preparing your report.",
  `They sit in your own account. Other customers cannot open them, and ${REVIEWER.name} sees them only to check your report.`,
  "Software, including an AI model, reads them to prepare the first draft.",
  "We never contact a buyer, your bank or anyone else about your business. The report is yours to share, or not.",
];

const money = (value: number) => `$${value.toLocaleString("en-NZ")}`;

export default async function HomePage() {
  const user = await getCurrentUser();
  if (user?.is_admin) redirect("/admin");
  if (user) redirect("/reports");

  const posts = listPosts().slice(0, 3);

  return (
    <div className="home">
      <section className="home-hero" aria-labelledby="home-title">
        <div className="marketing-container home-hero-grid">
          <div className="home-hero-copy">
            <h1 id="home-title">
              Know what your business is worth <em>before you talk to a buyer.</em>
            </h1>
            <p className="home-lead">
              Upload your financial statements and answer some questions. {reviewer} checks the numbers, and your
              report is back in {TURNAROUND}. One fixed fee of {FEE.display}.
            </p>
            <div className="home-actions">
              <Link className="home-button" href={appUrl(REGISTER_PATH)}>
                Start your valuation
                <Arrow />
              </Link>
              <Link className="home-button home-button-quiet" href="/valuation">
                See what is in the report
              </Link>
            </div>
            <p className="home-boundary">
              Indicative only. Not financial advice or a certified valuation.
              <br />
              Your statements are used only for your report, and we never contact anyone about your business.
            </p>
          </div>

          <figure className="home-report">
            <div className="home-report-sheet home-report-back" aria-hidden="true" />
            <div className="home-report-sheet home-report-middle" aria-hidden="true" />
            <div className="home-report-sheet home-report-front">
              <p className="home-report-kicker">Indicative valuation report</p>
              <p className="home-report-name">Harbour Joinery Ltd</p>
              <p className="home-report-meta">Sample report for a made-up business</p>

              <p className="home-report-label">Indicative value</p>
              <p className="home-report-range">
                {money(sample.low)} to {money(sample.high)}
              </p>
              <div className="home-report-scale" aria-hidden="true">
                <span className="home-report-band" style={{ left: at(sample.low), right: `calc(100% - ${at(sample.high)})` }} />
                <span className="home-report-mid" style={{ left: at(sample.mid) }} />
              </div>
              <p className="home-report-scenarios">
                <span>Low</span>
                <span>Mid {money(sample.mid)}</span>
                <span>High</span>
              </p>

              <dl className="home-report-rows">
                <div>
                  <dt>Reported profit</dt>
                  <dd>$182,400</dd>
                </div>
                <div className="home-report-adjust">
                  <dt>Owner&apos;s salary</dt>
                  <dd>+$38,000</dd>
                </div>
                <div className="home-report-adjust">
                  <dt>One-off legal</dt>
                  <dd>+$12,500</dd>
                </div>
                <div className="home-report-adjust">
                  <dt>Rent to market</dt>
                  <dd>−$9,800</dd>
                </div>
                <div className="home-report-strong">
                  <dt>Normalised profit</dt>
                  <dd>$223,100</dd>
                </div>
                <div>
                  <dt>Method</dt>
                  <dd>Discounted cash flow</dd>
                </div>
                <div>
                  <dt>Cross-check</dt>
                  <dd>Market multiples</dd>
                </div>
              </dl>

              <p className="home-report-signoff">
                <span>Reviewed by {reviewer}</span>
                <svg viewBox="0 0 48 22" aria-hidden="true" focusable="false">
                  <path d="M3 12 C6 15 8 18 10 21 C15 12 24 5 37 1" />
                </svg>
              </p>
            </div>
            <figcaption className="sr-only">Sample valuation report for a made-up business</figcaption>
          </figure>
        </div>

        <div className="marketing-container">
          <dl className="home-facts">
            <div>
              <dt>{FEE.display}</dt>
              <dd>Fixed fee, whatever you upload</dd>
            </div>
            <div>
              <dt>{TURNAROUND}</dt>
              <dd>From payment to your report</dd>
            </div>
            <div>
              <dt>Every report</dt>
              <dd>Read by {REVIEWER.name}, chartered accountant, before you see it</dd>
            </div>
          </dl>
        </div>
      </section>

      <div className="home-statement">
        <div className="marketing-container">
          <p>
            <em>The profit in your accounts is the profit of the business as you run it.</em> A buyer wants to know
            what it earns for whoever owns it.
          </p>
        </div>
      </div>

      <section className="home-section" aria-labelledby="home-working-title">
        <div className="marketing-container home-split">
          <div className="home-split-head">
            <h2 id="home-working-title">Where the number comes from</h2>
            <p className="home-intro">
              Getting from reported profit to normalised profit is called normalising. These are the lines on the
              sample report above. Free calculators skip them.
            </p>
          </div>
          <div>
            <ol className="home-glosses">
              {glosses.map((gloss) => (
                <li key={gloss.line} className={gloss.line === "Normalised profit" ? "home-gloss-total" : undefined}>
                  <h3>
                    {gloss.line}
                    <span className="home-gloss-figure">{gloss.figure}</span>
                  </h3>
                  <p>{gloss.words}</p>
                </li>
              ))}
            </ol>
            <p className="home-intro home-after-list">
              From the normalised profit we project the cash the business should produce and work out what it is
              worth today, in a low, base and high case. What similar businesses sell for is the cross-check.
            </p>
          </div>
        </div>
      </section>

      <section className="home-section home-section-white" aria-labelledby="home-report-title">
        <div className="marketing-container">
          <div className="home-section-head">
            <h2 id="home-report-title">What is in your report</h2>
            <p className="home-intro">
              Built from your own statements, then read by an accountant before you see it.
            </p>
          </div>
          <ol className="home-parts">
            {reportParts.map((part, index) => (
              <li key={part.title}>
                <span className="home-part-number">{String(index + 1).padStart(2, "0")}</span>
                <h3>{part.title}</h3>
                <p>{part.words}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="home-section" aria-labelledby="home-cost-title">
        <div className="marketing-container home-split">
          <div className="home-split-head">
            <h2 id="home-cost-title">What a valuation costs in New Zealand</h2>
            <p className="home-intro">
              The lowest published price for each kind of valuation. Ours is {FEE.display}, whatever you upload.
            </p>
            <p className="home-note">
              Other providers&apos; fees are the lowest they publish, in NZD excluding GST, checked 16 September 2026.
            </p>
          </div>
          <ul className="home-prices">
            {prices.map((item) => (
              <li key={item.name} className={item.name === "AccountIQ" ? "home-price-ours" : undefined}>
                <div className="home-price-line">
                  <span>{item.name}</span>
                  <span className="home-price-figure">{item.price}</span>
                </div>
                <span className="home-price-bar" aria-hidden="true">
                  <span style={{ width: `${Math.max((item.amount / dearest) * 100, 1.5)}%` }} />
                </span>
                <p>{item.note}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="home-section home-section-white" aria-labelledby="home-reviewer-title">
        <div className="marketing-container home-split">
          <div className="home-split-head">
            <h2 id="home-reviewer-title">
              A chartered accountant <em>reads every report</em>
            </h2>
          </div>
          <div className="home-reviewer">
            <p className="home-reviewer-words">
              Software prepares the first draft from your statements and your answers. {REVIEWER.name} then reads it
              against the statements, checks each adjustment and the range, and holds it back if something does not
              add up.
            </p>
            <p className="home-reviewer-sign">
              <span>
                Checked by <strong>{reviewer}</strong>
              </span>
              <svg viewBox="0 0 48 22" aria-hidden="true" focusable="false">
                <path d="M3 12 C6 15 8 18 10 21 C15 12 24 5 37 1" />
              </svg>
            </p>
          </div>
        </div>
      </section>

      <section className="home-section" aria-labelledby="home-steps-title">
        <div className="marketing-container">
          <div className="home-section-head">
            <h2 id="home-steps-title">How it works</h2>
          </div>
          <ol className="home-steps">
            {steps.map((step) => (
              <li key={step.title}>
                <h3>{step.title}</h3>
                <p>{step.words}</p>
              </li>
            ))}
          </ol>
          <div className="home-assurances">
            <div className="home-assurance">
              <h3>What happens to your accounts</h3>
              <ul>
                {privacy.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
            <div className="home-assurance">
              <h3>Who this is not for</h3>
              <p>
                If the number has to satisfy a court, the Family Court, the IRD or a formal dispute, you need a
                registered valuer. For deciding whether to talk to a buyer, and on what terms, this is usually enough.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* One post on its own reads as an empty shelf, so the section waits for a second. */}
      {posts.length > 1 ? (
        <section className="home-section home-section-white" aria-labelledby="home-writing-title">
          <div className="marketing-container">
            <div className="home-section-head">
              <h2 id="home-writing-title">Writing for business owners</h2>
            </div>
            <ul className="home-posts">
              {posts.map((post) => (
                <li key={post.slug}>
                  <Link href={`/blog/${post.slug}`}>
                    <time dateTime={post.date}>{formatNzDate(post.date, "long")}</time>
                    <h3>{post.title}</h3>
                    <p>{post.description}</p>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      <section className="home-close" aria-labelledby="home-close-title">
        <div className="marketing-container home-close-inner">
          <div>
            <h2 id="home-close-title">Find out what your business is worth</h2>
            <p>
              {FEE.display}, checked by {reviewer}, back in {TURNAROUND}.
            </p>
          </div>
          <Link className="home-button home-button-light" href={appUrl(REGISTER_PATH)}>
            Start your valuation
            <Arrow />
          </Link>
        </div>
      </section>
    </div>
  );
}
