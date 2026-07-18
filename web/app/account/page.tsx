import Link from "next/link";

import { CustomerHeader } from "@/components/customer-header";
import { purchaseStatusLabel, reportStatusLabel, reportTypeLabel } from "@/lib/presentation";
import { requireUser } from "@/lib/auth";
import { serverApiFetch } from "@/lib/server-api";
import type { PurchaseHistoryItem } from "@/types/domain";

function formatAmount(purchase: PurchaseHistoryItem) {
  return new Intl.NumberFormat("en-NZ", {
    style: "currency",
    currency: purchase.currency || "NZD",
  }).format(purchase.amount_cents / 100);
}

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
            <>
              <div className="table-wrap purchase-table-wrap" tabIndex={0}>
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
                        <td>{reportTypeLabel(purchase.report_type)}</td>
                        <td>{formatAmount(purchase)}</td>
                        <td>{purchaseStatusLabel(purchase.purchase_status)}</td>
                        <td>
                          <span className={`status-pill status-${purchase.report_status}`}>
                            {reportStatusLabel(purchase.report_status)}
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
              <div className="purchase-record-list">
                {purchases.map((purchase) => (
                  <article className="purchase-record" key={purchase.purchase_id}>
                    <div>
                      <strong>{purchase.company_name}</strong>
                      <p>{reportTypeLabel(purchase.report_type)}</p>
                    </div>
                    <dl>
                      <div><dt>Amount</dt><dd>{formatAmount(purchase)}</dd></div>
                      <div><dt>Payment</dt><dd>{purchaseStatusLabel(purchase.purchase_status)}</dd></div>
                      <div><dt>Delivery</dt><dd><span className={`status-pill status-${purchase.report_status}`}>{reportStatusLabel(purchase.report_status)}</span></dd></div>
                    </dl>
                    {purchase.report_status === "done" ? (
                      <div className="action-cell">
                        <a className="button button-secondary button-sm" href={`/api/backend/wizard/report/${purchase.report_id}/view`} target="_blank" rel="noreferrer">Open report</a>
                        <a className="button button-secondary button-sm" href={`/api/backend/wizard/report/${purchase.report_id}/pdf`}>Download PDF</a>
                      </div>
                    ) : <p className="muted">Available when ready</p>}
                  </article>
                ))}
              </div>
            </>
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
