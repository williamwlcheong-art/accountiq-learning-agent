import Link from "next/link";

import { LogoutButton } from "@/components/auth/logout-button";
import { requireUser } from "@/lib/auth";
import { serverApiFetch } from "@/lib/server-api";
import type { PurchaseHistoryItem } from "@/types/domain";

function reportLabel(reportType: string) {
  return reportType
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatAmount(purchase: PurchaseHistoryItem) {
  return new Intl.NumberFormat("en-NZ", {
    style: "currency",
    currency: purchase.currency || "NZD",
  }).format(purchase.amount_cents / 100);
}

function deliveryLabel(status: string) {
  const labels: Record<string, string> = {
    pending_payment: "Payment pending",
    queued: "Preparing",
    researching: "Preparing",
    generating: "Preparing",
    awaiting_review: "Awaiting review",
    done: "Ready",
    failed: "Needs attention",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

export default async function AccountPage() {
  const user = await requireUser();
  const purchases = await serverApiFetch<PurchaseHistoryItem[]>("/account/purchases");
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
          {purchases.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Report</th>
                    <th>Amount</th>
                    <th>Payment</th>
                    <th>Delivery</th>
                    <th>Purchased</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {purchases.map((purchase) => (
                    <tr key={purchase.purchase_id}>
                      <td>{purchase.company_name}</td>
                      <td>{reportLabel(purchase.report_type)}</td>
                      <td>{formatAmount(purchase)}</td>
                      <td>{purchase.purchase_status === "paid" ? "Paid" : "Pending"}</td>
                      <td>
                        <span className={`status-pill status-${purchase.report_status}`}>
                          {deliveryLabel(purchase.report_status)}
                        </span>
                      </td>
                      <td>{new Date(purchase.paid_at || purchase.created_at).toLocaleDateString("en-NZ")}</td>
                      <td>
                        {purchase.report_status === "done" ? (
                          <div className="action-cell">
                            <a
                              className="button button-secondary button-sm"
                              href={`/api/backend/wizard/report/${purchase.report_id}/view`}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Open report
                            </a>
                            <a
                              className="button button-secondary button-sm"
                              href={`/api/backend/wizard/report/${purchase.report_id}/pdf`}
                            >
                              Download PDF
                            </a>
                          </div>
                        ) : (
                          <span className="muted">Available when ready</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">No purchases yet. Your paid reports and delivery status will appear here.</p>
          )}
        </section>
      </main>
    </>
  );
}
