import Link from "next/link";
import { ArrowRight, ArrowUpRight, Terminal, BookOpen, SlidersHorizontal } from "@phosphor-icons/react/ssr";
import { BRAND, SITE_ID } from "@/lib/brands";
import { BRAND_TABS, brandCatalogPath } from "@/lib/catalog";
import { exactTime, money, relativeTime } from "@/lib/format";
import type { CatalogResponse, ProductCard } from "@/lib/types";
import { getArticles, type Article } from "@/lib/site-content";
import { SearchBox } from "./search-box";
import { PlatformIcon } from "./platform-icon";
import { SponsorShowcase } from "./sponsor-showcase";

function Snapshot({ data }: { data: CatalogResponse }) {
  return <p className="brand-snapshot"><span>{data.offer_count.toLocaleString("zh-CN")} 条公开报价</span><time dateTime={data.snapshot_at || undefined} title={exactTime(data.snapshot_at)}>{data.snapshot_at ? `${relativeTime(data.snapshot_at)}更新` : "暂无更新"}</time></p>;
}
function BrandLinks() {
  return <nav className="brand-categories" aria-label="品牌目录">{BRAND_TABS.map((brand, i) => <Link key={brand} href={brandCatalogPath(brand)}><span className="category-number">0{i + 1}</span><PlatformIcon platform={brand} size={24} /><span>{brand}</span><ArrowUpRight size={16} aria-hidden /></Link>)}</nav>;
}
function ProductLink({ product, index }: { product: ProductCard; index: number }) {
  return <Link href={`/products/${encodeURIComponent(product.slug)}`} className="brand-product">
    <span className="product-number">{String(index + 1).padStart(2, "0")}</span><span className="product-symbol"><PlatformIcon platform={product.brand} size={30} /></span>
    <div className="product-identity"><span>{product.brand}</span><h3>{product.display_name}</h3><p>{product.subtitle}</p></div>
    <div className="product-availability">{product.in_stock_count > 0 ? `${product.in_stock_count} 条有货` : "暂无现货"}<small>{product.source_count} 个来源</small></div>
    <div className="product-price"><small>有货观测价</small><strong>{money(product.lowest_price, product.price_currency)}</strong></div><ArrowUpRight className="product-arrow" size={20} aria-hidden />
  </Link>;
}
function Reading({ articles }: { articles: Article[] }) {
  return <section className="brand-reading"><div className="brand-section-heading"><h2>{SITE_ID === "aisi" ? "阅读，另一种发现" : "最近文章"}</h2><Link href="/articles">文章目录 <ArrowRight size={16} /></Link></div>{articles.length ? <div className="brand-reading-list">{articles.map(article => <article key={article.id}><p className="article-meta">{article.category || BRAND.name}</p><h3><Link href={`/articles/${article.slug}`}>{article.title}</Link></h3><p>{article.summary}</p></article>)}</div> : <div className="reading-empty"><BookOpen size={28} /><div><h3>新的文章正在准备</h3><p>关于 AI 的使用、订阅与选择，之后在这里见。</p></div><Link href="/articles">查看文章目录 <ArrowUpRight size={18} /></Link></div>}</section>;
}
export async function BrandHome({ data }: { data: CatalogResponse }) {
  const articles = await getArticles(1, 3).catch(() => null);
  const products = data.items.slice(0, 8);
  const productList = products.length ? products.map((product, index) => <ProductLink key={product.slug} product={product} index={index} />) : <p className="empty-state">暂无公开报价</p>;
  if (SITE_ID === "aiprice") return <main className="brand-home terminal-home shell">
    <div className="terminal-status"><span><span className="status-dot" />报价观察台</span><span>PUBLIC PRICE MONITOR</span></div>
    <section className="terminal-intro"><div><p className="brand-eyebrow">AI SUBSCRIPTIONS / MARKET OVERVIEW</p><h1>掌握价格。<br /><span>再做决定。</span></h1><p>把价格、库存和来源放在同一屏。</p></div><div className="terminal-search"><Terminal size={28} /><h2>查找订阅报价</h2><SearchBox /><Snapshot data={data} /></div></section>
    <BrandLinks /><section className="terminal-market"><div className="brand-section-heading"><h2>订阅行情 <span>/ QUOTES</span></h2><Link href="/products">打开全部报价 <ArrowUpRight size={16} /></Link></div><div className="terminal-columns" aria-hidden><span>产品 / PRODUCT</span><span>库存 / 来源</span><span>观测价</span></div><div className="brand-products">{productList}</div></section>
    <div className="terminal-lower"><Reading articles={articles?.items || []} /><aside><p className="brand-eyebrow">DATA NOTES</p><h2>每个价格，<br />都有出处。</h2><p>页面展示最近一次采集结果。购买前请核对来源页面。</p><Link href="/methodology">查看数据口径 <ArrowUpRight size={18} /></Link><Link href="/relays">打开中转站目录 <ArrowUpRight size={18} /></Link></aside></div><SponsorShowcase />
  </main>;
  if (SITE_ID === "aisi") return <main className="brand-home editorial-home shell">
    <div className="editorial-edition"><span>THE AI SUBSCRIPTION JOURNAL</span><span>工具 · 选择 · 日常</span></div>
    <section className="editorial-cover"><div className="editorial-cover-title"><p className="brand-eyebrow">关于 AI，也关于你的日常</p><h1>好的工具，<br />值得认真<span>挑选。</span></h1><p>在纷繁的订阅之间，找到适合自己的那一个。<br />从价格开始，也多了解一点。</p><Link href="/products" className="editorial-link">翻开订阅目录 <ArrowRight size={20} /></Link></div><aside className="editorial-cover-note"><span className="editorial-plus" aria-hidden>+</span><h2>先了解，<br />再订阅。</h2><p>比较公开报价，留意交付方式，也为实际的使用需求留一点空间。</p><SearchBox placeholder="寻找你想了解的 AI" /><Snapshot data={data} /></aside></section>
    <BrandLinks /><section className="editorial-selection"><div className="editorial-section-note"><span>01 / 订阅手册</span><h2>从这些<br />工具开始</h2><p>同一项订阅，也有不同的价格与交付方式。</p><Link href="/products">浏览全部订阅 <ArrowRight size={18} /></Link></div><div className="brand-products">{productList}</div></section><Reading articles={articles?.items || []} /><SponsorShowcase />
  </main>;
  if (SITE_ID === "pricein") return <main className="brand-home shop-home shell">
    <section className="shop-hero"><div><p className="brand-eyebrow">先比较，再下单</p><h1>你的 AI 订阅，<br />买得更明白。</h1><p>多家店铺放在一起看，价格和交付一并比较。</p><Link href="/products" className="shop-hero-cta">开始比价 <ArrowRight size={20} /></Link></div><aside className="shop-checklist"><SlidersHorizontal size={30} /><h2>比价格，也比这些</h2><ol><li><span>01</span>账号、直充还是合租</li><li><span>02</span>订阅期限与售后范围</li><li><span>03</span>有货状态和更新时间</li></ol><Link href="/methodology">了解报价如何整理 <ArrowUpRight size={16} /></Link></aside></section>
    <section className="shop-departments"><h2>按品牌逛一逛</h2><BrandLinks /></section><section className="shop-products"><div className="brand-section-heading"><div><h2>找到你想要的订阅</h2><Snapshot data={data} /></div><Link href="/products">全部报价 <ArrowRight size={18} /></Link></div><div className="brand-products">{productList}</div></section><Reading articles={articles?.items || []} /><SponsorShowcase />
  </main>;
  return <main className="brand-home index-home shell">
    <header className="index-intro"><p className="brand-eyebrow">OPENPRICE / PUBLIC INDEX</p><h1>AI 订阅价格索引<span>公开信息，逐项查阅。</span></h1><p>按产品查价格，沿来源看详情。</p><Snapshot data={data} /></header>
    <div className="index-workspace"><aside><p className="index-label">目录 / CONTENTS</p><a href="#price-index">01 产品索引</a><Link href="/relays">02 中转站目录</Link><Link href="/articles">03 文章档案</Link><Link href="/methodology">04 数据说明</Link><div className="index-aside-note">报价是采集时的记录。<br />实际成交条件请查阅原始页面。</div></aside><div><SearchBox placeholder="检索产品、品牌、店铺" /><section id="price-index"><div className="brand-section-heading"><h2><span>01</span> 产品索引</h2><Link href="/products">完整目录 <ArrowUpRight size={16} /></Link></div><BrandLinks /><div className="index-columns" aria-hidden><span>编号 / 名称</span><span>库存 / 来源</span><span>观测价</span></div><div className="brand-products">{productList}</div></section><Reading articles={articles?.items || []} /></div></div><SponsorShowcase />
  </main>;
}
