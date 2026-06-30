"use client";

import { ChangeEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch, postForm } from "@/lib/api-client";
import { FINANCIAL_FILE_ACCEPT, validateFinancialFile } from "@/lib/upload-files";
import type { Company, DocumentRecord } from "@/types/domain";

type UploadResult = {
  document_id: number;
  company_id: number;
  filename: string;
  status: string;
};

export function UploadPage() {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [entityType, setEntityType] = useState("listed");
  const [reportType, setReportType] = useState("annual_report");
  const [fiscalYearEnd, setFiscalYearEnd] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [activeDocId, setActiveDocId] = useState<number | null>(null);
  const [status, setStatus] = useState<DocumentRecord | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    apiFetch<Company[]>("/companies")
      .then((rows) => {
        setCompanies(rows);
        if (rows[0]) setCompanyId(String(rows[0].id));
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        setError(err instanceof Error ? err.message : "Companies failed to load.");
      });
  }, [router]);

  useEffect(() => {
    if (!activeDocId) return;
    let cancelled = false;

    async function loadStatus() {
      try {
        const nextStatus = await apiFetch<DocumentRecord>(`/documents/${activeDocId}/status`);
        if (cancelled) return;
        setStatus(nextStatus);
        if (nextStatus.extraction_status === "done" || nextStatus.extraction_status === "failed") {
          window.clearInterval(interval);
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) router.replace("/login");
      }
    }

    const interval = window.setInterval(loadStatus, 3000);
    loadStatus();
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [activeDocId, router]);

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    setError("");
    const nextFile = event.target.files?.[0] ?? null;
    if (!nextFile) {
      setFile(null);
      return;
    }
    const validationError = validateFinancialFile(nextFile);
    if (validationError) {
      setError(validationError);
      setFile(null);
      return;
    }
    setFile(nextFile);
  }

  async function uploadFile() {
    setError("");
    if (!file) {
      setError("Select a file to upload.");
      return;
    }

    const body = new FormData();
    if (companyId) body.append("company_id", companyId);
    if (!companyId && companyName.trim()) body.append("company_name", companyName.trim());
    body.append("entity_type", entityType);
    body.append("report_type", reportType);
    body.append("fiscal_year_end", fiscalYearEnd.trim());
    body.append("file", file);

    setUploading(true);
    try {
      const result = await postForm<UploadResult>("/documents/upload", body);
      setActiveDocId(result.document_id);
      setStatus(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="admin-page">
      <header className="page-header">
        <h1>Upload Financial Statement</h1>
      </header>

      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}

      <section className="panel admin-form">
        <div className="form-grid">
          <label htmlFor="upload-company">
            Company
            <select id="upload-company" value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
              <option value="">Auto-create / use company name below</option>
              {companies.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.name}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="upload-company-name">
            Company Name
            <input
              id="upload-company-name"
              value={companyName}
              onChange={(event) => setCompanyName(event.target.value)}
              placeholder="e.g. Acme Ltd"
            />
            <small className="muted">Required for Excel uploads when no existing company is selected.</small>
          </label>
          <label htmlFor="upload-entity-type">
            Entity Type
            <select id="upload-entity-type" value={entityType} onChange={(event) => setEntityType(event.target.value)}>
              <option value="listed">Listed (IFRS)</option>
              <option value="sme">Private SME (Compilation)</option>
            </select>
          </label>
          <label htmlFor="upload-report-type">
            Report Type
            <select id="upload-report-type" value={reportType} onChange={(event) => setReportType(event.target.value)}>
              <option value="annual_report">Annual Report</option>
              <option value="compilation">Compilation Report</option>
              <option value="management_accounts">Management Accounts</option>
            </select>
          </label>
          <label htmlFor="upload-fiscal-year-end">
            Fiscal Year End
            <input
              id="upload-fiscal-year-end"
              value={fiscalYearEnd}
              onChange={(event) => setFiscalYearEnd(event.target.value)}
              placeholder="2025-03-31"
            />
          </label>
        </div>

        <label className="drop-zone" htmlFor="upload-file">
          <span className="drop-zone-icon" aria-hidden="true">
            PDF
          </span>
          <strong>Click or drag file here</strong>
          <span>PDF, Excel, or Word financial statements</span>
          <input id="upload-file" type="file" accept={FINANCIAL_FILE_ACCEPT} onChange={chooseFile} />
        </label>
        {file ? <p className="muted">Selected: {file.name}</p> : null}
        <button className="button button-primary" onClick={uploadFile} disabled={uploading}>
          {uploading ? "Uploading..." : "Upload & Ingest"}
        </button>
      </section>

      {activeDocId ? (
        <section className="panel">
          <h2>Active Ingestion Job</h2>
          <p>Document #{activeDocId}</p>
          <p className={`status-pill status-${status?.extraction_status ?? "processing"}`}>
            {status?.extraction_status ?? "processing"}
          </p>
          {status?.logs?.length ? (
            <ul className="simple-list">
              {status.logs.slice(0, 5).map((log) => (
                <li key={`${log.created_at}-${log.message}`}>
                  <span>{log.level}</span>
                  <strong>{log.message}</strong>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
