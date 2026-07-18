import { AdminNavigation } from "@/components/admin/admin-navigation";
import { LogoutButton } from "@/components/auth/logout-button";
import { requireAdmin } from "@/lib/auth";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const user = await requireAdmin();

  return (
    <>
      <nav className="top-nav admin-nav">
        <div className="nav-brand">
          <strong>AccountIQ</strong>
          <span>Learning Agent</span>
        </div>
        <AdminNavigation />
        <div className="nav-user">
          <span>{user.email}</span>
          <LogoutButton />
        </div>
      </nav>
      <main className="shell">{children}</main>
    </>
  );
}
