"use client";

import { Fragment, FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch, postForm } from "@/lib/api-client";
import type { Company } from "@/types/domain";

type ProfileStatus = {
  sections_complete: number;
  total: number;
  sector_complete: boolean;
  description_complete: boolean;
  management_complete: boolean;
  ebitda_complete: boolean;
  can_generate: boolean;
  reported_ebitda: number | null;
  has_financials: boolean;
};

type ManagementMember = {
  id: number;
  name: string;
  title: string | null;
  bio: string | null;
};

type EbitdaAdjustment = {
  id: number;
  label: string;
  amount: number;
  rationale: string | null;
};

type MemberForm = {
  id: number | null;
  name: string;
  title: string;
  bio: string;
};

type AdjustmentForm = {
  id: number | null;
  label: string;
  amount: string;
  rationale: string;
};

const INDUSTRY_OPTIONS = [
  "Retail",
  "Construction",
  "Professional Services",
  "Hospitality & Food Service",
  "Healthcare & Medical",
  "Manufacturing",
  "Technology & Software",
  "Agriculture & Horticulture",
  "Transport & Logistics",
  "Property & Real Estate",
  "Wholesale & Distribution",
  "Financial Services",
  "Media & Communications",
  "Education & Training",
  "Other",
];

const emptyMemberForm: MemberForm = { id: null, name: "", title: "", bio: "" };
const emptyAdjustmentForm: AdjustmentForm = { id: null, label: "", amount: "", rationale: "" };

function formatAmount(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "-";
  const amount = Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 0 });
  return value < 0 ? `($${amount})` : `$${amount}`;
}

function isNegative(value: number | null | undefined) {
  return typeof value === "number" && value < 0;
}

