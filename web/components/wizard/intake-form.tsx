"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { apiFetch } from "@/lib/api-client";
import type { WizardReportType } from "@/components/wizard/report-type-picker";

type EbitdaAdjustment = {
  id: number;
  label: string;
  amount: number;
  rationale: string | null;
};

export type NormalisationRow = {
  id: string;
  label: string;
  amount: string;
  rationale: string;
};

type ProfileStatus = {
  sections_complete: number;
  total: number;
};

type ValuationStage = "questions" | "earnings-review";
type CreditStage = "research-hints" | "facility-questions";

export type IntakeDraft = {
  valuationStage?: ValuationStage;
  valuationAnswers?: Record<string, unknown>;
  valuationReviewAnswers?: Record<string, unknown>;
  normalisations?: NormalisationRow[];
  creditStage?: CreditStage;
  creditAnswers?: Record<string, unknown>;
};

type IntakeFormProps = {
  reportType: WizardReportType;
  companyId: number;
  demoMode?: boolean;
  initialDraft?: IntakeDraft;
  onDraftChange?: (draft: IntakeDraft) => void;
  onBack: () => void;
  onSubmit: (answers: Record<string, unknown>) => void;
  loading: boolean;
};

const valuationAnswerLabels: Record<string, Record<string, string>> = {
  valuation_purpose: {
    understand_value: "Understand what the business may be worth",
    sale_or_transaction: "Prepare for a sale or transaction",
    shareholder_or_employee_scheme: "Shareholder or employee share scheme",
    succession_planning: "Succession or estate planning",
    finance_or_investment: "Finance or investment discussions",
    other: "Another reason",
  },
  owner_dependency: {
    independent: "Yes - a management team runs it",
    shared: "Mostly - responsibility is shared",
    important: "An owner or key person is important day to day",
    critical: "The business depends heavily on an owner or key person",
    unknown: "Not sure",
  },
  customer_concentration: {
    under_10: "Less than 10%",
    "10_to_25": "10% to 25%",
    over_25: "More than 25%",
    consumer_or_diversified: "Consumer or highly diversified revenue",
    unknown: "Not sure",
  },
  revenue_quality: {
    mostly_contract: "Mostly contracted or recurring",
    mixed: "A mix of recurring and one-off work",
    mostly_one_off: "Mostly one-off or transactional",
    unknown: "Not sure",
  },
  revenue_outlook: {
    lower: "Likely lower than today",
    steady: "Broadly steady",
    modest_growth: "Modest growth",
    strong_growth: "Strong growth backed by pipeline or contracts",
    not_sure: "Not sure - use my financial history",
  },
};

const valuationAnswerSummary = [
  ["valuation_purpose", "Purpose"],
  ["owner_dependency", "Owner or key-person dependency"],
  ["customer_concentration", "Largest customer"],
  ["revenue_quality", "Revenue predictability"],
  ["revenue_outlook", "Revenue outlook"],
] as const;

const valuationRequiredAnswers = [
  { name: "valuation_purpose", label: "Purpose", missingLabel: "what the valuation is for" },
  {
    name: "owner_dependency",
    label: "Owner or key-person dependency",
    missingLabel: "how dependent the business is on an owner or key person",
  },
  { name: "customer_concentration", label: "Largest customer", missingLabel: "customer concentration" },
  { name: "revenue_quality", label: "Revenue predictability", missingLabel: "revenue quality" },
  { name: "revenue_outlook", label: "Revenue outlook", missingLabel: "the next 12-24 month outlook" },
] as const;

const valuationOptionalSummary = [
  ["company_website", "Business website"],
  ["company_location", "Main location"],
  ["public_source_urls", "Helpful public links"],
  ["private_context", "Private valuation context"],
] as const;

const valuationOptionalMoneyOverrides = [
  ["replacement_manager_cost", "Replacement manager cost"],
  ["debt_override", "Interest-bearing debt at valuation date"],
  ["surplus_assets", "Surplus or non-operating assets"],
] as const;

const creditSecurityLabels: Record<string, string> = {
  general_security: "General security over the business",
  fleet: "Fleet / vehicles / equipment",
  property: "Property security",
  fleet_and_property: "Fleet and property security",
  general_security_and_guarantee: "General security plus guarantee",
  unsecured: "No specific security identified",
  other: "Other security package",
};

const creditRepaymentProfileLabels: Record<string, string> = {
  principal_and_interest: "Principal and interest",
  interest_only: "Interest only",
  interest_only_then_amortising: "Interest only, then amortising",
};

const creditAnswerSummary = [
  ["company_website", "Business website"],
  ["company_location", "Main location"],
  ["public_source_urls", "Helpful public links"],
  ["borrower_structure", "Borrower / ownership structure"],
] as const;

const creditRequiredAnswers = [
  { name: "loan_purpose", label: "Loan purpose", missingLabel: "what the debt is for" },
  { name: "amount_requested", label: "Facility amount", missingLabel: "the facility amount requested" },
  { name: "proposed_term_years", label: "Term of debt", missingLabel: "the term of debt" },
  {
    name: "conservative_funding_cost_pct",
    label: "Conservative funding cost",
    missingLabel: "the conservative funding cost",
  },
  { name: "lvr_percent", label: "LVR / advance rate", missingLabel: "the LVR or advance-rate assumption" },
  { name: "security_package", label: "Security", missingLabel: "what security is available" },
  { name: "repayment_profile", label: "Repayment profile", missingLabel: "the repayment profile" },
] as const;

const creditCovenantPackageLabels: Record<string, string> = {
  light_touch: "Light touch",
  balanced: "Balanced",
  more_control: "More protective",
};

const creditCovenantPackageDescriptions: Record<string, string> = {
  light_touch: "Use the core controls only where the credit risk is straightforward.",
  balanced: "Use the normal SME lender package for serviceability, leverage, reporting and collateral monitoring.",
  more_control: "Add extra controls where risk needs tighter monitoring or more mitigation.",
};

const creditCovenantPackageDefaults: Record<string, string[]> = {
  light_touch: ["min_dscr", "max_senior_leverage", "information_reporting"],
  balanced: [
    "min_dscr",
    "min_interest_cover",
    "max_senior_leverage",
    "distribution_lockup",
    "information_reporting",
    "collateral_reporting",
  ],
  more_control: [
    "min_dscr",
    "min_interest_cover",
    "max_senior_leverage",
    "liquidity_minimum",
    "no_additional_debt",
    "distribution_lockup",
    "capex_controls",
    "information_reporting",
    "collateral_reporting",
    "borrowing_base_reporting",
  ],
};

const creditCovenantOptions = [
  {
    value: "min_dscr",
    label: "Minimum DSCR",
    help: "Requires cash earnings to cover interest and scheduled principal.",
  },
  {
    value: "min_interest_cover",
    label: "Minimum interest cover",
    help: "Protects against interest-rate pressure.",
  },
  {
    value: "max_senior_leverage",
    label: "Maximum senior leverage",
    help: "Limits debt relative to EBITDA.",
  },
  {
    value: "liquidity_minimum",
    label: "Minimum liquidity",
    help: "Adds a cash or undrawn-headroom early warning test.",
  },
  {
    value: "no_additional_debt",
    label: "No additional debt",
    help: "Restricts new borrowings without lender consent.",
  },
  {
    value: "distribution_lockup",
    label: "Distribution lock-up",
    help: "Stops discretionary distributions when coverage becomes tight.",
  },
  {
    value: "capex_controls",
    label: "Capex / asset-disposal controls",
    help: "Controls unbudgeted capex or asset sales.",
  },
  {
    value: "information_reporting",
    label: "Information reporting",
    help: "Requires management accounts, annual accounts and compliance certificates.",
  },
  {
    value: "collateral_reporting",
    label: "Collateral reporting",
    help: "Requires AR/AP/stock aging, asset values and insurance evidence where relevant.",
  },
  {
    value: "borrowing_base_reporting",
    label: "Borrowing-base reporting",
    help: "Tracks eligible collateral for working-capital or asset-backed facilities.",
  },
] as const;

const multiValueIntakeFields = new Set(["selected_covenants"]);

function toAnswerValue(value: FormDataEntryValue): string | number {
  const text = String(value).trim();
  if (text === "") return "";
  const numberValue = Number(text);
  return Number.isFinite(numberValue) && /^-?\d+(\.\d+)?$/.test(text) ? numberValue : text;
}

