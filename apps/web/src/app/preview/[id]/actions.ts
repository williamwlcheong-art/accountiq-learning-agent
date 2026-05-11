"use server";

import { redirect } from "next/navigation";
import { createReportCheckout } from "@/lib/stripe";

export async function unlockReport(formData: FormData) {
  const reportId = formData.get("reportId");
  if (typeof reportId !== "string" || !reportId) {
    throw new Error("Missing report id.");
  }

  redirect(await createReportCheckout(reportId));
}
