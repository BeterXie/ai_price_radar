import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export function GET() {
  const key = process.env.INDEXNOW_KEY?.trim();
  if (!key) return new NextResponse("Not configured", { status: 404 });
  return new NextResponse(`${key}\n`, {
    headers: {
      "Cache-Control": "public, max-age=300",
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}
