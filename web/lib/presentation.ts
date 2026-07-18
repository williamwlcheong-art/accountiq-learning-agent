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

const CLARIFICATION_FIELD_LABELS: Record<string, string> = {
  document_id: "Financial statement",
  document_ids: "Financial statements",
  filename: "File name",
  filenames: "Files",
  missing_statements: "Missing statements",
  required_statements: "Required statements",
  statement: "Financial statement",
  period: "Reporting period",
  periods: "Reporting periods",
  base_period: "Selected reporting period",
  balance_sheet_periods: "Balance sheet periods",
  currency: "Currency",
  currencies: "Currencies",
  unit: "Unit",
  field: "Required detail",
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

export function reportTypeLabel(value: string) {
  return REPORT_TYPE_LABELS[value] ?? readableFallback(value);
}

export function financialStatementLabel(value: string) {
  return FINANCIAL_STATEMENT_LABELS[value] ?? readableFallback(value);
}

export function clarificationDetailValue(key: string, value: string | number) {
  if (key === "statement") return financialStatementLabel(String(value));
  if (key === "field") return CLARIFICATION_DETAIL_VALUE_LABELS[String(value)] ?? "This detail";
  return String(value);
}

export function reportStatusLabel(value: string) {
  return REPORT_STATUS_LABELS[value] ?? readableFallback(value);
}

export function purchaseStatusLabel(value: string) {
  return PURCHASE_STATUS_LABELS[value] ?? readableFallback(value);
}

export function clarificationFieldLabel(value: string) {
  return CLARIFICATION_FIELD_LABELS[value] ?? readableFallback(value);
}

export function clarificationReasonLabel(value: string) {
  return CLARIFICATION_REASON_LABELS[value] ?? "Please upload a clearer or more complete set of financial statements.";
}