export function CompaniesPage() {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [openProfileId, setOpenProfileId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function loadCompanies(showLoading = true) {
    try {
      if (showLoading) setLoading(true);
      setCompanies(await apiFetch<Company[]>("/companies"));
      setError("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Companies failed to load.");
    } finally {
      if (showLoading) setLoading(false);
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
          <div className="table-wrap" tabIndex={0}>
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
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {companies.map((company) => (
                  <Fragment key={company.id}>
                    <tr>
                      <td>{company.name}</td>
                      <td>{company.ticker || "-"}</td>
                      <td>{company.exchange || "Private"}</td>
                      <td>{company.sector || "-"}</td>
                      <td>{company.country || "-"}</td>
                      <td>{company.doc_count ?? 0}</td>
                      <td>{company.sections_complete ?? 0}/4 complete</td>
                      <td className="action-cell">
                        <Link
                          className="button button-primary button-sm"
                          href={`/admin/upload?company_id=${company.id}&company_name=${encodeURIComponent(company.name)}`}
                        >
                          Upload PDF
                        </Link>
                        <button
                          type="button"
                          className="button button-secondary button-sm"
                          onClick={() => setOpenProfileId((value) => (value === company.id ? null : company.id))}
                        >
                          Edit Profile
                        </button>
                      </td>
                    </tr>
                    {openProfileId === company.id ? (
                      <tr className="profile-panel-row">
                        <td colSpan={8} className="profile-panel-cell">
                          <CompanyProfilePanel
                            company={company}
                            onClose={() => setOpenProfileId(null)}
                            onProfileChanged={() => loadCompanies(false)}
                          />
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
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

function CompanyProfilePanel({
  company,
  onClose,
  onProfileChanged,
}: {
  company: Company;
  onClose: () => void;
  onProfileChanged: () => Promise<void>;
}) {
  const router = useRouter();
  const [sector, setSector] = useState(company.sector ?? "");
  const [description, setDescription] = useState(company.description ?? "");
  const [members, setMembers] = useState<ManagementMember[]>([]);
  const [adjustments, setAdjustments] = useState<EbitdaAdjustment[]>([]);
  const [status, setStatus] = useState<ProfileStatus | null>(null);
  const [memberForm, setMemberForm] = useState<MemberForm>(emptyMemberForm);
  const [adjustmentForm, setAdjustmentForm] = useState<AdjustmentForm>(emptyAdjustmentForm);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const loadProfile = useCallback(async () => {
    try {
      setLoading(true);
      const [nextMembers, nextAdjustments, nextStatus] = await Promise.all([
        apiFetch<ManagementMember[]>(`/companies/${company.id}/management-team`),
        apiFetch<EbitdaAdjustment[]>(`/companies/${company.id}/ebitda-adjustments`),
        apiFetch<ProfileStatus>(`/companies/${company.id}/profile-status`),
      ]);
      setMembers(nextMembers);
      setAdjustments(nextAdjustments);
      setStatus(nextStatus);
      setError("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Profile failed to load.");
    } finally {
      setLoading(false);
    }
  }, [company.id, router]);

  useEffect(() => {
    void Promise.resolve().then(loadProfile);
  }, [loadProfile]);

  async function refreshAfterChange(nextMessage: string) {
    setMessage(nextMessage);
    await loadProfile();
    await onProfileChanged();
  }

  function handleError(err: unknown, fallback: string) {
    if (err instanceof ApiError && err.status === 401) {
      router.replace("/login");
      return;
    }
    setError(err instanceof Error ? err.message : fallback);
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    const trimmedDescription = description.trim();
    if (trimmedDescription && trimmedDescription.length < 50) {
      setSaving(false);
      setError("Description must be at least 50 characters.");
      return;
    }

    try {
      const form = new FormData();
      form.append("sector", sector);
      form.append("description", description);
      await postForm<{ sector: string | null; description: string | null }>(`/companies/${company.id}/profile`, form);
      await refreshAfterChange("Business profile saved.");
    } catch (err) {
      handleError(err, "Business profile could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  async function saveMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!memberForm.name.trim()) {
      setError("Management team member name is required.");
      return;
    }
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const form = new FormData();
      form.append("name", memberForm.name.trim());
      form.append("title", memberForm.title.trim());
      form.append("bio", memberForm.bio.trim());
      const path = memberForm.id
        ? `/companies/${company.id}/management-team/${memberForm.id}`
        : `/companies/${company.id}/management-team`;
      await apiFetch<ManagementMember>(path, { method: memberForm.id ? "PUT" : "POST", body: form });
      setMemberForm(emptyMemberForm);
      await refreshAfterChange(memberForm.id ? "Team member updated." : "Team member added.");
    } catch (err) {
      handleError(err, "Management team could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  async function removeMember(member: ManagementMember) {
    if (!window.confirm(`Remove ${member.name} from the management team?`)) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await apiFetch<void>(`/companies/${company.id}/management-team/${member.id}`, { method: "DELETE" });
      if (memberForm.id === member.id) setMemberForm(emptyMemberForm);
      await refreshAfterChange("Team member removed.");
    } catch (err) {
      handleError(err, "Team member could not be removed.");
    } finally {
      setSaving(false);
    }
  }

  async function saveAdjustment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!adjustmentForm.label.trim() || adjustmentForm.amount === "") {
      setError("Adjustment label and amount are required.");
      return;
    }
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const form = new FormData();
      form.append("label", adjustmentForm.label.trim());
      form.append("amount", adjustmentForm.amount);
      form.append("rationale", adjustmentForm.rationale.trim());
      const path = adjustmentForm.id
        ? `/companies/${company.id}/ebitda-adjustments/${adjustmentForm.id}`
        : `/companies/${company.id}/ebitda-adjustments`;
      await apiFetch<EbitdaAdjustment>(path, { method: adjustmentForm.id ? "PUT" : "POST", body: form });
      setAdjustmentForm(emptyAdjustmentForm);
      await refreshAfterChange(adjustmentForm.id ? "Adjustment updated." : "Adjustment added.");
    } catch (err) {
      handleError(err, "Adjustment could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  async function removeAdjustment(adjustment: EbitdaAdjustment) {
    if (!window.confirm(`Remove adjustment "${adjustment.label}"?`)) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await apiFetch<void>(`/companies/${company.id}/ebitda-adjustments/${adjustment.id}`, { method: "DELETE" });
      if (adjustmentForm.id === adjustment.id) setAdjustmentForm(emptyAdjustmentForm);
      await refreshAfterChange("Adjustment removed.");
    } catch (err) {
      handleError(err, "Adjustment could not be removed.");
    } finally {
      setSaving(false);
    }
  }

  const industryOptions = company.sector && !INDUSTRY_OPTIONS.includes(company.sector)
    ? [company.sector, ...INDUSTRY_OPTIONS]
    : INDUSTRY_OPTIONS;
  const descriptionLength = description.length;
  const adjustedEbitda = (status?.reported_ebitda ?? 0) + adjustments.reduce((total, item) => total + (item.amount || 0), 0);

  return (
    <div className="profile-panel">
      <header className="profile-panel-header">
        <div>
          <h2>Business Profile</h2>
          <p className="muted">{status ? `${status.sections_complete}/${status.total} complete` : "Loading profile..."}</p>
        </div>
        <button type="button" className="button button-secondary button-sm" onClick={onClose}>
          Close
        </button>
      </header>

      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}
      {message ? <div className="alert alert-success">{message}</div> : null}

      {loading ? <p className="muted">Loading...</p> : null}

      <div className="profile-grid">
        <section className="profile-section">
          <div className="profile-section-header">
            <h3>Industry & Description</h3>
          </div>
          <form className="admin-form" onSubmit={saveProfile}>
            <label htmlFor={`profile-sector-${company.id}`}>
              Industry
              <select id={`profile-sector-${company.id}`} value={sector} onChange={(event) => setSector(event.target.value)}>
                <option value="">Select industry...</option>
                {industryOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label htmlFor={`profile-description-${company.id}`}>
              Business Description
              <textarea
                id={`profile-description-${company.id}`}
                rows={4}
                minLength={50}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Describe products or services, customer base, operating geography, and competitive advantages..."
              />
            </label>
            <p className="field-note">{descriptionLength >= 50 ? `${descriptionLength} characters` : `${descriptionLength} / 50 minimum`}</p>
            <button className="button button-primary button-sm" disabled={saving}>
              {saving ? "Saving..." : "Save Profile"}
            </button>
          </form>
        </section>

        <section className="profile-section">
          <div className="profile-section-header">
            <h3>Management Team</h3>
          </div>
          <form className="admin-form profile-mini-form" onSubmit={saveMember}>
            <label htmlFor={`member-name-${company.id}`}>
              Name
              <input
                id={`member-name-${company.id}`}
                value={memberForm.name}
                onChange={(event) => setMemberForm((value) => ({ ...value, name: event.target.value }))}
                placeholder="Jane Smith"
              />
            </label>
            <label htmlFor={`member-title-${company.id}`}>
              Title
              <input
                id={`member-title-${company.id}`}
                value={memberForm.title}
                onChange={(event) => setMemberForm((value) => ({ ...value, title: event.target.value }))}
                placeholder="Managing Director"
              />
            </label>
            <label htmlFor={`member-bio-${company.id}`} className="span-all">
              Bio
              <textarea
                id={`member-bio-${company.id}`}
                rows={2}
                value={memberForm.bio}
                onChange={(event) => setMemberForm((value) => ({ ...value, bio: event.target.value }))}
                placeholder="Brief professional background..."
              />
            </label>
            <div className="profile-actions span-all">
              <button className="button button-primary button-sm" disabled={saving}>
                {memberForm.id ? "Save Member" : "Add Member"}
              </button>
              {memberForm.id ? (
                <button type="button" className="button button-secondary button-sm" onClick={() => setMemberForm(emptyMemberForm)}>
                  Cancel
                </button>
              ) : null}
            </div>
          </form>
          <ProfileList
            emptyText="No team members added yet."
            items={members.map((member) => ({
              id: member.id,
              title: member.title ? `${member.name} - ${member.title}` : member.name,
              detail: member.bio ?? "",
              onEdit: () => setMemberForm({
                id: member.id,
                name: member.name,
                title: member.title ?? "",
                bio: member.bio ?? "",
              }),
              onRemove: () => removeMember(member),
            }))}
          />
        </section>

        <section className="profile-section span-all">
          <div className="profile-section-header">
            <h3>EBITDA Add-Backs</h3>
          </div>
          <form className="admin-form profile-mini-form" onSubmit={saveAdjustment}>
            <label htmlFor={`adjustment-label-${company.id}`}>
              Label
              <input
                id={`adjustment-label-${company.id}`}
                value={adjustmentForm.label}
                onChange={(event) => setAdjustmentForm((value) => ({ ...value, label: event.target.value }))}
                placeholder="Owner salary above market rate"
              />
            </label>
            <label htmlFor={`adjustment-amount-${company.id}`}>
              Amount ($)
              <input
                id={`adjustment-amount-${company.id}`}
                type="number"
                step="any"
                value={adjustmentForm.amount}
                onChange={(event) => setAdjustmentForm((value) => ({ ...value, amount: event.target.value }))}
                placeholder="80000 or -15000"
              />
            </label>
            <label htmlFor={`adjustment-rationale-${company.id}`} className="span-all">
              Rationale
              <input
                id={`adjustment-rationale-${company.id}`}
                value={adjustmentForm.rationale}
                onChange={(event) => setAdjustmentForm((value) => ({ ...value, rationale: event.target.value }))}
                placeholder="Why this amount is added back or subtracted"
              />
            </label>
            <div className="profile-actions span-all">
              <button className="button button-primary button-sm" disabled={saving}>
                {adjustmentForm.id ? "Save Adjustment" : "Add Adjustment"}
              </button>
              {adjustmentForm.id ? (
                <button type="button" className="button button-secondary button-sm" onClick={() => setAdjustmentForm(emptyAdjustmentForm)}>
                  Cancel
                </button>
              ) : null}
            </div>
          </form>

          <div className="profile-split">
            <ProfileList
              emptyText="No adjustments added yet."
              items={adjustments.map((adjustment) => ({
                id: adjustment.id,
                title: adjustment.label,
                amount: adjustment.amount,
                detail: adjustment.rationale ?? "",
                onEdit: () => setAdjustmentForm({
                  id: adjustment.id,
                  label: adjustment.label,
                  amount: String(adjustment.amount),
                  rationale: adjustment.rationale ?? "",
                }),
                onRemove: () => removeAdjustment(adjustment),
              }))}
            />
            <div className="ebitda-bridge">
              <h4>EBITDA Bridge</h4>
              {status?.has_financials ? (
                <table>
                  <tbody>
                    <tr>
                      <td>Reported EBITDA</td>
                      <td className={isNegative(status.reported_ebitda) ? "amount-negative" : ""}>{formatAmount(status.reported_ebitda)}</td>
                    </tr>
                    {adjustments.map((adjustment) => (
                      <tr key={adjustment.id}>
                        <td>+ {adjustment.label}</td>
                        <td className={isNegative(adjustment.amount) ? "amount-negative" : ""}>{formatAmount(adjustment.amount)}</td>
                      </tr>
                    ))}
                    <tr className="bridge-total">
                      <td>Normalised EBITDA</td>
                      <td className={isNegative(adjustedEbitda) ? "amount-negative" : ""}>{formatAmount(adjustedEbitda)}</td>
                    </tr>
                  </tbody>
                </table>
              ) : (
                <p className="muted">Upload financials first to see your Normalised EBITDA.</p>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function ProfileList({
  emptyText,
  items,
}: {
  emptyText: string;
  items: Array<{
    id: number;
    title: string;
    amount?: number;
    detail: string;
    onEdit: () => void;
    onRemove: () => void;
  }>;
}) {
  if (!items.length) return <p className="muted profile-empty">{emptyText}</p>;

  return (
    <div className="inline-list">
      {items.map((item) => (
        <div className="inline-list-item" key={item.id}>
          <div>
            <div className="inline-list-title">
              <strong>{item.title}</strong>
              {typeof item.amount === "number" ? (
                <span className={isNegative(item.amount) ? "amount-negative" : ""}>{formatAmount(item.amount)}</span>
              ) : null}
            </div>
            {item.detail ? <p className="muted">{item.detail}</p> : null}
          </div>
          <div className="item-actions">
            <button type="button" className="button button-secondary button-sm" onClick={item.onEdit}>
              Edit
            </button>
            <button type="button" className="button button-danger button-sm" onClick={item.onRemove}>
              Remove
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
