"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api-client";
import type { Company } from "@/types/domain";

type FinancialRow = {
  statement: string;
  row_key: string;
  row_label: string;
  period: string;
  value: number | null;
  confidence: number | null;
  source_count: number;
};

export function FinancialsPage() {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState("");
  const [statement, setStatement] = useState("");
  const [rows, setRows] = useState<FinancialRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Company[]>("/companies")
      .then((nextCompanies) => {
        setCompanies(nextCompanies);
        if (nextCompanies[0]) setCompanyId(String(nextCompanies[0].id));
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) router.replace("/login");
        else setError(err instanceof Error ? err.message : "Companies failed to load.");
      });
  }, [router]);

  useEffect(() => {
    if (!companyId) return;
    const suffix = statement ? `?statement=${statement}` : "";
    apiFetch<FinancialRow[]>(`/financials/${companyId}${suffix}`)
      .then((nextRows) => {
        setRows(nextRows);
        setError("");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) router.replace("/login");
        else setError(err instanceof Error ? err.message : "Financials failed to load.");
      });
  }, [companyId, router, statement]);

  const periods = useMemo(() => Array.from(new Set(rows.map((row) => row.period))).sort().reverse(), [rows]);
  const groupedRows = useMemo(() => {
    const map = new Map<string, { statement: string; row_key: string; row_label: string; values: Record<string, number | null> }>();
    for (const row of rows) {
      const key = `${row.statement}:${row.row_key}`;
      const existing = map.get(key) ?? {
        statement: row.statement,
        row_key: row.row_key,
        row_label: row.row_label,
        values: {},
      };
      existing.values[row.period] = row.value;
      map.set(key, existing);
    }
    return Array.from(map.values());
  }, [rows]);

  return (
    <section className="admin-page">
      <header className="page-header">
        <h1>Financial Data</h1>
      </header>

      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}

      <section className="panel admin-form inline-controls">
        <label htmlFor="financial-company">
          Company
          <select id="financial-company" value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
            {companies.map((company) => (
              <option key={company.id} value={company.id}>
                {company.name}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="financial-statement">
          Statement
          <select id="financial-statement" value={statement} onChange={(event) => setStatement(event.target.value)}>
            <option value="">All statements</option>
            <option value="pnl">Profit & Loss</option>
            <option value="bs">Balance Sheet</option>
            <option value="cf">Cash Flow</option>
            <option value="eq">Equity</option>
          </select>
        </label>
      </section>

      <section className="panel">
        {groupedRows.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Statement</th>
                  <th>Row</th>
                  {periods.map((period) => (
                    <th key={period}>{period}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {groupedRows.map((row) => (
                  <tr key={`${row.statement}:${row.row_key}`}>
                    <td>{row.statement.toUpperCase()}</td>
                    <td>{row.row_label}</td>
                    {periods.map((period) => (
                      <td key={period}>{row.values[period] == null ? "-" : row.values[period]?.toLocaleString()}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No financial rows for this company yet.</p>
        )}
      </section>
    </section>
  );
}
