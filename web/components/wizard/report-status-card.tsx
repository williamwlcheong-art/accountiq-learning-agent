"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { StatusPill } from "@/components/status-pill";
import { ApiError, apiFetch } from "@/lib/api-client";
import type { ReportStatus } from "@/types/domain";

type ReportStatusCardProps = {
  reportId: number;
  userEmail: string;
  onRestartRequired: (status: ReportStatus) => void;
};

export function ReportStatusCard({ reportId, userEmail, onRestartRequired }: ReportStatusCardProps) {
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
        if (["done", "failed", "payment_failed", "payment_expired", "refunded"].includes(nextStatus.status)) {
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
  const isPaymentFailed = currentStatus === "payment_failed";
  const isPaymentExpired = currentStatus === "payment_expired";
  const isRefunded = currentStatus === "refunded";
  const isPaymentTerminal = isPaymentFailed || isPaymentExpired || isRefunded;
  const isAwaitingReview = currentStatus === "awaiting_review";
  let heading = "Your report is being prepared";
  if (currentStatus === "pending_payment") heading = "Complete payment to start your report";
  if (isPaymentFailed) heading = "Your payment was not completed";
  if (isPaymentExpired) heading = "Your payment link expired";
  if (isRefunded) heading = "This payment was refunded";
  if (isDone) heading = "Your report is ready";
  if (isFailed) heading = "Your report needs attention";
  if (isAwaitingReview) heading = "Your report is under review";

  return (
    <section className="wizard-card">
      <h2>{heading}</h2>

      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}

      {!isFailed && !isPaymentTerminal ? (
        <p>
          We will email <strong>{userEmail}</strong> when your report is ready.
        </p>
      ) : null}

      <StatusPill status={currentStatus} />

      {currentStatus === "pending_payment" ? (
        <p className="wizard-note">
          We are waiting for payment confirmation before starting report generation.
        </p>
      ) : null}

      {isPaymentTerminal ? (
        <div className="wizard-failed">
          <p>
            {isRefunded
              ? "Report access has been withdrawn because the payment was refunded."
              : "No report generation was started. Please begin a new checkout when you are ready."}
          </p>
          {!isRefunded ? (
            <Link className="button button-primary" href="/wizard">Start a new checkout</Link>
          ) : null}
        </div>
      ) : null}

      {currentStatus === "researching" ? (
        <p className="wizard-note">
          We are gathering market data and WACC inputs. This can take a little longer than standard reports.
        </p>
      ) : null}

      {isAwaitingReview ? (
        <p className="wizard-note">
          A reviewer is checking the draft before release. We will keep this page updated and email you when it is ready.
        </p>
      ) : null}

      {isDone ? (
        <div className="wizard-done">
          <p>Your report is ready.</p>
          <div className="report-actions">
            <a className="button button-primary" href={`/api/backend/wizard/report/${reportId}/view`} target="_blank" rel="noreferrer">
              Open report
            </a>
            <a className="button button-secondary" href={`/api/backend/wizard/report/${reportId}/pdf`}>
              Download PDF
            </a>
          </div>
        </div>
      ) : null}

      {isFailed ? (
        <div className="wizard-failed">
          <p>
            {status?.restart_required
              ? "We need updated valuation inputs to use the current calculation engine. Your existing payment will be reused."
              : status?.error_message || "Report generation failed."}
          </p>
          {status?.restart_required ? (
            <button className="button button-primary" onClick={() => onRestartRequired(status)}>
              Update valuation inputs
            </button>
          ) : (
            <button className="button button-primary" onClick={retry} disabled={retrying}>
              {retrying ? "Retrying..." : "Retry"}
            </button>
          )}
        </div>
      ) : null}
    </section>
  );
}