function answersFromFormData(
  formData: FormData,
  { includeEmpty = false }: { includeEmpty?: boolean } = {},
): Record<string, unknown> {
  const answers: Record<string, unknown> = {};
  const keys = new Set(Array.from(formData.keys()));

  for (const key of keys) {
    const values = formData.getAll(key);
    if (values.length > 1 || multiValueIntakeFields.has(key)) {
      const list = values
        .map((value) => toAnswerValue(value))
        .filter((answer) => answer !== "" || includeEmpty);
      if (list.length || includeEmpty) answers[key] = list;
      continue;
    }

    const answer = toAnswerValue(values[0]);
    if (answer !== "" || includeEmpty) answers[key] = answer;
  }

  return answers;
}

function normaliseCreditCovenantPackageLevel(value: unknown): string {
  const level = String(value ?? "").trim();
  return creditCovenantPackageDefaults[level] ? level : "balanced";
}

function selectedCreditCovenantsFromDraft(answers: Record<string, unknown>): string[] {
  const rawSelection = answers.selected_covenants;
  const selected = Array.isArray(rawSelection)
    ? rawSelection.map((item) => String(item)).filter((item) => creditCovenantOptions.some((option) => option.value === item))
    : typeof rawSelection === "string"
      ? rawSelection
          .split(/[\n,]+/)
          .map((item) => item.trim())
          .filter((item) => creditCovenantOptions.some((option) => option.value === item))
      : [];
  if (selected.length) return selected;
  return creditCovenantPackageDefaults[normaliseCreditCovenantPackageLevel(answers.covenant_package_level)];
}

function valuationAnswerText(name: string, value: unknown): string {
  const raw = String(value ?? "");
  if (!raw) return "Not answered";
  return valuationAnswerLabels[name]?.[raw] ?? raw;
}

function valuationOptionalAnswerText(name: string, value: unknown): string {
  if (name === "public_source_urls") {
    const links = Array.isArray(value)
      ? value.map((item) => String(item).trim())
      : String(value ?? "")
          .split(/[\n,]+/)
          .map((item) => item.trim());
    return links.filter(Boolean).join("; ");
  }
  return String(value ?? "").trim();
}

function isLocalOrPrivateHost(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (host === "localhost" || host.endsWith(".localhost") || host.endsWith(".local")) return true;
  if (host.includes(":")) {
    return (
      host === "::1" ||
      host === "0:0:0:0:0:0:0:1" ||
      host.startsWith("fe80:") ||
      host.startsWith("fc") ||
      host.startsWith("fd")
    );
  }

  const ipv4Match = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!ipv4Match) return false;
  const octets = ipv4Match.slice(1).map((part) => Number(part));
  if (octets.some((octet) => !Number.isInteger(octet) || octet < 0 || octet > 255)) return true;
  const [first, second] = octets;
  return (
    first === 0 ||
    first === 10 ||
    first === 127 ||
    (first === 169 && second === 254) ||
    (first === 172 && second >= 16 && second <= 31) ||
    (first === 192 && second === 168) ||
    first >= 224
  );
}

function normaliseOptionalPublicUrl(value: unknown, fieldLabel: string): { url: string; error?: string } {
  const raw = String(value ?? "").trim();
  if (!raw) return { url: "" };
  if (raw.length > 2048) return { url: "", error: `${fieldLabel} is too long.` };

  const candidate = raw.includes("://") ? raw : `https://${raw}`;
  if (candidate.length > 2048) return { url: "", error: `${fieldLabel} is too long.` };
  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    return { url: "", error: `${fieldLabel} must be a valid website or public URL.` };
  }

  const host = parsed.hostname.toLowerCase();
  const isHttp = parsed.protocol === "http:" || parsed.protocol === "https:";
  if (!isHttp || !host || /\s/.test(candidate)) {
    return { url: "", error: `${fieldLabel} must be a valid website or public URL.` };
  }
  if (isLocalOrPrivateHost(host)) {
    return { url: "", error: `${fieldLabel} must be a public website or public URL.` };
  }
  if (!host.includes(".")) {
    return { url: "", error: `${fieldLabel} must be a valid website or public URL.` };
  }

  return { url: candidate.replace(/\/+$/, "") };
}

function normalisePublicSourceUrls(value: unknown): { urls: string[]; error?: string } {
  if (value == null || value === "") return { urls: [] };

  const urls: string[] = [];
  const seen = new Set<string>();
  const candidates = Array.isArray(value)
    ? value.map((item) => String(item))
    : String(value).split(/[\n,]+/);
  if (!candidates.some((candidate) => candidate.trim())) return { urls: [] };

  for (const [index, candidate] of candidates.entries()) {
    const result = normaliseOptionalPublicUrl(candidate, `Helpful public link ${index + 1}`);
    if (result.error) return { urls: [], error: result.error };
    if (!result.url || seen.has(result.url)) continue;
    urls.push(result.url);
    seen.add(result.url);
  }

  if (urls.length > 10) {
    return { urls: [], error: "Helpful public links can include up to 10 URLs." };
  }

  return { urls };
}

function normaliseOptionalText(
  value: unknown,
  fieldLabel: string,
  maxLength: number,
): { text: string; error?: string } {
  const raw = String(value ?? "");
  if (!raw.trim()) return { text: "" };

  for (const character of raw) {
    if (character.charCodeAt(0) < 32 && !/\s/.test(character)) {
      return { text: "", error: `${fieldLabel} contains invalid characters.` };
    }
  }

  const text = raw.replace(/\s+/g, " ").trim();
  if (!text) return { text: "" };
  if (text.length > maxLength) return { text: "", error: `${fieldLabel} is too long.` };
  return { text };
}

function normaliseValuationSourceHints(answers: Record<string, unknown>): { answers: Record<string, unknown>; error?: string } {
  const normalised = { ...answers };

  const website = normaliseOptionalPublicUrl(normalised.company_website, "Business website");
  if (website.error) return { answers, error: website.error };
  if ("company_website" in normalised || website.url) normalised.company_website = website.url;

  const sourceLinks = normalisePublicSourceUrls(normalised.public_source_urls);
  if (sourceLinks.error) return { answers, error: sourceLinks.error };
  normalised.public_source_urls = sourceLinks.urls;

  const location = normaliseOptionalText(normalised.company_location, "Main location", 120);
  if (location.error) return { answers, error: location.error };
  if ("company_location" in normalised || location.text) normalised.company_location = location.text;

  const privateContext = normaliseOptionalText(normalised.private_context, "Private valuation context", 1200);
  if (privateContext.error) return { answers, error: privateContext.error };
  if ("private_context" in normalised || privateContext.text) normalised.private_context = privateContext.text;

  return { answers: normalised };
}

function creditOptionalAnswerText(name: string, value: unknown): string {
  if (name === "public_source_urls") return valuationOptionalAnswerText(name, value);
  return String(value ?? "").trim();
}

function normaliseCreditSourceHints(answers: Record<string, unknown>): { answers: Record<string, unknown>; error?: string } {
  const normalised = { ...answers };

  const website = normaliseOptionalPublicUrl(normalised.company_website, "Business website");
  if (website.error) return { answers, error: website.error };
  if ("company_website" in normalised || website.url) normalised.company_website = website.url;

  const sourceLinks = normalisePublicSourceUrls(normalised.public_source_urls);
  if (sourceLinks.error) return { answers, error: sourceLinks.error };
  normalised.public_source_urls = sourceLinks.urls;

  const location = normaliseOptionalText(normalised.company_location, "Main location", 120);
  if (location.error) return { answers, error: location.error };
  if ("company_location" in normalised || location.text) normalised.company_location = location.text;

  const borrowerStructure = normaliseOptionalText(
    normalised.borrower_structure,
    "Borrower / ownership structure",
    300,
  );
  if (borrowerStructure.error) return { answers, error: borrowerStructure.error };
  if ("borrower_structure" in normalised || borrowerStructure.text) {
    normalised.borrower_structure = borrowerStructure.text;
  }

  return { answers: normalised };
}

