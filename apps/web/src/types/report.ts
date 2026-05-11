export type ReportRow = {
  statement: "pnl" | "bs";
  label: string;
  period: string;
  value: number | null;
  confidence: number;
};

export type PreviewReportData = {
  id: string;
  companyName: string;
  status: "processing" | "ready" | "failed";
  confidence: number;
  summary: string;
  rows: ReportRow[];
  lockedSections: string[];
};
