import { ImageResponse } from "next/og";
import { BRAND, SITE_ID } from "@/lib/brands";

export const dynamic = "force-static";

export function GET() {
  const background = { pricememo: "#283322", aiprice: "#17243c", aisi: "#8c3d26", pricein: "#174b29", openprice: "#191919" }[SITE_ID];
  return new ImageResponse(
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "100%", height: "100%", background, color: "white", fontSize: 220, fontWeight: 700 }}>{BRAND.mark}</div>,
    { width: 512, height: 512 },
  );
}
