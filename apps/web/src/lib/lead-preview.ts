import { z } from "zod";
import { queueExtraction } from "@/lib/extractor-client";
import { createSupabaseAdminClient } from "@/lib/supabase-admin";

const leadSchema = z.object({
  name: z.string().trim().min(1).max(160),
  email: z.string().trim().email().max(254),
  company: z.string().trim().min(1).max(180),
  intent: z.string().trim().min(1).max(80),
  sourceUrl: z.string().trim().max(500).optional(),
});

const allowedTypes = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel.sheet.macroEnabled.12",
]);

function safeFilename(filename: string) {
  return filename.replace(/[^a-zA-Z0-9._-]/g, "-").replace(/-+/g, "-");
}

function getString(formData: FormData, key: string) {
  const value = formData.get(key);
  return typeof value === "string" ? value : "";
}

export async function createLeadPreview(formData: FormData) {
  const file = formData.get("statement");
  if (!(file instanceof File) || file.size === 0) {
    throw new Error("Please upload a financial statement.");
  }
  if (!allowedTypes.has(file.type)) {
    throw new Error("Upload a PDF, XLSX, or XLSM statement.");
  }

  const lead = leadSchema.parse({
    name: getString(formData, "name"),
    email: getString(formData, "email"),
    company: getString(formData, "company"),
    intent: getString(formData, "intent"),
    sourceUrl: getString(formData, "sourceUrl") || undefined,
  });

  const supabase = createSupabaseAdminClient();
  if (!supabase) {
    return { reportId: "demo", sessionToken: null };
  }

  const sessionToken = crypto.randomUUID();
  const filePath = `${sessionToken}/${crypto.randomUUID()}-${safeFilename(file.name)}`;

  const { data: leadRecord, error: leadError } = await supabase
    .from("leads")
    .insert({
      company: lead.company,
      email: lead.email,
      metadata: { intent: lead.intent },
      name: lead.name,
      source: "upload_flow",
      status: "upload_started",
    })
    .select("id")
    .single();
  if (leadError) throw leadError;

  const { data: sessionRecord, error: sessionError } = await supabase
    .from("upload_sessions")
    .insert({
      lead_id: leadRecord.id,
      session_token: sessionToken,
      source_url: lead.sourceUrl,
      status: "uploaded",
    })
    .select("id")
    .single();
  if (sessionError) throw sessionError;

  const { error: uploadError } = await supabase.storage
    .from("accountiq-uploads")
    .upload(filePath, file, {
      contentType: file.type,
      upsert: false,
    });
  if (uploadError) throw uploadError;

  const { data: documentRecord, error: documentError } = await supabase
    .from("documents")
    .insert({
      content_type: file.type,
      file_size_bytes: file.size,
      lead_id: leadRecord.id,
      original_filename: file.name,
      storage_path: filePath,
      upload_session_id: sessionRecord.id,
    })
    .select("id")
    .single();
  if (documentError) throw documentError;

  const { data: reportRecord, error: reportError } = await supabase
    .from("reports")
    .insert({
      document_id: documentRecord.id,
      lead_id: leadRecord.id,
      locked_sections: ["Full P&L", "Full balance sheet", "Source mapping"],
      preview_json: {
        companyName: lead.company,
        rows: [],
        status: "processing",
      },
      upload_session_id: sessionRecord.id,
    })
    .select("id")
    .single();
  if (reportError) throw reportError;

  try {
    const job = await queueExtraction({
      companyName: lead.company,
      entityType: "listed",
      originalFilename: file.name,
      reportType: "annual_report",
      storagePath: filePath,
      supabaseDocumentId: documentRecord.id as string,
      supabaseReportId: reportRecord.id as string,
      supabaseUploadSessionId: sessionRecord.id as string,
    });

    if (job) {
      await supabase
        .from("documents")
        .update({
          extraction_job_id: String(job.job_id),
          extraction_status: "extracting",
        })
        .eq("id", documentRecord.id);
      await supabase
        .from("upload_sessions")
        .update({ status: "extracting" })
        .eq("id", sessionRecord.id);
    }
  } catch (error) {
    await supabase
      .from("documents")
      .update({
        extraction_metadata: { queue_error: error instanceof Error ? error.message : "Unknown extractor queue error" },
      })
      .eq("id", documentRecord.id);
  }

  return { reportId: reportRecord.id as string, sessionToken };
}
