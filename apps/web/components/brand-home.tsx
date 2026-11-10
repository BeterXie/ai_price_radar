import Link from "next/link";
import { ArrowUpRight } from "@phosphor-icons/react/ssr";
import { BRAND, SITE_ID } from "@/lib/brands";
import { BRAND_TABS, brandCatalogPath } from "@/lib/catalog";
import { exactTime, relativeTime } from "@/lib/format";
import type { CatalogResponse } from "@/lib/types";
import { getArticles } from "@/lib/site-content";
import { SearchBox } from "./search-box";
import { ProductCard } from "./product-card";
import { PlatformIcon } from "./platform-icon";
import { SponsorShowcase } from "./sponsor-showcase";

export async function BrandHome({ data }: { data: CatalogResponse }) {
  const articles = await getArticles(1, 3).catch(() => null);
  const copy = {
    aiprice: ["AI 订阅。价格一目了然。", "比较价格、库存与交付方式，找到适合你的订阅。"],
    aisi: ["选一个合适的 AI，\n让日常轻松一点。", "从公开报价到使用心得，在这里慢慢看清选择。"],
    pricein: ["买之前，\n先比一比。", "ChatGPT、Claude、Gemini，多家报价放在一起看。"],
    openprice: ["AI 订阅价格索引", "价格、来源、时间。每一条报价都有迹可循。"],
    pricememo: ["AI 订阅比价", "公开报价记录"],
  }[SITE_ID];
  return <main className={`brand-home brand-home-${SITE_ID}`}>
    <section className="brand-hero shell">
      <div className="brand-hero-copy"><h1>{copy[0]}</h1><p>{copy[1]}</p></div>
      <div className="brand-search"><SearchBox /><p className="brand-snapshot"><span>{data.offer_count.toLocaleString()} 条公开报价</span><time dateTime={data.snapshot_at || undefined} title={exactTime(data.snapshot_at)}>{data.snapshot_at ? `${relativeTime(data.snapshot_at)}更新` : "暂无更新"}</time></p></div>
    </section>
    <div className="brand-directory shell">
      <nav className="brand-navigation" aria-label="品牌目录"><h2>按品牌浏览</h2>{BRAND_TABS.map(brand => <Link key={brand} href={brandCatalogPath(brand)}><PlatformIcon platform={brand} size={22} /><span>{brand}</span><ArrowUpRight size={16} /></Link>)}<Link href="/products">全部商品 <ArrowUpRight size={16} /></Link></nav>
      <section className="brand-quotes" aria-labelledby="brand-quote-title"><div className="brand-section-heading"><h2 id="brand-quote-title">当前报价</h2><Link href="/products">查看全部 →</Link></div>
        <div className="brand-product-list">{data.items.length ? data.items.slice(0, 8).map(product => <ProductCard key={product.slug} product={product} />) : <p className="empty-state">暂无公开报价</p>}</div>
      </section>
    </div>
    <SponsorShowcase />
    {articles?.items.length ? <section className="shell brand-reading"><div className="brand-section-heading"><h2>最近文章</h2><Link href="/articles">全部文章 →</Link></div><div className="article-grid">{articles.items.map(article => <article key={article.id}><p className="article-meta">{article.category || BRAND.name}</p><h3><Link href={`/articles/${article.slug}`}>{article.title}</Link></h3><p>{article.summary}</p></article>)}</div></section> : null}
    <nav className="shell brand-bottom-links" aria-label="进一步了解"><Link href="/relays">中转站目录 <ArrowUpRight size={20} /></Link><Link href="/articles">文章 <ArrowUpRight size={20} /></Link><Link href="/methodology">报价整理方法 <ArrowUpRight size={20} /></Link></nav>
  </main>;
}
