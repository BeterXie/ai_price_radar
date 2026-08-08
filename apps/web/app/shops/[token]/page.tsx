import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArrowSquareOut, Calendar, Clock, ShieldCheck } from "@phosphor-icons/react/ssr";
import { OfferTable } from "@/components/offer-table";
import { PageHero, SectionIntro } from "@/components/page-shell";
import { getShop } from "@/lib/api";
import { exactTime, relativeTime } from "@/lib/format";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ token: string }> }): Promise<Metadata> {
  const { token } = await params;
  const shop = await getShop(token);
  return { title: shop ? `${shop.name}报价` : "店铺不存在" };
}

export default async function ShopPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const shop = await getShop(token);
  if (!shop) notFound();
  const lastSeen = new Date(shop.last_seen_at || shop.last_success_at || shop.first_seen_at).getTime();
  const observedDays = Math.max(1, Math.floor((lastSeen - new Date(shop.first_seen_at).getTime()) / 86_400_000) + 1);
  return (
    <main id="main-content" className="shell">
      <PageHero eyebrow={`店铺 / ${shop.token}`} title={shop.name} compact meta={<><span>来源平台：{shop.source_platform_label}</span><span>采集方式：{shop.source_kind_label}</span><span className="flex items-center gap-2"><Calendar size={17} />已收录 {observedDays} 天</span><span className="flex items-center gap-2"><Clock size={17} />最近一次成功更新：{relativeTime(shop.last_success_at)}</span><span>最近一次观测：{exactTime(shop.last_seen_at)}</span></>} actions={<a href={shop.source_url} target="_blank" rel="noreferrer nofollow" className="button-primary tactile">访问原店铺 <ArrowSquareOut size={17} /></a>} />
      <section className="surface-panel mt-6 border-l-4 !border-l-[color:var(--info)] p-5">
        <div className="flex items-center gap-3"><ShieldCheck size={22} /><div><p className="text-sm font-semibold">来源更新状态：{shop.source_health.score} / 100 · {shop.source_health.label}</p><p className="mt-1 text-xs leading-5 text-black/50">{shop.source_health.reasons.join("；")}。这里只说明页面能否正常更新，不代表商家信誉或交易安全。</p></div></div>
      </section>
      <section className="py-12"><SectionIntro eyebrow="当前报价" title={`当前公开报价 · ${shop.offer_count}`} description="点开每条报价可核对交付、来源、原文与更新时间。" /><div className="mt-6"><OfferTable offers={shop.offers} /></div></section>
    </main>
  );
}
