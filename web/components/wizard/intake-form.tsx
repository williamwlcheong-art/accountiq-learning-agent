"use client";

import { FormEvent, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api-client";
import type { WizardReportType } from "@/components/wizard/report-type-picker";
import type { FcffAssumptionReadiness, FcffAssumptionsInput } from "@/types/domain";

type EbitdaAdjustment = {
  id: number;
  label: string;
  amount: number;
  rationale: string | null;
};

type NormalisationRow = {
  id: string;
  label: string;
  amount: string;
  rationale: string;
};

type ProfileStatus = {
  sections_complete: number;
  total: number;
};

type IntakeFormProps = {
  reportType: WizardReportType;
  companyId: number;
  onBack: () => void;
  onSubmit: (answers: Record<string, unknown>) => void;
  loading: boolean;
  submitLabel?: string;
};

const simpleFields: Record<Exclude<WizardReportType, "valuation_advisory">, Array<{
  name: string;
  label: string;
  kind: "text" | "number" | "textarea" | "select";
  options?: string[];
}>> = {
  bank_credit_paper: [
    { name: "facility_type", label: "Facility type", kind: "text" },
    { name: "amount_requested", label: "Amount requested ($)", kind: "number" },
    { name: "proposed_term_years", label: "Proposed term (years)", kind: "number" },
    { name: "repayment_structure", label: "Repayment structure", kind: "text" },
    { name: "security_collateral", label: "Security / collateral offered", kind: "text" },
    { name: "loan_purpose", label: "Loan purpose", kind: "textarea" },
    { name: "existing_debt_facilities", label: "Existing debt facilities", kind: "text" },
  ],
  financial_forecast: [
    { name: "forecast_horizon", label: "Forecast horizon", kind: "select", options: ["1 year", "3 years", "5 years"] },
    { name: "revenue_growth_rate", label: "Revenue growth rate per year", kind: "number" },
    { name: "key_business_drivers", label: "Key business drivers", kind: "textarea" },
    { name: "planned_capex", label: "Planned capex ($)", kind: "number" },
    { name: "headcount_changes", label: "Headcount changes", kind: "text" },
    { name: "one_off_events", label: "One-off events", kind: "text" },
  ],
  capital_raising: [
    { name: "amount", label: "Amount to raise ($)", kind: "number" },
    { name: "instrument_type", label: "Instrument type", kind: "select", options: ["Equity", "Convertible note", "Debt", "Hybrid"] },
    { name: "use_of_proceeds", label: "Use of proceeds", kind: "textarea" },
    { name: "business_stage", label: "Business stage", kind: "select", options: ["Pre-revenue", "Early revenue", "Growth", "Mature"] },
    { name: "target_investor_profile", label: "Target investor profile", kind: "text" },
    { name: "key_milestones", label: "Key milestones", kind: "textarea" },
  ],
  information_memorandum: [
    { name: "sale_rationale", label: "Sale rationale", kind: "textarea" },
    { name: "key_business_highlights", label: "Key business highlights", kind: "textarea" },
    { name: "growth_opportunities", label: "Growth opportunities", kind: "textarea" },
    { name: "target_buyer_type", label: "Target buyer type", kind: "text" },
    { name: "transaction_structure", label: "Transaction structure", kind: "text" },
    { name: "any_exclusions", label: "Assets or liabilities to exclude", kind: "text" },
  ],
};

const riskQuestions = [
  ["rq_revenue_quality", "Revenue quality", ["1 - mostly transactional", "2", "3", "4", "5 - mostly contracted or recurring"]],
  ["rq_owner_dependency", "Owner / key-person dependency", ["1 - fully owner-dependent", "2", "3", "4", "5 - fully managed"]],
  ["rq_ebitda_growth", "EBITDA growth trend", ["1 - declining", "2", "3", "4", "5 - strong growth"]],
  ["rq_customer_concentration", "Customer concentration", ["1 - high concentration", "2", "3", "4", "5 - diversified"]],
  ["rq_gross_margin", "Gross profit margin", ["1 - below 20%", "2", "3", "4", "5 - above 50%"]],
  ["rq_competitive_barriers", "Barriers to entry", ["1 - easy to replicate", "2", "3", "4", "5 - very hard"]],
  ["rq_growth_outlook", "Growth outlook", ["1 - declining", "2", "3", "4", "5 - strong tailwinds"]],
  ["rq_management_depth", "Management depth", ["1 - owner does everything", "2", "3", "4", "5 - deep bench"]],
] as const;

function percentageToRatio(value: unknown): number {
  return Number((Number(value) / 100).toFixed(10));
}

function toAnswerValue(value: FormDataEntryValue): string | number {
  const text = String(value).trim();
  if (text === "") return "";
  const numberValue = Number(text);
  return Number.isFinite(numberValue) && /^-?\d+(\.\d+)?$/.test(text) ? numberValue : text;
}

function ratingDescription(option: string) {
  const [, description] = option.split(" - ");
  return description ?? "";
}

function renderField(field: (typeof simpleFields)["bank_credit_paper"][number]) {
  const id = `intake-${field.name}`;
  if (field.kind === "textarea") {
    return (
      <label key={field.name} htmlFor={id}>
        {field.label}
        <textarea id={id} name={field.name} rows={3} />
      </label>
    );
  }
  if (field.kind === "select") {
    return (
      <label key={field.name} htmlFor={id}>
        {field.label}
        <select id={id} name={field.name}>
          {(field.options ?? []).map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <label key={field.name} htmlFor={id}>
      {field.label}
      <input id={id} name={field.name} type={field.kind} step={field.kind === "number" ? "0.01" : undefined} />
    </label>
  );
}

export function IntakeForm({
  reportType,
  companyId,
  onBack,
  onSubmit,
  loading,
  submitLabel = "Review and continue",
}: IntakeFormProps) {
  const [normalisations, setNormalisations] = useState<NormalisationRow[]>([]);
  const [profileStatus, setProfileStatus] = useState<ProfileStatus | null>(null);
  const [fcffReadiness, setFcffReadiness] = useState<FcffAssumptionReadiness | null>(null);
  const [assumptionOverrides, setAssumptionOverrides] = useState<Record<string, boolean>>({});
  const [assumptionRatios, setAssumptionRatios] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    apiFetch<ProfileStatus>(`/wizard/company/${companyId}/profile-status`)
      .then((status) => {
        if (!cancelled) setProfileStatus(status);
      })
      .catch(() => {
        if (!cancelled) setProfileStatus(null);
      });

    return () => {
      cancelled = true;
    };
  }, [companyId]);

  useEffect(() => {
    let cancelled = false;
    if (reportType !== "valuation_advisory") return;

    apiFetch<EbitdaAdjustment[]>(`/wizard/company/${companyId}/ebitda-adjustments`)
      .then((rows) => {
        if (cancelled) return;
        setNormalisations(
          rows.map((row) => ({
            id: String(row.id),
            label: row.label ?? "",
            amount: String(row.amount ?? ""),
            rationale: row.rationale ?? "",
          })),
        );
      })
      .catch(() => {
        if (!cancelled) setNormalisations([]);
      });

    return () => {
      cancelled = true;
    };
  }, [companyId, reportType]);

  useEffect(() => {
    let cancelled = false;
    if (reportType !== "valuation_advisory") return;

    apiFetch<FcffAssumptionReadiness>(`/wizard/company/${companyId}/fcff-assumptions`)
      .then((readiness) => {
        if (!cancelled) setFcffReadiness(readiness);
      })
      .catch(() => {
        if (!cancelled) {
          setFcffReadiness({
            state: "needs_adviser_assistance",
            message: "We need an adviser to confirm the investment assumptions from your statements.",
            depreciation: { rate: null, status: "missing" },
            operating_nwc: { rate: null, status: "missing" },
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [companyId, reportType]);

  function addNormalisation() {
    setNormalisations((rows) => [
      ...rows,
      { id: `new-${Date.now()}`, label: "", amount: "", rationale: "" },
    ]);
  }

  function updateNormalisation(id: string, key: keyof NormalisationRow, value: string) {
    setNormalisations((rows) => rows.map((row) => (row.id === id ? { ...row, [key]: value } : row)));
  }

  function removeNormalisation(id: string) {
    setNormalisations((rows) => rows.filter((row) => row.id !== id));
  }

  function setCalculatedAssumption(key: string, rate: number) {
    setAssumptionOverrides((current) => ({ ...current, [key]: false }));
    setAssumptionRatios((current) => ({ ...current, [key]: String(rate * 100) }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const formData = new FormData(event.currentTarget);
    const answers: Record<string, unknown> = {};
    for (const [key, value] of formData.entries()) {
      const answer = toAnswerValue(value);
      if (answer !== "") answers[key] = answer;
    }

    if (reportType === "valuation_advisory") {
      const cagr = Number(answers.revenue_growth_cagr);
      const terminalGrowth = Number(answers.terminal_growth_rate);
      const missingRisk = riskQuestions.find(([name]) => !answers[name]);
      if (!answers.forecast_horizon) {
        setError("Please select a forecast horizon.");
        return;
      }
      if (!Number.isFinite(cagr) || cagr < 0 || cagr > 100) {
        setError("Revenue growth rate must be between 0 and 100.");
        return;
      }
      if (!Number.isFinite(terminalGrowth) || terminalGrowth < 0 || terminalGrowth > 20) {
        setError("Terminal growth rate must be between 0 and 20.");
        return;
      }
      if (missingRisk) {
        setError(`Please select a ${missingRisk[1].toLowerCase()} rating.`);
        return;
      }
      if (fcffReadiness?.state === "needs_adviser_assistance") {
        setError("An adviser needs to confirm the investment and working capital assumptions before you can continue.");
        return;
      }
      for (const [field, zeroRationaleField] of [
        ["depreciation_ratio", "depreciation_zero_rationale"],
        ["operating_nwc_ratio", "operating_nwc_zero_rationale"],
        ["capex_ratio", "capex_zero_rationale"],
      ]) {
        const value = Number(answers[field]);
        if (!Number.isFinite(value) || value < 0 || value > 100) {
          setError("Please enter each investment and working capital ratio as a percentage between 0 and 100.");
          return;
        }
        if (value === 0 && !answers[zeroRationaleField]) {
          setError("Please explain why an investment or working capital ratio is zero.");
          return;
        }
      }
      for (const field of ["depreciation", "operating_nwc"]) {
        if (!answers[`${field}_confirmation`]) {
          setError("Please confirm each figure derived from your statements or provide an updated figure.");
          return;
        }
        if (answers[`${field}_confirmation`] === "override" && !answers[`${field}_override_rationale`]) {
          setError("Please explain why you are using an updated figure.");
          return;
        }
      }
      const forecastHorizon = Number(answers.forecast_horizon);
      const fcffAssumptions: FcffAssumptionsInput = {
        forecast: {
          horizon_years: forecastHorizon,
          revenue_growth_rate: percentageToRatio(cagr),
          terminal_growth_rate: percentageToRatio(terminalGrowth),
          confirmed: true,
        },
        depreciation: {
          rate: percentageToRatio(answers.depreciation_ratio),
          confirmed: true,
          rationale: answers.depreciation_confirmation === "override"
            ? String(answers.depreciation_override_rationale ?? "")
            : String(answers.depreciation_zero_rationale ?? ""),
          confirmation_method: answers.depreciation_confirmation === "override" ? "override" : "calculated",
          confirmation_source: answers.depreciation_confirmation === "override" ? "customer" : "financial_statements",
          source_period: answers.depreciation_confirmation === "override" ? undefined : fcffReadiness?.depreciation.source_period ?? undefined,
        },
        capex: {
          rate: percentageToRatio(answers.capex_ratio),
          confirmed: true,
          rationale: String(answers.capex_zero_rationale ?? ""),
          confirmation_method: "manual",
          confirmation_source: "customer",
        },
        operating_nwc: {
          rate: percentageToRatio(answers.operating_nwc_ratio),
          confirmed: true,
          rationale: answers.operating_nwc_confirmation === "override"
            ? String(answers.operating_nwc_override_rationale ?? "")
            : String(answers.operating_nwc_zero_rationale ?? ""),
          confirmation_method: answers.operating_nwc_confirmation === "override" ? "override" : "calculated",
          confirmation_source: answers.operating_nwc_confirmation === "override" ? "customer" : "financial_statements",
          source_period: answers.operating_nwc_confirmation === "override" ? undefined : fcffReadiness?.operating_nwc.source_period ?? undefined,
        },
      };
      answers.fcff_assumptions = fcffAssumptions;
      delete answers.forecast_horizon;
      delete answers.revenue_growth_cagr;
      delete answers.terminal_growth_rate;
      for (const field of [
        "depreciation_ratio", "depreciation_confirmation", "depreciation_override_rationale", "depreciation_zero_rationale",
        "capex_ratio", "capex_zero_rationale",
        "operating_nwc_ratio", "operating_nwc_confirmation", "operating_nwc_override_rationale", "operating_nwc_zero_rationale",
      ]) delete answers[field];
      answers.normalisations = normalisations
        .filter((row) => row.label.trim())
        .map((row) => ({
          label: row.label.trim(),
          amount: Number(row.amount) || 0,
          rationale: row.rationale.trim(),
        }));
    }

    onSubmit(answers);
  }

  return (
    <form className="wizard-form" onSubmit={submit}>
      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}
      {profileStatus && profileStatus.sections_complete < profileStatus.total ? (
        <div className="alert alert-warning">
          Some profile data is incomplete - your report may have gaps. You can still generate the report.
        </div>
      ) : null}

      {reportType === "valuation_advisory" ? (
        <>
          <fieldset>
            <legend>Narrative risk assessment</legend>
            <label htmlFor="owner-key-person-dependency">
              Owner / key-person dependency
              <textarea id="owner-key-person-dependency" name="owner_key_person_dependency" rows={3} />
            </label>
            <label htmlFor="customer-concentration">
              Customer concentration
              <textarea id="customer-concentration" name="customer_concentration" rows={3} />
            </label>
            <label htmlFor="competitive-position">
              Competitive position
              <textarea id="competitive-position" name="competitive_position" rows={3} />
            </label>
            <label htmlFor="growth-strategy-pipeline">
              Growth strategy and pipeline
              <textarea id="growth-strategy-pipeline" name="growth_strategy_pipeline" rows={3} />
            </label>
          </fieldset>

          <fieldset>
            <legend>Normalisation schedule</legend>
            {normalisations.map((row) => (
              <div className="normalisation-row" key={row.id}>
                <label>
                  Label
                  <input value={row.label} onChange={(event) => updateNormalisation(row.id, "label", event.target.value)} />
                </label>
                <label>
                  Amount ($)
                  <input
                    type="number"
                    value={row.amount}
                    onChange={(event) => updateNormalisation(row.id, "amount", event.target.value)}
                  />
                </label>
                <label>
                  Rationale
                  <input
                    value={row.rationale}
                    onChange={(event) => updateNormalisation(row.id, "rationale", event.target.value)}
                  />
                </label>
                <button type="button" className="button button-secondary" onClick={() => removeNormalisation(row.id)}>
                  Remove
                </button>
              </div>
            ))}
            <button type="button" className="button button-secondary" onClick={addNormalisation}>
              Add normalisation item
            </button>
          </fieldset>

          <fieldset>
            <legend>Financial assumptions</legend>
            <label htmlFor="forecast-horizon">
              Forecast horizon
              <select id="forecast-horizon" name="forecast_horizon" defaultValue="" required>
                <option value="" disabled>
                  Select horizon
                </option>
                <option value="3">3 years</option>
                <option value="5">5 years</option>
              </select>
            </label>
            <label htmlFor="revenue-growth-cagr">
              Revenue growth rate (CAGR %)
              <input id="revenue-growth-cagr" name="revenue_growth_cagr" type="number" min="0" max="100" step="0.1" required />
            </label>
            <label htmlFor="terminal-growth-rate">
              Terminal growth rate (%)
              <input id="terminal-growth-rate" name="terminal_growth_rate" type="number" min="0" max="20" step="0.1" required />
            </label>
          </fieldset>

          <fieldset>
            <legend>Investment and working capital</legend>
            <p className="muted">
              These assumptions help estimate cash available to investors. We have kept the accounting detail out of the main flow.
            </p>
            {fcffReadiness?.state === "needs_adviser_assistance" ? (
              <div className="alert alert-warning" role="status">
                <p>{fcffReadiness.message}</p>
                <p>An adviser will help confirm these assumptions before any payment step.</p>
              </div>
            ) : null}
            <details>
              <summary>How we derived these figures</summary>
              <p>
                Depreciation and amortisation, and operating working capital, are shown as percentages of revenue only when the
                same reporting period supports the calculation.
              </p>
            </details>
            {([
              ["depreciation", "Depreciation and amortisation", fcffReadiness?.depreciation],
              ["operating_nwc", "Operating working capital", fcffReadiness?.operating_nwc],
            ] as const).map(([key, label, derived]) => {
              const ratioName = `${key}_ratio`;
              const isAvailable = derived?.status === "available" && derived.rate != null;
              return (
                <section className="panel" key={key}>
                  <h3>{label}</h3>
                  {isAvailable ? (
                    <p>
                      We calculated <strong>{((derived.rate ?? 0) * 100).toFixed(1)}% of revenue</strong>{derived.source_period ? ` from ${derived.source_period}` : ""}.
                    </p>
                  ) : (
                    <p className="muted">We could not safely calculate this figure from the statements provided.</p>
                  )}
                  <fieldset>
                    <legend>Use this figure?</legend>
                    <label>
                      <input
                        type="radio"
                        name={`${key}_confirmation`}
                        value="confirm"
                        required
                        disabled={!isAvailable}
                        onChange={() => setCalculatedAssumption(key, derived?.rate ?? 0)}
                      />
                      Yes, use the calculated figure
                    </label>
                    <label>
                      <input
                        type="radio"
                        name={`${key}_confirmation`}
                        value="override"
                        required
                        onChange={() => {
                          setAssumptionOverrides((current) => ({ ...current, [key]: true }));
                          setAssumptionRatios((current) => ({
                            ...current,
                            [key]: current[key] ?? (isAvailable ? String((derived.rate ?? 0) * 100) : ""),
                          }));
                        }}
                      />
                      Use an updated figure
                    </label>
                  </fieldset>
                  <label htmlFor={`${key}-ratio`}>
                    {label} (% of revenue)
                    <input
                      id={`${key}-ratio`}
                      name={ratioName}
                      type="number"
                      min="0"
                      max="100"
                      step="0.1"
                      value={assumptionRatios[key] ?? (isAvailable ? String((derived.rate ?? 0) * 100) : "")}
                      onChange={(event) => setAssumptionRatios((current) => ({ ...current, [key]: event.target.value }))}
                      readOnly={isAvailable && !assumptionOverrides[key]}
                      aria-readonly={isAvailable && !assumptionOverrides[key]}
                      required
                    />
                  </label>
                  <label htmlFor={`${key}-override-rationale`}>
                    Why are you using this figure?
                    <textarea id={`${key}-override-rationale`} name={`${key}_override_rationale`} rows={2} />
                  </label>
                  <label htmlFor={`${key}-zero-rationale`}>
                    If this is zero, why?
                    <textarea id={`${key}-zero-rationale`} name={`${key}_zero_rationale`} rows={2} />
                  </label>
                </section>
              );
            })}
            <section className="panel">
              <h3>Capital investment (capex)</h3>
              <p>Enter the annual capital investment you expect as a percentage of revenue. We cannot safely derive this from your statements.</p>
              <label htmlFor="capex-ratio">
                Capital investment (% of revenue)
                <input id="capex-ratio" name="capex_ratio" type="number" min="0" max="100" step="0.1" required />
              </label>
              <label htmlFor="capex-zero-rationale">
                If this is zero, why?
                <textarea id="capex-zero-rationale" name="capex_zero_rationale" rows={2} />
              </label>
            </section>
          </fieldset>

          <fieldset>
            <legend>Business risk assessment</legend>
            {riskQuestions.map(([name, label, options]) => (
              <div className="rating-question" key={name}>
                <span className="field-label" id={`${name}-label`}>
                  {label} rating
                </span>
                <div className="rating-options" role="radiogroup" aria-labelledby={`${name}-label`}>
                  {options.map((option, index) => {
                    const value = String(index + 1);
                    const id = `${name}-${value}`;
                    const description = ratingDescription(option);
                    return (
                      <label className="rating-option" key={option} htmlFor={id}>
                        <input id={id} type="radio" name={name} value={value} required />
                        <span className="rating-score">{value}</span>
                        {description ? <span className="rating-description">{description}</span> : null}
                      </label>
                    );
                  })}
                </div>
              </div>
            ))}
          </fieldset>
        </>
      ) : (
        <fieldset>
          <legend>Report details</legend>
          {simpleFields[reportType].map(renderField)}
        </fieldset>
      )}

      <div className="wizard-actions">
        <button type="button" className="button button-secondary" onClick={onBack}>
          Back
        </button>
        <button type="submit" className="button button-primary" disabled={loading}>
          {loading ? "Preparing..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
