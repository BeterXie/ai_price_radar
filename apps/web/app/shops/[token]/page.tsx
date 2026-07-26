import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArrowSquareOut, Calendar, Clock } from "@phosphor-icons/react/ssr";
import { OfferTable } from "@/components/offer-table";
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
    <main id="main-content" className="shell py-12">
      <section className="grid gap-8 border-b border-black pb-10 lg:grid-cols-[1fr_auto] lg:items-end">
        <div><p className="mono text-xs tracking-[.15em] text-black/45">店铺 / {shop.token}</p><h1 className="mt-4 text-6xl font-semibold tracking-[-.065em]">{shop.name}</h1><div className="mt-6 flex flex-wrap gap-5 text-sm text-black/55"><span className="flex items-center gap-2"><Calendar size={17} />已连续发现 {observedDays} 天</span><span className="flex items-center gap-2"><Clock size={17} />最近成功 {relativeTime(shop.last_success_at)}</span><span>最近发现：{exactTime(shop.last_seen_at)}</span><span>扫描状态：{shop.status}</span><span>{shop.consecutive_failures ? `连续失败 ${shop.consecutive_failures} 次` : "当前无连续扫描失败"}</span></div></div>
        <a href={shop.source_url} target="_blank" rel="noreferrer nofollow" className="tactile flex items-center gap-2 rounded-[10px] bg-[color:var(--ink)] px-5 py-3 text-sm text-white">访问原店铺 <ArrowSquareOut size={17} /></a>
      </section>
      <section className="py-12"><div className="mb-5"><p className="mono text-xs tracking-[.15em] text-black/45">当前报价</p><h2 className="mt-2 text-3xl font-semibold tracking-[-.04em]">当前公开报价 · {shop.offer_count}</h2></div><OfferTable offers={shop.offers} /></section>
    </main>
  );
}
