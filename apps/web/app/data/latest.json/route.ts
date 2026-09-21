import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";

export const dynamic = "force-dynamic";

function etagForStat(stat: fs.Stats): string {
  return `W/"${Math.trunc(stat.mtimeMs).toString(16)}-${stat.size.toString(16)}"`;
}

function matchesIfNoneMatch(headerValue: string | null, etag: string): boolean {
  if (!headerValue) return false;
  const normalizedEtag = etag.replace(/^W\//, "");
  return headerValue
    .split(",")
    .map((value) => value.trim().replace(/^W\//, ""))
    .some((value) => value === normalizedEtag || value === "*");
}

function notModified(etag: string, maxAge: number): NextResponse {
  return new NextResponse(null, {
    status: 304,
    headers: {
      ETag: etag,
      "Cache-Control": `public, max-age=${maxAge}, stale-while-revalidate=300`,
      "Access-Control-Allow-Origin": "*",
    },
  });
}

export async function GET(request: NextRequest) {
  const ifNoneMatch = request.headers.get("if-none-match");
  const dataPath = path.join(process.cwd(), "public", "data", "latest.json");
  try {
      const stat = await fs.promises.stat(dataPath);
      const etag = etagForStat(stat);
      if (matchesIfNoneMatch(ifNoneMatch, etag)) {
        return notModified(etag, 60);
      }
      const body = Readable.toWeb(fs.createReadStream(dataPath)) as ReadableStream;
      return new Response(body, {
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
          "Access-Control-Allow-Origin": "*",
          ETag: etag,
        },
      });
  } catch {
    // fallback to internal API
  }

  // Keep the fallback chain identical to lib/api.ts, lib/snapshot-catalog.ts
  // and next.config.ts: local development assumes the API runs on the host.
  const internalApiBase =
    process.env.INTERNAL_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://127.0.0.1:8000";
  try {
    // Forward the conditional request so the API's own 304 handling is preserved.
    const forwardHeaders: Record<string, string> = { Accept: "application/json" };
    if (ifNoneMatch) {
      forwardHeaders["If-None-Match"] = ifNoneMatch;
    }
    const res = await fetch(`${internalApiBase}/data/latest.json`, {
      headers: forwardHeaders,
      next: { revalidate: 60 },
    });
    if (res.status === 304) {
      const upstreamEtag = res.headers.get("etag") || "";
      if (upstreamEtag) {
        return notModified(upstreamEtag, 60);
      }
      return new NextResponse(null, { status: 304 });
    }
    // Note: res.ok is false for 304, so it is handled above explicitly.
    if (res.ok) {
      const data = await res.text();
      const headers: Record<string, string> = {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
        "Access-Control-Allow-Origin": "*",
      };
      const upstreamEtag = res.headers.get("etag");
      if (upstreamEtag) headers.ETag = upstreamEtag;
      return new NextResponse(data, { headers });
    }
    const errorBody = await res.text();
    const headers: Record<string, string> = {
      "Cache-Control": "no-store",
      "Content-Type": res.headers.get("content-type") || "application/json; charset=utf-8",
    };
    const retryAfter = res.headers.get("retry-after");
    if (retryAfter) headers["Retry-After"] = retryAfter;
    return new NextResponse(errorBody || JSON.stringify({ error: "Snapshot feed unavailable" }), {
      status: res.status,
      headers,
    });
  } catch {
    return NextResponse.json({ error: "Snapshot feed upstream unavailable" }, { status: 502 });
  }
}
