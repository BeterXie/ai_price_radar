import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import "./globals.css";
import { BackToTop } from "@/components/back-to-top";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { CommunityPrompts } from "@/components/community-prompts";
import { NewFeatureModal } from "@/components/new-feature-modal";
import { LuckyCouponDrop } from "@/components/lucky-coupon-drop";
import { SiteNoticePrompt } from "@/components/site-notice";
import { SiteStructuredData } from "@/components/structured-data";
import { GoogleAnalytics } from "@/components/google-analytics";
import { getMeta } from "@/lib/api";
import { getSearchEngineVerificationMetadata } from "@/lib/search-engine-verification";
import { SITE_URL } from "@/lib/site";

export async function generateMetadata(): Promise<Metadata> {
  const verification = getSearchEngineVerificationMetadata();
  return {
    metadataBase: new URL(SITE_URL),
    title: { default: "AI Price Memory (AI Price Radar) · PriceMemo", template: "%s · AI Price Memory · AI Price Radar · PriceMemo" },
    description: "聚合公开 AI 订阅商品报价，比较价格、库存、来源和更新时间。",
    openGraph: { siteName: "AI Price Memory / AI Price Radar", locale: "zh_CN", type: "website" },
    robots: {
      index: true,
      follow: true,
      googleBot: {
        index: true,
        follow: true,
        "max-video-preview": -1,
        "max-image-preview": "large",
        "max-snippet": -1,
      },
    },
    icons: {
      icon: [
        { url: "/favicon.ico", sizes: "any" },
        { url: "/icon.svg", type: "image/svg+xml" },
        { url: "/icon.png", type: "image/png", sizes: "512x512" },
      ],
      apple: [
        { url: "/apple-icon.png", sizes: "180x180", type: "image/png" },
      ],
      shortcut: "/favicon.ico",
    },
    ...(verification ? { verification } : {}),
  };
}

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const meta = await getMeta().catch(() => null);
  const advertiseEnabled = Boolean(meta?.advertise_enabled);

  return (
    <html lang="zh-CN" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <SiteStructuredData />
        <GoogleAnalytics />
        <a href="#page-content" className="skip-link">跳到主要内容</a>
        <SiteNoticePrompt notice={meta?.site_notice} />
        <SiteHeader advertiseEnabled={advertiseEnabled} />
        <div id="page-content" tabIndex={-1}>{children}</div>
        <BackToTop />
        <SiteFooter advertiseEnabled={advertiseEnabled} />
        <CommunityPrompts communityNotice={meta?.community_notice} />
        <NewFeatureModal />
        <LuckyCouponDrop />
      </body>
    </html>
  );
}