export function IntakeForm({
  reportType,
  companyId,
  demoMode = false,
  initialDraft,
  onDraftChange,
  onBack,
  onSubmit,
  loading,
}: IntakeFormProps) {
  const formRef = useRef<HTMLFormElement>(null);
  const [normalisations, setNormalisations] = useState<NormalisationRow[]>(initialDraft?.normalisations ?? []);
  const [profileStatus, setProfileStatus] = useState<ProfileStatus | null>(null);
  const [valuationStage, setValuationStage] = useState<ValuationStage>(initialDraft?.valuationStage ?? "questions");
  const [valuationAnswers, setValuationAnswers] = useState<Record<string, unknown>>(
    initialDraft?.valuationAnswers ?? {},
  );
  const [valuationQuestionSnapshot, setValuationQuestionSnapshot] = useState<Record<string, unknown>>(
    initialDraft?.valuationAnswers ?? {},
  );
  const [valuationReviewAnswers, setValuationReviewAnswers] = useState<Record<string, unknown>>(
    initialDraft?.valuationReviewAnswers ?? {},
  );
  const [creditStage, setCreditStage] = useState<CreditStage>(initialDraft?.creditStage ?? "research-hints");
  const [creditAnswers, setCreditAnswers] = useState<Record<string, unknown>>(
    initialDraft?.creditAnswers ?? {},
  );
  const [creditCovenantPackageLevel, setCreditCovenantPackageLevel] = useState<string>(
    normaliseCreditCovenantPackageLevel(initialDraft?.creditAnswers?.covenant_package_level),
  );
  const [selectedCreditCovenants, setSelectedCreditCovenants] = useState<string[]>(
    selectedCreditCovenantsFromDraft(initialDraft?.creditAnswers ?? {}),
  );
  const [error, setError] = useState("");
  const answeredRequiredValuationAnswers = valuationRequiredAnswers.filter(({ name }) =>
    String(valuationQuestionSnapshot[name] ?? valuationAnswers[name] ?? "").trim(),
  ).length;
  const optionalValuationAnswers = valuationOptionalSummary
    .map(([name, label]) => ({
      name,
      label,
      value: valuationOptionalAnswerText(name, valuationAnswers[name]),
    }))
    .filter((item) => item.value);
  const optionalCreditAnswers = creditAnswerSummary
    .map(([name, label]) => ({
      name,
      label,
      value: creditOptionalAnswerText(name, creditAnswers[name]),
    }))
    .filter((item) => item.value);

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
    if (initialDraft?.normalisations !== undefined) return;

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
  }, [companyId, initialDraft?.normalisations, reportType]);

  function visibleFormAnswers({ includeEmpty = false }: { includeEmpty?: boolean } = {}): Record<string, unknown> {
    const form = formRef.current;
    if (!form) return {};
    return answersFromFormData(new FormData(form), { includeEmpty });
  }

  function persistDraft(nextDraft: IntakeDraft) {
    onDraftChange?.(nextDraft);
  }

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

  function updateValuationQuestionSnapshot(name: string, value: string) {
    setValuationQuestionSnapshot((current) => ({ ...current, [name]: value }));
  }

  function updateCreditCovenantPackage(level: string) {
    const nextLevel = normaliseCreditCovenantPackageLevel(level);
    setCreditCovenantPackageLevel(nextLevel);
    setSelectedCreditCovenants([...creditCovenantPackageDefaults[nextLevel]]);
  }

  function toggleCreditCovenant(value: string, checked: boolean) {
    setSelectedCreditCovenants((current) => {
      if (checked) {
        return current.includes(value) ? current : [...current, value];
      }
      return current.filter((item) => item !== value);
    });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const formData = new FormData(event.currentTarget);
    const visibleAnswers = answersFromFormData(formData, { includeEmpty: reportType === "valuation_advisory" });

    if (reportType === "valuation_advisory") {
      let answers = { ...valuationAnswers, ...valuationReviewAnswers, ...visibleAnswers };
      const missingAnswer = valuationRequiredAnswers.find(({ name }) => !answers[name]);
      if (missingAnswer) {
        setError(`Please tell us ${missingAnswer.missingLabel}.`);
        return;
      }

      const sourceHintResult = normaliseValuationSourceHints(answers);
      if (sourceHintResult.error) {
        setError(sourceHintResult.error);
        return;
      }
      answers = sourceHintResult.answers;

      if (valuationStage === "questions") {
        setValuationAnswers(answers);
        setValuationQuestionSnapshot(answers);
        persistDraft({
          valuationStage: "earnings-review",
          valuationAnswers: answers,
          valuationReviewAnswers,
          normalisations,
        });
        setValuationStage("earnings-review");
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }

      for (const [field, label] of valuationOptionalMoneyOverrides) {
        const value = answers[field];
        if (value === undefined || value === "") continue;
        const numberValue = Number(value);
        if (!Number.isFinite(numberValue)) {
          setError(`${label} must be a number.`);
          return;
        }
        if (numberValue < 0) {
          setError(`${label} must be zero or greater.`);
          return;
        }
      }

      const customGrowth = answers.custom_growth_rate;
      if (
        customGrowth !== undefined
        && customGrowth !== ""
        && (!Number.isFinite(Number(customGrowth)) || Number(customGrowth) < -50 || Number(customGrowth) > 100)
      ) {
        setError("The optional supported revenue-growth view must be between -50 and 100.");
        return;
      }
      const completedNormalisations = normalisations.filter(
        (row) => row.label.trim() || row.amount.trim() || row.rationale.trim(),
      );
      for (const [index, row] of completedNormalisations.entries()) {
        const label = row.label.trim();
        const amountText = row.amount.trim();
        const amount = Number(amountText);
        const rationale = row.rationale.trim();
        if (!label) {
          setError(`Adjustment ${index + 1} needs a label, or remove the row.`);
          return;
        }
        if (!amountText || !Number.isFinite(amount) || amount === 0) {
          setError(`Adjustment ${index + 1} needs a non-zero amount, or remove the row.`);
          return;
        }
        if (!rationale) {
          setError(`Adjustment ${index + 1} needs a short rationale, or remove the row.`);
          return;
        }
      }
      answers.normalisations = completedNormalisations.map((row) => ({
        label: row.label.trim(),
        amount: Number(row.amount),
        rationale: row.rationale.trim(),
      }));
      persistDraft({
        valuationStage,
        valuationAnswers,
        valuationReviewAnswers: { ...valuationReviewAnswers, ...visibleAnswers },
        normalisations,
      });
      onSubmit(answers);
      return;
    }

    if (reportType === "bank_credit_paper") {
      let answers = { ...creditAnswers, ...visibleAnswers };
      const sourceHintResult = normaliseCreditSourceHints(answers);
      if (sourceHintResult.error) {
        setError(sourceHintResult.error);
        return;
      }
      answers = sourceHintResult.answers;

      if (creditStage === "research-hints") {
        setCreditAnswers(answers);
        persistDraft({
          creditStage: "facility-questions",
          creditAnswers: answers,
        });
        setCreditStage("facility-questions");
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }

      const missingAnswer = creditRequiredAnswers.find(({ name }) => !String(answers[name] ?? "").trim());
      if (missingAnswer) {
        setError(`Please tell us ${missingAnswer.missingLabel}.`);
        return;
      }

      const numericFields = [
        ["amount_requested", "Facility amount"],
        ["proposed_term_years", "Term of debt"],
        ["conservative_funding_cost_pct", "Conservative funding cost"],
        ["lvr_percent", "LVR / advance rate"],
      ] as const;
      for (const [field, label] of numericFields) {
        const numberValue = Number(answers[field]);
        if (!Number.isFinite(numberValue) || numberValue <= 0) {
          setError(`${label} must be greater than zero.`);
          return;
        }
        if (field === "proposed_term_years" && numberValue > 30) {
          setError("Term of debt must be 30 years or less.");
          return;
        }
        if (field === "conservative_funding_cost_pct" && numberValue > 30) {
          setError("Conservative funding cost must be 30% or less.");
          return;
        }
        if (field === "lvr_percent" && numberValue > 100) {
          setError("LVR / advance rate must be 100% or less.");
          return;
        }
        answers[field] = numberValue;
      }

      const optionalNumericFields = [
        ["transaction_value", "Purchase price / asset value"],
        ["equity_contribution", "Equity contribution"],
        ["refinance_amount", "Refinance amount"],
        ["transaction_costs", "Transaction costs"],
        ["working_capital_buffer", "Working-capital buffer"],
        ["sponsor_bridge_amount", "Additional bridge amount"],
        ["sponsor_bridge_term_months", "Bridge term"],
      ] as const;
      for (const [field, label] of optionalNumericFields) {
        const value = answers[field];
        if (value === undefined || value === "") continue;
        const numberValue = Number(value);
        if (!Number.isFinite(numberValue) || numberValue <= 0) {
          setError(`${label} must be greater than zero, or left blank.`);
          return;
        }
        if (field === "sponsor_bridge_term_months" && numberValue > 60) {
          setError("Bridge term must be 60 months or less.");
          return;
        }
        answers[field] = numberValue;
      }

      const securityValue = answers.security_value;
      if (securityValue !== undefined && securityValue !== "") {
        const numberValue = Number(securityValue);
        if (!Number.isFinite(numberValue) || numberValue <= 0) {
          setError("Security value must be greater than zero, or left blank.");
          return;
        }
        answers.security_value = numberValue;
      }

      if (!creditSecurityLabels[String(answers.security_package)]) {
        setError("Please choose what security is available.");
        return;
      }
      if (!creditRepaymentProfileLabels[String(answers.repayment_profile)]) {
        setError("Please choose the repayment profile.");
        return;
      }
      if (!selectedCreditCovenants.length) {
        setError("Please choose at least one covenant or lender control.");
        return;
      }
      answers.covenant_package_level = creditCovenantPackageLevel;
      answers.selected_covenants = selectedCreditCovenants;

      const privateCreditContext = normaliseOptionalText(
        answers.private_credit_context,
        "Credit context",
        1200,
      );
      if (privateCreditContext.error) {
        setError(privateCreditContext.error);
        return;
      }
      answers.private_credit_context = privateCreditContext.text;

      const securityNotes = normaliseOptionalText(answers.security_notes, "Security notes", 600);
      if (securityNotes.error) {
        setError(securityNotes.error);
        return;
      }
      answers.security_notes = securityNotes.text;

      const sourceOfRepayment = normaliseOptionalText(answers.source_of_repayment, "Source of repayment", 500);
      if (sourceOfRepayment.error) {
        setError(sourceOfRepayment.error);
        return;
      }
      answers.source_of_repayment = sourceOfRepayment.text;

      const bridgeRepaymentSource = normaliseOptionalText(
        answers.sponsor_bridge_repayment_source,
        "Bridge repayment source",
        500,
      );
      if (bridgeRepaymentSource.error) {
        setError(bridgeRepaymentSource.error);
        return;
      }
      answers.sponsor_bridge_repayment_source = bridgeRepaymentSource.text;

      persistDraft({
        creditStage,
        creditAnswers: answers,
      });
      onSubmit(answers);
      return;
    }

    setError("This report type is not available in the self-serve wizard right now.");
  }

  function goBack() {
    setError("");
    if (reportType === "valuation_advisory" && valuationStage === "earnings-review") {
      const nextReviewAnswers = { ...valuationReviewAnswers, ...visibleFormAnswers({ includeEmpty: true }) };
      setValuationReviewAnswers(nextReviewAnswers);
      persistDraft({
        valuationStage: "questions",
        valuationAnswers,
        valuationReviewAnswers: nextReviewAnswers,
        normalisations,
      });
      setValuationStage("questions");
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    if (reportType === "valuation_advisory") {
      persistDraft({
        valuationStage: "questions",
        valuationAnswers: { ...valuationAnswers, ...visibleFormAnswers({ includeEmpty: true }) },
        valuationReviewAnswers,
        normalisations,
      });
    }
    if (reportType === "bank_credit_paper" && creditStage === "facility-questions") {
      const nextCreditAnswers = { ...creditAnswers, ...visibleFormAnswers({ includeEmpty: true }) };
      setCreditAnswers(nextCreditAnswers);
      persistDraft({
        creditStage: "research-hints",
        creditAnswers: nextCreditAnswers,
      });
      setCreditStage("research-hints");
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    if (reportType === "bank_credit_paper") {
      persistDraft({
        creditStage: "research-hints",
        creditAnswers: { ...creditAnswers, ...visibleFormAnswers({ includeEmpty: true }) },
      });
    }
    onBack();
  }

  if (reportType === "bank_credit_paper") {
    return (
      <form ref={formRef} className="wizard-form" onSubmit={submit} noValidate>
        {error ? (
          <div role="alert" className="alert alert-error">
            {error}
          </div>
        ) : null}
        {profileStatus && profileStatus.sections_complete < profileStatus.total ? (
          <div className="alert alert-info">
            {demoMode
              ? "Demo mode will supply sample public client context. You only need to complete the lender questions below."
              : "You can continue. AccountIQ will research public client context and use your uploaded accounts; only lender-specific facts are requested below."}
          </div>
        ) : null}

        <div className="valuation-intake-progress" aria-label="Credit paper progress">
          <div>
            <span className="eyebrow">Credit paper details</span>
            <strong>
              {creditStage === "research-hints" ? "Client research setup" : "Facility and security questions"}
            </strong>
          </div>
          <span>
            {creditStage === "research-hints" ? "Step 1 of 2" : "Step 2 of 2"}
          </span>
        </div>

        {creditStage === "research-hints" ? (
          <>
            <section className="valuation-question-contract" aria-labelledby="credit-research-contract-title">
              <div>
                <span className="eyebrow">Research first</span>
                <h2 id="credit-research-contract-title">AccountIQ will research the client before drafting</h2>
              </div>
              <p>
                The uploaded accounts provide the numbers. Public web research helps describe the business,
                sector, operating footprint and market context. These fields are optional hints, not a
                research assignment for you.
              </p>
              <ul>
                <li>Uploaded financials drive the credit metrics and balance-sheet strength view</li>
                <li>Public sources support the borrower and industry sections</li>
                <li>The next screen only asks for facility, LVR, funding cost and security details</li>
              </ul>
            </section>

            <fieldset>
              <legend>Optional public-source hints</legend>
              <div className="valuation-question-grid">
                <label htmlFor="credit-company-website">
                  Business website
                  <input
                    id="credit-company-website"
                    name="company_website"
                    type="url"
                    placeholder="https://example.co.nz"
                    defaultValue={String(creditAnswers.company_website ?? "")}
                  />
                  <span className="field-help">Used to help AccountIQ identify the right business online.</span>
                </label>
                <label htmlFor="credit-company-location">
                  Main location
                  <input
                    id="credit-company-location"
                    name="company_location"
                    placeholder="e.g. Henderson, Auckland"
                    defaultValue={String(creditAnswers.company_location ?? "")}
                  />
                  <span className="field-help">Useful for local competitors, branch network and sector context.</span>
                </label>
                <label htmlFor="credit-borrower-structure" className="valuation-wide-field">
                  Borrower / ownership structure
                  <input
                    id="credit-borrower-structure"
                    name="borrower_structure"
                    placeholder="e.g. operating company, HoldCo borrower, owner-operator, guarantors"
                    defaultValue={String(creditAnswers.borrower_structure ?? "")}
                  />
                  <span className="field-help">Optional. Add anything the accounts and public research may not show.</span>
                </label>
                <label htmlFor="credit-public-source-urls" className="valuation-wide-field">
                  Helpful public links
                  <textarea
                    id="credit-public-source-urls"
                    name="public_source_urls"
                    rows={3}
                    placeholder="Companies Office profile, business website, LinkedIn, media article, industry page..."
                    defaultValue={
                      Array.isArray(creditAnswers.public_source_urls)
                        ? creditAnswers.public_source_urls.join("\n")
                        : String(creditAnswers.public_source_urls ?? "")
                    }
                  />
                  <span className="field-help">Optional. Up to 10 public URLs; AccountIQ treats them as hints to corroborate.</span>
                </label>
              </div>
            </fieldset>

            <section className="valuation-next-step-note" aria-labelledby="credit-next-step-title">
              <div>
                <span className="eyebrow">Next</span>
                <h3 id="credit-next-step-title">A short lender input set</h3>
              </div>
              <p>
                The next screen asks for the items that change the credit view: facility amount,
                LVR, conservative funding cost, debt term and available security.
              </p>
            </section>
          </>
        ) : (
          <>
            {optionalCreditAnswers.length ? (
              <section className="valuation-answer-summary" aria-labelledby="credit-research-summary-title">
                <div className="valuation-answer-summary-header">
                  <div>
                    <span className="eyebrow">Research setup</span>
                    <h3 id="credit-research-summary-title">Client research hints retained</h3>
                  </div>
                </div>
                <dl>
                  {optionalCreditAnswers.map(({ name, label, value }) => (
                    <div key={name}>
                      <dt>{label}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ) : null}

            <section className="valuation-question-contract" aria-labelledby="credit-facility-contract-title">
              <div>
                <span className="eyebrow">Lender questions</span>
                <h2 id="credit-facility-contract-title">Only the credit-structuring facts are required</h2>
              </div>
              <p>
                AccountIQ will use the uploaded P&amp;L and balance sheet for the credit metrics.
                These answers set the proposed debt structure so the app can calculate DSCR, ICR,
                LVR, NTOA and debt capacity.
              </p>
              <ul>
                {creditRequiredAnswers.map(({ name, label }) => (
                  <li key={name}>{label}</li>
                ))}
              </ul>
            </section>

            <fieldset>
              <legend>Facility request</legend>
              <div className="valuation-question-grid">
                <label htmlFor="credit-loan-purpose" className="valuation-wide-field">
                  What is the debt for? <span className="required" aria-hidden="true">*</span>
                  <textarea
                    id="credit-loan-purpose"
                    name="loan_purpose"
                    rows={3}
                    placeholder="e.g. acquisition funding, working capital, refinance, fleet purchase, property-backed facility"
                    defaultValue={String(creditAnswers.loan_purpose ?? "")}
                  />
                </label>
                <label htmlFor="credit-amount-requested">
                  Facility amount requested ($) <span className="required" aria-hidden="true">*</span>
                  <input
                    id="credit-amount-requested"
                    name="amount_requested"
                    type="number"
                    min="0"
                    step="1000"
                    defaultValue={String(creditAnswers.amount_requested ?? "")}
                  />
                </label>
                <label htmlFor="credit-term">
                  Term of debt (years) <span className="required" aria-hidden="true">*</span>
                  <input
                    id="credit-term"
                    name="proposed_term_years"
                    type="number"
                    min="0.25"
                    max="30"
                    step="0.25"
                    defaultValue={String(creditAnswers.proposed_term_years ?? "")}
                  />
                </label>
                <label htmlFor="credit-funding-cost">
                  Conservative funding cost (%) <span className="required" aria-hidden="true">*</span>
                  <input
                    id="credit-funding-cost"
                    name="conservative_funding_cost_pct"
                    type="number"
                    min="0"
                    max="30"
                    step="0.05"
                    placeholder="e.g. 8.50"
                    defaultValue={String(creditAnswers.conservative_funding_cost_pct ?? "")}
                  />
                </label>
                <label htmlFor="credit-repayment-profile">
                  Repayment profile <span className="required" aria-hidden="true">*</span>
                  <select
                    id="credit-repayment-profile"
                    name="repayment_profile"
                    defaultValue={String(creditAnswers.repayment_profile ?? "")}
                  >
                    <option value="">Select...</option>
                    {Object.entries(creditRepaymentProfileLabels).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </fieldset>

            <fieldset>
              <legend>Security and LVR</legend>
              <div className="valuation-question-grid">
                <label htmlFor="credit-security-package">
                  Can the debt be secured? <span className="required" aria-hidden="true">*</span>
                  <select
                    id="credit-security-package"
                    name="security_package"
                    defaultValue={String(creditAnswers.security_package ?? "")}
                  >
                    <option value="">Select...</option>
                    {Object.entries(creditSecurityLabels).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label htmlFor="credit-lvr">
                  LVR / advance rate (%) <span className="required" aria-hidden="true">*</span>
                  <input
                    id="credit-lvr"
                    name="lvr_percent"
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    placeholder="e.g. 60"
                    defaultValue={String(creditAnswers.lvr_percent ?? "")}
                  />
                  <span className="field-help">Use the conservative advance rate the lender is likely to test.</span>
                </label>
                <label htmlFor="credit-security-value">
                  Estimated security value ($)
                  <input
                    id="credit-security-value"
                    name="security_value"
                    type="number"
                    min="0"
                    step="1000"
                    placeholder="Optional; app can still show implied value from LVR"
                    defaultValue={String(creditAnswers.security_value ?? "")}
                  />
                </label>
                <label htmlFor="credit-security-notes" className="valuation-wide-field">
                  Security notes
                  <textarea
                    id="credit-security-notes"
                    name="security_notes"
                    rows={3}
                    placeholder="e.g. fleet list available, property owned separately, GSA possible, personal guarantee available"
                    defaultValue={String(creditAnswers.security_notes ?? "")}
                  />
                </label>
              </div>
            </fieldset>

            <fieldset>
              <legend>Covenant package</legend>
              <p className="field-help">
                Choose how much lender control you want the paper to propose. The preset ticks the usual controls;
                you can then add or remove specific covenants before generating the paper.
              </p>
              <div className="valuation-question-grid">
                {Object.entries(creditCovenantPackageLabels).map(([value, label]) => (
                  <label key={value} htmlFor={`credit-covenant-package-${value}`}>
                    <input
                      id={`credit-covenant-package-${value}`}
                      name="covenant_package_level"
                      type="radio"
                      value={value}
                      checked={creditCovenantPackageLevel === value}
                      onChange={(event) => updateCreditCovenantPackage(event.currentTarget.value)}
                    />
                    {label}
                    <span className="field-help">{creditCovenantPackageDescriptions[value]}</span>
                  </label>
                ))}
              </div>

              <div className="valuation-question-grid">
                {creditCovenantOptions.map((option) => (
                  <label key={option.value} htmlFor={`credit-covenant-${option.value}`}>
                    <input
                      id={`credit-covenant-${option.value}`}
                      name="selected_covenants"
                      type="checkbox"
                      value={option.value}
                      checked={selectedCreditCovenants.includes(option.value)}
                      onChange={(event) => toggleCreditCovenant(option.value, event.currentTarget.checked)}
                    />
                    {option.label}
                    <span className="field-help">{option.help}</span>
                  </label>
                ))}
              </div>

              <label htmlFor="credit-covenant-notes" className="valuation-wide-field">
                Covenant notes
                <textarea
                  id="credit-covenant-notes"
                  name="covenant_package_notes"
                  rows={3}
                  placeholder="Optional. e.g. Keep covenants light because existing leverage is low; add tighter controls until collateral values are confirmed."
                  defaultValue={String(creditAnswers.covenant_package_notes ?? "")}
                />
                <span className="field-help">
                  These notes will flow into the proposed covenants section as drafting context.
                </span>
              </label>
            </fieldset>

            <details className="advanced-valuation-details">
              <summary>Optional: add sources & uses, bridge details or stricter lender thresholds</summary>
              <div className="valuation-question-grid">
                <label htmlFor="credit-facility-type">
                  Facility type
                  <input
                    id="credit-facility-type"
                    name="facility_type"
                    placeholder="e.g. senior secured term loan, acquisition facility, working capital line"
                    defaultValue={String(creditAnswers.facility_type ?? "")}
                  />
                </label>
                <label htmlFor="credit-transaction-value">
                  Purchase price / asset value ($)
                  <input
                    id="credit-transaction-value"
                    name="transaction_value"
                    type="number"
                    min="0"
                    step="1000"
                    placeholder="Optional; used for LVR / LTV context"
                    defaultValue={String(creditAnswers.transaction_value ?? "")}
                  />
                </label>
                <label htmlFor="credit-equity-contribution">
                  Equity contribution ($)
                  <input
                    id="credit-equity-contribution"
                    name="equity_contribution"
                    type="number"
                    min="0"
                    step="1000"
                    placeholder="Optional"
                    defaultValue={String(creditAnswers.equity_contribution ?? "")}
                  />
                </label>
                <label htmlFor="credit-refinance-amount">
                  Refinance amount ($)
                  <input
                    id="credit-refinance-amount"
                    name="refinance_amount"
                    type="number"
                    min="0"
                    step="1000"
                    placeholder="Optional"
                    defaultValue={String(creditAnswers.refinance_amount ?? "")}
                  />
                </label>
                <label htmlFor="credit-transaction-costs">
                  Transaction costs / fees ($)
                  <input
                    id="credit-transaction-costs"
                    name="transaction_costs"
                    type="number"
                    min="0"
                    step="1000"
                    placeholder="Optional"
                    defaultValue={String(creditAnswers.transaction_costs ?? "")}
                  />
                </label>
                <label htmlFor="credit-working-capital-buffer">
                  Working-capital buffer ($)
                  <input
                    id="credit-working-capital-buffer"
                    name="working_capital_buffer"
                    type="number"
                    min="0"
                    step="1000"
                    placeholder="Optional"
                    defaultValue={String(creditAnswers.working_capital_buffer ?? "")}
                  />
                </label>
                <label htmlFor="credit-source-of-repayment" className="valuation-wide-field">
                  Source of repayment
                  <textarea
                    id="credit-source-of-repayment"
                    name="source_of_repayment"
                    rows={3}
                    placeholder="e.g. operating cash flow, contract cash flows, refinance, asset sale, estate distribution, shareholder support"
                    defaultValue={String(creditAnswers.source_of_repayment ?? "")}
                  />
                </label>
                <label htmlFor="credit-sponsor-bridge-amount">
                  Additional bridge amount ($)
                  <input
                    id="credit-sponsor-bridge-amount"
                    name="sponsor_bridge_amount"
                    type="number"
                    min="0"
                    step="1000"
                    placeholder="Optional"
                    defaultValue={String(creditAnswers.sponsor_bridge_amount ?? "")}
                  />
                </label>
                <label htmlFor="credit-sponsor-bridge-term">
                  Bridge term (months)
                  <input
                    id="credit-sponsor-bridge-term"
                    name="sponsor_bridge_term_months"
                    type="number"
                    min="0"
                    max="60"
                    step="1"
                    placeholder="Optional"
                    defaultValue={String(creditAnswers.sponsor_bridge_term_months ?? "")}
                  />
                </label>
                <label htmlFor="credit-sponsor-bridge-repayment" className="valuation-wide-field">
                  Bridge repayment source
                  <textarea
                    id="credit-sponsor-bridge-repayment"
                    name="sponsor_bridge_repayment_source"
                    rows={3}
                    placeholder="e.g. estate distribution, shareholder contribution, property refinance, planned asset sale"
                    defaultValue={String(creditAnswers.sponsor_bridge_repayment_source ?? "")}
                  />
                </label>
                <label htmlFor="credit-private-context" className="valuation-wide-field">
                  Private credit context
                  <textarea
                    id="credit-private-context"
                    name="private_credit_context"
                    rows={4}
                    placeholder="Key contracts, pending acquisition, owner support, seasonal working capital, covenant concerns, recent trading changes..."
                    defaultValue={String(creditAnswers.private_credit_context ?? "")}
                  />
                </label>
                <label htmlFor="credit-minimum-dscr">
                  Minimum DSCR threshold
                  <input
                    id="credit-minimum-dscr"
                    name="minimum_dscr"
                    type="number"
                    min="0"
                    max="10"
                    step="0.05"
                    placeholder="Default 1.40x"
                    defaultValue={String(creditAnswers.minimum_dscr ?? "")}
                  />
                </label>
                <label htmlFor="credit-minimum-interest-cover">
                  Minimum interest cover
                  <input
                    id="credit-minimum-interest-cover"
                    name="minimum_interest_cover"
                    type="number"
                    min="0"
                    max="20"
                    step="0.05"
                    placeholder="Default 3.00x"
                    defaultValue={String(creditAnswers.minimum_interest_cover ?? "")}
                  />
                </label>
                <label htmlFor="credit-max-leverage">
                  Maximum senior leverage
                  <input
                    id="credit-max-leverage"
                    name="maximum_senior_leverage"
                    type="number"
                    min="0"
                    max="20"
                    step="0.05"
                    placeholder="Default 2.50x"
                    defaultValue={String(creditAnswers.maximum_senior_leverage ?? "")}
                  />
                </label>
              </div>
            </details>
          </>
        )}

        <div className="wizard-actions">
          <button type="button" className="button button-secondary" onClick={goBack}>
            {creditStage === "research-hints" ? "Back" : "Back to research setup"}
          </button>
          <button type="submit" className="button button-primary" disabled={loading}>
            {loading
              ? "Preparing..."
              : creditStage === "research-hints"
                ? "Continue to lending questions"
                : "Research & prepare credit paper"}
          </button>
        </div>
      </form>
    );
  }

  if (reportType !== "valuation_advisory") {
    return (
      <form ref={formRef} className="wizard-form" onSubmit={submit}>
        {error ? (
          <div role="alert" className="alert alert-error">
            {error}
          </div>
        ) : null}
        <section className="valuation-review-intro" aria-labelledby="coming-soon-report-title">
          <span className="eyebrow">Coming soon</span>
          <h2 id="coming-soon-report-title">This report type is not part of the self-serve journey yet</h2>
          <p>
            AccountIQ self-serve is focused on Valuation Advisory first. We will not ask you to
            complete a different report questionnaire inside this valuation flow.
          </p>
        </section>
        <div className="wizard-actions">
          <button type="button" className="button button-secondary" onClick={goBack}>
            Back
          </button>
          <button type="submit" className="button button-primary" disabled>
            Coming soon
          </button>
        </div>
      </form>
    );
  }

  return (
    <form ref={formRef} className="wizard-form" onSubmit={submit} noValidate={reportType === "valuation_advisory"}>
      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}
      {profileStatus && profileStatus.sections_complete < profileStatus.total ? (
        <div className={reportType === "valuation_advisory" ? "alert alert-info" : "alert alert-warning"}>
          {reportType === "valuation_advisory"
            ? demoMode
              ? "Demo mode will supply sample public business context. You only need to complete the private facts below."
              : "You can continue. AccountIQ will research missing public business context; only private facts are requested below."
            : "Some profile data is incomplete - your report may have gaps. You can still generate the report."}
        </div>
      ) : null}

      {(
        <>
          <div className="valuation-intake-progress" aria-label="Valuation details progress">
            <div>
              <span className="eyebrow">Valuation details</span>
              <strong>
                {valuationStage === "questions" ? "Five quick answers" : "Earnings review"}
              </strong>
            </div>
            <span>
              {valuationStage === "questions"
                ? `${answeredRequiredValuationAnswers} of 5`
                : "2 of 2"}
            </span>
          </div>

          {valuationStage === "questions" ? (
            <>
          <section className="valuation-question-contract" aria-labelledby="valuation-question-contract-title">
            <div>
              <span className="eyebrow">Short by design</span>
              <h2 id="valuation-question-contract-title">Only five answers are required</h2>
              <p>
                Optional links and private context can be skipped. AccountIQ will use the upload,
                public research and its valuation model for the technical assumptions.
              </p>
            </div>
            <ul aria-label="Valuation intake promise">
              <li>
                <strong>5 required</strong>
                <span>Private facts only you know</span>
              </li>
              <li>
                <strong>Optional clues</strong>
                <span>Links or context if handy</span>
              </li>
              <li>
                <strong>Automatic</strong>
                <span>WACC, terminal growth and forecast period</span>
              </li>
            </ul>
          </section>

          <section
            className="valuation-required-checklist"
            aria-labelledby="valuation-required-checklist-title"
            aria-live="polite"
          >
            <div>
              <span className="eyebrow">Required answers</span>
              <h3 id="valuation-required-checklist-title">
                {answeredRequiredValuationAnswers} of 5 required answers complete
              </h3>
              <p>
                Optional research clues stay optional. This checklist only tracks the five
                private facts needed to prepare the valuation pack.
              </p>
            </div>
            <ul>
              {valuationRequiredAnswers.map(({ name, label }) => {
                const answered = Boolean(
                  String(valuationQuestionSnapshot[name] ?? valuationAnswers[name] ?? "").trim(),
                );
                return (
                  <li key={name} className={answered ? "complete" : "missing"}>
                    <span>{label}</span>
                    <strong>{answered ? "Done" : "Required"}</strong>
                  </li>
                );
              })}
            </ul>
          </section>

          <section className="valuation-uncertainty-panel" aria-labelledby="valuation-uncertainty-title">
            <div>
              <span className="eyebrow">No guessing required</span>
              <h3 id="valuation-uncertainty-title">Not sure is an acceptable answer</h3>
              <p>
                If you do not know an exact customer percentage, contract mix or forecast, choose
                Not sure. AccountIQ will either use uploaded financial history or flag the item as
                a diligence point in the report.
              </p>
            </div>
            <ul>
              <li>Use Not sure for uncertain private facts.</li>
              <li>Purpose is the only answer that needs your closest reason.</li>
              <li>No discount-rate, WACC or terminal-growth choices are required.</li>
            </ul>
          </section>

          <section className="research-first-panel" aria-labelledby="research-first-title">
            <div>
              <span className="eyebrow">{demoMode ? "Demo journey" : "Research first"}</span>
              <h2 id="research-first-title">
                {demoMode ? "We will simulate the desk work" : "We will do the desk work"}
              </h2>
              <p>
                {demoMode
                  ? "AccountIQ will use sample business research, sample market evidence and simulated valuation assumptions so you can test the finished journey without an API key. You only need to answer the same private facts a live valuation would require."
                  : "AccountIQ will research the business, sector, comparable transactions and current market evidence. You only need to answer the private facts we cannot verify online."}
              </p>
            </div>
            <ul>
              <li>{demoMode ? "Sample company background" : "Company background and public milestones"}</li>
              <li>{demoMode ? "Sample market and competitor context" : "Market, competitors and sector conditions"}</li>
              <li>{demoMode ? "Sample discount-rate and inflation assumptions" : "Current discount-rate evidence and NZ inflation"}</li>
              <li>{demoMode ? "Sample comparable evidence" : "Comparable transaction evidence"}</li>
            </ul>
            <aside className="source-trail-note" aria-label="Source trail reassurance">
              <strong>{demoMode ? "Source trail demonstrated" : "Source trail retained"}</strong>
              <span>
                {demoMode
                  ? "The sample report demonstrates how sample public evidence and labelled demo URLs appear in the finished pack."
                  : "Public evidence and URLs are kept in the report so a reader can see what supported the valuation assumptions."}
              </span>
            </aside>
          </section>

          <section className="valuation-answer-map" aria-labelledby="valuation-answer-map-title">
            <div>
              <span className="eyebrow">Why we ask</span>
              <h3 id="valuation-answer-map-title">Five required answers, each used in the report</h3>
              <p>
                We keep this to five required answers by using your financial upload and public research for everything else.
                These answers cover private facts that usually are not visible in accounts or online searches.
              </p>
            </div>
            <dl>
              <div>
                <dt>Purpose</dt>
                <dd>Sets the report scope and how the conclusion is framed.</dd>
              </div>
              <div>
                <dt>Owner or key-person dependency</dt>
                <dd>Feeds the continuity, handover and transition-risk discussion.</dd>
              </div>
              <div>
                <dt>Customer concentration</dt>
                <dd>Highlights earnings risk and revenue-retention sensitivity.</dd>
              </div>
              <div>
                <dt>Revenue predictability</dt>
                <dd>Helps explain cash-flow reliability and recurring revenue quality.</dd>
              </div>
              <div>
                <dt>Revenue outlook</dt>
                <dd>Guides the growth assumption or lets us use uploaded financial history.</dd>
              </div>
            </dl>
          </section>

          <fieldset>
            <legend>First, what is this valuation for?</legend>
            <p className="fieldset-intro">This changes how we frame the conclusion and assumptions.</p>
            <div className="valuation-question-grid">
              <label htmlFor="valuation-purpose">
                Purpose
                <select
                  id="valuation-purpose"
                  name="valuation_purpose"
                  defaultValue={String(valuationAnswers.valuation_purpose ?? "")}
                  onChange={(event) => updateValuationQuestionSnapshot("valuation_purpose", event.target.value)}
                  required
                >
                  <option value="" disabled>Select the closest reason</option>
                  <option value="understand_value">Understand what the business may be worth</option>
                  <option value="sale_or_transaction">Prepare for a sale or transaction</option>
                  <option value="shareholder_or_employee_scheme">Shareholder or employee share scheme</option>
                  <option value="succession_planning">Succession or estate planning</option>
                  <option value="finance_or_investment">Finance or investment discussions</option>
                  <option value="other">Another reason</option>
                </select>
                <span className="field-hint">
                  Used to set the report scope, reliance wording and how the valuation conclusion is framed.
                </span>
              </label>
            </div>
            <details className="optional-research-details">
              <summary>Optional: help us find the right business online</summary>
              <p>
                Skip this if you do not have links handy. AccountIQ will still research the business;
                these fields are just shortcuts for matching the correct website and public records.
                We use them as clues, corroborate material public facts, and keep retained source URLs
                in the finished report.
              </p>
              <div className="valuation-question-grid">
                <label htmlFor="company-website">
                  Website <span className="optional-label">Optional</span>
                  <input
                    id="company-website"
                    name="company_website"
                    inputMode="url"
                    placeholder="example.co.nz or https://example.co.nz"
                    defaultValue={String(valuationAnswers.company_website ?? "")}
                  />
                  <span className="field-hint">Helps us identify the right business online.</span>
                </label>
                <label htmlFor="company-location">
                  Main location <span className="optional-label">Optional</span>
                  <input
                    id="company-location"
                    name="company_location"
                    placeholder="e.g. Auckland, New Zealand"
                    maxLength={120}
                    defaultValue={String(valuationAnswers.company_location ?? "")}
                  />
                  <span className="field-hint">
                    Helps us distinguish businesses with similar names and focus research on the right market.
                  </span>
                </label>
                <label htmlFor="public-source-urls" className="valuation-wide-field">
                  Helpful public links <span className="optional-label">Optional</span>
                  <textarea
                    id="public-source-urls"
                    name="public_source_urls"
                    rows={3}
                    placeholder="Paste any useful public links, one per line: website pages, Companies Office, LinkedIn, media articles."
                    defaultValue={
                      Array.isArray(valuationAnswers.public_source_urls)
                        ? valuationAnswers.public_source_urls.join("\n")
                        : String(valuationAnswers.public_source_urls ?? "")
                    }
                  />
                  <span className="field-hint">
                    This is only a shortcut for research - leave it blank if you do not have links handy.
                    Supplied links are treated as clues, not standalone proof.
                  </span>
                </label>
              </div>
            </details>
              </fieldset>

              <fieldset>
            <legend>Only you would know this</legend>
            <p className="fieldset-intro">
              Together with the purpose above, five quick answers cover the private factors that
              materially affect a valuation.
            </p>
            <div className="valuation-question-grid">
              <label htmlFor="owner-dependency">
                How dependent is the business on the owner or a key person?
                <select
                  id="owner-dependency"
                  name="owner_dependency"
                  defaultValue={String(valuationAnswers.owner_dependency ?? "")}
                  onChange={(event) => updateValuationQuestionSnapshot("owner_dependency", event.target.value)}
                  required
                >
                  <option value="" disabled>Select one</option>
                  <option value="independent">Yes - a management team runs it</option>
                  <option value="shared">Mostly - responsibility is shared</option>
                  <option value="important">An owner, founder or key person is important day to day</option>
                  <option value="critical">The business depends heavily on an owner or key person</option>
                  <option value="unknown">Not sure</option>
                </select>
                <span className="field-hint">
                  Used to explain continuity, handover and transition risk in the report.
                  If you are unsure, choose Not sure; we will treat it as a diligence point rather
                  than making you guess.
                </span>
              </label>
              <label htmlFor="customer-concentration">
                How much revenue comes from the largest customer?
                <select
                  id="customer-concentration"
                  name="customer_concentration"
                  defaultValue={String(valuationAnswers.customer_concentration ?? "")}
                  onChange={(event) => updateValuationQuestionSnapshot("customer_concentration", event.target.value)}
                  required
                >
                  <option value="" disabled>Select one</option>
                  <option value="under_10">Less than 10%</option>
                  <option value="10_to_25">10% to 25%</option>
                  <option value="over_25">More than 25%</option>
                  <option value="consumer_or_diversified">Consumer or highly diversified revenue</option>
                  <option value="unknown">Not sure</option>
                </select>
                <span className="field-hint">
                  Used to assess concentration risk that usually is not visible in accounts or public research.
                  If you do not know the exact percentage, choose Not sure; the report will record
                  the uncertainty as a diligence note rather than making you guess.
                </span>
              </label>
              <label htmlFor="revenue-quality">
                How predictable is revenue?
                <select
                  id="revenue-quality"
                  name="revenue_quality"
                  defaultValue={String(valuationAnswers.revenue_quality ?? "")}
                  onChange={(event) => updateValuationQuestionSnapshot("revenue_quality", event.target.value)}
                  required
                >
                  <option value="" disabled>Select one</option>
                  <option value="mostly_contract">Mostly contracted or recurring</option>
                  <option value="mixed">A mix of recurring and one-off work</option>
                  <option value="mostly_one_off">Mostly one-off or transactional</option>
                  <option value="unknown">Not sure</option>
                </select>
                <span className="field-hint">
                  Used to explain cash-flow reliability, contract security and recurring revenue quality.
                  Choose Not sure if contracts and repeat work are unclear; we will describe the
                  uncertainty instead of forcing a precise answer.
                </span>
              </label>
              <label htmlFor="revenue-outlook">
                What is the realistic revenue outlook for the next 12-24 months?
                <select
                  id="revenue-outlook"
                  name="revenue_outlook"
                  defaultValue={String(valuationAnswers.revenue_outlook ?? "")}
                  onChange={(event) => updateValuationQuestionSnapshot("revenue_outlook", event.target.value)}
                  required
                >
                  <option value="" disabled>Select one</option>
                  <option value="lower">Likely lower than today</option>
                  <option value="steady">Broadly steady</option>
                  <option value="modest_growth">Modest growth</option>
                  <option value="strong_growth">Strong growth backed by pipeline or contracts</option>
                  <option value="not_sure">Not sure - use my financial history</option>
                </select>
                <span className="field-hint">
                  If you are unsure, we will derive a conservative assumption from uploaded revenue history.
                </span>
              </label>
            </div>
            <details className="optional-research-details">
              <summary>Optional: add private valuation context</summary>
              <p>
                Use this only if there is a contract, signed pipeline, dispute, upcoming change or unusual risk
                that would matter to the valuation but would not appear in the accounts or public research.
              </p>
              <label htmlFor="private-context">
                Is there anything important the accounts or public research will not show?
                <textarea
                  id="private-context"
                  name="private_context"
                  rows={4}
                  maxLength={1200}
                  placeholder="Optional: key contracts, signed pipeline, upcoming changes, disputes, unusual risks or opportunities."
                  defaultValue={String(valuationAnswers.private_context ?? "")}
                />
                <span className="field-hint">
                  Keep this to a short note. It is optional and only used for valuation-relevant context that accounts and public research cannot show.
                </span>
              </label>
            </details>
              </fieldset>

              <section className="valuation-next-step-note" aria-labelledby="valuation-next-step-title">
                <div>
                  <span className="eyebrow">What happens next</span>
                  <h3 id="valuation-next-step-title">One quick earnings check, then AccountIQ prepares the report</h3>
                  <p>
                    After these five answers, the only remaining customer step is to confirm any
                    obvious one-off earnings adjustments. AccountIQ derives WACC, terminal growth,
                    forecast mechanics and the research/source trail for you.
                  </p>
                </div>
                <ol aria-label="Valuation preparation steps">
                  <li>
                    <strong>Now</strong>
                    <span>Five private facts</span>
                  </li>
                  <li>
                    <strong>Next</strong>
                    <span>Quick earnings check</span>
                  </li>
                  <li>
                    <strong>Then</strong>
                    <span>Research, model and report pack</span>
                  </li>
                </ol>
              </section>
            </>
          ) : (
            <>
              <section className="valuation-review-intro" aria-labelledby="earnings-review-title">
                <span className="eyebrow">Private facts complete</span>
                <h2 id="earnings-review-title">One final check before we prepare the report</h2>
                <p>
                  Review any candidate earnings adjustments already listed for this business, or
                  add one only if the uploaded accounts include a clear one-off, owner-specific or
                  non-operating item. This is separate from the five private answers because it
                  checks the earnings bridge rather than asking you to estimate technical valuation
                  assumptions.
                </p>
              </section>

              <section className="earnings-review-reassurance" aria-label="Earnings review reassurance">
                <div>
                  <strong>This is a review, not a finance test</strong>
                  <span>
                    Keep a suggested adjustment only if it genuinely applies to this upload. Remove it,
                    leave it blank or do nothing if you are unsure.
                  </span>
                </div>
                <div>
                  <strong>Do not forecast here</strong>
                  <span>
                    Future growth, pipeline upside and normal trading costs stay out of this check.
                    AccountIQ handles forecast assumptions separately.
                  </span>
                </div>
                <div>
                  <strong>No extra required answers</strong>
                  <span>
                    The five private answers are already captured. This step only confirms whether
                    the uploaded earnings need obvious one-off adjustments.
                  </span>
                </div>
              </section>

              <section className="valuation-answer-summary" aria-labelledby="valuation-answer-summary-title">
                <div className="valuation-answer-summary-header">
                  <div>
                    <span className="eyebrow">Captured from step 1</span>
                    <h3 id="valuation-answer-summary-title">Your five valuation answers</h3>
                    <p>
                      These are the private facts AccountIQ will use in the report. If anything
                      looks wrong, change the answers; otherwise you only need to check the earnings
                      adjustments below.
                    </p>
                  </div>
                  <button type="button" className="button button-secondary" onClick={goBack}>
                    Change answers
                  </button>
                </div>
                <dl>
                  {valuationAnswerSummary.map(([name, label]) => (
                    <div key={name}>
                      <dt>{label}</dt>
                      <dd>{valuationAnswerText(name, valuationAnswers[name])}</dd>
                    </div>
                  ))}
                </dl>
                {optionalValuationAnswers.length > 0 ? (
                  <div
                    className="valuation-context-summary"
                    aria-label="Research and private context to use"
                  >
                    <div>
                      <span className="eyebrow">Optional clues captured</span>
                      <h4>Research and private context to use</h4>
                      <p>
                        These do not add to the required five. They are shortcuts or private notes
                        AccountIQ will use to match the right business and explain valuation-relevant context.
                      </p>
                    </div>
                    <dl>
                      {optionalValuationAnswers.map((item) => (
                        <div key={item.name}>
                          <dt>{item.label}</dt>
                          <dd>{item.value}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                ) : null}
              </section>

              <section className="valuation-delivery-preview" aria-labelledby="valuation-delivery-preview-title">
                <div>
                  <span className="eyebrow">When you click prepare</span>
                  <h3 id="valuation-delivery-preview-title">No more required answers after this check</h3>
                  <p>
                    AccountIQ will turn your upload, five private answers and public-source research
                    into a professional valuation pack that explains the calculation trail.
                  </p>
                </div>
                <ul>
                  <li>
                    <strong>Research trail</strong>
                    <span>Business context, market evidence and source URLs retained for review.</span>
                  </li>
                  <li>
                    <strong>Valuation model</strong>
                    <span>DCF, multiples cross-check, sensitivity analysis and risk factors.</span>
                  </li>
                  <li>
                    <strong>Report pack</strong>
                    <span>Browser report plus downloadable PDF with cover, contents, report letter, prepared-by identity and basis of preparation.</span>
                  </li>
                </ul>
              </section>

              <fieldset>
                <legend>Check the earnings adjustments</legend>
                <p className="fieldset-intro">
                  Treat any pre-filled items as candidates. Keep only genuine one-off,
                  owner-specific or non-operating items that apply to this upload.
                  If you keep or add an adjustment, include a non-zero amount and a short rationale.
                </p>
                <div className="earnings-review-guide" aria-label="Earnings adjustment guidance">
                  <div>
                    <strong>Usually worth adjusting</strong>
                    <ul>
                      <li>One-off legal, restructuring or relocation costs</li>
                      <li>Owner salary that is clearly above or below market</li>
                      <li>Non-operating income, assets or expenses</li>
                    </ul>
                  </div>
                  <div>
                    <strong>Usually leave alone</strong>
                    <ul>
                      <li>Normal wages, rent, materials and recurring overheads</li>
                      <li>Expected future growth or pipeline assumptions</li>
                      <li>Anything already included in the uploaded accounts</li>
                    </ul>
                  </div>
                </div>
                {normalisations.length === 0 ? (
                  <p className="empty-state">No candidate adjustments are listed. Add one only if it is relevant.</p>
                ) : null}
                {normalisations.map((row) => (
                  <div className="normalisation-row" key={row.id}>
                    <label>
                      Label
                      <input
                        value={row.label}
                        maxLength={120}
                        onChange={(event) => updateNormalisation(row.id, "label", event.target.value)}
                      />
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
                        maxLength={300}
                        onChange={(event) => updateNormalisation(row.id, "rationale", event.target.value)}
                      />
                    </label>
                    <button type="button" className="button button-secondary" onClick={() => removeNormalisation(row.id)}>
                      Remove
                    </button>
                  </div>
                ))}
                <button type="button" className="button button-secondary" onClick={addNormalisation}>
                  Add an adjustment
                </button>
              </fieldset>

              <details className="advanced-valuation-details">
                <summary>Optional: adjust figures we should use</summary>
                <p>
                  Most people can leave these blank. Use them only when you know the uploaded
                  accounts need an override; otherwise AccountIQ uses the financial statements,
                  your five answers and researched market evidence.
                </p>
                <div className="valuation-question-grid">
                  <label htmlFor="replacement-manager-cost">
                    Annual replacement manager cost ($)
                    <input
                      id="replacement-manager-cost"
                      name="replacement_manager_cost"
                      type="number"
                      min="0"
                      step="1000"
                      defaultValue={String(valuationReviewAnswers.replacement_manager_cost ?? "")}
                    />
                    <span className="field-hint">
                      Only needed if owner pay should be normalised to an external manager cost.
                    </span>
                  </label>
                  <label htmlFor="debt-override">
                    Interest-bearing debt at valuation date ($)
                    <input
                      id="debt-override"
                      name="debt_override"
                      type="number"
                      min="0"
                      step="1000"
                      defaultValue={String(valuationReviewAnswers.debt_override ?? "")}
                    />
                    <span className="field-hint">
                      Only needed if the uploaded statements do not show the debt balance to use.
                    </span>
                  </label>
                  <label htmlFor="surplus-assets">
                    Surplus or non-operating assets ($)
                    <input
                      id="surplus-assets"
                      name="surplus_assets"
                      type="number"
                      min="0"
                      step="1000"
                      defaultValue={String(valuationReviewAnswers.surplus_assets ?? "")}
                    />
                    <span className="field-hint">
                      Only include assets not required to operate the business.
                    </span>
                  </label>
                  <label htmlFor="custom-growth-rate">
                    Specific supported annual revenue growth (%)
                    <input
                      id="custom-growth-rate"
                      name="custom_growth_rate"
                      type="number"
                      min="-50"
                      max="100"
                      step="0.1"
                      defaultValue={String(valuationReviewAnswers.custom_growth_rate ?? "")}
                    />
                    <span className="field-hint">
                      Leave blank unless you have a specific supported forecast; otherwise we use
                      your outlook and uploaded revenue history.
                    </span>
                  </label>
                </div>
              </details>
            </>
          )}
        </>
      )}

      <div className="wizard-actions">
        <button type="button" className="button button-secondary" onClick={goBack}>
          Back
        </button>
        <button type="submit" className="button button-primary" disabled={loading}>
          {loading
            ? "Preparing..."
            : valuationStage === "questions"
              ? "Review earnings adjustments"
              : "Research & prepare valuation"}
        </button>
      </div>
    </form>
  );
}
