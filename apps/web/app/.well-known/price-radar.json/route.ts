import { NextResponse } from "next/server";

export const dynamic = "force-static";
export const revalidate = 300;

export function GET() {
  const data = {
    schema_version: "price-radar.discovery.v1",
    name: "AI Price Radar (PriceMemo)",
    description: "PriceMemo standard AI product minimum prices, Top 5 offers, and immutable snapshot feed for agents, scripts, and developers.",
    latest_url: "https://ai.pricememo.cn/data/latest.json",
    schema_url: "https://ai.pricememo.cn/price-radar-v1.schema.json",
    documentation_url: "https://ai.pricememo.cn/price-radar-api.md",
    refresh_interval_seconds: 300,
    authentication: "none",
    license: "PriceMemo public data terms",
    homepage: "https://ai.pricememo.cn"
  };

  return NextResponse.json(data, {
    headers: {
      "Cache-Control": "public, max-age=300, stale-while-revalidate=600",
      "Access-Control-Allow-Origin": "*",
    },
  });
}
