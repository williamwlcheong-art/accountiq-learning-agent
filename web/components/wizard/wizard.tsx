"use client";

import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { LogoutButton } from "@/components/auth/logout-button";
import { IntakeForm, type IntakeDraft } from "@/components/wizard/intake-form";
import { ReportStatusCard } from "@/components/wizard/report-status-card";
import {
  ReportTypePicker,
  SELF_SERVE_REPORT_TYPE,
  type WizardReportType,
} from "@/components/wizard/report-type-picker";
import { ApiError, apiFetch, postForm, postJson } from "@/lib/api-client";
import { FINANCIAL_FILE_ACCEPT, validateFinancialFile } from "@/lib/upload-files";
import type { CurrentUser } from "@/types/domain";

type WizardStep = "upload" | "processing" | "financial-review" | "report-type" | "intake" | "status";

type UploadResult = {
  company_id: number;
  document_id: number;
  document_ids?: number[];
  filenames?: string[];
  status: string;
  demo_mode: boolean;
};

type GenerateResult = {
  report_id: number;
  status: string;
};

type WizardDocumentStatus = {
  id: number;
  extraction_status: "pending" | "processing" | "done" | "failed" | string;
  message: string;
  demo_mode: boolean;
};

type FinancialReviewSource = {
  document_id: number;
  filename: string;
  value: number;
  currency: string;
  confidence: number | null;
};

type FinancialReviewConflict = {
  id: string;
  statement: string;
  row_key: string;
  row_label: string;
  period: string;
  suggested_document_id: number;
  selected_document_id: number;
  resolved: boolean;
  sources: FinancialReviewSource[];
};

type BalanceSheetReview = {
  ready: boolean;
  warnings: string[];
  issues: string[];
  periods: Array<{
    period: string;
    classifications: Array<{ key: string; label: string; value: number; source_filename: string }>;
    missing_categories: string[];
    unclassified_lines: string[];
    checks: Array<{ name: string; status: string; difference: number }>;
  }>;
};

type FinancialReview = {
  status: "ready" | "needs_review";
  document_ids: number[];
  conflicts: FinancialReviewConflict[];
  unresolved_conflict_ids: string[];
  invalid_override_ids: string[];
  warnings: string[];
  balance_sheet: BalanceSheetReview;
};

type WizardProps = {
  user: CurrentUser;
};

