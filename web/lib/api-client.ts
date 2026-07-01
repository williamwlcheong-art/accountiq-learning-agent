import type { ApiErrorBody } from "@/types/domain";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/backend";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.clone().json()) as ApiErrorBody;
      if (body.detail) message = body.detail;
    } catch {
      const text = await response.text();
      if (text) message = text;
    }
    throw new ApiError(response.status, message);
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
