import { redirect } from "next/navigation";
import { createSupabaseAdminClient } from "@/lib/supabase-admin";
import { createSupabaseServerClient } from "@/lib/supabase-server";

export type AdminLead = {
  id: string;
  company: string | null;
  email: string;
  status: string;
  created_at: string;
};

export type AdminUpload = {
  id: string;
  original_filename: string;
  extraction_status: string;
  extraction_job_id: string | null;
  created_at: string;
};

export type AdminReport = {
  id: string;
  confidence: number | null;
  is_unlocked: boolean;
  created_at: string;
};

const localDashboard = {
  leads: [
    { id: "local-1", company: "Southern Hardware Ltd", email: "ana@example.com", status: "preview_viewed", created_at: "Local demo" },
    { id: "local-2", company: "Koru Build Co", email: "liam@example.com", status: "upload_started", created_at: "Local demo" },
  ],
  reports: [
    { id: "demo", confidence: 0.91, is_unlocked: false, created_at: "Local demo" },
  ],
  uploads: [
    { id: "local-doc-1", original_filename: "annual-report.pdf", extraction_status: "preview_ready", extraction_job_id: "1", created_at: "Local demo" },
  ],
};

export async function getAdminDashboard() {
  const authClient = await createSupabaseServerClient();
  const adminClient = createSupabaseAdminClient();

  if (!authClient || !adminClient) {
    return localDashboard;
  }

  const {
    data: { user },
  } = await authClient.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  if (user.app_metadata?.role !== "admin") {
    return { leads: [], reports: [], uploads: [] };
  }

  const [{ data: leads }, { data: uploads }, { data: reports }] = await Promise.all([
    adminClient
      .from("leads")
      .select("id, company, email, status, created_at")
      .order("created_at", { ascending: false })
      .limit(50),
    adminClient
      .from("documents")
      .select("id, original_filename, extraction_status, extraction_job_id, created_at")
      .order("created_at", { ascending: false })
      .limit(50),
    adminClient
      .from("reports")
      .select("id, confidence, is_unlocked, created_at")
      .order("created_at", { ascending: false })
      .limit(50),
  ]);

  return {
    leads: (leads ?? []) as AdminLead[],
    uploads: (uploads ?? []) as AdminUpload[],
    reports: (reports ?? []) as AdminReport[],
  };
}
