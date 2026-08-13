export const WIZARD_REPORT_TYPES = [
  {
    key: "valuation_advisory",
    name: "Valuation Advisory",
    desc: "Indicative business value using cash-flow analysis and market multiples, based on your financials and industry benchmarks.",
    available: true,
    status: "Self-serve now",
  },
  {
    key: "bank_credit_paper",
    name: "Bank Credit Paper",
    desc: "Lender-style credit paper using the uploaded financials, public client research, security, LVR, funding cost and debt-capacity analysis.",
    available: true,
    status: "Self-serve now",
  },
  {
    key: "financial_forecast",
    name: "Financial Forecast",
    desc: "Three-year forward projections with base, bull, and bear scenarios derived from historical performance.",
    available: false,
    status: "Coming soon",
  },
  {
    key: "capital_raising",
    name: "Capital Raising Document",
    desc: "Investor-ready summary covering business model, financials, growth strategy, and use of funds.",
    available: false,
    status: "Coming soon",
  },
  {
    key: "information_memorandum",
    name: "Information Memorandum",
    desc: "Full sale document covering business overview, operations, financials, and growth opportunities.",
    available: false,
    status: "Coming soon",
  },
] as const;

export type WizardReportType = (typeof WIZARD_REPORT_TYPES)[number]["key"];
export const SELF_SERVE_REPORT_TYPE: WizardReportType = "valuation_advisory";

type ReportTypePickerProps = {
  selected: WizardReportType | null;
  onSelect: (reportType: WizardReportType) => void;
  readiness?: Partial<Record<WizardReportType, ReportReadiness>> | null;
};

export type ReportReadiness = {
  ready: boolean;
  issues: string[];
  warnings: string[];
  follow_up_items: Array<{ label: string; impact: string }>;
};

export function ReportTypePicker({ selected, onSelect, readiness }: ReportTypePickerProps) {
  return (
    <div className="report-type-list">
      {WIZARD_REPORT_TYPES.map((reportType) => {
        const isSelected = selected === reportType.key;
        const reportReadiness = readiness?.[reportType.key];
        const className = [
          "report-type-card",
          isSelected ? "selected" : "",
          reportType.available ? "" : "disabled",
        ].filter(Boolean).join(" ");

        return (
          <button
            key={reportType.key}
            type="button"
            className={className}
            onClick={() => {
              if (reportType.available) onSelect(reportType.key);
            }}
            disabled={!reportType.available}
          >
            <span className="report-type-card-header">
              <span className="report-type-name">{reportType.name}</span>
              <span className={reportType.available ? "report-type-badge live" : "report-type-badge"}>
                {reportType.status}
              </span>
            </span>
            <small>{reportType.desc}</small>
            {!reportType.available ? (
              <small className="report-type-unavailable">
                This professional pack is still on the roadmap.
              </small>
            ) : reportReadiness ? (
              <small className={reportReadiness.ready ? "report-type-readiness ready" : "report-type-readiness needs-info"}>
                {reportReadiness.ready
                  ? "Core financial information is ready"
                  : `Needs more financial information: ${reportReadiness.issues.join(", ")}.`}
              </small>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
