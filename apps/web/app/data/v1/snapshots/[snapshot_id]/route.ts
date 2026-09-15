import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ snapshot_id: string }> }
) {
  const { snapshot_id } = await params;
  const safeId = snapshot_id.replace(/[^a-zA-Z0-9_\-]/g, "");
  if (!safeId) {
    return NextResponse.json({ error: "Invalid snapshot ID" }, { status: 400 });
  }

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
      return new NextResponse(content, {
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "public, max-age=31536000, immutable",
          "Access-Control-Allow-Origin": "*",
        },
      });
    } catch {
      // fallback
    }
  }

  const internalApiBase = process.env.INTERNAL_API_BASE_URL || "http://api:8000";
  try {
    const res = await fetch(`${internalApiBase}/data/v1/snapshots/${safeId}.json`, {
      headers: { Accept: "application/json" },
    });
    if (res.ok) {
      const data = await res.text();
      return new NextResponse(data, {
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "public, max-age=31536000, immutable",
          "Access-Control-Allow-Origin": "*",
        },
      });
    }
  } catch {
    // ignore
  }

  return NextResponse.json({ error: `Snapshot ${safeId} not found` }, { status: 404 });
}
