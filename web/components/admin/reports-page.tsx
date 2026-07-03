"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api-client";
import type { AdminPendingReport } from "@/types/domain";

type ApproveResponse = {
  id: number;
  status: string;
};

function reportLabel(reportType: string) {
  return reportType
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatPaidAmount(report: AdminPendingReport) {
  if (report.amount_cents == null) return "-";
  return new Intl.NumberFormat("en-NZ", {
    style: "currency",
    currency: report.currency || "NZD",
  }).format(report.amount_cents / 100);
}

export function ReportsPage() {
  const router = useRouter();
  const [reports, setReports] = useState<AdminPendingReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [approvingId, setApprovingId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadReports = useCallback(async () => {
    try {
      setLoading(true);
      setReports(await apiFetch<AdminPendingReport[]>("/admin/reports/pending"));
      setError("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Reports failed to load.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    let cancelled = false;
    apiFetch<AdminPendingReport[]>("/admin/reports/pending")
      .then((rows) => {
        if (cancelled) return;
        setReports(rows);
        setError("");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        if (!cancelled) setError(err instanceof Error ? err.message : "Reports failed to load.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  async function approve(reportId: number) {
    try {
      setApprovingId(reportId);
      const result = await apiFetch<ApproveResponse>(`/admin/reports/${reportId}/approve`, { method: "POST" });
      setMessage(`Report #${result.id} approved and released.`);
      await loadReports();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Approve failed.");
    } finally {
      setApprovingId(null);
    }
  }

  return (
    <section className="admin-page">
      <header className="page-header">
        <h1>Reports</h1>
        <button className="button button-secondary" onClick={loadReports}>
          Refresh
        </button>
      </header>

      {message ? (
        <div role="status" className="alert alert-success">
          {message}
        </div>
      ) : null}

      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}

      <section className="panel">
        {loading ? (
          <p className="muted">Loading reports...</p>
        ) : reports.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Customer</th>
                  <th>Report</th>
                  <th>Paid</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((report) => (
                  <tr key={report.id}>
                    <td>{report.company_name}</td>
                    <td>{report.user_email}</td>
                    <td>{reportLabel(report.report_type)}</td>
                    <td>{formatPaidAmount(report)}</td>
                    <td>
                      <span className={`status-pill status-${report.status}`}>{report.status}</span>
                    </td>
                    <td>{new Date(report.created_at).toLocaleString()}</td>
                    <td>
                      <div className="action-cell">
                        <a
                          className="button button-secondary button-sm"
                          href={`/api/backend/admin/reports/${report.id}/view`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open draft
                        </a>
                        <button
                          className="button button-primary button-sm"
                          onClick={() => approve(report.id)}
                          disabled={approvingId === report.id}
                        >
                          {approvingId === report.id ? "Approving..." : "Approve"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No reports awaiting review.</p>
        )}
      </section>
    </section>
  );
}
