import crypto from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export const dynamic = "force-dynamic";

function etagFor(body: string): string {
  return `"${crypto.createHash("sha256").update(body).digest("hex").slice(0, 16)}"`;
}

function matchesIfNoneMatch(headerValue: string | null, etag: string): boolean {
  if (!headerValue) return false;
  return headerValue
    .split(",")
    .map((value) => value.trim().replace(/^W\//, ""))
    .some((value) => value === etag || value === "*");
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
  if (fs.existsSync(dataPath)) {
    try {
      const content = fs.readFileSync(dataPath, "utf-8");
      const etag = etagFor(content);
      if (matchesIfNoneMatch(ifNoneMatch, etag)) {
        return notModified(etag, 60);
      }
      return new NextResponse(content, {
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
  }

  const internalApiBase = process.env.INTERNAL_API_BASE_URL || "http://api:8000";
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
      headers.ETag = upstreamEtag || etagFor(data);
      return new NextResponse(data, { headers });
    }
  } catch {
    // ignore
  }

  return NextResponse.json({ error: "Snapshot feed not ready" }, { status: 404 });
}
