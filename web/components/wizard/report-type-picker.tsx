export const WIZARD_REPORT_TYPES = [
  {
    key: "valuation_advisory",
    name: "Valuation Advisory",
    desc: "Enterprise value using DCF and market multiples, based on your financials and industry benchmarks.",
  },
  {
    key: "bank_credit_paper",
    name: "Bank Credit Paper",
    desc: "Structured credit submission covering business overview, financial performance, and lending rationale.",
  },
  {
    key: "financial_forecast",
    name: "Financial Forecast",
    desc: "Three-year forward projections with base, bull, and bear scenarios derived from historical performance.",
  },
  {
    key: "capital_raising",
    name: "Capital Raising Document",
    desc: "Investor-ready summary covering business model, financials, growth strategy, and use of funds.",
  },
  {
    key: "information_memorandum",
    name: "Information Memorandum",
    desc: "Full sale document covering business overview, operations, financials, and growth opportunities.",
  },
] as const;

export type WizardReportType = (typeof WIZARD_REPORT_TYPES)[number]["key"];

type ReportTypePickerProps = {
  selected: WizardReportType | null;
  onSelect: (reportType: WizardReportType) => void;
};

export function ReportTypePicker({ selected, onSelect }: ReportTypePickerProps) {
  return (
    <div className="report-type-list">
      {WIZARD_REPORT_TYPES.map((reportType) => (
        <button
          key={reportType.key}
          type="button"
          className={selected === reportType.key ? "report-type-card selected" : "report-type-card"}
          onClick={() => onSelect(reportType.key)}
        >
          <span>{reportType.name}</span>
          <small>{reportType.desc}</small>
        </button>
      ))}
    </div>
  );
}
