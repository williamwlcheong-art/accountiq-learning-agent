import type { ApiErrorBody } from "@/types/domain";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/backend";

export class ApiError extends Error {
  status: number;
  detail: ApiErrorBody["detail"];

  constructor(status: number, message: string, detail?: ApiErrorBody["detail"]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    let detail: ApiErrorBody["detail"];
    try {
      const body = (await response.clone().json()) as ApiErrorBody;
      detail = body.detail;
      if (typeof detail === "string") message = detail;
      if (detail && typeof detail === "object" && typeof detail.message === "string") {
        message = detail.message;
      }
    } catch {
      const text = await response.text();
      if (text) message = text;
    }
    throw new ApiError(response.status, message, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function postForm<T>(path: string, body: FormData): Promise<T> {
  return apiFetch<T>(path, { method: "POST", body });
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
