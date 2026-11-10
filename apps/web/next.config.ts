import type { NextConfig } from "next";
import { IS_PRIMARY_SITE } from "./lib/brands";

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
  // Keep auth and browser requests on the visited domain, including the apex alias.
  env: { NEXT_PUBLIC_API_BASE_URL: "" },
  async redirects() {
    return IS_PRIMARY_SITE ? [] : [
      { source: "/guides/:path*", destination: "/articles", permanent: false },
      { source: "/skills/:path*", destination: "/articles", permanent: false },
    ];
  },
  async rewrites() {
    return { beforeFiles: IS_PRIMARY_SITE ? [] : [
      { source: "/favicon.ico", destination: "/brand-icon" },
      { source: "/icon.png", destination: "/brand-icon" },
      { source: "/apple-icon.png", destination: "/brand-icon" },
      { source: "/icon.svg", destination: `/brands/${process.env.NEXT_PUBLIC_SITE_ID}.svg` },
    ], afterFiles: [
      {
        source: "/api/:path*",
        destination: `${internalApiBaseUrl}/api/:path*`,
      },
    ], fallback: [] };
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
