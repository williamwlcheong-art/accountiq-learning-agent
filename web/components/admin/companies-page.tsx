"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch, postForm } from "@/lib/api-client";
import type { Company } from "@/types/domain";

export function CompaniesPage() {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function loadCompanies() {
    try {
      setLoading(true);
      setCompanies(await apiFetch<Company[]>("/companies"));
      setError("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Companies failed to load.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    apiFetch<Company[]>("/companies")
      .then((rows) => {
        if (cancelled) return;
        setCompanies(rows);
        setError("");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        if (!cancelled) setError(err instanceof Error ? err.message : "Companies failed to load.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  async function createCompany(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setError("");
    setSaving(true);
    try {
      const form = new FormData(formElement);
      await postForm<{ id: number; name: string }>("/companies", form);
      formElement.reset();
      setShowForm(false);
      await loadCompanies();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Company could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="admin-page">
      <header className="page-header">
        <h1>Companies</h1>
        <button className="button button-primary" onClick={() => setShowForm((value) => !value)}>
          {showForm ? "Cancel" : "Add Company"}
        </button>
      </header>

      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}

      {showForm ? (
        <form className="panel admin-form" onSubmit={createCompany}>
          <label htmlFor="company-name">
            Company Name
            <input id="company-name" name="name" required />
          </label>
          <label htmlFor="company-ticker">
            Ticker
            <input id="company-ticker" name="ticker" />
          </label>
          <label htmlFor="company-exchange">
            Exchange
            <select id="company-exchange" name="exchange" defaultValue="Private">
              <option value="Private">Private</option>
              <option value="NZX">NZX</option>
              <option value="ASX">ASX</option>
            </select>
          </label>
          <label htmlFor="company-sector">
            Sector
            <input id="company-sector" name="sector" />
          </label>
          <label htmlFor="company-country">
            Country
            <select id="company-country" name="country" defaultValue="NZ">
              <option value="NZ">NZ</option>
              <option value="AU">AU</option>
              <option value="Other">Other</option>
            </select>
          </label>
          <button className="button button-primary" disabled={saving}>
            {saving ? "Saving..." : "Save Company"}
          </button>
        </form>
      ) : null}

      <section className="panel">
        {loading ? (
          <p className="muted">Loading companies...</p>
        ) : companies.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Ticker</th>
                  <th>Exchange</th>
                  <th>Sector</th>
                  <th>Country</th>
                  <th>Documents</th>
                  <th>Profile</th>
                </tr>
              </thead>
              <tbody>
                {companies.map((company) => (
                  <tr key={company.id}>
                    <td>{company.name}</td>
                    <td>{company.ticker || "-"}</td>
                    <td>{company.exchange || "Private"}</td>
                    <td>{company.sector || "-"}</td>
                    <td>{company.country || "-"}</td>
                    <td>{company.doc_count ?? 0}</td>
                    <td>{company.sections_complete ?? 0}/4 complete</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No companies yet.</p>
        )}
      </section>
    </section>
  );
}
