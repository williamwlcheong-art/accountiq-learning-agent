import { redirect } from "next/navigation";

import { serverApiFetch } from "@/lib/server-api";
import type { CurrentUser } from "@/types/domain";

export async function getCurrentUser(): Promise<CurrentUser | null> {
  try {
    return await serverApiFetch<CurrentUser>("/auth/me");
  } catch {
    return null;
  }
}

export async function requireUser(): Promise<CurrentUser> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  return user;
}

export async function requireAdmin(): Promise<CurrentUser> {
  const user = await requireUser();
  if (!user.is_admin) redirect("/wizard");
  return user;
}
