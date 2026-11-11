import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type ProxyContext = {
  params: Promise<{ path: string[] }>;
};

const MAX_BODY_BYTES = 26 * 1024 * 1024;
const FASTAPI_ORIGIN = process.env.FASTAPI_ORIGIN ?? "http://127.0.0.1:8765";
const HOP_BY_HOP_HEADERS = [
  "connection",
  "content-encoding",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
];

function proxyHeaders(headers: Headers) {
  const nextHeaders = new Headers(headers);
  for (const header of HOP_BY_HOP_HEADERS) {
    nextHeaders.delete(header);
  }
  return nextHeaders;
}

async function proxy(request: NextRequest, context: ProxyContext) {
  const { path } = await context.params;
  const target = new URL(`/${path.map(encodeURIComponent).join("/")}`, FASTAPI_ORIGIN);
  target.search = request.nextUrl.search;

  const method = request.method.toUpperCase();
  // FastAPI caps each file at 25 MB; refuse anything far bigger before buffering it here.
  if (Number(request.headers.get("content-length") ?? 0) > MAX_BODY_BYTES) {
    return Response.json({ detail: "Files can be up to 25 MB. Try a smaller export or split the file." }, { status: 413 });
  }
  const body = method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer();
  const response = await fetch(target, {
    method,
    headers: proxyHeaders(request.headers),
    body,
    cache: "no-store",
    redirect: "manual",
  });

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: proxyHeaders(response.headers),
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
