"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, FileText, LogOut, UploadCloud } from "lucide-react";
import { API_BASE, apiFetch } from "../lib/api";

type User = {
  id: number;
  email: string;
  is_admin?: number;
};

type UploadResult = {
  company_id: number;
  document_id: number;
  status: string;
};

type ReportResult = {
  report_id: number;
  status: string;
};

type ReportStatus = {
  id: number;
  report_type: string;
  status: string;
  error_message?: string | null;
};

export function DashboardClient() {
  const [user, setUser] = useState<User | null>(null);
  const [businessName, setBusinessName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [report, setReport] = useState<ReportResult | null>(null);
  const [reportStatus, setReportStatus] = useState<ReportStatus | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const reportViewHref = useMemo(() => {
    if (!report || reportStatus?.status !== "done") {
      return "";
    }
    return `${API_BASE}/wizard/report/${report.report_id}/view`;
  }, [report, reportStatus]);

  useEffect(() => {
    apiFetch<User>("/auth/me")
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  useEffect(() => {
    if (!report || reportStatus?.status === "done" || reportStatus?.status === "failed") {
      return;
    }

    const interval = window.setInterval(() => {
      apiFetch<ReportStatus>(`/wizard/report/${report.report_id}/status`)
        .then(setReportStatus)
        .catch((err) => setError(err instanceof Error ? err.message : "Could not fetch report status"));
    }, 1000);

    return () => window.clearInterval(interval);
  }, [report, reportStatus?.status]);

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] || null);
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Select a statement file first.");
      return;
    }

    setBusy("upload");
    setError("");
    setReport(null);
    setReportStatus(null);

    const body = new FormData();
    body.append("business_name", businessName);
    body.append("file", file);

    try {
      const result = await apiFetch<UploadResult>("/wizard/upload", {
        method: "POST",
        body,
      });
      setUploadResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy("");
    }
  }

  async function generateReport() {
    if (!uploadResult) {
      return;
    }

    setBusy("report");
    setError("");

    try {
      const result = await apiFetch<ReportResult>("/wizard/report/generate", {
        method: "POST",
        body: JSON.stringify({
          company_id: uploadResult.company_id,
          report_type: "valuation_advisory",
          intake_answers: {
            purpose: "Owner planning",
            company_location: "New Zealand",
          },
        }),
      });
      setReport(result);
      setReportStatus({
        id: result.report_id,
        report_type: "valuation_advisory",
        status: result.status,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report generation failed");
    } finally {
      setBusy("");
    }
  }

  async function logout() {
    await apiFetch<{ ok: boolean }>("/auth/logout", { method: "POST" });
    window.location.href = "/";
  }

  if (user === null) {
    return (
      <main className="screen dashboard-screen">
        <section className="empty-state">
          <h1>AccountIQ dashboard</h1>
          <p>Sign in to upload statements and view report jobs.</p>
          <Link className="primary-button" href="/login">
            Sign in
            <ArrowRight aria-hidden="true" size={18} />
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="screen dashboard-screen">
      <nav className="app-nav">
        <Link className="brand small" href="/">
          <span className="brand-mark">a</span>
          AccountIQ
        </Link>
        <div className="nav-actions">
          <span>{user.email}</span>
          <button className="icon-button" onClick={logout} title="Sign out" type="button">
            <LogOut aria-hidden="true" size={18} />
          </button>
        </div>
      </nav>

      <section className="dashboard-grid">
        <div className="panel upload-panel">
          <div className="panel-heading">
            <UploadCloud aria-hidden="true" size={22} />
            <div>
              <h1>New valuation report</h1>
              <p>Upload recent financial statements for the business.</p>
            </div>
          </div>

          <form onSubmit={upload}>
            <label>
              Business name
              <input
                onChange={(event) => setBusinessName(event.target.value)}
                required
                type="text"
                value={businessName}
              />
            </label>
            <label>
              Financial statements
              <input
                accept=".pdf,.xlsx,.xls,.xlsm,.docx"
                onChange={handleFile}
                required
                type="file"
              />
            </label>
            <button className="primary-button full-width" disabled={busy === "upload"} type="submit">
              <UploadCloud aria-hidden="true" size={18} />
              {busy === "upload" ? "Uploading" : "Upload statements"}
            </button>
          </form>
        </div>

        <div className="panel report-panel">
          <div className="panel-heading">
            <FileText aria-hidden="true" size={22} />
            <div>
              <h2>Report job</h2>
              <p>Business valuation with adviser review workflow.</p>
            </div>
          </div>

          <div className="status-list">
            <div>
              <span>Upload</span>
              <strong>{uploadResult ? `Document #${uploadResult.document_id}` : "Waiting"}</strong>
            </div>
            <div>
              <span>Generation</span>
              <strong>{reportStatus?.status || "Waiting"}</strong>
            </div>
          </div>

          <button
            className="primary-button full-width"
            disabled={!uploadResult || busy === "report"}
            onClick={generateReport}
            type="button"
          >
            <FileText aria-hidden="true" size={18} />
            {busy === "report" ? "Creating" : "Generate valuation report"}
          </button>

          {reportViewHref ? (
            <a className="secondary-button full-width" href={reportViewHref} rel="noreferrer" target="_blank">
              Open report
              <ArrowRight aria-hidden="true" size={18} />
            </a>
          ) : null}

          {error ? <p className="form-error">{error}</p> : null}
        </div>
      </section>
    </main>
  );
}
