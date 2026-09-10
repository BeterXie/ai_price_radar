import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowRight, Clock, Package, Storefront } from "@phosphor-icons/react/ssr";
import { getMeta, getShopCards } from "@/lib/api";
import { JsonLd, breadcrumbJsonLd } from "@/components/structured-data";
import { DIRECTORY_PAGE_SIZE, getTotalPages, PaginationNav, parsePage } from "@/components/pagination-nav";
import { relativeTime } from "@/lib/format";

export const dynamic = "force-dynamic";
const SITE_URL = "https://ai.pricememo.cn";

export async function generateMetadata({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }): Promise<Metadata> {
  const params = await searchParams;
  return { title: "AI 来源店铺目录", description: "查看 AI Price Radar 收录的公开 AI 商品店铺，包含 16688、LDXP 等平台来源的报价数、库存和最近更新时间。", alternates: { canonical: `${SITE_URL}/shops` }, robots: { index: Object.keys(params).length === 0, follow: true } };
}

export default async function ShopsPage({ searchParams }: { searchParams: Promise<{ source_platform?: string; page?: string }> }) {
  const { source_platform = "", page: rawPage = "1" } = await searchParams;
  const page = parsePage(rawPage);
  const pageHref = (targetPage: number) => { const params = new URLSearchParams(); if (source_platform) params.set("source_platform", source_platform); params.set("page", String(targetPage)); return `/shops?${params}`; };
  const query = new URLSearchParams({ sort: "offer_count", offset: String((page - 1) * DIRECTORY_PAGE_SIZE), limit: String(DIRECTORY_PAGE_SIZE) });
  if (source_platform) query.set("source_platform", source_platform);
  const [{ items: shops, total }, meta] = await Promise.all([getShopCards(query.toString()), getMeta()]);
  const totalPages = getTotalPages(total, DIRECTORY_PAGE_SIZE);
  if (page > totalPages) redirect(pageHref(totalPages));
  const canonical = `${SITE_URL}/shops`;
  const structuredData = [breadcrumbJsonLd([{ name: "首页", path: "/" }, { name: "来源店铺", path: "/shops" }]), { "@context": "https://schema.org", "@type": "CollectionPage", "@id": canonical, url: canonical, name: "AI 来源店铺目录", description: "查看公开 AI 商品店铺的报价数、库存和最近更新时间。", isPartOf: { "@id": "https://ai.pricememo.cn/#website" }, mainEntity: { "@type": "ItemList", numberOfItems: shops.length, itemListElement: shops.map((shop, index) => ({ "@type": "ListItem", position: index + 1, name: shop.name, url: `${SITE_URL}/shops/${encodeURIComponent(shop.token)}` })) } }];

  return (
    <main id="main-content" className="container">
      <JsonLd data={structuredData} />
      <div className="page-content">
        <header className="page-intro"><span className="eyebrow">PUBLIC SOURCES</span><h1>公开店铺，<br /><span className="green-text">每条报价有出处。</span></h1><p>当前共收录 {total} 家有公开报价的店铺。查看来源平台、商品范围、库存和最近观测时间。</p></header>
        <nav className="directory-tabs" aria-label="来源平台筛选"><Link href="/shops" className={!source_platform ? "active" : ""}>全部来源</Link>{meta.source_platforms.filter((item) => item.id !== "dujiao_next").map((item) => <Link key={item.id} className={source_platform === item.id ? "active" : ""} href={`/shops?source_platform=${encodeURIComponent(item.id)}`}>{item.label}</Link>)}</nav>
        {shops.length ? <section className="directory-grid">{shops.map((shop) => <Link key={shop.token} href={`/shops/${encodeURIComponent(shop.token)}`} className="directory-card"><div className="directory-card-icon"><Storefront size={20} /></div><div className="directory-card-copy"><span className="eyebrow">{shop.source_platform_label}</span><h2>{shop.name}</h2><p>{shop.product_slugs.length ? `涉及 ${shop.product_slugs.slice(0,4).join("、")}${shop.product_slugs.length > 4 ? " 等" : ""}` : "公开 AI 商品来源"}</p><div className="directory-card-meta"><span><Package size={13} />{shop.offer_count} 条报价 · {shop.in_stock_count} 条有货</span><span><Clock size={13} />{relativeTime(shop.last_seen_at || shop.last_success_at)}</span></div></div><ArrowRight className="directory-arrow" size={18} /></Link>)}</section> : <div className="empty"><Storefront size={32} /><h3>暂无符合条件的店铺</h3><p>换一个来源平台再看看。</p></div>}
        <PaginationNav page={page} totalPages={totalPages} hrefForPage={pageHref} ariaLabel="店铺目录分页" />
      </div>
    </main>
  );
}
