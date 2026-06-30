import Link from "next/link";

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
        <div className="admin-links">
          <Link href="/admin">Dashboard</Link>
          <Link href="/admin/companies">Companies</Link>
          <Link href="/admin/upload">Upload</Link>
          <Link href="/admin/documents">Documents</Link>
          <Link href="/admin/patterns">Patterns</Link>
          <Link href="/admin/financials">Financials</Link>
          <Link href="/account">Account</Link>
          <Link href="/admin/settings">Settings</Link>
        </div>
        <div className="nav-user">
          <span>{user.email}</span>
          <LogoutButton />
        </div>
      </nav>
      <main className="shell">{children}</main>
    </>
  );
}
