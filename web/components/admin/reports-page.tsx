"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api-client";
import { StatusPill } from "@/components/status-pill";
import { formatMoney, reportTypeLabel } from "@/lib/presentation";
import type { AdminPendingReport } from "@/types/domain";

type ApproveResponse = {
  id: number;
  status: string;
};

export function ReportsPage() {
  const router = useRouter();
  const [reports, setReports] = useState<AdminPendingReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [approvingId, setApprovingId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadReports = useCallback(async (signal?: AbortSignal) => {
    try {
      setLoading(true);
      setReports(await apiFetch<AdminPendingReport[]>("/admin/reports/pending", { signal }));
      setError("");
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Reports failed to load.");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => void loadReports(controller.signal));
    return () => controller.abort();
  }, [loadReports]);

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
        <button className="button button-secondary" onClick={() => void loadReports()}>
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
          <div className="table-wrap" tabIndex={0}>
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
                    <td>{reportTypeLabel(report.report_type)}</td>
                    <td>{report.amount_cents == null ? "-" : formatMoney(report.amount_cents, report.currency || "NZD")}</td>
                    <td>
                      <StatusPill status={report.status} />
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
