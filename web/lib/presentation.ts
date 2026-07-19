const REPORT_TYPE_LABELS: Record<string, string> = {
  valuation_advisory: "Valuation advisory",
  bank_credit_paper: "Bank credit paper",
  financial_forecast: "Financial forecast",
  capital_raising: "Capital raising document",
  information_memorandum: "Information memorandum",
};

const FINANCIAL_STATEMENT_LABELS: Record<string, string> = {
  balance_sheet: "Balance sheet",
  bs: "Balance sheet",
  cash_flow: "Cash flow",
  pnl: "Profit and loss",
  profit_and_loss: "Profit and loss",
};

const REPORT_STATUS_LABELS: Record<string, string> = {
  pending_payment: "Payment pending",
  queued: "Preparing your report",
  researching: "Preparing your report",
  generating: "Preparing your report",
  processing: "Processing",
  extracting: "Extracting information",
  awaiting_review: "Under review",
  done: "Ready",
  failed: "Needs attention",
};

const PURCHASE_STATUS_LABELS: Record<string, string> = {
  paid: "Paid",
  pending: "Payment pending",
  pending_payment: "Payment pending",
  failed: "Payment needs attention",
};

export type StatusTone = "success" | "info" | "warning" | "danger" | "neutral";

const REPORT_STATUS_TONES: Record<string, StatusTone> = {
  pending_payment: "warning",
  queued: "info",
  researching: "info",
  generating: "info",
  processing: "info",
  extracting: "info",
  awaiting_review: "warning",
  done: "success",
  failed: "danger",
};

const CLARIFICATION_DETAILS: Record<string, {
  label: string;
  format?: (value: string | number) => string;
}> = {
  statement: { label: "Financial statement", format: (value) => financialStatementLabel(String(value)) },
  period: { label: "Reporting period" },
  periods: { label: "Reporting periods" },
  base_period: { label: "Selected reporting period" },
  balance_sheet_periods: { label: "Balance sheet periods" },
  currency: { label: "Currency" },
  currencies: { label: "Currencies" },
  unit: { label: "Unit" },
  field: {
    label: "Required detail",
    format: (value) => CLARIFICATION_DETAIL_VALUE_LABELS[String(value)] ?? "This detail",
  },
};

const CLARIFICATION_DETAIL_VALUE_LABELS: Record<string, string> = {
  normalisations: "EBITDA normalisations",
  approved_surplus_assets: "Approved surplus assets",
};

const CLARIFICATION_REASON_LABELS: Record<string, string> = {
  insufficient_financial_coverage: "The uploaded statements do not include enough financial coverage.",
  missing_required_statements: "Some required financial statements are missing.",
  conflicting_financial_data: "The uploaded financial information needs clarification.",
  document_extraction_failed: "We could not read the uploaded financial statements.",
};

function readableFallback(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatMoney(amountCents: number, currency: string) {
  return new Intl.NumberFormat("en-NZ", {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(amountCents / 100);
}

export function reportTypeLabel(value: string) {
  return REPORT_TYPE_LABELS[value] ?? readableFallback(value);
}

export function financialStatementLabel(value: string) {
  return FINANCIAL_STATEMENT_LABELS[value] ?? readableFallback(value);
}

export function clarificationDetail(key: string, value: unknown): readonly [string, string] | null {
  const detail = CLARIFICATION_DETAILS[key];
  if (!detail) return null;

  const format = detail.format ?? ((item: string | number) => String(item));
  if (typeof value === "string" || typeof value === "number") {
    return [detail.label, format(value)];
  }
  if (Array.isArray(value)) {
    const items = value.filter((item): item is string | number => typeof item === "string" || typeof item === "number");
    if (items.length === value.length) return [detail.label, items.map(format).join(", ")];
  }
  return null;
}

export function reportStatusLabel(value: string) {
  return REPORT_STATUS_LABELS[value] ?? readableFallback(value);
}

export function reportStatusTone(value: string): StatusTone {
  return REPORT_STATUS_TONES[value] ?? "neutral";
}

export function purchaseStatusLabel(value: string) {
  return PURCHASE_STATUS_LABELS[value] ?? readableFallback(value);
}

export function clarificationReasonLabel(value: string) {
  return CLARIFICATION_REASON_LABELS[value] ?? "Please upload a clearer or more complete set of financial statements.";
}
