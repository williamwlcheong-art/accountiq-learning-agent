"use client";

import { ChangeEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch, postForm } from "@/lib/api-client";
import type { Company, DocumentRecord } from "@/types/domain";

type UploadResult = {
  document_id: number;
  company_id: number;
  filename: string;
  status: string;
};

const allowedExtensions = [".pdf", ".xlsx", ".xls", ".xlsm", ".docx"];

function extensionFor(filename: string) {
  const index = filename.lastIndexOf(".");
  return index >= 0 ? filename.slice(index).toLowerCase() : "";
}

export function UploadPage() {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState("");
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
    const extension = extensionFor(nextFile.name);
    if (!allowedExtensions.includes(extension)) {
      setError(`Only PDF, Excel, and Word files are accepted. Got: ${extension || "unknown"}.`);
      setFile(null);
      return;
    }
    setFile(nextFile);
  }

  async function uploadFile() {
    setError("");
    if (!companyId) {
      setError("Select a company before uploading.");
      return;
    }
    if (!file) {
      setError("Select a file to upload.");
      return;
    }

    const body = new FormData();
    body.append("company_id", companyId);
    body.append("file", file);
    body.append("entity_type", "sme");
    body.append("report_type", "compilation");

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
        <label htmlFor="upload-company">
          Company
          <select id="upload-company" value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
            {companies.map((company) => (
              <option key={company.id} value={company.id}>
                {company.name}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="upload-file">
          Financial statement file
          <input id="upload-file" type="file" accept={allowedExtensions.join(",")} onChange={chooseFile} />
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
