import type { WizardReadiness } from "@/types/domain";
import { FinancialSourceList } from "./financial-source-list";
import { formatMoney } from "@/lib/presentation";

type CheckoutConfirmationProps = {
  businessName: string;
  readiness: WizardReadiness;
  answers: Record<string, unknown>;
  loading: boolean;
  onBack: () => void;
  onConfirm: () => void;
};

export function CheckoutConfirmation({ businessName, readiness, answers, loading, onBack, onConfirm }: CheckoutConfirmationProps) {
  const normalisations = Array.isArray(answers.normalisations) ? answers.normalisations as Array<Record<string, unknown>> : [];
  return (
    <section className="wizard-card confirmation-card">
      <p className="eyebrow">Final check before payment</p>
      <h1>Confirm your valuation order</h1>
      <p>Review the source coverage and assumptions that will be bound to this report.</p>

      <dl className="confirmation-grid">
        <div><dt>Company</dt><dd>{businessName}</dd></div>
        <div><dt>Report</dt><dd>Valuation Advisory</dd></div>
        <div><dt>Fee</dt><dd>{formatMoney(readiness.checkout.amount_cents, readiness.checkout.currency)}</dd></div>
        <div><dt>Review</dt><dd>Draft generation followed by human review before release</dd></div>
      </dl>

      <div className="confirmation-section">
        <h2>Selected financial coverage</h2>
        <FinancialSourceList
          sources={readiness.source_periods}
          className="confirmation-list"
          filenameFirst
        />
      </div>

      <div className="confirmation-section">
        <h2>Assumptions and normalisations</h2>
        <p>
          Forecast: {String(answers.forecast_horizon ?? "Not supplied")} years · Revenue growth {String(answers.revenue_growth_cagr ?? "Not supplied")}% · Terminal growth {String(answers.terminal_growth_rate ?? "Not supplied")}%
        </p>
        {normalisations.length ? (
          <ul className="confirmation-list">
            {normalisations.map((item, index) => (
              <li key={`${String(item.label)}-${index}`}>
                <span>{String(item.label)}</span>
                <strong>{String(item.amount)}{item.rationale ? ` · ${String(item.rationale)}` : ""}</strong>
              </li>
            ))}
          </ul>
        ) : <p className="wizard-note">No normalisation adjustments supplied.</p>}
      </div>

      <div className="alert alert-info frozen-notice">
        These inputs are frozen when checkout starts. Later uploads or profile edits will not change this report.
      </div>
      <div className="wizard-actions">
        <button className="button button-secondary" onClick={onBack}>Back</button>
        <button className="button button-primary" onClick={onConfirm} disabled={loading}>
          {loading ? "Starting checkout..." : "Proceed to secure checkout"}
        </button>
      </div>
    </section>
  );
}
