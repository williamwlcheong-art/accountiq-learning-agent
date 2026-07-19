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
  const fcff = answers.fcff_assumptions && typeof answers.fcff_assumptions === "object"
    ? answers.fcff_assumptions as Record<string, Record<string, unknown>>
    : {};
  const forecast = fcff.forecast ?? {};
  const assumptionLabel = (key: "depreciation" | "capex" | "operating_nwc") => {
    const item = fcff[key] ?? {};
    const percentage = Number(item.rate) * 100;
    const method = item.confirmation_method === "calculated"
      ? `Calculated from the financial statements${item.source_period ? ` for ${String(item.source_period)}` : ""}`
      : item.confirmation_method === "override"
        ? "Updated by you"
        : "Provided by you";
    return {
      percentage: Number.isFinite(percentage) ? `${percentage.toFixed(1)}% of revenue` : "Not supplied",
      method,
      rationale: String(item.rationale ?? "").trim(),
    };
  };
  const depreciation = assumptionLabel("depreciation");
  const capex = assumptionLabel("capex");
  const operatingNwc = assumptionLabel("operating_nwc");
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
        <dl className="confirmation-grid">
          <div><dt>Forecast period</dt><dd>{String(forecast.horizon_years ?? "Not supplied")} years</dd></div>
          <div><dt>Revenue growth</dt><dd>{Number.isFinite(Number(forecast.revenue_growth_rate)) ? `${(Number(forecast.revenue_growth_rate) * 100).toFixed(1)}% each year` : "Not supplied"}</dd></div>
          <div><dt>Terminal growth</dt><dd>{Number.isFinite(Number(forecast.terminal_growth_rate)) ? `${(Number(forecast.terminal_growth_rate) * 100).toFixed(1)}%` : "Not supplied"}</dd></div>
          <div><dt>Depreciation and amortisation</dt><dd>{depreciation.percentage}<br />{depreciation.method}{depreciation.rationale ? <><br />Reason: {depreciation.rationale}</> : null}</dd></div>
          <div><dt>Capital expenditure</dt><dd>{capex.percentage}<br />{capex.method}{capex.rationale ? <><br />Reason: {capex.rationale}</> : null}</dd></div>
          <div><dt>Operating working capital</dt><dd>{operatingNwc.percentage}<br />{operatingNwc.method}{operatingNwc.rationale ? <><br />Reason: {operatingNwc.rationale}</> : null}</dd></div>
        </dl>
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