function financialFileKey(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function mergeFinancialFiles(existingFiles: File[], nextFiles: File[]) {
  const merged = [...existingFiles];
  const seen = new Set(existingFiles.map(financialFileKey));
  for (const file of nextFiles) {
    const key = financialFileKey(file);
    if (seen.has(key)) continue;
    merged.push(file);
    seen.add(key);
  }
  return merged;
}

function formatFinancialReviewValue(value: number, currency: string) {
  const formatted = new Intl.NumberFormat("en-NZ", {
    maximumFractionDigits: 0,
  }).format(value);
  return currency === "NZD" ? `$${formatted}` : `${currency} ${formatted}`;
}

export function Wizard({ user }: WizardProps) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<WizardStep>("upload");
  const [businessName, setBusinessName] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [draggingFile, setDraggingFile] = useState(false);
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [documentStatus, setDocumentStatus] = useState<WizardDocumentStatus | null>(null);
  const [financialReview, setFinancialReview] = useState<FinancialReview | null>(null);
  const [financialReconciliationOverrides, setFinancialReconciliationOverrides] = useState<Record<string, number>>({});
  const [reportType, setReportType] = useState<WizardReportType | null>(null);
  const [intakeDrafts, setIntakeDrafts] = useState<Partial<Record<WizardReportType, IntakeDraft>>>({});
  const [reportId, setReportId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (step !== "processing" || !upload) return;
    let cancelled = false;

    async function loadDocumentStatus() {
      try {
        const documentIds = upload!.document_ids?.length
          ? upload!.document_ids
          : [upload!.document_id];
        const statuses = await Promise.all(
          documentIds.map((documentId) =>
            apiFetch<WizardDocumentStatus>(`/wizard/document/${documentId}/status`),
          ),
        );
        if (cancelled) return;
        const failedStatus = statuses.find((status) => status.extraction_status === "failed");
        const waitingStatus = statuses.find((status) => status.extraction_status !== "done");
        const doneCount = statuses.filter((status) => status.extraction_status === "done").length;
        const aggregateStatus = failedStatus ?? waitingStatus ?? statuses[statuses.length - 1];
        setDocumentStatus({
          ...aggregateStatus,
          message:
            statuses.length > 1
              ? `${doneCount} of ${statuses.length} financial files ready. ${
                  failedStatus?.message ??
                  waitingStatus?.message ??
                  "All financial statements are ready."
                }`
              : aggregateStatus.message,
        });
        if (statuses.every((status) => status.extraction_status === "done")) {
          const financialReviewResult = await postJson<FinancialReview>("/wizard/financial-review", {
            company_id: upload!.company_id,
            source_document_ids: documentIds,
          });
          if (cancelled) return;
          const suggestedOverrides = Object.fromEntries(
            financialReviewResult.conflicts.map((conflict) => [
              conflict.id,
              conflict.suggested_document_id,
            ]),
          );
          setFinancialReview(financialReviewResult);
          setFinancialReconciliationOverrides(suggestedOverrides);
          setError("");
          setReportType((current) => current ?? SELF_SERVE_REPORT_TYPE);
          setStep(
            financialReviewResult.unresolved_conflict_ids.length > 0
              ? "financial-review"
              : "report-type",
          );
        } else if (failedStatus) {
          setError(failedStatus.message);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        setError(err instanceof Error ? err.message : "We could not check the uploaded file.");
      }
    }

    const interval = window.setInterval(loadDocumentStatus, 2000);
    loadDocumentStatus();
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [router, step, upload]);

  function handleAuthError(err: unknown) {
    if (err instanceof ApiError && err.status === 401) {
      router.replace("/login");
      return true;
    }
    return false;
  }

  function handleFiles(nextFiles: File[], { append = false }: { append?: boolean } = {}) {
    setError("");
    const selectedFiles = append ? mergeFinancialFiles(files, nextFiles) : nextFiles;
    if (selectedFiles.length === 0) {
      setFiles([]);
      return;
    }
    const invalidFile = selectedFiles.find((nextFile) => validateFinancialFile(nextFile));
    if (invalidFile) {
      setFiles([]);
      const validationError = validateFinancialFile(invalidFile);
      setError(validationError);
      return;
    }
    setFiles(selectedFiles);
  }

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    handleFiles(Array.from(event.target.files ?? []), { append: files.length > 0 });
    event.currentTarget.value = "";
  }

  function dropFile(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDraggingFile(false);
    handleFiles(Array.from(event.dataTransfer.files ?? []), { append: files.length > 0 });
  }

  function removeSelectedFile(fileToRemove: File) {
    setError("");
    const removeKey = financialFileKey(fileToRemove);
    setFiles((currentFiles) => currentFiles.filter((file) => financialFileKey(file) !== removeKey));
  }

  async function submitUpload() {
    setError("");
    const name = businessName.trim();
    if (!name) {
      setError("Business name is required.");
      return;
    }
    if (files.length === 0) {
      setError("Please select at least one financial statement file.");
      return;
    }

    const body = new FormData();
    body.append("business_name", name);
    files.forEach((selectedFile) => {
      body.append("files", selectedFile);
    });

    setLoading(true);
    try {
      const result = await postForm<UploadResult>("/wizard/upload", body);
      setUpload(result);
      setDocumentStatus({
        id: result.document_id,
        extraction_status: result.status,
        message: result.demo_mode
          ? "Demo mode is reading your uploaded financials and using simulated public research and report assumptions for this test journey."
          : "We are reading the financial statements and checking the extracted figures.",
        demo_mode: result.demo_mode,
      });
      setStep("processing");
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
        source_document_id: upload.document_id,
        source_document_ids: upload.document_ids?.length ? upload.document_ids : [upload.document_id],
        financial_reconciliation_overrides: financialReconciliationOverrides,
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
    setFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setUpload(null);
    setDocumentStatus(null);
    setFinancialReview(null);
    setFinancialReconciliationOverrides({});
    setReportType(null);
    setIntakeDrafts({});
    setReportId(null);
    setError("");
  }

  const selectedFileLabel =
    files.length === 0
      ? ""
      : files.length === 1
        ? "1 financial statement selected"
        : `${files.length} financial statements selected`;
  const isFinancialReadinessError = /key valuation figures/i.test(error);
  const extractionFailed = step === "processing" && documentStatus?.extraction_status === "failed";

  return (
    <>
      <nav className="top-nav">
        <div className="nav-brand">
          <strong>AccountIQ</strong>
          <span>Step {step === "upload" || step === "processing" || step === "financial-review" ? "1" : step === "status" ? "3" : "2"} of 3</span>
        </div>
        <div className="nav-user">
          <span>{user.email}</span>
          <LogoutButton />
        </div>
      </nav>

      <main className="wizard-shell">
        {error ? (
          <div role="alert" className="alert alert-error">
            <p>{error}</p>
            {isFinancialReadinessError ? (
              <div className="alert-actions">
                <p>
                  Try uploading a clearer profit and loss statement or financial statements showing
                  revenue plus EBITDA or profit.
                </p>
                <button type="button" className="button button-secondary" onClick={reset}>
                  Upload clearer statements
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        {step === "upload" ? (
          <section className="wizard-card">
            <h1>Upload your financial statements</h1>
            <div className="upload-guidance-panel" aria-label="Best files for valuation and credit paper">
              <div>
                <span className="eyebrow">Best files for valuation or credit paper</span>
                <p>
                  Upload the statements you already have. AccountIQ reads the numbers first so
                  the report questions can stay short.
                </p>
              </div>
              <ul>
                <li>Profit and loss or income statement with revenue and profit/EBITDA</li>
                <li>Balance sheet with cash, borrowings and working-capital balances</li>
                <li>Upload multiple PDFs if the last 3-4 years are split across separate files</li>
              </ul>
            </div>
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
                <strong>Click or drag financial files here</strong>
                <span>PDF, Excel or Word - select one file, multi-select a 3-4 year pack, or add files one by one</span>
                <input
                  ref={fileInputRef}
                  id="financial-file"
                  type="file"
                  multiple
                  accept={FINANCIAL_FILE_ACCEPT}
                  onChange={chooseFile}
                />
              </label>
              {files.length > 0 ? (
                <div className="selected-financial-files" aria-live="polite">
                  <div className="selected-financial-files-header">
                    <p className="wizard-note">{selectedFileLabel}</p>
                    <button
                      type="button"
                      className="button button-secondary button-small"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      Add another file
                    </button>
                  </div>
                  <ul>
                    {files.map((selectedFile) => (
                      <li key={financialFileKey(selectedFile)}>
                        <span>
                          {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(1)} MB)
                        </span>
                        <button type="button" onClick={() => removeSelectedFile(selectedFile)}>
                          Remove
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
            <button className="button button-primary" onClick={submitUpload} disabled={loading}>
              {loading ? "Uploading..." : "Continue ->"}
            </button>
          </section>
        ) : null}

        {step === "processing" ? (
          <section className="wizard-card" aria-live="polite">
            <span className="eyebrow">Preparing your information</span>
            <h1>Reading your financial statements</h1>
            <p>
              {upload?.demo_mode
                ? "We are reading the uploaded financial statements and using simulated public research and report assumptions so you can test the journey without an API key."
                : "We are extracting the financial history, balance sheet and possible earnings adjustments before asking you anything else."}
            </p>
            <p className={`status-pill status-${documentStatus?.extraction_status ?? "processing"}`}>
              Status: {documentStatus?.extraction_status ?? "processing"}
            </p>
            <p className="wizard-note">
              {documentStatus?.message ?? "This usually takes a few moments."}
            </p>
            {extractionFailed ? (
              <div className="extraction-failure-help" aria-label="Upload guidance">
                  <strong>No report questions yet</strong>
                <p>
                  We have not asked the report questions because the report needs usable financial
                  history first. Upload a clearer file and AccountIQ will read it before asking for
                  the private business or lending facts.
                </p>
                <ul>
                  <li>Profit and loss or income statement showing revenue and profit/EBITDA</li>
                  <li>Balance sheet showing cash, borrowings and working-capital items</li>
                  <li>Ideally the last 3-4 financial years in one file or multiple PDFs</li>
                </ul>
                <button className="button button-secondary" onClick={reset}>
                  Upload clearer statements
                </button>
              </div>
            ) : null}
          </section>
        ) : null}

        {step === "financial-review" && financialReview ? (
          <section className="wizard-card" aria-live="polite">
            <span className="eyebrow">Financial review needed</span>
            <h1>Choose the source for overlapping figures</h1>
            <p>
              We found different values for the same financial year in more than one uploaded file.
              AccountIQ will use only the source you select below for each difference, and retain that
              source trail in the report.
            </p>
            <div className="upload-guidance-panel">
              <div>
                <span className="eyebrow">Balance sheet classification</span>
                <p>
                  {financialReview.balance_sheet.ready
                    ? "The extracted balance sheet has been classified into working-capital, debt, fixed-asset and equity categories."
                    : "Some balance-sheet categories need review. The report will disclose unavailable items rather than infer them."}
                </p>
              </div>
              {financialReview.balance_sheet.issues.length > 0 ? (
                <ul>
                  {financialReview.balance_sheet.issues.map((issue) => (
                    <li key={issue}>{issue}</li>
                  ))}
                </ul>
              ) : null}
            </div>
            <div className="report-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Financial line</th>
                    <th>Financial year</th>
                    <th>Source to use</th>
                  </tr>
                </thead>
                <tbody>
                  {financialReview.conflicts.map((conflict) => (
                    <tr key={conflict.id}>
                      <td>{conflict.row_label}</td>
                      <td>{conflict.period}</td>
                      <td>
                        <label htmlFor={`financial-conflict-${conflict.id}`} className="sr-only">
                          Choose a source for {conflict.row_label} in {conflict.period}
                        </label>
                        <select
                          id={`financial-conflict-${conflict.id}`}
                          value={financialReconciliationOverrides[conflict.id] ?? conflict.suggested_document_id}
                          onChange={(event) =>
                            setFinancialReconciliationOverrides((current) => ({
                              ...current,
                              [conflict.id]: Number(event.target.value),
                            }))
                          }
                        >
                          {conflict.sources.map((source) => (
                            <option key={source.document_id} value={source.document_id}>
                              {source.filename} — {formatFinancialReviewValue(source.value, source.currency)}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="wizard-actions">
              <button className="button button-secondary" onClick={reset}>
                Upload different statements
              </button>
              <button className="button button-primary" onClick={() => setStep("report-type")}>
                Continue with selected figures -&gt;
              </button>
            </div>
          </section>
        ) : null}

        {step === "report-type" ? (
          <section className="wizard-card">
            <h1>Choose your report</h1>
            <p className="wizard-note">
              Select the report you want from the same uploaded accounts. Valuation focuses on
              enterprise value; Bank Credit Paper adds public client research, lender questions,
              security, LVR and debt-capacity analysis.
            </p>
            {financialReview?.balance_sheet.periods.length ? (
              <div className="upload-guidance-panel" aria-label="Balance sheet review">
                <div>
                  <span className="eyebrow">Balance sheet review</span>
                  <p>
                    AccountIQ has classified the uploaded balance sheet for the valuation bridge and
                    credit debt-capacity analysis. Missing categories are shown as unavailable rather
                    than estimated.
                  </p>
                </div>
                {financialReview.balance_sheet.warnings.length ? (
                  <ul>
                    {financialReview.balance_sheet.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
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
              demoMode={upload.demo_mode}
              initialDraft={intakeDrafts[reportType]}
              onDraftChange={(draft) =>
                setIntakeDrafts((current) => ({
                  ...current,
                  [reportType]: draft,
                }))
              }
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
