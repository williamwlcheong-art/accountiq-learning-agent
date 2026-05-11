"use server";

import { createSupabaseServerClient } from "@/lib/supabase-server";

export async function sendMagicLink(formData: FormData) {
  const email = formData.get("email");
  if (typeof email !== "string" || !email.includes("@")) {
    throw new Error("Enter a valid email address.");
  }

  const supabase = await createSupabaseServerClient();
  if (!supabase) {
    return;
  }

  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: `${siteUrl}/app`,
    },
  });

  if (error) {
    throw error;
  }
}
