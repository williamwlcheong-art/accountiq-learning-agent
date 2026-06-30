import type { NextConfig } from "next";

const fastapiOrigin = process.env.FASTAPI_ORIGIN ?? "http://127.0.0.1:8765";

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    root: process.cwd(),
  },
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${fastapiOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
