import { writeFile } from "node:fs/promises";

const origin = process.env.FASTAPI_ORIGIN ?? "http://127.0.0.1:8765";
const response = await fetch(`${origin}/openapi.json`);

if (!response.ok) {
  throw new Error(`Failed to fetch OpenAPI: ${response.status} ${response.statusText}`);
}

await writeFile(new URL("../openapi.json", import.meta.url), await response.text());
console.log(`Saved OpenAPI schema from ${origin}`);
