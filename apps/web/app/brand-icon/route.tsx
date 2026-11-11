import { ImageResponse } from "next/og";
import { BRAND, SITE_ID } from "@/lib/brands";

export const dynamic = "force-static";

export function GET() {
  const background = { pricememo: "#283322", aiprice: "#10151b", aisi: "#8e3c35", pricein: "#c44318", openprice: "#191919" }[SITE_ID];
  return new ImageResponse(
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "100%", height: "100%", background, color: SITE_ID === "aiprice" ? "#7ce4dc" : "white", fontSize: 220, fontWeight: 700 }}>{BRAND.mark}</div>,
    { width: 512, height: 512 },
  );
}
