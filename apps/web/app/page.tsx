import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, BookOpenText, CheckCircle, Clock, Database, Package, ShieldCheck, Sparkle, Stack } from "@phosphor-icons/react/ssr";
import { SearchBox } from "@/components/search-box";
import { ProductCard } from "@/components/product-card";
import { PlatformIcon } from "@/components/platform-icon";
import { getProducts } from "@/lib/api";
import { exactTime, money, relativeTime } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "AI 订阅比价｜查价格、库存和交付方式",
  description: "汇总 ChatGPT、Claude、Gemini、Grok 等 AI 产品的公开报价，比较价格、库存、交付方式和更新时间。",
  alternates: { canonical: "https://ai.pricememo.cn" },
  openGraph: {
    title: "AI 订阅比价｜查价格、库存和交付方式",
    description: "汇总主流 AI 产品的公开报价，比较价格、库存、交付方式和更新时间。",
    url: "https://ai.pricememo.cn",
    siteName: "AI Price Memory",
    locale: "zh_CN",
    type: "website",
  },
  twitter: { card: "summary_large_image", title: "AI 订阅比价｜查价格、库存和交付方式", description: "查看主流 AI 产品的公开价格、库存、交付方式和更新时间。" },
};

const brandLinks = ["OpenAI", "Claude", "Gemini", "Grok", "X"];

