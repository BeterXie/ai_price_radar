import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import "./globals.css";
import { BackToTop } from "@/components/back-to-top";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { CommunityPrompts } from "@/components/community-prompts";
import { NewFeatureModal } from "@/components/new-feature-modal";
import { SiteStructuredData } from "@/components/structured-data";
import { GoogleAnalytics } from "@/components/google-analytics";
import { getMeta } from "@/lib/api";

export const metadata: Metadata = {
  metadataBase: new URL("https://ai.pricememo.cn"),
  title: { default: "AI Price Radar · PriceMemo", template: "%s · AI Price Radar · PriceMemo" },
  description: "聚合公开 AI 订阅商品报价，比较价格、库存、来源和更新时间。",
  openGraph: { siteName: "AI Price Radar", locale: "zh_CN", type: "website" },
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const meta = await getMeta().catch(() => null);
  const advertiseEnabled = Boolean(meta?.advertise_enabled);

  return (
    <html lang="zh-CN" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <SiteStructuredData />
        <GoogleAnalytics />
        <a href="#page-content" className="skip-link">跳到主要内容</a>
        <SiteHeader advertiseEnabled={advertiseEnabled} />
        <div id="page-content" tabIndex={-1}>{children}</div>
        <BackToTop />
        <SiteFooter advertiseEnabled={advertiseEnabled} />
        <CommunityPrompts />
        <NewFeatureModal />
      </body>
    </html>
  );
}
