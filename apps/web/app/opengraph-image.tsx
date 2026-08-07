import { ImageResponse } from "next/og";

export const alt = "AI Price Radar public AI subscription price comparison";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#f7f7fc",
          color: "#171a2b",
          padding: "72px 80px",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 22, fontSize: 30, fontWeight: 700 }}>
          <div style={{ width: 64, height: 64, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 14, background: "#171a2b" }}>
            <div style={{ width: 36, height: 36, display: "flex", border: "4px solid #74e1ff", borderRadius: 999 }} />
          </div>
          AI Price Radar
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ maxWidth: 980, fontSize: 82, lineHeight: 0.98, letterSpacing: "-5px", fontWeight: 750 }}>
            Public AI prices, checked against the source.
          </div>
          <div style={{ fontSize: 28, color: "#697086" }}>Price / Stock / Delivery / Update time</div>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 23 }}>
          <span>ai.pricememo.cn</span>
          <span style={{ padding: "12px 18px", borderRadius: 10, background: "#74e1ff" }}>Verification over promotion</span>
        </div>
      </div>
    ),
    size,
  );
}
