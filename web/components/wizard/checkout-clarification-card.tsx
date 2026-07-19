import { clarificationDetail, clarificationReasonLabel } from "@/lib/presentation";
import type { CheckoutClarification } from "@/types/domain";

type CheckoutClarificationCardProps = {
  clarification: CheckoutClarification;
  onReset: () => void;
};

export function CheckoutClarificationCard({ clarification, onReset }: CheckoutClarificationCardProps) {
  const affectedDetails = Object.entries(clarification.details)
    .map(([key, value]) => clarificationDetail(key, value))
    .filter((entry): entry is readonly [string, string] => entry !== null);
  return (
    <section className="wizard-card clarification-card" role="alert">
      <p className="eyebrow">We need clearer financial statements</p>
      <h1>We could not confirm the figures for your valuation</h1>
      <p>{clarification.message}</p>
      {affectedDetails.length ? (
        <dl className="confirmation-grid clarification-details">
          {affectedDetails.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{String(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      <p className="wizard-note">{clarificationReasonLabel(clarification.reason_code)}</p>
      <div className="alert alert-info clarification-payment-note">
        No payment was taken. Upload a clearer or more complete set of financial statements to start again.
      </div>
      <button className="button button-primary" onClick={onReset}>
        Upload different statements
      </button>
    </section>
  );
}
