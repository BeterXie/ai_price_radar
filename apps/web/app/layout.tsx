import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import "./globals.css";
import "./brands.css";
import "./brand-quotes.css";
import { BRAND, IS_PRIMARY_SITE, SITE_ID } from "@/lib/brands";
import { getSiteSettings } from "@/lib/site-content";
import { BackToTop } from "@/components/back-to-top";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { CommunityPrompts } from "@/components/community-prompts";
import { NewFeatureModal } from "@/components/new-feature-modal";
import { LuckyCouponDrop } from "@/components/lucky-coupon-drop";
import { SiteNoticePrompt } from "@/components/site-notice";
import { SiteStructuredData } from "@/components/structured-data";
import { SiteAnalytics } from "@/components/site-analytics";
import { getMeta } from "@/lib/api";
import { getSearchEngineVerificationMetadata } from "@/lib/search-engine-verification";
import { SITE_URL } from "@/lib/site";
import { version } from "@/package.json";

export async function generateMetadata(): Promise<Metadata> {
  const settings = await getSiteSettings().catch(() => null);
  const existingVerification = IS_PRIMARY_SITE ? getSearchEngineVerificationMetadata() : undefined;
  const verification = settings?.configured ? {
    ...(settings.google_verification ? { google: settings.google_verification } : {}),
    other: { ...existingVerification?.other, ...(settings.bing_verification ? { "msvalidate.01": settings.bing_verification } : {}), ...(settings.baidu_verification ? { "baidu-site-verification": settings.baidu_verification } : {}) },
  } : existingVerification;
  return {
    metadataBase: new URL(SITE_URL),
    other: { "application-version": version },
    title: { default: `AI 订阅比价 · ${BRAND.name}`, template: `%s · ${BRAND.name}` },
    description: "聚合公开 AI 订阅商品报价，比较价格、库存、来源和更新时间。",
    openGraph: { siteName: BRAND.name, locale: "zh_CN", type: "website" },
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
    icons: IS_PRIMARY_SITE ? {
      icon: [
        { url: "/favicon.ico", sizes: "any" },
        { url: "/icon.svg", type: "image/svg+xml" },
        { url: "/icon.png", type: "image/png", sizes: "512x512" },
      ],
      apple: [
        { url: "/apple-icon.png", sizes: "180x180", type: "image/png" },
      ],
      shortcut: "/favicon.ico",
    } : {
      icon: [{ url: `/brands/${SITE_ID}-favicon.ico`, sizes: "any" }, { url: `/brands/${SITE_ID}-32.png`, type: "image/png", sizes: "32x32" }],
      apple: { url: `/brands/${SITE_ID}-180.png`, type: "image/png", sizes: "180x180" },
      shortcut: `/brands/${SITE_ID}-favicon.ico`,
    },
    ...(verification ? { verification } : {}),
  };
}

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const meta = await getMeta().catch(() => null);
  const settings = await getSiteSettings().catch(() => null);
  const advertiseEnabled = Boolean(meta?.advertise_enabled);
  const relayHubEnabled = meta?.relay_hub_enabled !== false;

  return (
    <html lang="zh-CN" data-brand={SITE_ID} className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <SiteStructuredData />
        <SiteAnalytics {...(settings?.configured ? { measurementId: settings.ga_measurement_id, baiduId: settings.baidu_analytics_id } : IS_PRIMARY_SITE ? {} : { measurementId: "", baiduId: "" })} />
        <a href="#page-content" className="skip-link">跳到主要内容</a>
        <SiteNoticePrompt notice={meta?.site_notice} />
        <SiteHeader advertiseEnabled={advertiseEnabled} relayHubEnabled={relayHubEnabled} />
        <div id="page-content" tabIndex={-1}>{children}</div>
        <BackToTop />
        <SiteFooter advertiseEnabled={advertiseEnabled} />
        {IS_PRIMARY_SITE && <><CommunityPrompts communityNotice={meta?.community_notice} /><NewFeatureModal /><LuckyCouponDrop /></>}
      </body>
    </html>
  );
}
