import { ImageResponse } from "next/og";
import { getProductOgTitle } from "@/lib/product-seo";

export const alt = "AI product public price comparison";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const title = getProductOgTitle(slug);
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#12130f",
          color: "#f2f3ed",
          padding: "72px 80px",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18, fontSize: 27, color: "#cfff47" }}>
          <div style={{ width: 18, height: 18, display: "flex", borderRadius: 999, background: "#cfff47" }} />
          AI Price Radar
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ fontSize: 35, color: "#9da092" }}>PUBLIC PRICE COMPARISON</div>
          <div style={{ maxWidth: 1040, fontSize: 92, lineHeight: 0.98, letterSpacing: "-5px", fontWeight: 750 }}>{title}</div>
          <div style={{ fontSize: 29, color: "#b8baaf" }}>Compare price, stock, delivery and source updates.</div>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 23 }}>
          <span>ai.pricememo.cn</span>
          <span style={{ padding: "12px 18px", borderRadius: 10, background: "#cfff47", color: "#172000" }}>Check the source before buying</span>
        </div>
      </div>
    ),
    size,
  );
}
