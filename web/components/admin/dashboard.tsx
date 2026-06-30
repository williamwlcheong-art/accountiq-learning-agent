"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api-client";

type Overview = {
  companies: number;
  documents: number;
  docs_done: number;
  financial_rows: number;
  by_exchange: Array<{ exchange: string | null; n: number }>;
};

type ConfidenceRow = {
  row_key: string;
  avg_conf: number | null;
  n: number;
};

type PatternRow = {
  canonical_key: string;
};

export function Dashboard() {
  const router = useRouter();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [confidence, setConfidence] = useState<ConfidenceRow[]>([]);
  const [patternCount, setPatternCount] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [nextOverview, nextConfidence, patterns] = await Promise.all([
          apiFetch<Overview>("/analytics/overview"),
          apiFetch<ConfidenceRow[]>("/analytics/confidence"),
          apiFetch<PatternRow[]>("/patterns"),
        ]);
        if (cancelled) return;
        setOverview(nextOverview);
        setConfidence(nextConfidence);
        setPatternCount(patterns.length);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        setError(err instanceof Error ? err.message : "Dashboard failed to load.");
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (error) {
    return (
      <div role="alert" className="alert alert-error">
        {error}
      </div>
    );
  }

  if (!overview) {
    return <p className="muted">Loading dashboard...</p>;
  }

  return (
    <section className="admin-page">
      <header className="page-header">
        <h1>Overview</h1>
      </header>

      <div className="stats-row">
        <div className="stat-tile">
          <strong>{overview.companies}</strong>
          <span>Companies</span>
        </div>
        <div className="stat-tile">
          <strong>{overview.documents}</strong>
          <span>Documents</span>
        </div>
        <div className="stat-tile">
          <strong>{overview.docs_done}</strong>
          <span>Processed</span>
        </div>
        <div className="stat-tile">
          <strong>{overview.financial_rows.toLocaleString()}</strong>
          <span>Financial Rows</span>
        </div>
        <div className="stat-tile">
          <strong>{patternCount ?? "-"}</strong>
          <span>Label Patterns</span>
        </div>
      </div>

      <div className="admin-grid">
        <section className="panel">
          <h2>Coverage by Exchange</h2>
          {overview.by_exchange.length ? (
            <ul className="simple-list">
              {overview.by_exchange.map((row) => (
                <li key={row.exchange ?? "Private"}>
                  <span>{row.exchange || "Private"}</span>
                  <strong>{row.n}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No company data yet.</p>
          )}
        </section>

        <section className="panel">
          <h2>Lowest Confidence Rows</h2>
          {confidence.length ? (
            <ul className="simple-list">
              {confidence.slice(0, 8).map((row) => (
                <li key={row.row_key}>
                  <span>{row.row_key}</span>
                  <strong>{row.avg_conf == null ? "-" : `${(row.avg_conf * 100).toFixed(0)}%`}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No extracted rows yet.</p>
          )}
        </section>
      </div>
    </section>
  );
}
