import Link from "next/link";

import { CustomerHeader } from "@/components/customer-header";
import { StatusPill } from "@/components/status-pill";
import { formatMoney, purchaseStatusLabel, reportTypeLabel } from "@/lib/presentation";
import { requireUser } from "@/lib/auth";
import { serverApiFetch } from "@/lib/server-api";
import type { PurchaseHistoryItem } from "@/types/domain";

export default async function AccountPage() {
  const user = await requireUser();
  const purchases = await serverApiFetch<PurchaseHistoryItem[]>("/account/purchases");
  const created = user.created_at ? new Date(user.created_at).toLocaleDateString("en-NZ") : "-";

  return (
    <>
      <CustomerHeader email={user.email} activePage="account" />
      <main className="shell customer-account">
        <section className="panel">
          <p className="eyebrow">Your AccountIQ account</p>
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
          <div className="page-header">
            <div>
              <h2>Report purchase history</h2>
              <p className="muted">Your paid reports and their delivery status appear here.</p>
            </div>
            <Link className="button button-primary" href="/wizard">New valuation</Link>
          </div>
          {purchases.length ? (
            <div className="table-wrap purchase-table-wrap" tabIndex={0}>
              <table className="purchase-table">
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
                      <td data-label="Company">{purchase.company_name}</td>
                      <td data-label="Report">{reportTypeLabel(purchase.report_type)}</td>
                      <td data-label="Amount">{formatMoney(purchase.amount_cents, purchase.currency || "NZD")}</td>
                      <td data-label="Payment">{purchaseStatusLabel(purchase.purchase_status)}</td>
                      <td data-label="Delivery"><StatusPill status={purchase.report_status} /></td>
                      <td data-label="Purchased">{new Date(purchase.paid_at || purchase.created_at).toLocaleDateString("en-NZ")}</td>
                      <td data-label="Actions">
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
            <div className="account-empty-state">
              <p>No purchases yet.</p>
              <Link href="/wizard" className="button button-primary">Start a valuation</Link>
            </div>
          )}
        </section>
      </main>
    </>
  );
}
