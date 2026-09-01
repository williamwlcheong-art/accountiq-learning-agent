import type { Metadata } from "next";

import { AccountDetails } from "@/components/account-details";
import { requireAdmin } from "@/lib/auth";

export const metadata: Metadata = {
  title: "Account | AccountIQ admin",
};

export default async function AdminAccountPage() {
  const user = await requireAdmin();

  return (
    <div className="admin-page">
      <div className="page-header">
        <div>
          <h1>Account</h1>
          <p className="muted">Your administrator sign-in details.</p>
        </div>
      </div>
      <AccountDetails user={user} />
    </div>
  );
}
