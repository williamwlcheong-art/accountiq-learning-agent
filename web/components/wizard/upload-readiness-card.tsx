import type { WizardReadiness } from "@/types/domain";
import { FinancialSourceList, formatMoney } from "./financial-source-list";

type UploadReadinessCardProps = {
  readiness: WizardReadiness | null;
  onContinue: () => void;
  onReset: () => void;
};

export function UploadReadinessCard({ readiness, onContinue, onReset }: UploadReadinessCardProps) {
  const state = readiness?.state ?? "processing";
  return (
    <section className="wizard-card readiness-card" aria-live="polite">
      <div className={`readiness-mark readiness-${state}`} aria-hidden="true" />
      <p className="eyebrow">Financial source check</p>
      <h1>{state === "ready" ? "Your accounts are ready" : "Checking your financial statements"}</h1>
      <p>{readiness?.message ?? "We are extracting the figures and confirming which periods will be used."}</p>

      {readiness?.source_periods.length ? (
        <div className="source-summary">
          <h2>Authoritative sources</h2>
          <FinancialSourceList sources={readiness.source_periods} />
          <p className="wizard-note">
            Valuation Advisory · {formatMoney(readiness.checkout.amount_cents, readiness.checkout.currency)}
          </p>
        </div>
      ) : null}

      <div className="wizard-actions">
        {state === "ready" ? (
          <button className="button button-primary" onClick={onContinue}>Continue to report</button>
        ) : null}
        {state === "failed" || state === "conflict" ? (
          <button className="button button-secondary" onClick={onReset}>Upload another file</button>
        ) : null}
      </div>
    </section>
  );
}
