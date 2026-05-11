type QueueExtractionInput = {
  companyName: string;
  entityType: "listed" | "sme";
  originalFilename: string;
  reportType: string;
  storagePath: string;
};

export async function queueExtraction(input: QueueExtractionInput) {
  const baseUrl = process.env.EXTRACTOR_BASE_URL;
  const token = process.env.EXTRACTOR_SERVICE_TOKEN;

  if (!baseUrl || !token) {
    return null;
  }

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/extract`, {
    body: JSON.stringify({
      metadata: {
        company_name: input.companyName,
        entity_type: input.entityType,
        original_filename: input.originalFilename,
        report_type: input.reportType,
      },
      storage_object_path: input.storagePath,
    }),
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-Service-Token": token,
    },
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`Extractor queue failed: ${response.status}`);
  }

  return (await response.json()) as { job_id: number; status: string };
}
