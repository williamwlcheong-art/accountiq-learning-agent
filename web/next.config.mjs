import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const backendOrigin = process.env.FASTAPI_ORIGIN || "http://127.0.0.1:8765";
const webRoot = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  devIndicators: false,
  outputFileTracingRoot: webRoot,
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
