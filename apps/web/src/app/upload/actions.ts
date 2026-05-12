"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createLeadPreview } from "@/lib/lead-preview";

export async function submitLeadPreview(formData: FormData) {
  const preview = await createLeadPreview(formData);
  if (preview.sessionToken) {
    const cookieStore = await cookies();
    cookieStore.set("accountiq_preview_token", preview.sessionToken, {
      httpOnly: true,
      maxAge: 60 * 60 * 24 * 14,
      path: "/preview",
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
    });
  }
  redirect(`/preview/${preview.reportId}`);
}
