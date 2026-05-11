import type { PreviewReportData } from "@/types/report";
import { createSupabaseAdminClient } from "@/lib/supabase-admin";

export const demoReport: PreviewReportData = {
  id: "demo",
  companyName: "Southern Hardware Ltd",
  status: "ready",
  confidence: 0.91,
  summary:
    "Revenue growth is positive, gross margin is steady, and working capital should be checked before lending decisions.",
  rows: [
    { statement: "pnl", label: "Revenue", period: "2025", value: 1842000, confidence: 0.96 },
    { statement: "pnl", label: "Gross profit", period: "2025", value: 712000, confidence: 0.93 },
    { statement: "pnl", label: "Profit before tax", period: "2025", value: 214000, confidence: 0.9 },
    { statement: "bs", label: "Cash and bank", period: "2025", value: 138000, confidence: 0.88 },
    { statement: "bs", label: "Total liabilities", period: "2025", value: 489000, confidence: 0.87 },
  ],
  lockedSections: ["Full P&L reconstruction", "Balance sheet mapping", "Narrative review"],
};

export function getPreviewReport(id: string): PreviewReportData {
  return {
    ...demoReport,
    id,
  };
}

type ReportRecord = {
  id: string;
  confidence: number | null;
  locked_sections: unknown;
  narrative: string | null;
  preview_json: {
    companyName?: string;
    rows?: PreviewReportData["rows"];
    status?: PreviewReportData["status"];
    summary?: string;
  };
};

export async function getReportForPreview(id: string): Promise<PreviewReportData> {
  if (id === "demo") {
    return getPreviewReport(id);
  }

  const supabase = createSupabaseAdminClient();
  if (!supabase) {
    return getPreviewReport(id);
  }

  const { data, error } = await supabase
    .from("reports")
    .select("id, confidence, locked_sections, narrative, preview_json")
    .eq("id", id)
    .single<ReportRecord>();

  if (error || !data) {
    return getPreviewReport(id);
  }

  const lockedSections = Array.isArray(data.locked_sections)
    ? data.locked_sections.filter((item): item is string => typeof item === "string")
    : demoReport.lockedSections;

  return {
    id: data.id,
    companyName: data.preview_json.companyName ?? "Uploaded statement",
    status: data.preview_json.status ?? "processing",
    confidence: data.confidence ?? 0,
    summary: data.preview_json.summary ?? data.narrative ?? "Extraction is queued. Your preview will update once the report is ready.",
    rows: data.preview_json.rows ?? [],
    lockedSections,
  };
}
