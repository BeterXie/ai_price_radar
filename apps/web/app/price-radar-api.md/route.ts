import { NextResponse } from "next/server";

export const dynamic = "force-static";
export const revalidate = 3600;

const DOC = `# AI Price Memory (PriceMemo) Snapshot Feed API

AI Price Memory provides a read-only public snapshot feed for autonomous agents, automated scripts, and developers.

Instead of scraping HTML or polling internal dynamic search routes, clients should consume this immutable snapshot feed.

---

## Quickstart for Agents

1. **Discovery**: Inspect \`/.well-known/price-radar.json\` to obtain the latest feed metadata.
2. **Fetch Pointer**: Send a \`GET\` request to \`https://ai.pricememo.cn/data/latest.json\`.
3. **Inspect Snapshot Pointer**:
   - \`snapshot_id\`: Unique timestamped identifier of the published catalog generation.
   - \`snapshot_url\`: URL of the immutable snapshot document.
   - \`published_at\`: ISO timestamp when this generation was published.
   - \`stale\`: Boolean indicating whether the snapshot is older than 2 hours.
4. **Download Snapshot**:
   - If \`snapshot_id\` has changed since your last poll, fetch \`snapshot_url\`.
   - If \`snapshot_id\` is identical, do not re-fetch; your local cache is current.
5. **Lookup Prices & Offers**:
   - Find products by \`slug\` (e.g., \`chatgpt-plus\`, \`claude-pro\`, \`deepseek-official\`).
   - Read \`min_price\` for the current minimum valid market price.
   - Read \`top_5_offers\` for the top 5 ranked offers (available, non-shared, comparable items prioritized).

---

## API Contract

| Endpoint | Method | Format | Description |
| :--- | :--- | :--- | :--- |
| \`/.well-known/price-radar.json\` | GET | JSON | RFC discovery metadata pointer |
| \`/price-radar-api.md\` | GET | Markdown | This documentation |
| \`/price-radar-v1.schema.json\` | GET | JSON Schema | Machine-verifiable JSON Schema contract |
| \`/data/latest.json\` | GET | JSON | Latest snapshot pointer (poll at most once per 60s) |
| \`/data/v1/snapshots/{id}.json\` | GET | JSON | Immutable snapshot dataset (cache indefinitely) |

---

## Caching & Rate Limits

- **No Authentication Required**: The public snapshot feed is completely open.
- **Poll Cadence**: Do not poll \`/data/latest.json\` faster than once every 60 seconds. The catalog snapshot updates approximately every 5 minutes.
- **Immutable Snapshots**: Each \`/data/v1/snapshots/{snapshot_id}.json\` document is strictly immutable. Set your HTTP cache to cache these responses indefinitely.
- **Respect Headers**: Support standard \`ETag\`, \`If-None-Match\`, and \`Cache-Control\` headers.

---

## Disclaimer

AI Price Memory is an independent data aggregation and price comparison tool. Always verify final prices, inventory, delivery methods, and warranties on the merchant platform before purchase.
`;

export function GET() {
  return new NextResponse(DOC, {
    headers: {
      "Content-Type": "text/markdown; charset=utf-8",
      "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
      "Access-Control-Allow-Origin": "*",
    },
  });
}
