"use client";

import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
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
  checkout_url?: string | null;
};

type WizardProps = {
  user: CurrentUser;
};

export function Wizard({ user }: WizardProps) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<WizardStep>("upload");
  const [businessName, setBusinessName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [draggingFile, setDraggingFile] = useState(false);
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [reportType, setReportType] = useState<WizardReportType | null>(null);
  const [reportId, setReportId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const activeReportKey = `accountiq.activeReport.${user.id}`;

  useEffect(() => {
    const restore = window.setTimeout(() => {
      const savedReportId = Number.parseInt(window.localStorage.getItem(activeReportKey) ?? "", 10);
      if (Number.isInteger(savedReportId) && savedReportId > 0) {
        setReportId(savedReportId);
        setStep("status");
      }
    }, 0);
    return () => window.clearTimeout(restore);
  }, [activeReportKey]);

  function handleAuthError(err: unknown) {
    if (err instanceof ApiError && err.status === 401) {
      router.replace("/login");
      return true;
    }
    return false;
  }

  function handleFile(nextFile: File | null) {
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

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    handleFile(event.target.files?.[0] ?? null);
  }

  function dropFile(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDraggingFile(false);
    handleFile(event.dataTransfer.files?.[0] ?? null);
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
      const result = await postJson<GenerateResult>("/wizard/report/checkout", {
        company_id: upload.company_id,
        report_type: reportType,
        intake_answers: answers,
      });
      if (result.checkout_url) {
        window.location.href = result.checkout_url;
        return;
      }
      window.localStorage.setItem(activeReportKey, String(result.report_id));
      setReportId(result.report_id);
      setStep("status");
    } catch (err) {
      if (!handleAuthError(err)) {
        setError(err instanceof Error ? err.message : "Failed to start checkout.");
      }
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    window.localStorage.removeItem(activeReportKey);
    setStep("upload");
    setBusinessName("");
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setUpload(null);
    setReportType(null);
    setReportId(null);
    setError("");
  }

  const selectedFileLabel = file ? `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)` : "";

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
              Business name <span className="required" aria-hidden="true">*</span>
              <input
                id="business-name"
                value={businessName}
                onChange={(event) => setBusinessName(event.target.value)}
                placeholder="e.g. Acme Holdings Ltd"
                autoComplete="organization"
              />
            </label>
            <div className="wizard-upload-field">
              <span className="field-label">
                Financial statements <span className="required" aria-hidden="true">*</span>
              </span>
              <label
                className={draggingFile ? "drop-zone drag-over" : "drop-zone"}
                htmlFor="financial-file"
                onDragOver={(event) => {
                  event.preventDefault();
                  setDraggingFile(true);
                }}
                onDragLeave={() => setDraggingFile(false)}
                onDrop={dropFile}
              >
                <span className="drop-zone-icon" aria-hidden="true">
                  PDF
                </span>
                <strong>Click or drag file here</strong>
                <span>PDF or Excel - last 2-3 years preferred</span>
                <input
                  ref={fileInputRef}
                  id="financial-file"
                  type="file"
                  accept={FINANCIAL_FILE_ACCEPT}
                  onChange={chooseFile}
                />
              </label>
              {file ? <p className="wizard-note">{selectedFileLabel}</p> : null}
            </div>
            <button className="button button-primary" onClick={submitUpload} disabled={loading}>
              {loading ? "Uploading..." : "Continue ->"}
            </button>
          </section>
        ) : null}

        {step === "report-type" ? (
          <section className="wizard-card">
            <h1>What report do you need?</h1>
            <ReportTypePicker selected={reportType} onSelect={setReportType} />
            <div className="wizard-actions">
              <button className="button button-secondary" onClick={() => setStep("upload")}>
                {"<- Back"}
              </button>
              <button className="button button-primary" onClick={() => setStep("intake")} disabled={!reportType}>
                Continue -&gt;
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
              Upload another -&gt;
            </button>
          </>
        ) : null}
      </main>
    </>
  );
}
