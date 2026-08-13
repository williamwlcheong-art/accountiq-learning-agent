"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api-client";
import type { ReportStatus } from "@/types/domain";

type ReportStatusCardProps = {
  reportId: number;
  userEmail: string;
  onAddDocuments?: () => void;
};

export function ReportStatusCard({ reportId, userEmail, onAddDocuments }: ReportStatusCardProps) {
  const router = useRouter();
  const [status, setStatus] = useState<ReportStatus | null>(null);
  const [error, setError] = useState("");
  const [retrying, setRetrying] = useState(false);
  const [pollRestart, setPollRestart] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadStatus() {
      try {
        const nextStatus = await apiFetch<ReportStatus>(`/wizard/report/${reportId}/status`);
        if (cancelled) return;
        setStatus(nextStatus);
        setError("");
        if (nextStatus.status === "done" || nextStatus.status === "failed") {
          window.clearInterval(interval);
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
      }
    }

    const interval = window.setInterval(() => {
      if (cancelled) return;
      loadStatus();
    }, 3000);
    loadStatus();

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [reportId, router, pollRestart]);

  async function retry() {
    setRetrying(true);
    setError("");
    try {
      const nextStatus = await apiFetch<ReportStatus>(`/wizard/report/${reportId}/retry`, { method: "POST" });
      setStatus(nextStatus);
      setPollRestart((value) => value + 1);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Retry failed.");
    } finally {
      setRetrying(false);
    }
  }

  const currentStatus = status?.status ?? "queued";
  const isDone = currentStatus === "done";
  const isFailed = currentStatus === "failed";
  const isValuationReport = status?.report_type === "valuation_advisory";
  const isCreditReport = status?.report_type === "bank_credit_paper";
  const isDemoReport = Boolean(status?.demo_mode);
  const isEvidenceReport = status?.generation_mode === "evidence";
  const heading = isDone
    ? isValuationReport
      ? "Your valuation report is ready"
      : isCreditReport
        ? "Your bank credit paper is ready"
        : "Your report is ready"
    : isFailed
      ? isValuationReport
        ? "We paused this valuation report"
        : isCreditReport
          ? "We paused this bank credit paper"
          : "Your report needs attention"
      : isValuationReport
        ? "Preparing your valuation report"
        : isCreditReport
          ? "Preparing your bank credit paper"
          : "Your report is being prepared";
  const readableStatus = {
    queued: "Queued",
    generating: "Building report",
    researching: isDemoReport
      ? "Preparing simulated evidence"
      : isEvidenceReport
        ? "Collecting approved public-source evidence"
      : isCreditReport
        ? "Researching client and credit evidence"
        : "Researching market evidence",
    done: "Ready",
    failed: "Needs attention",
  }[currentStatus] ?? currentStatus;
  const valuationStatusMessage = isDone
    ? isDemoReport
      ? "AccountIQ has prepared your labelled demo valuation pack from the uploaded financials, five private answers, earnings review, simulated public research, valuation model and report-letter front matter. "
      : isEvidenceReport
        ? "AccountIQ has prepared your evidence-mode valuation pack from the uploaded financials, private answers, earnings review, approved public sources and valuation model. "
      : "AccountIQ has prepared your source-backed valuation pack from the uploaded financials, five private answers, earnings review, market research, valuation model and report-letter front matter. "
    : isDemoReport
      ? "AccountIQ is combining your financial upload, private answers, simulated public research, valuation modelling, report-letter front matter and PDF formatting to prepare a labelled demo valuation pack. "
      : isEvidenceReport
        ? "AccountIQ is combining your financial upload, private answers, approved public-source evidence and valuation modelling to prepare an evidence-mode valuation pack. "
      : "AccountIQ is combining your financial upload, private answers, market research, valuation modelling, report-letter front matter and PDF formatting to prepare a source-backed valuation pack. ";
  const genericStatusMessage = isDone
    ? isCreditReport
      ? "Your bank credit paper is ready to review. "
      : "Your report is ready to review. "
    : isCreditReport
      ? "AccountIQ is combining your uploaded financials, public client research, facility terms, LVR, security and debt-capacity calculations to prepare the credit paper. "
      : "We are preparing your report. ";
  const reportStatusDetail = isDone
    ? "You can review it online, download the PDF and use the basis/source sections to see what the conclusion relies on."
    : (
      <>
        We will email <strong>{userEmail}</strong> when it is ready.
      </>
    );
  const valuationEvidenceTrail = isDone
    ? isDemoReport
      ? "The report shows the calculation trail, assumptions and labelled demo source URLs."
      : "The report shows the calculation trail, assumptions and retained source URLs."
    : isDemoReport
      ? "The report will show the calculation trail, assumptions and labelled demo source URLs."
      : "The report will show the calculation trail, assumptions and retained source URLs.";
  const packEyebrow = isDone ? "Report pack ready" : "Report pack being prepared";
  const packSummary = isDone
    ? "AccountIQ has turned the upload, five private answers and earnings review into the core pages a professional valuation reader expects."
    : "AccountIQ is turning the upload, five private answers and earnings review into the core pages a professional valuation reader expects.";

  const valuationStepState = (step: "answers" | "research" | "model" | "delivery") => {
    if (isFailed) return "pending";
    if (isDone) return "complete";
    if (step === "answers") return "complete";
    if (currentStatus === "researching" && step === "research") return "current";
    if (currentStatus === "generating" && step === "research") return "complete";
    if (currentStatus === "generating" && step === "model") return "current";
    if (currentStatus === "queued" && step === "research") return "pending";
    return "pending";
  };

  const creditStepState = (step: "inputs" | "research" | "analysis" | "delivery") => {
    if (isFailed) return "pending";
    if (isDone) return "complete";
    if (step === "inputs") return "complete";
    if (currentStatus === "researching" && step === "research") return "current";
    if (currentStatus === "generating" && step === "research") return "complete";
    if (currentStatus === "generating" && step === "analysis") return "current";
    return "pending";
  };

  return (
    <section className="wizard-card">
      <h2>{heading}</h2>

      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}

      {isDemoReport ? (
        <div className="alert alert-info">
          <strong>Demo report</strong>
          <p>
            This report uses your uploaded financial extraction with simulated
            public research and simulated report conclusions. It demonstrates
            the finished experience and is not for reliance.
          </p>
        </div>
      ) : null}

      {isEvidenceReport ? (
        <div className="alert alert-info">
          <strong>Evidence-mode report</strong>
          <p>
            This report is generated without a commercial AI provider. AccountIQ uses the uploaded
            financials, lender or valuation inputs, and only the public URLs approved in the
            intake. The report records what was retrieved and does not present model conventions
            as independently researched market facts.
          </p>
        </div>
      ) : null}

      {!isFailed ? (
        <p>
          {isValuationReport
            ? valuationStatusMessage
            : genericStatusMessage}
          {reportStatusDetail}
        </p>
      ) : null}

      <p className={`status-pill status-${currentStatus}`}>Status: {readableStatus}</p>

      {isValuationReport && !isFailed ? (
        <>
          <ol className="valuation-prep-steps" aria-label="Valuation report preparation steps">
            <li className={`valuation-prep-step valuation-prep-step-${valuationStepState("answers")}`}>
              <strong>Upload and private inputs captured</strong>
              <span>We have the financial statements and the short private-fact intake.</span>
            </li>
            <li className={`valuation-prep-step valuation-prep-step-${valuationStepState("research")}`}>
              <strong>{isDemoReport ? "Simulated research and market evidence" : isEvidenceReport ? "Approved public-source evidence" : "Research and market evidence"}</strong>
              <span>
                {isDemoReport
                  ? "We use simulated public-source context and sample valuation evidence, retaining labelled demo source URLs for review."
                  : isEvidenceReport
                    ? "We fetch only the company website and public URLs you approved, retaining retrieval status and source URLs for review."
                  : "We match the business to public sources, market context and valuation evidence, retaining source URLs for review."}
              </span>
            </li>
            <li className={`valuation-prep-step valuation-prep-step-${valuationStepState("model")}`}>
              <strong>Valuation calculations and quality checks</strong>
              <span>AccountIQ calculates the valuation range, cross-checks, sensitivity analysis and assumption/source trail.</span>
            </li>
            <li className={`valuation-prep-step valuation-prep-step-${valuationStepState("delivery")}`}>
              <strong>Report and PDF delivery</strong>
              <span>The finished report is formatted with a professional cover, contents, report letter, prepared-by identity, basis of preparation, browser review, PDF formatting and PDF download.</span>
            </li>
          </ol>

          <aside className="valuation-wait-reassurance" aria-label="Valuation preparation reassurance">
            <strong>No more valuation answers are needed</strong>
            <ul>
              <li>The five private answers and earnings review are saved.</li>
              <li>AccountIQ derives WACC, terminal growth and forecast mechanics for you.</li>
              <li>{valuationEvidenceTrail}</li>
            </ul>
          </aside>

          <section className="valuation-pack-preview" aria-labelledby="valuation-pack-preview-title">
            <div>
              <span className="eyebrow">{packEyebrow}</span>
              <h3 id="valuation-pack-preview-title">The output is a full valuation pack, not more questions</h3>
              <p>{packSummary}</p>
            </div>
            <ul>
              <li>
                <strong>Front matter</strong>
                <span>Cover, contents, report letter, prepared-by identity, basis of preparation and reliance limits.</span>
              </li>
              <li>
                <strong>Valuation workpapers</strong>
                <span>DCF, WACC, multiples cross-check, equity bridge and sensitivity.</span>
              </li>
              <li>
                <strong>Evidence trail</strong>
                <span>
                  {isDemoReport
                    ? "Management input trail, labelled demo source URLs, sample comparable evidence and PDF delivery."
                    : isEvidenceReport
                      ? "Management input trail, approved public-source URLs, evidence boundaries and PDF delivery."
                    : "Management input trail, public source URLs, comparable evidence and PDF delivery."}
                </span>
              </li>
            </ul>
          </section>
        </>
      ) : null}

      {isCreditReport && !isFailed ? (
        <>
          <ol className="valuation-prep-steps credit-prep-steps" aria-label="Credit paper preparation steps">
            <li className={`valuation-prep-step credit-prep-step-${creditStepState("inputs")}`}>
              <strong>Financials and lender inputs captured</strong>
              <span>We have the accounts, facility request, repayment profile, security and covenant choices.</span>
            </li>
            <li className={`valuation-prep-step credit-prep-step-${creditStepState("research")}`}>
              <strong>{isDemoReport ? "Simulated client and sector context" : isEvidenceReport ? "Approved public-source evidence" : "Client and credit context"}</strong>
              <span>
                {isDemoReport
                  ? "Demo context is labelled and kept separate from the uploaded financial evidence."
                  : isEvidenceReport
                    ? "Only the website and public links you approved are retained as evidence."
                    : "Borrower, sector and operating context are assembled for the lender view."}
              </span>
            </li>
            <li className={`valuation-prep-step credit-prep-step-${creditStepState("analysis")}`}>
              <strong>Coverage, security and debt capacity</strong>
              <span>AccountIQ calculates DSCR, ICR, LVR, leverage, NTOA, downside sensitivity and proposed controls.</span>
            </li>
            <li className={`valuation-prep-step credit-prep-step-${creditStepState("delivery")}`}>
              <strong>Credit paper and PDF delivery</strong>
              <span>The finished pack shows risks, conditions precedent, recommendation, browser review and PDF delivery.</span>
            </li>
          </ol>

          <section className="valuation-pack-preview credit-pack-preview" aria-labelledby="credit-pack-preview-title">
            <div>
              <span className="eyebrow">{isDone ? "Credit paper ready" : "Credit paper being prepared"}</span>
              <h3 id="credit-pack-preview-title">A screening paper with a clear route to committee</h3>
              <p>
                The output is not a bank approval. It records what the uploaded evidence supports, what is missing,
                and what should be cleared before committee.
              </p>
            </div>
            <ul>
              <li>
                <strong>Credit case</strong>
                <span>Facility request, sources and uses, borrower context and repayment source.</span>
              </li>
              <li>
                <strong>Capacity analysis</strong>
                <span>Financial trend, coverage, security, LVR and balance-sheet debt capacity.</span>
              </li>
              <li>
                <strong>Decision controls</strong>
                <span>Proposed covenants, risks and mitigants, conditions precedent and recommendation.</span>
              </li>
            </ul>
          </section>
        </>
      ) : null}

      {currentStatus === "researching" ? (
        <p className="wizard-note">
          {isDemoReport
            ? "AccountIQ is preparing simulated market evidence and sample professional valuation assumptions for this demo journey."
            : isEvidenceReport
              ? "AccountIQ is retrieving the approved public sources and assembling the evidence trail without using a commercial AI provider."
            : "AccountIQ is gathering market evidence and professional valuation assumptions. This can take a little longer than standard reports."}
        </p>
      ) : null}

      {isDone ? (
        <div className="wizard-done">
          <p>
            {isValuationReport
              ? "Your valuation report is ready to review online or download as a PDF."
              : isCreditReport
                ? "Your bank credit paper is ready to review online or download as a PDF."
              : "Your report is ready."}
          </p>
          <div className="wizard-delivery-actions">
            <a className="button button-primary" href={`/api/backend/wizard/report/${reportId}/view`} target="_blank" rel="noreferrer">
              Open report
            </a>
            <a className="button button-secondary" href={`/api/backend/wizard/report/${reportId}/pdf`} download>
              Download PDF
            </a>
            {onAddDocuments ? (
              <button type="button" className="button button-secondary" onClick={onAddDocuments}>
                Add supporting files
              </button>
            ) : null}
          </div>
          {isValuationReport ? (
            <div className="wizard-delivery-guide" aria-label="How to use the valuation report pack">
              <div>
                <strong>Review online first</strong>
                <span>Use the browser report to check the valuation snapshot, report letter, basis of preparation and source trail.</span>
              </div>
              <div>
                <strong>Download the PDF for sharing</strong>
                <span>The PDF is the print-ready professional pack for adviser, lender, board or owner discussions.</span>
              </div>
            </div>
          ) : null}
          {isCreditReport ? (
            <div className="wizard-delivery-guide" aria-label="How to use the credit paper">
              <div>
                <strong>Use this as a screening paper</strong>
                <span>Before lender review, obtain current management accounts, the debt schedule and payout letters, and current security evidence or appraisals.</span>
              </div>
              <div>
                <strong>Clear the conditions before committee</strong>
                <span>Confirm borrower and guarantor details, AR/AP or stock ageing where relevant, tax status, insurance and signed lender terms.</span>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {isFailed ? (
        <div className="wizard-failed">
          {isValuationReport ? (
            <>
              <strong>We kept this unfinished report out of delivery.</strong>
              <p>
                AccountIQ could not finish a customer-ready valuation report from this run,
                so it was not sent to you as if it were complete.
              </p>
              <p>
                Your financial upload, five private answers and earnings review are saved.
                Retry will reuse the same inputs; you do not need to enter the valuation
                answers again.
              </p>
            </>
          ) : (
            <p>{status?.error_message || "Report generation failed."}</p>
          )}
          <button className="button button-primary" onClick={retry} disabled={retrying}>
            {isValuationReport
              ? retrying
                ? "Retrying preparation..."
                : "Retry preparation"
              : retrying
                ? "Retrying..."
                : "Retry"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
