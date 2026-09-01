export const WIZARD_STEPS = [
  "Financial statements",
  "Business details",
  "Review and payment",
  "Report delivery",
] as const;

type WizardStepsProps = {
  current: number;
};

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true" focusable="false">
      <path d="M3.5 8.5l3 3 6-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function WizardSteps({ current }: WizardStepsProps) {
  return (
    <ol className="wizard-steps" aria-label="Valuation steps">
      {WIZARD_STEPS.map((label, index) => {
        const isDone = index < current;
        const isCurrent = index === current;
        return (
          <li
            key={label}
            className={isDone ? "is-done" : undefined}
            aria-current={isCurrent ? "step" : undefined}
          >
            <span>
              {isDone ? <CheckIcon /> : null}
              <span className="wizard-step-label">{label}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
