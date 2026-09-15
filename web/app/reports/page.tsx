import type { Metadata } from "next";
import Link from "next/link";

import { CustomerShell } from "@/components/customer-shell";
import { PdfDownloadLink } from "@/components/pdf-download-link";
import { StatusPill } from "@/components/status-pill";
import { formatMoney, formatNzDate } from "@/lib/presentation";
import { requireUser } from "@/lib/auth";
import { serverApiFetch } from "@/lib/server-api";
import type { PurchaseHistoryItem } from "@/types/domain";

export const metadata: Metadata = {
  title: "Your valuations | AccountIQ",
  description: "Your AccountIQ valuation reports and their delivery status.",
};

function CheckIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true" focusable="false">
      <circle cx="10" cy="10" r="8.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M6.5 10.5l2.5 2.5 4.5-5.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function deliveryNote(status: string) {
  if (status === "awaiting_review") return "A reviewer is checking the draft. We will email you when it is released.";
  if (status === "pending_payment") return "Waiting for payment confirmation.";
  if (status === "payment_failed" || status === "payment_expired") return "No payment was taken. Start a new valuation when ready.";
  if (status === "refunded") return "This payment was refunded.";
  if (status === "failed") return "Something went wrong on our side. We are looking into it. Reply to your confirmation email if you have questions.";
  return "Being prepared. This usually takes a few minutes.";
}

export default async function ReportsPage() {
  const user = await requireUser();
  const purchases = await serverApiFetch<PurchaseHistoryItem[]>("/account/purchases");

  return (
    <CustomerShell user={user} activePage="reports">
      <div className="portal-page-header">
        <div>
          <h1>Your valuations</h1>
          <p>Every report you have ordered, with where it is up to.</p>
        </div>
        {purchases.length ? (
          <Link className="button button-primary" href="/wizard">
            New valuation
          </Link>
        ) : null}
      </div>

      {purchases.length ? (
        <section className="panel" aria-label="Valuation reports">
          <div className="table-wrap purchase-table-wrap" tabIndex={0}>
            <table className="purchase-table">
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Status</th>
                  <th>Ordered</th>
                  <th>Amount</th>
                  <th>Report</th>
                </tr>
              </thead>
              <tbody>
                {purchases.map((purchase) => (
                  <tr key={purchase.purchase_id}>
                    <td data-label="Company">
                      <strong>{purchase.company_name}</strong>
                    </td>
                    <td data-label="Status">
                      <StatusPill status={purchase.report_status} />
                    </td>
                    <td data-label="Ordered">{formatNzDate(purchase.paid_at || purchase.created_at)}</td>
                    <td data-label="Amount">{formatMoney(purchase.amount_cents, purchase.currency || "NZD")}</td>
                    <td data-label="Report">
                      {purchase.report_status === "done" ? (
                        <div className="action-cell">
                          <a
                            className="button button-primary button-sm"
                            href={`/api/backend/wizard/report/${purchase.report_id}/view`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open report
                          </a>
                          <PdfDownloadLink
                            reportId={purchase.report_id}
                            companyName={purchase.company_name}
                            className="button button-secondary button-sm"
                          />
                        </div>
                      ) : (
                        <span className="muted">{deliveryNote(purchase.report_status)}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <section className="portal-empty" aria-labelledby="first-valuation-heading">
          <h2 id="first-valuation-heading">Start your first valuation</h2>
          <p>Here is what to expect.</p>
          <ul>
            <li>
              <CheckIcon />
              <span>Upload your last two to three years of financial statements as PDF or Excel.</span>
            </li>
            <li>
              <CheckIcon />
              <span>Answer a short set of questions about the business. Around ten minutes.</span>
            </li>
            <li>
              <CheckIcon />
              <span>Pay one fixed fee, shown before payment, once your figures are confirmed.</span>
            </li>
            <li>
              <CheckIcon />
              <span>A reviewer checks the draft before it is released to you here.</span>
            </li>
          </ul>
          <div>
            <Link className="button button-primary" href="/wizard">
              Start a valuation
            </Link>
          </div>
        </section>
      )}
    </CustomerShell>
  );
}
