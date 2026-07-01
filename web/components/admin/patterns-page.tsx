"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api-client";

type PatternRow = {
  canonical_key: string;
  statement: string;
  raw_label: string;
  match_count: number;
};

export function PatternsPage() {
  const router = useRouter();
  const [statement, setStatement] = useState("");
  const [patterns, setPatterns] = useState<PatternRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const suffix = statement ? `?statement=${statement}` : "";
    apiFetch<PatternRow[]>(`/patterns${suffix}`)
      .then((rows) => {
        setPatterns(rows);
        setError("");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) router.replace("/login");
        else setError(err instanceof Error ? err.message : "Patterns failed to load.");
      });
  }, [router, statement]);

  return (
    <section className="admin-page">
      <header className="page-header">
        <h1>Label Pattern Library</h1>
        <a className="button button-primary export-link" href="/api/backend/patterns/export" download>
          Export JSON
        </a>
      </header>

      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}

      <section className="panel admin-form inline-controls">
        <label htmlFor="pattern-statement">
          Statement
          <select id="pattern-statement" value={statement} onChange={(event) => setStatement(event.target.value)}>
            <option value="">All statements</option>
            <option value="pnl">Profit & Loss</option>
            <option value="bs">Balance Sheet</option>
            <option value="cf">Cash Flow</option>
            <option value="eq">Equity</option>
          </select>
        </label>
      </section>

      <section className="panel">
        <p className="muted">{patterns.length} learned labels</p>
        {patterns.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Statement</th>
                  <th>Canonical Key</th>
                  <th>Raw Label</th>
                  <th>Matches</th>
                </tr>
              </thead>
              <tbody>
                {patterns.map((pattern) => (
                  <tr key={`${pattern.statement}:${pattern.canonical_key}:${pattern.raw_label}`}>
                    <td>{pattern.statement.toUpperCase()}</td>
                    <td>{pattern.canonical_key}</td>
                    <td>{pattern.raw_label}</td>
                    <td>{pattern.match_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </section>
  );
}
