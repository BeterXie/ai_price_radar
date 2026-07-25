import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import "./globals.css";
import { BackToTop } from "@/components/back-to-top";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

export const metadata: Metadata = {
  title: { default: "AI Price Radar", template: "%s · AI Price Radar" },
  description: "聚合公开 AI 订阅商品报价，比较价格、库存、来源和更新时间。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <SiteHeader />
        {children}
        <BackToTop />
        <SiteFooter />
      </body>
    </html>
  );
}
