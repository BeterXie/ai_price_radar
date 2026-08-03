import type { Metadata } from "next";
import { CockpitJsonConverter } from "@/components/guides/cockpit-json-converter";

export const metadata: Metadata = {
  title: "JSON 转 Cockpit 在线工具",
  description: "在浏览器本地把常见 ChatGPT Session、CPA、Sub2 或 Codex JSON 转成 Cockpit Tools 可导入格式，不上传凭证。",
  alternates: { canonical: "/tools/json-to-cockpit" },
  openGraph: {
    title: "JSON 转 Cockpit 在线工具 · AI Price Radar",
    description: "浏览器本地转换，不上传 token，不写入站内存储。",
    url: "/tools/json-to-cockpit",
  },
};

export default function JsonToCockpitPage() {
  return <CockpitJsonConverter />;
}
