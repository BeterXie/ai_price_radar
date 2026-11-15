import { NextResponse } from "next/server";
import { version } from "@/package.json";

export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({ status: "ok", version }, { headers: { "Cache-Control": "no-store" } });
}
