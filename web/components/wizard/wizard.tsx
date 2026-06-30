"use client";

import { ChangeEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { LogoutButton } from "@/components/auth/logout-button";
import { IntakeForm } from "@/components/wizard/intake-form";
import { ReportStatusCard } from "@/components/wizard/report-status-card";
import { ReportTypePicker, type WizardReportType } from "@/components/wizard/report-type-picker";
import { ApiError, postForm, postJson } from "@/lib/api-client";
import { FINANCIAL_FILE_ACCEPT, validateFinancialFile } from "@/lib/upload-files";
import type { CurrentUser } from "@/types/domain";

type WizardStep = "upload" | "report-type" | "intake" | "status";

type UploadResult = {
  company_id: number;
  document_id: number;
  status: string;
};

type GenerateResult = {
  report_id: number;
  status: string;
};

type WizardProps = {
  user: CurrentUser;
};

export function Wizard({ user }: WizardProps) {
  const router = useRouter();
  const [step, setStep] = useState<WizardStep>("upload");
  const [businessName, setBusinessName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [reportType, setReportType] = useState<WizardReportType | null>(null);
  const [reportId, setReportId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function handleAuthError(err: unknown) {
    if (err instanceof ApiError && err.status === 401) {
      router.replace("/login");
      return true;
    }
    return false;
  }

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0] ?? null;
    setError("");
    if (!nextFile) {
      setFile(null);
      return;
    }
    const validationError = validateFinancialFile(nextFile);
    if (validationError) {
      setFile(null);
      setError(validationError);
      return;
    }
    setFile(nextFile);
  }

  async function submitUpload() {
    setError("");
    const name = businessName.trim();
    if (!name) {
      setError("Business name is required.");
      return;
    }
    if (!file) {
      setError("Please select a financial statement file.");
      return;
    }

    const body = new FormData();
    body.append("business_name", name);
    body.append("file", file);

    setLoading(true);
    try {
      const result = await postForm<UploadResult>("/wizard/upload", body);
      setUpload(result);
      setStep("report-type");
    } catch (err) {
      if (!handleAuthError(err)) {
        setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function generateReport(answers: Record<string, unknown>) {
    if (!upload || !reportType) {
      setError("Missing upload or report type.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const result = await postJson<GenerateResult>("/wizard/report/generate", {
        company_id: upload.company_id,
        report_type: reportType,
        intake_answers: answers,
      });
      setReportId(result.report_id);
      setStep("status");
    } catch (err) {
      if (!handleAuthError(err)) {
        setError(err instanceof Error ? err.message : "Failed to queue report.");
      }
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setStep("upload");
    setBusinessName("");
    setFile(null);
    setUpload(null);
    setReportType(null);
    setReportId(null);
    setError("");
  }

  return (
    <>
      <nav className="top-nav">
        <div className="nav-brand">
          <strong>AccountIQ</strong>
          <span>Step {step === "upload" ? "1" : step === "status" ? "3" : "2"} of 3</span>
        </div>
        <div className="nav-user">
          <span>{user.email}</span>
          <LogoutButton />
        </div>
      </nav>

      <main className="wizard-shell">
        {error ? (
          <div role="alert" className="alert alert-error">
            {error}
          </div>
        ) : null}

        {step === "upload" ? (
          <section className="wizard-card">
            <h1>Upload your financial statements</h1>
            <label htmlFor="business-name">
              Business name
              <input
                id="business-name"
                value={businessName}
                onChange={(event) => setBusinessName(event.target.value)}
                autoComplete="organization"
              />
            </label>
            <label htmlFor="financial-file">
              Financial statements
              <input id="financial-file" type="file" accept={FINANCIAL_FILE_ACCEPT} onChange={chooseFile} />
            </label>
            {file ? <p className="wizard-note">Selected: {file.name}</p> : null}
            <button className="button button-primary" onClick={submitUpload} disabled={loading}>
              {loading ? "Uploading..." : "Continue"}
            </button>
          </section>
        ) : null}

        {step === "report-type" ? (
          <section className="wizard-card">
            <h1>What report do you need?</h1>
            <ReportTypePicker selected={reportType} onSelect={setReportType} />
            <div className="wizard-actions">
              <button className="button button-secondary" onClick={() => setStep("upload")}>
                Back
              </button>
              <button className="button button-primary" onClick={() => setStep("intake")} disabled={!reportType}>
                Continue
              </button>
            </div>
          </section>
        ) : null}

        {step === "intake" && reportType && upload ? (
          <section className="wizard-card">
            <h1>Tell us about the business</h1>
            <IntakeForm
              reportType={reportType}
              companyId={upload.company_id}
              onBack={() => setStep("report-type")}
              onSubmit={generateReport}
              loading={loading}
            />
          </section>
        ) : null}

        {step === "status" && reportId ? (
          <>
            <ReportStatusCard reportId={reportId} userEmail={user.email} />
            <button className="button button-secondary wizard-reset" onClick={reset}>
              Upload another
            </button>
          </>
        ) : null}
      </main>
    </>
  );
}
