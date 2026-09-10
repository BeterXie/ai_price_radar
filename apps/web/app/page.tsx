import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  CheckCircle,
  Clock,
  Database,
  Flask,
  Globe,
  Info,
  Package,
  ArrowsClockwise,
  ShieldCheck,
  Sparkle,
  Stack,
} from "@phosphor-icons/react/ssr";
import { SearchBox } from "@/components/search-box";
import { ProductCardGrid } from "@/components/product-card-grid";
import { PlatformIcon } from "@/components/platform-icon";
import { SectionIntro } from "@/components/page-shell";
import { getProducts } from "@/lib/api";
import { clockTime, money, relativeTime } from "@/lib/format";

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
  twitter: {
    card: "summary_large_image",
    title: "AI 订阅比价｜查价格、库存和交付方式",
    description: "查看主流 AI 产品的公开价格、库存、交付方式和更新时间。",
  },
};

export default async function HomePage() {
  const data = await getProducts("sort=quality");
  const products = data.items.slice(0, 6);
  const availableProducts = data.items.filter((product) => product.in_stock_count > 0).slice(0, 3);
  return (
    <main id="main-content" data-vds-schema="v3.1" data-vds-layer="field">
      {/* Announcement */}
      <div className="announcement-bar">
        <span className="announcement-tag">新发现</span>
        <span>从比价格，到比能力。AI 技能与实验室现已上线</span>
        <Link href="/skills">去探索 <ArrowRight size={13} /></Link>
      </div>

      {/* Snapshot rail */}
      <div className="snapshot-rail" data-vds-role="evidence">
        <div className="shell snapshot-rail-inner">
          <span className="snapshot-state">{data.snapshot_at ? `${relativeTime(data.snapshot_at)}完成刷新` : "暂未取得刷新时间"}</span>
          <span>快照 #{data.snapshot_id || "—"} · {data.offer_count} 条报价 · {data.in_stock_count} 条有货</span>
          <span>每条报价保留来源和观测时间</span>
        </div>
      </div>

      {/* Hero */}
      <section className="home-hero">
        <div className="shell home-hero-layout">
          <div className="min-w-0">
            {/* Eyebrow */}
            <div className="hero-eyebrow">
              <span className="signal-dot" aria-hidden="true" />
              公开报价，透明可查
              <span className="eyebrow-separator" aria-hidden="true" />
              为每一个 AI 选择提供依据
            </div>

            {/* H1 with underline decoration */}
            <h1 className="display-title mt-0" data-vds-role="title">
              先看懂商品，
              <br />
              再找到
              <span className="hero-highlight">
                好价格
                <svg viewBox="0 0 120 12" aria-hidden="true" preserveAspectRatio="none">
                  <path d="M3 9Q57 -1 117 7" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
                </svg>
              </span>
              。
            </h1>

            <p className="lede mt-5" data-vds-role="explanation">
              AI 订阅、账号与 API 额度，一站式发现与比较。<br />
              看清交付方式、库存和来源，让每一次选择更有把握。
            </p>

            <div className="mt-7 max-w-2xl hero-search"><SearchBox /></div>

            {/* Quick links */}
            <div className="hero-quick-links">
              <span>热门搜索</span>
              <Link href="/products?q=ChatGPT+Plus" className="quick-link">ChatGPT Plus ↗</Link>
              <Link href="/products?q=Claude+Pro" className="quick-link">Claude Pro ↗</Link>
              <Link href="/products?q=API" className="quick-link">API 额度 ↗</Link>
            </div>

            {/* Trust bar */}
            <div className="hero-trust">
              <span><ShieldCheck size={15} weight="fill" /> 来源可追溯</span>
              <span><ArrowsClockwise size={14} /> 持续更新</span>
              <span><CheckCircle size={15} weight="fill" /> 免费开放</span>
            </div>
          </div>

          {/* Live panel */}
          <div className="hero-panel-wrap min-w-0">
            <div className="panel-backdrop" aria-hidden="true" />
            <aside className="live-panel" aria-label="有货报价速览" data-vds-layer="evidence">
              <div className="live-panel-heading">
                <div>
                  <p className="eyebrow">MARKET SNAPSHOT</p>
                  <h3>刚更新的好价格<span className="ml-1.5 text-[color:var(--brand)] opacity-60">✦</span></h3>
                </div>
                <span className="pill"><span className="signal-dot" aria-hidden="true" /> 持续监测</span>
              </div>
              <div className="live-panel-rows">
                {availableProducts.map((product) => (
                  <Link key={product.slug} href={`/products/${encodeURIComponent(product.slug)}`} className="live-row group">
                    <span className="product-brand-icon" aria-hidden="true"><PlatformIcon platform={product.brand} size={22} /></span>
                    <span className="live-row-name">
                      <strong>{product.display_name}</strong>
                      <small>{product.in_stock_count} 条有货报价<span>·</span>{relativeTime(product.last_updated_at)}</small>
                    </span>
                    <span className="live-price">
                      <strong>{money(product.lowest_price, product.price_currency)}</strong>
                      <small>近期参考价</small>
                    </span>
                  </Link>
                ))}
                {availableProducts.length === 0 && (
                  <p className="py-8 text-xs leading-6 text-[color:var(--muted)]">当前没有可展示的有货报价，可进入目录查看全部库存状态。</p>
                )}
              </div>
              <div className="market-summary">
                <div>
                  <span><span className="signal-dot" aria-hidden="true" /> 市场动态</span>
                  <p>更多选择，更透明的价格。</p>
                </div>
                <div className="market-bars" aria-hidden="true">
                  {[13, 22, 17, 30, 22, 34, 28, 42, 35, 46, 39, 52, 47, 59, 52, 64].map((height, index) => (
                    <i key={index} style={{ height: Math.round(height / 1.5) }} />
                  ))}
                </div>
              </div>
              <Link href="/products" className="live-board-link" data-vds-role="action">
                发现全部报价 <ArrowRight size={16} />
              </Link>
            </aside>
            <div className="floating-note">
              <span className="inline-flex items-center text-[color:var(--brand)]"><ShieldCheck size={15} /></span>
              <span>每一条报价，都有迹可循</span>
              <CheckCircle size={13} weight="fill" />
            </div>
          </div>
        </div>
      </section>

      {/* Stats strip */}
      <div className="shell">
        <dl className="home-stats" aria-label="报价概况">
          <div>
            <dt><Stack size={14} />商品分类</dt>
            <dd>{data.total}<span>种</span></dd>
            <p className="stat-note">按商品与交付方式细分</p>
          </div>
          <div>
            <dt><Database size={14} />收录报价</dt>
            <dd>{data.offer_count}<span>条</span></dd>
            <p className="stat-note">汇聚多个公开商品来源</p>
          </div>
          <div>
            <dt><Package size={14} />有货报价</dt>
            <dd className="green-stat">{data.in_stock_count}<span>条</span></dd>
            <p className="stat-note">优先展示可用选择</p>
          </div>
          <div>
            <dt>
              <Clock size={14} />最近更新
              <span className="signal-dot" aria-hidden="true" />
            </dt>
            <dd>{clockTime(data.snapshot_at)}<span>北京时间</span></dd>
            <p className="stat-note">每一条记录都保留更新时间</p>
          </div>
        </dl>
      </div>

      {/* Lab discovery banner */}
      <section className="shell" aria-labelledby="lab-discovery-title">
        <div className="lab-banner">
          <div className="lab-art" aria-hidden="true">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="lab-art-core"><Flask size={31} /></div>
            <Sparkle className="orbit-spark" size={20} />
            <span className="orbit-dot" />
          </div>
          <div className="lab-banner-copy">
            <div className="eyebrow">
              <span className="new-label">NEW</span>
              不止比价，也探索 AI 的更多可能
            </div>
            <h2 id="lab-discovery-title">模型好不好用？让真实表现说话。</h2>
            <p>精选模型实测、开源 Skills 与实战技巧，把 AI 用出价值。</p>
            <div className="banner-tags">
              <span># 模型能力评测</span>
              <span># 精选 Agent Skills</span>
              <span># 开发者实践</span>
            </div>
          </div>
          <Link href="/skills" className="button-secondary tactile">探索技能与实验室 <ArrowRight size={16} /></Link>
        </div>
      </section>

      {/* Product listing */}
      <section className="shell quotes-section home-page" data-vds-layer="evidence">
        <SectionIntro
          eyebrow="FIND YOUR NEXT AI"
          title="热门产品，清晰比较"
          description="优先呈现有货、近期更新且商品信息明确的报价。"
          action={<Link href="/products" className="button-tertiary">查看全部报价 <ArrowRight size={16} /></Link>}
        />
        <ProductCardGrid products={products} />
        <p className="quote-disclaimer">
          <Info size={12} aria-hidden="true" />
          参考价仅用于同类商品比较，不代表官方定价或最终成交价。购买前请核对来源页面。
        </p>
      </section>

      {/* Trust section */}
      <section className="shell trust-section" aria-labelledby="trust-heading">
        <div className="trust-intro">
          <span className="eyebrow-label">TRANSPARENCY FIRST</span>
          <h2 id="trust-heading">信息透明，<br />选择才有底气。</h2>
          <p>我们整理信息，不替你做决定。<br />每一份报价，都保留判断所需的细节。</p>
          <Link href="/methodology" className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[color:var(--brand)]">
            了解数据方法 <ArrowRight size={16} />
          </Link>
        </div>
        <div className="trust-grid">
          {[
            { Icon: Globe, title: "原始来源，随时核对", text: "保留店铺、商品标题与来源链接，信息不止一个价格。" },
            { Icon: Clock, title: "更新时间，清楚标注", text: "展示最近观测时间，让过时的信息不再影响判断。" },
            { Icon: ShieldCheck, title: "交付限制，不做美化", text: "如实呈现商品原文中的限制、质保与售后说明。" },
            { Icon: CheckCircle, title: "发现问题，一起修正", text: "支持提交价格、库存与分类纠错，让数据持续变好。" },
          ].map(({ Icon, title, text }) => (
            <div key={title} className="trust-item">
              <Icon size={22} aria-hidden="true" />
              <h3>{title}</h3>
              <p>{text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Guide callout */}
      <div className="shell">
        <section className="guide-callout" aria-labelledby="guide-callout-heading">
          <div className="callout-icon" aria-hidden="true">
            <BookOpen size={24} />
          </div>
          <div>
            <h3 id="guide-callout-heading">第一次购买 AI 产品？先花 5 分钟看懂。</h3>
            <p>从交付方式到账号安全，一份指南帮你少走弯路。</p>
          </div>
          <Link href="/guides" className="button-secondary" style={{ flexShrink: 0 }}>
            阅读购买指南 <ArrowRight size={16} />
          </Link>
        </section>
      </div>

      {/* Method band */}
      <section className="method-band border-y border-[color:var(--line-strong)]">
        <div className="shell grid lg:grid-cols-[.58fr_1.42fr]">
          <div className="border-b border-[color:var(--line)] py-10 lg:border-b-0 lg:border-r lg:pr-10 lg:py-12">
            <h2 className="text-3xl font-semibold tracking-[-.04em]">报价包含哪些信息</h2>
            <p className="mt-4 max-w-md text-sm leading-7 text-[color:var(--muted)]">每条报价保留来源、更新时间、商品类型和交付说明。用于展示的参考价只在同类商品内计算。</p>
            <Link href="/methodology" className="mt-6 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-[color:var(--brand)]">
              查看数据方法 <ArrowRight size={17} />
            </Link>
          </div>
          <div className="divide-y divide-[color:var(--line)] lg:grid lg:grid-cols-2 lg:divide-x lg:divide-y-0">
            {[
              { Icon: Database, title: "查看原始商品页", copy: "每条报价都会保留店铺、商品标题和原始购买链接。" },
              { Icon: Clock, title: "标明数据时间", copy: "每条报价都会显示最近一次观测时间，长时间未更新的报价会降低展示优先级。" },
              { Icon: ShieldCheck, title: "限制来自商品说明", copy: "限制、质保和售后提示只引用商品原文，不替商家补充或推断。" },
              { Icon: CheckCircle, title: "有误可提交纠错", copy: "分类、价格或库存有问题，可以提交纠错。" },
            ].map(({ Icon, title, copy }) => (
              <div key={title} className="method-item p-7 lg:p-8">
                <Icon size={22} className="text-[color:var(--brand)]" aria-hidden="true" />
                <h3 className="mt-5 text-lg font-semibold">{title}</h3>
                <p className="mt-2 max-w-sm text-sm leading-6 text-[color:var(--muted)]">{copy}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}



