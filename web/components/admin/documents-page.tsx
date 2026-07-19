"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { StatusPill } from "@/components/status-pill";
import { ApiError, apiFetch } from "@/lib/api-client";
import type { DocumentRecord } from "@/types/domain";

export function DocumentsPage() {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function loadDocuments() {
    try {
      setLoading(true);
      setDocuments(await apiFetch<DocumentRecord[]>("/documents"));
      setError("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Documents failed to load.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    apiFetch<DocumentRecord[]>("/documents")
      .then((rows) => {
        if (cancelled) return;
        setDocuments(rows);
        setError("");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        if (!cancelled) setError(err instanceof Error ? err.message : "Documents failed to load.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  async function retry(documentId: number) {
    try {
      await apiFetch(`/documents/${documentId}/retry`, { method: "POST" });
      await loadDocuments();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Retry failed.");
    }
  }

  return (
    <section className="admin-page">
      <header className="page-header">
        <h1>Documents</h1>
        <button className="button button-secondary" onClick={loadDocuments}>
          Refresh
        </button>
      </header>

      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}

      <section className="panel">
        {loading ? (
          <p className="muted">Loading documents...</p>
        ) : documents.length ? (
          <div className="table-wrap" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>Company</th>
                  <th>File</th>
                  <th>Type</th>
                  <th>Entity</th>
                  <th>Standard</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id}>
                    <td>{doc.company_name || doc.company_id}</td>
                    <td>{doc.filename}</td>
                    <td>{doc.report_type || "-"}</td>
                    <td>{doc.entity_type || "-"}</td>
                    <td>{doc.reporting_standard || "-"}</td>
                    <td>
                      <StatusPill status={doc.extraction_status} />
                    </td>
                    <td>{doc.confidence_score == null ? "-" : `${(doc.confidence_score * 100).toFixed(0)}%`}</td>
                    <td>
                      {doc.extraction_status === "failed" ? (
                        <button className="button button-secondary" onClick={() => retry(doc.id)}>
                          Retry
                        </button>
                      ) : (
                        "-"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No documents yet.</p>
        )}
      </section>
    </section>
  );
}
