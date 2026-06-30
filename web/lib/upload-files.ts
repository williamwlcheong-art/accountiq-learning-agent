export const ALLOWED_FINANCIAL_FILE_EXTENSIONS = [".pdf", ".xlsx", ".xls", ".xlsm", ".docx"] as const;
export const FINANCIAL_FILE_ACCEPT = ALLOWED_FINANCIAL_FILE_EXTENSIONS.join(",");

export function fileExtension(filename: string) {
  const dotIndex = filename.lastIndexOf(".");
  return dotIndex >= 0 ? filename.slice(dotIndex).toLowerCase() : "";
}

export function validateFinancialFile(file: File) {
  const extension = fileExtension(file.name);
  if (ALLOWED_FINANCIAL_FILE_EXTENSIONS.includes(extension as (typeof ALLOWED_FINANCIAL_FILE_EXTENSIONS)[number])) {
    return "";
  }
  return `Only PDF, Excel, and Word files are accepted. Got: ${extension || "unknown"}.`;
}
