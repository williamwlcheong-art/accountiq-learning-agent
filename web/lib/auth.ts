import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { serverApiFetch } from "@/lib/server-api";
import type { CurrentUser } from "@/types/domain";

/** Set by FastAPI at sign-in (backend/auth.py COOKIE_NAME). */
const SESSION_COOKIE = "accountiq_session";

export async function getCurrentUser(): Promise<CurrentUser | null> {
  // No session cookie means no user, so anonymous visitors skip the round trip to FastAPI.
  if (!(await cookies()).has(SESSION_COOKIE)) return null;
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
  if (!user.is_admin) redirect("/reports");
  return user;
}
