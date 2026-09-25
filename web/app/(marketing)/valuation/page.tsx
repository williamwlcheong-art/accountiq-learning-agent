import type { Metadata } from "next";
import Link from "next/link";

import { Arrow } from "@/components/marketing/arrow";
import { FEE, PRIVACY_LINES, REGISTER_PATH, REVIEWER, SIGN_IN_PATH, SITE_URL, TURNAROUND, appUrl } from "@/lib/site";

const reviewer = `${REVIEWER.name} ${REVIEWER.credential}`;

export const metadata: Metadata = {
  title: "What is in your valuation report | AccountIQ",
  description: `Every section of an AccountIQ business valuation report, in plain words. Built from your own statements, checked by ${reviewer}, ${FEE.display}.`,
  alternates: { canonical: `${SITE_URL}/valuation` },
};

/*
 * The valuation report's sections, in order (backend/report_prompts.py). The
 * wording describes William's method, so he signs off any change to it.
 */
const sections = [
  {
    name: "Introduction",
    words:
      "What the report is for, what it is based on, and its limits. It says up front that a discounted cash flow is the main method and market multiples are the check.",
  },
  { name: "Business overview", words: "What your business does, written from your answers and our research." },
  {
    name: "Market position",
    words: "Where your business sits in its New Zealand industry, with the market figures we used and where they came from.",
  },
  { name: "Financial performance", words: "Your results for the years you uploaded, in a table, and what they show." },
  {
    name: "Normalisations",
    words:
      "Each adjustment a buyer would make to your profit, such as your own salary or a one-off cost, and the normalised profit that results.",
  },
  {
    name: "Balance sheet",
    words: "Your debt, your cash and any assets the business does not need, and how they get you from the value of the business to the value of your shares.",
  },
  { name: "Method", words: "Why the discounted cash flow is the main method, and how the market multiples check it." },
  {
    name: "Discount rate",
    words: "The rate that turns future cash into today's dollars, with every part of it shown, in a low, mid and high case.",
  },
  {
    name: "Discounted cash flow",
    words: "The forecast year by year, the cash the business should produce, and what that cash is worth today.",
  },
  { name: "Valuation summary", words: "The value of your shares in the low, mid and high cases. This is the answer." },
  {
    name: "Market multiples",
    words: "What similar businesses sell for, as a multiple of profit, set against your range. It is a check, not a second answer.",
  },
  {
    name: "Disclaimer",
    words: "What the report is not. It is indicative, it is not financial advice, and it is not a certified valuation.",
  },
];

const readyList = [
  "Your last two to three years of annual accounts, profit and loss and balance sheet, as PDF or Excel.",
  "What you pay yourself, and anything that happened once, like a legal bill or an insurance payout.",
  "A rough idea of how much of your revenue comes from your biggest customers.",
];

const usefulFor = [
  "Deciding whether to talk to a buyer, and what to expect.",
  "Going into a conversation with your bank or an investor.",
  "Giving shareholders or family a shared starting point on succession.",
];

const faqs = [
  {
    question: "Is this financial advice?",
    answer: "No. The report is an indicative valuation to help you plan. It is not financial advice.",
  },
  {
    question: "Is this a certified valuation?",
    answer:
      "No. It is not a certified, official, or court-standard valuation. If you need one of those, you need a registered valuer.",
  },
  {
    question: "What documents do I need?",
    answer: "Recent PDF or Excel financial statements covering the last two to three years are preferred.",
  },
  {
    question: "When do I pay?",
    answer: `After you have uploaded your statements and answered the questions. The fee is ${FEE.display} and does not change with what you upload.`,
  },
  {
    question: "Who checks the report?",
    answer: `Software prepares the first draft, and ${reviewer}, a chartered accountant, checks it before it is released to your account.`,
  },
  {
    question: "How long does it take?",
    answer: `${TURNAROUND} from payment. You can open the report online and download it as a PDF.`,
  },
  { question: "What happens to my statements?", answer: PRIVACY_LINES.join(" ") },
];

export default function ValuationPage() {
  return (
    <div className="home">
      <section className="home-hero valuation-hero" aria-labelledby="valuation-title">
        <div className="marketing-container">
          <h1 id="valuation-title">What is in your valuation report</h1>
          <p className="home-lead">
            Twelve sections, built from your own statements and checked by {reviewer}. {FEE.display}, back in{" "}
            {TURNAROUND}.
          </p>
          <div className="home-actions">
            <Link className="home-button" href={appUrl(REGISTER_PATH)}>
              Start your valuation
              <Arrow />
            </Link>
            <Link className="home-button home-button-quiet" href={appUrl(SIGN_IN_PATH)}>
              Sign in
            </Link>
          </div>
          <p className="home-boundary">Indicative only. Not financial advice or a certified valuation.</p>
        </div>
      </section>

      <section className="home-section home-section-white" aria-labelledby="valuation-sections-title">
        <div className="marketing-container home-split">
          <div className="home-split-head">
            <h2 id="valuation-sections-title">The report, section by section</h2>
            <p className="home-intro">In the order you will read them. Every figure comes from your statements and your answers.</p>
          </div>
          <ol className="home-glosses valuation-sections">
            {sections.map((section) => (
              <li key={section.name}>
                <h3>{section.name}</h3>
                <p>{section.words}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="home-section" aria-labelledby="valuation-ready-title">
        <div className="marketing-container">
          <div className="home-section-head">
            <h2 id="valuation-ready-title">Before you start</h2>
          </div>
          <div className="home-assurances valuation-assurances">
            <div className="home-assurance">
              <h3>What to have ready</h3>
              <ul>
                {readyList.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
            <div className="home-assurance">
              <h3>What it is useful for</h3>
              <ul>
                {usefulFor.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
            <div className="home-assurance">
              <h3>Who this is not for</h3>
              <p>
                If the number has to satisfy a court, the Family Court, the IRD or a formal dispute, you need a
                registered valuer.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="home-section home-section-white" aria-labelledby="valuation-faq-title">
        <div className="marketing-container home-split">
          <div className="home-split-head">
            <h2 id="valuation-faq-title">Questions before you begin</h2>
          </div>
          <div className="valuation-faq">
            {faqs.map((faq) => (
              <details key={faq.question}>
                <summary>{faq.question}</summary>
                <p>{faq.answer}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="home-close" aria-labelledby="valuation-close-title">
        <div className="marketing-container home-close-inner">
          <div>
            <h2 id="valuation-close-title">Find out what your business is worth</h2>
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
