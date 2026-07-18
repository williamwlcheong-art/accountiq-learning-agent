import { clarificationDetailValue, clarificationFieldLabel, clarificationReasonLabel } from "@/lib/presentation";
import type { CheckoutClarification } from "@/types/domain";

const CUSTOMER_SAFE_DETAIL_KEYS = new Set([
  "statement",
  "period",
  "periods",
  "base_period",
  "balance_sheet_periods",
  "currency",
  "currencies",
  "unit",
  "field",
]);

type CheckoutClarificationCardProps = {
  clarification: CheckoutClarification;
  onReset: () => void;
};

export function CheckoutClarificationCard({ clarification, onReset }: CheckoutClarificationCardProps) {
  const affectedDetails = Object.entries(clarification.details)
    .filter(([key]) => CUSTOMER_SAFE_DETAIL_KEYS.has(key))
    .map(([key, value]) => {
      if (typeof value === "string" || typeof value === "number") {
        return [key, clarificationDetailValue(key, value)] as const;
      }
      if (Array.isArray(value)) {
        const items = value.filter((item): item is string | number => typeof item === "string" || typeof item === "number");
        if (items.length === value.length) {
          return [key, items.map((item) => clarificationDetailValue(key, item)).join(", ")] as const;
        }
      }
      return null;
    })
    .filter((entry): entry is readonly [string, string] => entry !== null);
  return (
    <section className="wizard-card clarification-card" role="alert">
      <p className="eyebrow">We need clearer financial statements</p>
      <h1>We could not confirm the figures for your valuation</h1>
      <p>{clarification.message}</p>
      {affectedDetails.length ? (
        <dl className="confirmation-grid clarification-details">
          {affectedDetails.map(([key, value]) => (
            <div key={key}>
              <dt>{clarificationFieldLabel(key)}</dt>
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
