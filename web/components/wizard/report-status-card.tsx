"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api-client";
import type { ReportStatus } from "@/types/domain";

type ReportStatusCardProps = {
  reportId: number;
  userEmail: string;
};

export function ReportStatusCard({ reportId, userEmail }: ReportStatusCardProps) {
  const router = useRouter();
  const [status, setStatus] = useState<ReportStatus | null>(null);
  const [error, setError] = useState("");
  const [retrying, setRetrying] = useState(false);
  const [pollRestart, setPollRestart] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadStatus() {
      try {
        const nextStatus = await apiFetch<ReportStatus>(`/wizard/report/${reportId}/status`);
        if (cancelled) return;
        setStatus(nextStatus);
        setError("");
        if (nextStatus.status === "done" || nextStatus.status === "failed") {
          window.clearInterval(interval);
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
      }
    }

    const interval = window.setInterval(() => {
      if (cancelled) return;
      loadStatus();
    }, 3000);
    loadStatus();

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [reportId, router, pollRestart]);

  async function retry() {
    setRetrying(true);
    setError("");
    try {
      const nextStatus = await apiFetch<ReportStatus>(`/wizard/report/${reportId}/retry`, { method: "POST" });
      setStatus(nextStatus);
      setPollRestart((value) => value + 1);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Retry failed.");
    } finally {
      setRetrying(false);
    }
  }

  const currentStatus = status?.status ?? "queued";
  const isDone = currentStatus === "done";
  const isFailed = currentStatus === "failed";

  return (
    <section className="wizard-card">
      <h2>Your report is being prepared</h2>

      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}

      {!isFailed ? (
        <p>
          We will email <strong>{userEmail}</strong> when your report is ready.
        </p>
      ) : null}

      <p className={`status-pill status-${currentStatus}`}>Status: {currentStatus}</p>

      {currentStatus === "researching" ? (
        <p className="wizard-note">
          The agent is gathering market data and WACC inputs. This can take a little longer than standard reports.
        </p>
      ) : null}

      {isDone ? (
        <div className="wizard-done">
          <p>Your report is ready.</p>
          <a className="button button-primary" href={`/api/backend/wizard/report/${reportId}/view`} target="_blank" rel="noreferrer">
            Open report
          </a>
        </div>
      ) : null}

      {isFailed ? (
        <div className="wizard-failed">
          <p>{status?.error_message || "Report generation failed."}</p>
          <button className="button button-primary" onClick={retry} disabled={retrying}>
            {retrying ? "Retrying..." : "Retry"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
