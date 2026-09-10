import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowRight, Clock, Package, Storefront } from "@phosphor-icons/react/ssr";
import { getProducts, getShopCards, getMeta } from "@/lib/api";
import { ProductCard } from "@/components/product-card";
import { JsonLd, breadcrumbJsonLd } from "@/components/structured-data";
import { DIRECTORY_PAGE_SIZE, getTotalPages, PaginationNav, parsePage } from "@/components/pagination-nav";
import { relativeTime } from "@/lib/format";

export const dynamic = "force-dynamic";
const SITE_URL = "https://ai.pricememo.cn";
const DISABLED_SOURCES = new Set(["dujiao_next"]);
const SOURCE_META: Record<string, { title: string; description: string; h1: string; intro: string }> = {
  "16688": { title: "16688 AI 商品与店铺报价｜ChatGPT、Codex、Claude、Gemini、Grok", description: "查看来自 16688 公开店铺的 ChatGPT、Codex、Claude、Gemini、Grok 商品报价、库存、店铺和最近更新时间。", h1: "16688 AI 商品与店铺报价", intro: "汇总来自 16688 公开店铺的 ChatGPT、Codex、Claude、Gemini、Grok 等公开报价，展示价格、库存、交付方式与更新时间。" },
  ldxp: { title: "LDXP AI 商品报价", description: "查看来自 LDXP 公开来源的 AI 订阅商品报价、库存和更新时间。", h1: "LDXP AI 商品报价", intro: "汇总来自 LDXP 来源的 AI 订阅公开报价，展示价格、库存与更新时间。" },
};
const getSourceMeta = (source: string) => SOURCE_META[source] ?? { title: `${source} AI 商品报价`, description: `查看来自 ${source} 来源的 AI 商品公开报价、库存和更新时间。`, h1: `${source} AI 商品报价`, intro: `汇总来自 ${source} 来源的 AI 订阅公开报价。` };

export async function generateMetadata({ params, searchParams }: { params: Promise<{ source: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }): Promise<Metadata> {
  const [{ source }, raw] = await Promise.all([params, searchParams]); if (DISABLED_SOURCES.has(source)) notFound(); const meta = getSourceMeta(source); const canonical = `${SITE_URL}/sources/${encodeURIComponent(source)}`; return { title: meta.title, description: meta.description, alternates: { canonical }, robots: { index: Object.keys(raw).length === 0, follow: true }, openGraph: { title: meta.title, description: meta.description, url: canonical, type: "website" } };
}

export default async function SourcePage({ params, searchParams }: { params: Promise<{ source: string }>; searchParams: Promise<{ page?: string }> }) {
  const { source } = await params; if (DISABLED_SOURCES.has(source)) notFound(); const { page: rawPage = "1" } = await searchParams; const page = parsePage(rawPage);
  const apiMeta = await getMeta(); if (!apiMeta.source_platforms.some((p) => p.id === source)) notFound();
  const pageMeta = getSourceMeta(source); const canonical = `${SITE_URL}/sources/${encodeURIComponent(source)}`; const pageHref = (targetPage: number) => `/sources/${encodeURIComponent(source)}?page=${targetPage}`;
  const shopQuery = new URLSearchParams({ source_platform: source, sort: "offer_count", offset: String((page - 1) * DIRECTORY_PAGE_SIZE), limit: String(DIRECTORY_PAGE_SIZE) });
  const [catalog, shopsData] = await Promise.all([getProducts(`source_platform=${encodeURIComponent(source)}&sort=quality`), getShopCards(shopQuery.toString())]);
  const shops = shopsData.items; const products = catalog.items.filter((p) => p.offer_count > 0); const totalPages = getTotalPages(shopsData.total, DIRECTORY_PAGE_SIZE); if (page > totalPages) redirect(pageHref(totalPages));
  const structuredData = [breadcrumbJsonLd([{ name: "首页", path: "/" }, { name: "来源平台", path: "/sources" }, { name: pageMeta.h1, path: `/sources/${encodeURIComponent(source)}` }]), { "@context": "https://schema.org", "@type": "CollectionPage", "@id": canonical, url: canonical, name: pageMeta.h1, description: pageMeta.intro, isPartOf: { "@id": "https://ai.pricememo.cn/#website" }, mainEntity: { "@type": "ItemList", numberOfItems: products.length, itemListElement: products.map((product, index) => ({ "@type": "ListItem", position: index + 1, name: product.display_name, url: `${SITE_URL}/sources/${encodeURIComponent(source)}/products/${encodeURIComponent(product.slug)}` })) } }];
  return <main id="main-content" className="container"><JsonLd data={structuredData} /><div className="page-content"><header className="page-intro"><span className="eyebrow">SOURCE · {source.toUpperCase()}</span><h1>{pageMeta.h1}</h1><p>{pageMeta.intro}</p></header><section className="detail-stats source-stats"><div><span>当前有效报价</span><strong>{catalog.offer_count}</strong><p><Package size={12} />公开报价</p></div><div><span>当前店铺</span><strong>{shopsData.total}</strong><p><Storefront size={12} />来源店铺</p></div><div><span>有货报价</span><strong>{catalog.in_stock_count}</strong><p><span className="status-dot" />当前观测</p></div><div><span>标准产品</span><strong>{products.length}</strong><p>已映射分类</p></div></section>{products.length ? <section className="quotes-section source-products"><div className="section-heading"><div><span className="eyebrow">STANDARD PRODUCTS</span><h2>这个来源正在提供的产品</h2><p>继续进入标准产品页，可与其他公开来源横向比较。</p></div></div><div className="product-grid">{products.map((product) => <ProductCard key={product.slug} product={product} />)}</div></section> : null}{shops.length ? <section className="directory-section"><div className="section-heading"><div><span className="eyebrow">SOURCE SHOPS</span><h2>当前店铺 · {shopsData.total}</h2><p>点击店铺查看该来源下的完整公开报价。</p></div></div><div className="directory-grid">{shops.map((shop) => <Link key={shop.token} href={`/shops/${encodeURIComponent(shop.token)}`} className="directory-card"><div className="directory-card-icon"><Storefront size={20} /></div><div className="directory-card-copy"><h2>{shop.name}</h2><p>{shop.product_slugs.slice(0,3).join("、") || "公开 AI 商品"}</p><div className="directory-card-meta"><span><Package size={13} />{shop.offer_count} 条报价 · {shop.in_stock_count} 条有货</span><span><Clock size={13} />{relativeTime(shop.last_seen_at || shop.last_success_at)}</span></div></div><ArrowRight className="directory-arrow" size={18} /></Link>)}</div><PaginationNav page={page} totalPages={totalPages} hrefForPage={pageHref} ariaLabel="来源店铺分页" /></section> : null}</div></main>;
}
