import type { CheckoutClarification } from "@/types/domain";

type CheckoutClarificationCardProps = {
  clarification: CheckoutClarification;
  onReset: () => void;
};

export function CheckoutClarificationCard({ clarification, onReset }: CheckoutClarificationCardProps) {
  const affectedDetails = Object.entries(clarification.details)
    .map(([key, value]) => {
      if (typeof value === "string" || typeof value === "number") {
        return [key, String(value)] as const;
      }
      if (Array.isArray(value)) {
        const items = value.filter((item) => typeof item === "string" || typeof item === "number");
        if (items.length === value.length) return [key, items.join(", ")] as const;
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
              <dt>{key.replaceAll("_", " ")}</dt>
              <dd>{String(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      <p className="wizard-note">Reference: {clarification.reason_code.replaceAll("_", " ")}</p>
      <div className="alert alert-info clarification-payment-note">
        No payment was taken. Upload a clearer or more complete set of financial statements to start again.
      </div>
      <button className="button button-primary" onClick={onReset}>
        Upload different statements
      </button>
    </section>
  );
}
