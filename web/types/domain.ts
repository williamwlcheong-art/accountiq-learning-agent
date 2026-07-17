export type CurrentUser = {
  id: number;
  email: string;
  is_admin: number;
  created_at: string;
};

export type Company = {
  id: number;
  name: string;
  ticker: string | null;
  exchange: string | null;
  sector: string | null;
  country: string | null;
  description: string | null;
  created_at?: string;
  doc_count?: number;
  sections_complete?: number;
};

export type DocumentRecord = {
  id: number;
  company_id: number;
  filename: string;
  report_type: string | null;
  entity_type: string | null;
  fiscal_year_end: string | null;
  extraction_status: string;
  confidence_score: number | null;
  narrative?: string | null;
  reporting_standard?: string | null;
  created_at: string;
  company_name?: string;
  logs?: Array<{ level: string; message: string; created_at: string }>;
};

export type WizardReadiness = {
  state: "processing" | "failed" | "conflict" | "ready";
  code: string;
  message: string;
  document: {
    id: number;
    filename: string;
    extraction_status: string;
  };
  source_periods: Array<{
    statement: string;
    period: string;
    document_id: number;
    filename: string;
  }>;
  profile: {
    name: string;
    sector: string | null;
    description: string | null;
    country: string | null;
    exchange: string | null;
    management_team_count: number;
    ebitda_adjustment_count: number;
  };
  checkout: {
    report_type: "valuation_advisory";
    amount_cents: number;
    currency: string;
  };
};

export type ReportStatus = {
  id: number;
  report_type: string;
  status: string;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
};

export type AdminPendingReport = {
  id: number;
  company_id: number;
  company_name: string;
  user_email: string;
  report_type: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  amount_cents: number | null;
  currency: string | null;
  paid_at: string | null;
};

export type PurchaseHistoryItem = {
  purchase_id: number;
  report_id: number;
  company_name: string;
  report_type: string;
  purchase_status: string;
  report_status: string;
  amount_cents: number;
  currency: string;
  paid_at: string | null;
  created_at: string;
};

export type ApiErrorBody = {
  detail?: string;
};
