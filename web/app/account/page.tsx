import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { AccountDetails } from "@/components/account-details";
import { LogoutButton } from "@/components/auth/logout-button";
import { CustomerShell } from "@/components/customer-shell";
import { requireUser } from "@/lib/auth";

export const metadata: Metadata = {
  title: "Account | AccountIQ",
  description: "Your AccountIQ account details.",
};

export default async function AccountPage() {
  const user = await requireUser();
  if (user.is_admin) redirect("/admin/account");

  return (
    <CustomerShell user={user} activePage="account" narrow>
      <div className="portal-page-header">
        <div>
          <h1>Account</h1>
          <p>Your sign-in details and how to reach us.</p>
        </div>
      </div>

      <AccountDetails user={user} />

      <section className="panel" aria-labelledby="account-reports-heading">
        <h2 id="account-reports-heading">Your reports</h2>
        <p className="muted">Every valuation you have ordered, and its delivery status, lives on one page.</p>
        <div>
          <Link className="button button-secondary" href="/reports">
            Go to your valuations
          </Link>
        </div>
      </section>

      <div className="portal-signout">
        <LogoutButton />
      </div>
    </CustomerShell>
  );
}
