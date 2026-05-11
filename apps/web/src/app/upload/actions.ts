"use server";

import { redirect } from "next/navigation";
import { createLeadPreview } from "@/lib/lead-preview";

export async function submitLeadPreview(formData: FormData) {
  const previewId = await createLeadPreview(formData);
  redirect(`/preview/${previewId}`);
}
