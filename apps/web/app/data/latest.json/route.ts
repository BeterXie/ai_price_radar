import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const dataPath = path.join(process.cwd(), "public", "data", "latest.json");
  if (fs.existsSync(dataPath)) {
    try {
      const content = fs.readFileSync(dataPath, "utf-8");
      return new NextResponse(content, {
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
          "Access-Control-Allow-Origin": "*",
        },
      });
    } catch {
      // fallback to internal API
    }
  }

  const internalApiBase = process.env.INTERNAL_API_BASE_URL || "http://api:8000";
  try {
    const res = await fetch(`${internalApiBase}/data/latest.json`, {
      headers: { Accept: "application/json" },
      next: { revalidate: 60 },
    });
    if (res.ok) {
      const data = await res.text();
      return new NextResponse(data, {
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
          "Access-Control-Allow-Origin": "*",
        },
      });
    }
  } catch {
    // ignore
  }

  return NextResponse.json({ error: "Snapshot feed not ready" }, { status: 404 });
}
