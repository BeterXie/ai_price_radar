import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, CheckCircle, Clock, Database, Package, ShieldCheck, Sparkle } from "@phosphor-icons/react/ssr";
import { SearchBox } from "@/components/search-box";
import { ProductCard } from "@/components/product-card";
import { PlatformIcon } from "@/components/platform-icon";
import { SectionIntro } from "@/components/page-shell";
import { getProducts } from "@/lib/api";
import { exactTime, money, relativeTime } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "AI 订阅比价｜查价格、库存和交付方式",
  description: "汇总 ChatGPT、Claude、Gemini、Grok 等 AI 产品的公开报价，快速比较价格、库存、交付方式和更新时间。",
  alternates: { canonical: "https://ai.pricememo.cn" },
  openGraph: {
    title: "AI 订阅比价｜查价格、库存和交付方式",
    description: "汇总主流 AI 产品的公开报价，比较价格、库存、交付方式和更新时间。",
    url: "https://ai.pricememo.cn",
    siteName: "AI Price Radar",
    locale: "zh_CN",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "AI 订阅比价｜查价格、库存和交付方式",
    description: "快速比较主流 AI 产品的公开价格、库存、交付方式和更新时间。",
  },
};

export default async function HomePage() {
  const data = await getProducts("sort=quality");
  const products = data.items.slice(0, 6);
  return (
    <main id="main-content">
      <section className="home-hero relative overflow-hidden border-b border-[color:var(--line)]">
        <span className="hero-orb hero-orb-home-a" aria-hidden="true" />
        <span className="hero-orb hero-orb-home-b" aria-hidden="true" />
        <div className="shell relative z-[1] grid items-center gap-10 py-14 lg:grid-cols-[minmax(0,1.02fr)_minmax(370px,.78fr)] lg:py-20 xl:gap-16">
          <div>
            <p className="eyebrow"><Sparkle size={14} weight="fill" aria-hidden="true" />AI 订阅公开报价雷达</p>
            <h1 className="display-title mt-6">先看清商品，<br /><span className="gradient-text">再决定价格。</span></h1>
            <p className="lede mt-7">把不同店铺的 AI 订阅、账号和 API 报价放进同一个比较视图。价格只是结果，商品类型、库存、交付方式和更新时间才是购买判断的上下文。</p>
            <div className="mt-9 max-w-2xl"><SearchBox /></div>
            <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-[color:var(--muted)]">
              <span className="font-medium">快速查看</span>
              <Link href="/products?platform=OpenAI" className="quick-link">OpenAI</Link>
              <Link href="/products?platform=Claude" className="quick-link">Claude</Link>
              <Link href="/products?in_stock=true" className="quick-link">仅看有货</Link>
            </div>
          </div>

          <aside className="live-board overflow-hidden" aria-label="近期报价样本">
            <div className="flex items-start justify-between gap-4 border-b border-[color:var(--line)] p-5 sm:p-6">
              <div><p className="section-kicker">Live catalog</p><h2 className="mt-2 text-xl font-semibold tracking-[-.03em]">现在值得先看的报价</h2></div>
              <span className="status-pill status-success">实时快照</span>
            </div>
            <div className="divide-y divide-[color:var(--line)]">
              {products.slice(0, 3).map((product) => (
                <Link key={product.slug} href={`/products/${encodeURIComponent(product.slug)}`} className="group grid min-h-[96px] grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-5 py-4 transition-colors hover:bg-[color:var(--brand-soft)]/55 sm:px-6">
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 text-xs text-[color:var(--muted)]"><PlatformIcon platform={product.brand} size={14} />{product.brand} · {relativeTime(product.last_updated_at)}</p>
                    <h3 className="mt-2 truncate font-semibold tracking-[-.02em] group-hover:text-[color:var(--brand-strong)]">{product.display_name}</h3>
                    <p className="mt-1 flex items-center gap-1.5 text-xs text-[color:var(--muted)]"><Package size={14} />{product.in_stock_count} 条有货</p>
                  </div>
                  <div className="text-right">
                    <p className="mono text-lg font-semibold">{money(product.lowest_price, product.price_currency)}</p>
                    <p className="mt-1 text-[11px] text-[color:var(--muted)]">近期最低</p>
                  </div>
                </Link>
              ))}
            </div>
            <Link href="/products" className="live-board-link">进入完整目录 <ArrowRight size={17} /></Link>
          </aside>
        </div>

        <div className="shell relative z-[1] grid gap-3 pb-8 sm:grid-cols-3 lg:pb-10">
          <div className="metric-card"><p className="data-label">标准商品</p><p className="data-value">{data.total}<span className="ml-1 text-sm font-normal text-[color:var(--muted)]">种</span></p><p className="metric-note">统一商品口径后再比较</p></div>
          <div className="metric-card"><p className="data-label">当前报价</p><p className="data-value">{data.offer_count}<span className="ml-1 text-sm font-normal text-[color:var(--muted)]">条</span></p><p className="metric-note">来自公开可访问来源</p></div>
          <div className="metric-card"><p className="data-label">有货报价</p><p className="data-value">{data.in_stock_count}<span className="ml-1 text-sm font-normal text-[color:var(--muted)]">条</span></p><p className="metric-note">{exactTime(data.snapshot_at)} 更新</p></div>
        </div>
      </section>

      <section className="shell py-14 sm:py-20">
        <SectionIntro eyebrow="价格排行" title="近期有货低价" description="优先展示近期更新、仍有库存的同类型报价。明显异常或长时间未更新的价格不会排在最前面。" action={<Link href="/products" className="button-secondary">查看全部报价 <ArrowRight size={17} /></Link>} />
        <div className="mt-2">{products.map((product, index) => <ProductCard key={product.slug} product={product} index={index} />)}</div>
      </section>

      <section className="trust-band">
        <div className="shell grid lg:grid-cols-[.62fr_1.38fr]">
          <div className="border-b border-white/12 py-12 lg:border-b-0 lg:border-r lg:border-white/12 lg:pr-12 lg:py-16">
            <p className="section-kicker !text-[color:var(--accent)]">为什么这份报价更容易判断</p>
            <h2 className="mt-5 text-4xl font-semibold leading-[1.02] tracking-[-.055em] sm:text-5xl">把证据放前面，<br />把决定留给你。</h2>
            <p className="mt-5 max-w-md text-sm leading-7 text-white/60">不把“最低价”包装成推荐。所有关键判断都尽量回到来源、时间和商品原文。</p>
            <Link href="/methodology" className="mt-7 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-[color:var(--accent)]">查看完整方法 <ArrowRight size={17} /></Link>
          </div>
          <div className="divide-y divide-white/10 lg:grid lg:grid-cols-2 lg:divide-x lg:divide-y-0 lg:divide-white/10">
            {[
              { Icon: Database, title: "能找到来源", copy: "每条报价都会保留店铺、商品标题和原始购买链接。" },
              { Icon: Clock, title: "显示更新时间", copy: "长时间没有更新的报价，会降低展示优先级。" },
              { Icon: ShieldCheck, title: "风险提示有出处", copy: "只提示商品原文中明确写出的限制、质保和售后说明。" },
              { Icon: CheckCircle, title: "发现错误可反馈", copy: "分类、价格或库存有问题，可以随时提交纠错。" },
            ].map(({ Icon, title, copy }, index) => <div key={title} className="trust-cell p-7 lg:p-9"><div className="flex items-center justify-between"><span className="trust-icon"><Icon size={23} /></span><span className="mono text-xs text-white/30">0{index + 1}</span></div><h3 className="mt-8 text-xl font-semibold">{title}</h3><p className="mt-3 max-w-sm text-sm leading-6 text-white/60">{copy}</p></div>)}
          </div>
        </div>
      </section>
    </main>
  );
}