export default async function HomePage() {
  const data = await getProducts("sort=quality");
  const products = data.items.slice(0, 6);
  const live = products.filter((product) => product.in_stock_count > 0).slice(0, 3);
  const snapshotLabel = data.snapshot_at ? relativeTime(data.snapshot_at) : "等待下一次采集";

  return (
    <main id="main-content" className="container">
      <section className="hero">
        <div className="hero-copy">
          <div className="hero-eyebrow"><span className="status-dot" />公开报价，透明可查 <span className="eyebrow-separator" /> 为每一个 AI 选择提供依据</div>
          <h1>先看懂商品，<br />再找到<span className="hero-highlight">好价格<svg viewBox="0 0 270 13" aria-hidden="true"><path d="M3 9Q130 -1 267 7" fill="none" stroke="currentColor" strokeWidth="5" strokeLinecap="round" /></svg></span>。</h1>
          <p className="hero-description">AI 订阅、账号与 API 额度，一站式发现与比较。<br />看清交付方式、库存和来源，让每一次选择更有把握。</p>
          <SearchBox />
          <div className="quick-links"><span>热门搜索</span><Link href="/products?q=ChatGPT%20Plus">ChatGPT Plus <ArrowUpRight size={11} /></Link><Link href="/products?q=Claude%20Pro">Claude Pro <ArrowUpRight size={11} /></Link><Link href="/products?product_type=api">API 额度 <ArrowUpRight size={11} /></Link></div>
          <div className="hero-trust"><span><ShieldCheck size={15} />来源可追溯</span><span><Clock size={14} />持续更新</span><span><CheckCircle size={15} />免费开放</span></div>
        </div>

        <div className="hero-panel-wrap">
          <div className="panel-backdrop" />
          <aside className="live-panel" aria-label="刚更新的有货报价">
            <div className="live-panel-heading"><div><span className="eyebrow">MARKET SNAPSHOT</span><h3>刚更新的好价格<span className="tiny-spark">✦</span></h3></div><span className="pill green"><span className="status-dot" />持续监测</span></div>
            <div className="live-panel-rows">
              {live.map((product) => (
                <Link className="live-row" key={product.slug} href={`/products/${encodeURIComponent(product.slug)}`}>
                  <span className={`brand-icon ${product.brand.toLowerCase()}`}><PlatformIcon platform={product.brand} size={28} /></span>
                  <span className="live-row-name"><strong>{product.display_name}</strong><small>{product.in_stock_count} 条有货报价<span>·</span>{relativeTime(product.last_updated_at)}</small></span>
                  <span className="live-price"><strong>{money(product.lowest_price, product.price_currency)}</strong><small>近期参考价</small></span>
                </Link>
              ))}
            </div>
            <div className="market-summary"><div><span><span className="status-dot" />市场动态</span><p>{data.offer_count} 条公开报价正在整理中。</p></div><div className="market-bars" aria-hidden="true">{[18,24,20,31,26,36,30,43,38,49,44,56,50,61,55,66].map((h, index) => <i key={index} style={{ height: `${h / 1.5}px` }} />)}</div></div>
            <Link className="live-panel-footer" href="/products">发现全部报价 <ArrowRight size={16} /></Link>
          </aside>
          <div className="floating-note"><span className="floating-icon"><ShieldCheck size={17} /></span><span>每一条报价，都有迹可循</span><CheckCircle size={14} /></div>
        </div>
      </section>

      <section className="stats-strip" aria-label="报价概况">
        {[
          { Icon: Stack, title: "覆盖商品分类", number: String(data.total), suffix: "种", note: "按商品与交付方式细分" },
          { Icon: Database, title: "收录公开报价", number: data.offer_count.toLocaleString("zh-CN"), suffix: "条", note: "汇聚多个公开商品来源" },
          { Icon: Package, title: "当前有货报价", number: data.in_stock_count.toLocaleString("zh-CN"), suffix: "条", note: "优先展示可用选择", green: true },
          { Icon: Clock, title: "最近一次更新", number: snapshotLabel, suffix: "", note: exactTime(data.snapshot_at) },
        ].map(({ Icon, title, number, suffix, note, green }) => (
          <div className="stat" key={title}><div className="stat-label"><Icon size={15} />{title}</div><div className={`stat-number ${green ? "green-text" : ""}`}>{number}<span>{suffix}</span></div><p>{note}</p></div>
        ))}
      </section>

      <section className="lab-banner">
        <div className="lab-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="lab-art-core"><Sparkle size={34} /></div><Sparkle className="orbit-spark" size={17} /><i className="orbit-dot" /></div>
        <div className="lab-banner-copy"><div className="eyebrow"><span className="new-label">NEW</span> AI SKILLS & LAB</div><h2>从比价格，到比能力。找到值得亲手试一试的 AI。</h2><p>模型体检、开源 Skills 与开发者实战内容，和报价目录一起帮助你做更完整的判断。</p><div className="banner-tags"><span># 模型评测</span><span># Agent Skills</span><span># 开发者工作流</span></div></div>
        <Link href="/skills" className="button">去探索 <ArrowRight size={15} /></Link>
      </section>

      <section className="quotes-section">
        <div className="section-heading"><div><div className="eyebrow">FIND YOUR NEXT AI</div><h2>热门产品，清晰比较</h2><p>优先呈现有货、近期更新且商品信息明确的报价。</p></div><Link className="text-button" href="/products">查看全部报价 <ArrowRight size={16} /></Link></div>
        <div className="home-filter-row"><div className="tabs"><Link className="active" href="/products">全部品牌</Link>{brandLinks.map((brand) => <Link key={brand} href={`/products?brand=${encodeURIComponent(brand)}`}><span className="brand-icon small"><PlatformIcon platform={brand} size={14} /></span>{brand}</Link>)}</div><Link className="toggle-label" href="/products?in_stock=true"><span className="toggle" />仅看有货</Link></div>
        <div className="product-grid">{products.map((product) => <ProductCard key={product.slug} product={product} />)}</div>
        <div className="quote-disclaimer"><ShieldCheck size={14} />参考价仅用于同类商品比较，不代表官方定价或最终成交价。购买前请核对来源页面。</div>
      </section>

      <section className="trust-section">
        <div className="trust-intro"><span className="eyebrow">TRANSPARENCY FIRST</span><h2>信息透明，<br />选择才有底气。</h2><p>我们整理信息，不替你做决定。<br />每一份报价，都保留判断所需的细节。</p><Link className="text-button" href="/methodology">了解数据方法 <ArrowRight size={16} /></Link></div>
        <div className="trust-grid">
          {[
            { Icon: Database, title: "原始来源，随时核对", text: "保留店铺、商品标题与来源链接，信息不止一个价格。" },
            { Icon: Clock, title: "更新时间，清楚标注", text: "展示最近观测时间，让过时的信息不再影响判断。" },
            { Icon: ShieldCheck, title: "交付限制，不做美化", text: "如实呈现商品原文中的限制、质保与售后说明。" },
            { Icon: CheckCircle, title: "发现问题，一起修正", text: "支持提交价格、库存与分类纠错，让数据持续变好。" },
          ].map(({ Icon, title, text }) => <div className="trust-item" key={title}><Icon size={22} /><h3>{title}</h3><p>{text}</p></div>)}
        </div>
      </section>

      <section className="guide-callout"><div className="callout-icon"><BookOpenText size={26} /></div><div><h3>第一次购买 AI 产品？先花 5 分钟看懂。</h3><p>从交付方式到账号安全，一份指南帮你少走弯路。</p></div><Link className="button" href="/guides/buying-checklist">阅读购买指南 <ArrowRight size={16} /></Link></section>
    </main>
  );
}
