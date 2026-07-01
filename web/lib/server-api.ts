import { headers } from "next/headers";

const FASTAPI_ORIGIN = process.env.FASTAPI_ORIGIN ?? "http://127.0.0.1:8765";

export async function serverApiFetch<T>(path: string): Promise<T> {
  const incoming = await headers();
  const cookie = incoming.get("cookie") ?? "";

  const response = await fetch(`${FASTAPI_ORIGIN}${path}`, {
    headers: { cookie },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`FastAPI request failed: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}
