"use server";

import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { getReportForPreview } from "@/lib/mock-report";
import { createReportCheckout } from "@/lib/stripe";

export async function unlockReport(formData: FormData) {
  const reportId = formData.get("reportId");
  if (typeof reportId !== "string" || !reportId) {
    throw new Error("Missing report id.");
  }

  const cookieStore = await cookies();
  const report = await getReportForPreview(reportId, cookieStore.get("accountiq_preview_token")?.value);
  if (!report) {
    notFound();
  }

  redirect(await createReportCheckout(reportId));
}
