import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";

export const dynamic = "force-dynamic";

const IMMUTABLE_MAX_AGE = 31536000;

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

function notModified(etag: string): NextResponse {
  return new NextResponse(null, {
    status: 304,
    headers: {
      ETag: etag,
      "Cache-Control": `public, max-age=${IMMUTABLE_MAX_AGE}, immutable`,
      "Access-Control-Allow-Origin": "*",
    },
  });
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ snapshot_id: string }> }
) {
  const { snapshot_id } = await params;
  // Public links are published as `<id>.json`; strip only that suffix, then
  // reject the whole value if any other character is invalid.
  const rawId = snapshot_id.replace(/\.json$/i, "");
  if (!/^[a-zA-Z0-9_-]{1,128}$/.test(rawId)) {
    return NextResponse.json({ error: "Invalid snapshot ID" }, { status: 400 });
  }
  const safeId = rawId;

  const ifNoneMatch = request.headers.get("if-none-match");
  const snapshotPath = path.join(
    process.cwd(),
    "public",
    "data",
    "v1",
    "snapshots",
    `${safeId}.json`
  );

  try {
      const stat = await fs.promises.stat(snapshotPath);
      const etag = etagForStat(stat);
      if (matchesIfNoneMatch(ifNoneMatch, etag)) {
        return notModified(etag);
      }
      const body = Readable.toWeb(fs.createReadStream(snapshotPath)) as ReadableStream;
      return new Response(body, {
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": `public, max-age=${IMMUTABLE_MAX_AGE}, immutable`,
          "Access-Control-Allow-Origin": "*",
          ETag: etag,
        },
      });
  } catch {
    // fallback to internal API
  }

  const internalApiBase = process.env.INTERNAL_API_BASE_URL || "http://api:8000";
  try {
    const forwardHeaders: Record<string, string> = { Accept: "application/json" };
    if (ifNoneMatch) {
      forwardHeaders["If-None-Match"] = ifNoneMatch;
    }
    const res = await fetch(`${internalApiBase}/data/v1/snapshots/${safeId}.json`, {
      headers: forwardHeaders,
    });
    if (res.status === 304) {
      const upstreamEtag = res.headers.get("etag") || "";
      if (upstreamEtag) {
        return notModified(upstreamEtag);
      }
      return new NextResponse(null, { status: 304 });
    }
    // Note: res.ok is false for 304, so it is handled above explicitly.
    if (res.ok) {
      const data = await res.text();
      const headers: Record<string, string> = {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": `public, max-age=${IMMUTABLE_MAX_AGE}, immutable`,
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
    return new NextResponse(errorBody || JSON.stringify({ error: `Snapshot ${safeId} unavailable` }), {
      status: res.status,
      headers,
    });
  } catch {
    return NextResponse.json({ error: "Snapshot feed upstream unavailable" }, { status: 502 });
  }
}
