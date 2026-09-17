import crypto from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export const dynamic = "force-dynamic";

const IMMUTABLE_MAX_AGE = 31536000;

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
  // Public links are published as `<id>.json`; strip the suffix before
  // sanitizing, otherwise "1234.json" becomes the id "1234json".
  const rawId = snapshot_id.replace(/\.json$/i, "");
  const safeId = rawId.replace(/[^a-zA-Z0-9_\-]/g, "");
  if (!safeId) {
    return NextResponse.json({ error: "Invalid snapshot ID" }, { status: 400 });
  }

  const ifNoneMatch = request.headers.get("if-none-match");
  const snapshotPath = path.join(
    process.cwd(),
    "public",
    "data",
    "v1",
    "snapshots",
    `${safeId}.json`
  );

  if (fs.existsSync(snapshotPath)) {
    try {
      const content = fs.readFileSync(snapshotPath, "utf-8");
      const etag = etagFor(content);
      if (matchesIfNoneMatch(ifNoneMatch, etag)) {
        return notModified(etag);
      }
      return new NextResponse(content, {
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": `public, max-age=${IMMUTABLE_MAX_AGE}, immutable`,
          "Access-Control-Allow-Origin": "*",
          ETag: etag,
        },
      });
    } catch {
      // fallback
    }
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
      headers.ETag = res.headers.get("etag") || etagFor(data);
      return new NextResponse(data, { headers });
    }
  } catch {
    // ignore
  }

  return NextResponse.json({ error: `Snapshot ${safeId} not found` }, { status: 404 });
}
