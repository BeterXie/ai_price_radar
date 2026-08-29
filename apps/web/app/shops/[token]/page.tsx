import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArrowSquareOut, Calendar, Clock, ShieldCheck } from "@phosphor-icons/react/ssr";
import { OfferTable } from "@/components/offer-table";
import { PageHero, SectionIntro } from "@/components/page-shell";
import { JsonLd, breadcrumbJsonLd } from "@/components/structured-data";
import { getShop } from "@/lib/api";
import { exactTime, relativeTime } from "@/lib/format";

export const dynamic = "force-dynamic";

const SITE_URL = "https://ai.pricememo.cn";

export async function generateMetadata({ params }: { params: Promise<{ token: string }> }): Promise<Metadata> {
  const { token } = await params;
  const shop = await getShop(token);

  if (!shop) {
    return {
      title: "店铺不存在",
      robots: { index: false, follow: true },
    };
  }

  const canonical = `${SITE_URL}/shops/${encodeURIComponent(shop.token)}`;
  const description = `查看 ${shop.name} 在 ${shop.source_platform_label} 的 AI 商品公开报价、库存、交付方式、更新时间和原始来源。`;

  return {
    title: `${shop.name}｜${shop.source_platform_label} AI 商品报价`,
    description,
    alternates: { canonical },
    robots: {
      index: shop.offer_count > 0,
      follow: true,
    },
    openGraph: {
      title: `${shop.name}｜${shop.source_platform_label} AI 商品报价`,
      description,
      url: canonical,
      type: "website",
    },
  };
}

export default async function ShopPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const shop = await getShop(token);
  if (!shop) notFound();
  const lastSeen = new Date(shop.last_seen_at || shop.last_success_at || shop.first_seen_at).getTime();
  const observedDays = Math.max(1, Math.floor((lastSeen - new Date(shop.first_seen_at).getTime()) / 86_400_000) + 1);
  const canonical = `${SITE_URL}/shops/${encodeURIComponent(shop.token)}`;
  const structuredData = [
    breadcrumbJsonLd([
      { name: "首页", path: "/" },
      { name: "来源店铺", path: "/shops" },
      { name: shop.name, path: canonical.replace(SITE_URL, "") },
    ]),
    {
      "@context": "https://schema.org",
      "@type": "WebPage",
      "@id": canonical,
      url: canonical,
      name: `${shop.name}｜${shop.source_platform_label} AI 商品报价`,
      description: `查看 ${shop.name} 在 ${shop.source_platform_label} 的 AI 商品公开报价、库存、交付方式、更新时间和原始来源。`,
      inLanguage: "zh-CN",
      isPartOf: { "@id": "https://ai.pricememo.cn/#website" },
      about: {
        "@type": "Thing",
        name: `${shop.source_platform_label} 公开店铺来源`,
      },
    },
  ];

  return (
    <main id="main-content" className="shell" data-vds-schema="v3.1" data-vds-layer="field" data-vds-action="source-identity health-context observed-offers outbound-verification">
      <JsonLd data={structuredData} />
      <PageHero eyebrow={`公开来源 · ${shop.source_platform_label}`} title={shop.name} compact meta={<><span>来源编号：{shop.token}</span><span>采集方式：{shop.source_kind_label}</span><span className="flex items-center gap-2"><Calendar size={17} />已收录 {observedDays} 天</span><span className="flex items-center gap-2"><Clock size={17} />最近成功更新：{relativeTime(shop.last_success_at)}</span><span>最近观测：{exactTime(shop.last_seen_at)}</span></>} actions={<a href={shop.source_url} target="_blank" rel="noreferrer nofollow" className="button-primary tactile">访问原店铺 <ArrowSquareOut size={17} /></a>} />
      <section className="evidence-callout mt-6">
        <div className="flex items-center gap-3"><ShieldCheck size={22} /><div><p className="text-sm font-semibold">来源更新状态：{shop.source_health.score} / 100 · {shop.source_health.label}</p><p className="mt-1 text-xs leading-5 text-black/50">{shop.source_health.reasons.join("；")}。这里只说明页面能否正常更新，不代表商家信誉或交易安全。</p></div></div>
      </section>
      <section className="py-12"><SectionIntro eyebrow="当前报价" title={`当前公开报价 · ${shop.offer_count}`} description="点开每条报价可核对交付、来源、原文与更新时间。" /><div className="mt-6"><OfferTable offers={shop.offers} /></div></section>
    </main>
  );
}
