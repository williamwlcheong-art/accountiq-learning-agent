import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AuthCard } from "@/components/auth/auth-card";
import { getCurrentUser } from "@/lib/auth";

type LoginSearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

function resolveMode(mode: string | string[] | undefined): "login" | "register" {
  return mode === "register" ? "register" : "login";
}

export async function generateMetadata({
  searchParams,
}: {
  searchParams: LoginSearchParams;
}): Promise<Metadata> {
  const mode = resolveMode((await searchParams).mode);
  return {
    title: mode === "register" ? "Create your account | AccountIQ" : "Sign in | AccountIQ",
    description: "Sign in to AccountIQ to access your valuations and report delivery.",
  };
}

export default async function LoginPage({ searchParams }: { searchParams: LoginSearchParams }) {
  const user = await getCurrentUser();
  if (user) redirect(user.is_admin ? "/admin" : "/wizard");

  const mode = resolveMode((await searchParams).mode);

  return (
    <main className="auth-page">
      <AuthCard initialMode={mode} />
    </main>
  );
}
