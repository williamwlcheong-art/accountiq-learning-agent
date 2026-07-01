import { AuthCard } from "@/components/auth/auth-card";
import { getCurrentUser } from "@/lib/auth";
import { redirect } from "next/navigation";

export default async function LoginPage() {
  const user = await getCurrentUser();
  if (user) redirect(user.is_admin ? "/admin" : "/wizard");

  return (
    <main className="auth-page">
      <AuthCard />
    </main>
  );
}
