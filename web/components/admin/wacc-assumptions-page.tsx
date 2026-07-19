"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api-client";
import type { WaccAssumptionSet, WaccAssumptionSetPayload } from "@/types/domain";

const emptyForm: WaccAssumptionSetPayload = {
  name: "",
  risk_free_rate: 0,
  equity_risk_premium: 0,
  beta: 1,
  beta_type: "Industry beta",
  cost_of_debt: 0,
  target_debt_weight: 0,
  target_equity_weight: 100,
  additional_premium: null,
  scenario_spread: null,
  source_references: "",
  publisher: "",
  as_of_date: "",
  rationale: "",
};

function percentage(value: number | null) {
  return value == null ? "-" : `${value}%`;
}

export function WaccAssumptionsPage() {
  const router = useRouter();
  const [sets, setSets] = useState<WaccAssumptionSet[]>([]);
  const [form, setForm] = useState<WaccAssumptionSetPayload>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadSets = useCallback(async (signal?: AbortSignal) => {
    try {
      setLoading(true);
      setSets(await apiFetch<WaccAssumptionSet[]>("/admin/wacc-assumption-sets", { signal }));
      setError("");
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "WACC assumption sets failed to load.");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => void loadSets(controller.signal));
    return () => controller.abort();
  }, [loadSets]);

  function updateField<Key extends keyof WaccAssumptionSetPayload>(key: Key, value: WaccAssumptionSetPayload[Key]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function startEdit(set: WaccAssumptionSet) {
    setEditingId(set.id);
    setForm({
      name: set.name,
      risk_free_rate: set.risk_free_rate,
      equity_risk_premium: set.equity_risk_premium,
      beta: set.beta,
      beta_type: set.beta_type,
      cost_of_debt: set.cost_of_debt,
      target_debt_weight: set.target_debt_weight,
      target_equity_weight: set.target_equity_weight,
      additional_premium: set.additional_premium,
      scenario_spread: set.scenario_spread,
      source_references: set.source_references,
      publisher: set.publisher,
      as_of_date: set.as_of_date,
      rationale: set.rationale,
    });
    setMessage("");
    setError("");
  }

  function resetForm() {
    setEditingId(null);
    setForm(emptyForm);
    setError("");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (form.target_debt_weight + form.target_equity_weight !== 100) {
      setError("Target debt and equity weights must add up to 100%.");
      return;
    }
    try {
      setSaving(true);
      if (editingId == null) {
        await apiFetch<WaccAssumptionSet>("/admin/wacc-assumption-sets", { method: "POST", body: JSON.stringify(form) });
        setMessage("WACC assumption set created as a draft.");
      } else {
        await apiFetch<WaccAssumptionSet>(`/admin/wacc-assumption-sets/${editingId}`, { method: "PUT", body: JSON.stringify(form) });
        setMessage("WACC assumption set updated.");
      }
      resetForm();
      await loadSets();
    } catch (err) {
      setError(err instanceof Error ? err.message : "WACC assumption set could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  async function updateStatus(id: number, action: "approve" | "activate") {
    try {
      await apiFetch<WaccAssumptionSet>(`/admin/wacc-assumption-sets/${id}/${action}`, { method: "POST" });
      setMessage(action === "approve" ? "WACC assumption set approved." : "WACC assumption set is now active.");
      await loadSets();
    } catch (err) {
      setError(err instanceof Error ? err.message : `WACC assumption set could not be ${action}d.`);
    }
  }

  return (
    <section className="admin-page">
      <header className="page-header">
        <h1>WACC assumption sets</h1>
        <button className="button button-secondary" onClick={() => void loadSets()}>Refresh</button>
      </header>
      <p className="muted">Create and approve the rates used in future valuations. Customers do not see these technical inputs.</p>

      {message ? <div role="status" className="alert alert-success">{message}</div> : null}
      {error ? <div role="alert" className="alert alert-error">{error}</div> : null}

      <form className="panel admin-form" onSubmit={save}>
        <h2>{editingId == null ? "New assumption set" : `Edit assumption set #${editingId}`}</h2>
        <label htmlFor="wacc-name">Name<input id="wacc-name" value={form.name} onChange={(event) => updateField("name", event.target.value)} required /></label>
        <div className="inline-controls">
          {([
            ["risk_free_rate", "Risk-free rate (%)"],
            ["equity_risk_premium", "Equity risk premium (%)"],
            ["beta", "Beta"],
            ["cost_of_debt", "Cost of debt (%)"],
            ["target_debt_weight", "Target debt weight (%)"],
            ["target_equity_weight", "Target equity weight (%)"],
            ["additional_premium", "Additional premium (%)"],
            ["scenario_spread", "Scenario spread (%)"],
          ] as const).map(([key, label]) => (
            <label key={key} htmlFor={`wacc-${key}`}>
              {label}
              <input id={`wacc-${key}`} type="number" step="0.01" value={form[key] ?? ""} onChange={(event) => updateField(key, event.target.value === "" ? null : Number(event.target.value))} required={!(["additional_premium", "scenario_spread"] as string[]).includes(key)} />
            </label>
          ))}
          <label htmlFor="wacc-beta-type">Beta type<input id="wacc-beta-type" value={form.beta_type} onChange={(event) => updateField("beta_type", event.target.value)} required /></label>
        </div>
        <label htmlFor="wacc-publisher">Publisher<input id="wacc-publisher" value={form.publisher} onChange={(event) => updateField("publisher", event.target.value)} required /></label>
        <label htmlFor="wacc-as-of-date">As-of date<input id="wacc-as-of-date" type="date" value={form.as_of_date} onChange={(event) => updateField("as_of_date", event.target.value)} required /></label>
        <label htmlFor="wacc-sources">Source references<textarea id="wacc-sources" rows={2} value={form.source_references} onChange={(event) => updateField("source_references", event.target.value)} required /></label>
        <label htmlFor="wacc-rationale">Rationale<textarea id="wacc-rationale" rows={3} value={form.rationale} onChange={(event) => updateField("rationale", event.target.value)} required /></label>
        <div className="wizard-actions">
          {editingId != null ? <button type="button" className="button button-secondary" onClick={resetForm}>Cancel edit</button> : null}
          <button className="button button-primary" disabled={saving}>{saving ? "Saving..." : editingId == null ? "Create draft" : "Save changes"}</button>
        </div>
      </form>

      <section className="panel">
        <h2>Saved sets</h2>
        {loading ? <p className="muted">Loading WACC assumption sets...</p> : sets.length ? (
          <div className="table-wrap" tabIndex={0}>
            <table>
              <thead><tr><th>Name</th><th>Version</th><th>WACC inputs</th><th>As of</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>{sets.map((set) => (
                <tr key={set.id}>
                  <td>{set.name}</td><td>{set.version}</td><td>Rf {percentage(set.risk_free_rate)}, ERP {percentage(set.equity_risk_premium)}, beta {set.beta}</td><td>{set.as_of_date}</td>
                  <td>{set.active ? "Active" : set.status}</td>
                  <td><div className="action-cell"><button className="button button-secondary button-sm" onClick={() => startEdit(set)}>Edit</button>{set.status === "draft" ? <button className="button button-primary button-sm" onClick={() => void updateStatus(set.id, "approve")}>Approve</button> : null}{set.status === "approved" && !set.active ? <button className="button button-primary button-sm" onClick={() => void updateStatus(set.id, "activate")}>Activate</button> : null}</div></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <p className="muted">No WACC assumption sets have been created.</p>}
      </section>
    </section>
  );
}
