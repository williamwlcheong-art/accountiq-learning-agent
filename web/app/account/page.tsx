import Link from "next/link";

import { LogoutButton } from "@/components/auth/logout-button";
import { requireUser } from "@/lib/auth";

export default async function AccountPage() {
  const user = await requireUser();
  const created = user.created_at ? new Date(user.created_at).toLocaleDateString() : "-";

  return (
    <>
      <nav className="top-nav">
        <Link className="nav-brand nav-brand-link" href={user.is_admin ? "/admin" : "/wizard"}>
          <strong>AccountIQ</strong>
          <span>{user.is_admin ? "Admin" : "Wizard"}</span>
        </Link>
        <div className="nav-user">
          <span>{user.email}</span>
          <LogoutButton />
        </div>
      </nav>
      <main className="shell">
        <section className="panel">
          <h1>Account</h1>
          <dl className="detail-list">
            <div>
              <dt>Email address</dt>
              <dd>{user.email}</dd>
            </div>
            <div>
              <dt>Member since</dt>
              <dd>{created}</dd>
            </div>
          </dl>
        </section>
        <section className="panel">
          <h2>Report Purchase History</h2>
          <p className="muted">Purchased reports will appear here after payment integration is enabled.</p>
        </section>
      </main>
    </>
  );
}
