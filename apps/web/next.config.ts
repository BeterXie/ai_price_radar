import type { NextConfig } from "next";

// Next.js resolves `rewrites()` at build time and bakes the destination into
// routes-manifest.json, so this value must be correct when the image/standalone
// bundle is built — a runtime env var alone cannot change it.
//
// `INTERNAL_API_BASE_URL` is the same name used by every other server-side
// module (lib/api.ts, route handlers) and by docker-compose. Production builds
// pass it explicitly (Dockerfile ARG / deploy script); the default keeps local
// development working, where the API runs on the host at 127.0.0.1:8000.
const internalApiBaseUrl = (
  process.env.INTERNAL_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: process.cwd(),
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${internalApiBaseUrl}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
