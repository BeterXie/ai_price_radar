import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, CheckCircle, Clock, Database, Package, ShieldCheck } from "@phosphor-icons/react/ssr";
import { SearchBox } from "@/components/search-box";
import { ProductCard } from "@/components/product-card";
import { PlatformIcon } from "@/components/platform-icon";
import { SectionIntro } from "@/components/page-shell";
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
    siteName: "AI Price Radar",
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
  return (
    <main id="main-content" data-vds-schema="v3.1" data-vds-layer="field" data-vds-action="snapshot-rail ledger-alignment semantic-search responsive-recomposition">
      <div className="snapshot-rail" data-vds-role="evidence" data-vds-cause="持续显示本轮报价的新鲜度与来源证据">
        <div className="shell snapshot-rail-inner">
          <span className="snapshot-state">{data.snapshot_at ? `${relativeTime(data.snapshot_at)}完成刷新` : "暂未取得刷新时间"}</span>
          <span>快照 #{data.snapshot_id || "—"} · {data.offer_count} 条报价 · {data.in_stock_count} 条有货</span>
          <span>每条报价保留来源和观测时间</span>
        </div>
      </div>

      <section className="home-hero border-b border-[color:var(--line-strong)]">
        <div className="shell grid items-center gap-10 py-10 lg:grid-cols-[minmax(0,1.08fr)_minmax(360px,.72fr)] lg:py-14 xl:gap-16" data-vds-layer="event">
          <div className="min-w-0">
            <p className="eyebrow">公开 AI 商品报价</p>
            <h1 className="display-title mt-4" data-vds-role="title">先分清商品，<span className="whitespace-nowrap">再比较价格</span></h1>
            <p className="lede mt-5" data-vds-role="explanation">把公开店铺里的订阅、账号、API 额度和辅助服务整理到同一份报价台账。按库存、交付方式、来源和更新时间筛选，再进入商品页核对。</p>
            <div className="mt-7 max-w-2xl"><SearchBox /></div>
            <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-[color:var(--muted)]">
              <span className="font-medium">常用入口</span>
              <Link href="/products?platform=OpenAI" className="quick-link">OpenAI</Link>
              <Link href="/products?platform=Claude" className="quick-link">Claude</Link>
              <Link href="/products?in_stock=true" className="quick-link">仅看有货</Link>
              <Link href="/guides/buying-checklist" className="quick-link">购买前检查</Link>
            </div>
          </div>

          <aside className="live-board min-w-0 overflow-hidden" aria-label="刚更新的有货报价" data-vds-layer="evidence">
            <div className="flex items-center justify-between gap-4 border-b border-[color:var(--line)] p-5">
              <h2 className="text-lg font-semibold tracking-[-.025em]">刚更新的有货报价</h2>
              <span className={`status-pill ${data.snapshot_at ? "status-success" : "status-info"}`}>{data.snapshot_at ? `${relativeTime(data.snapshot_at)}刷新` : "暂无更新时间"}</span>
            </div>
            <div className="divide-y divide-[color:var(--line)]">
              {products.slice(0, 3).map((product) => (
                <Link key={product.slug} href={`/products/${encodeURIComponent(product.slug)}`} className="group grid min-h-[92px] grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-5 py-4 hover:bg-[color:var(--subtle)]">
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 text-xs text-[color:var(--muted)]"><PlatformIcon platform={product.brand} size={14} />{product.brand} · {relativeTime(product.last_updated_at)}</p>
                    <h3 className="mt-2 truncate font-semibold tracking-[-.02em] group-hover:underline">{product.display_name}</h3>
                    <p className="mt-1 flex items-center gap-1.5 text-xs text-[color:var(--muted)]"><Package size={14} />{product.in_stock_count} 条有货</p>
                  </div>
                  <div className="text-right">
                    <p className="mono text-lg font-semibold">{money(product.lowest_price, product.price_currency)}</p>
                    <p className="mt-1 text-[11px] text-[color:var(--muted)]">观测价</p>
                  </div>
                </Link>
              ))}
            </div>
            <Link href="/products" className="live-board-link" data-vds-role="action">查看全部报价 <ArrowRight size={17} /></Link>
          </aside>
        </div>

        <dl className="shell home-stats" aria-label="报价概况">
          <div><dt>商品分类</dt><dd>{data.total} 种</dd></div>
          <div><dt>当前报价</dt><dd>{data.offer_count} 条</dd></div>
          <div><dt>有货报价</dt><dd>{data.in_stock_count} 条</dd></div>
          <div><dt>最近更新</dt><dd>{exactTime(data.snapshot_at)}</dd></div>
        </dl>
      </section>

      <section className="shell py-12 sm:py-16" data-vds-layer="evidence">
        <SectionIntro title="当前报价" description="优先显示有货、近期更新且商品口径明确的报价。" action={<Link href="/products" className="button-secondary">查看全部报价 <ArrowRight size={17} /></Link>} />
        <div className="mt-2">{products.map((product) => <ProductCard key={product.slug} product={product} />)}</div>
      </section>

      <section className="method-band border-y border-[color:var(--line-strong)]">
        <div className="shell grid lg:grid-cols-[.58fr_1.42fr]">
          <div className="border-b border-[color:var(--line)] py-10 lg:border-b-0 lg:border-r lg:pr-10 lg:py-12">
            <h2 className="text-3xl font-semibold tracking-[-.04em]">报价包含哪些信息</h2>
            <p className="mt-4 max-w-md text-sm leading-7 text-[color:var(--muted)]">每条报价保留来源、更新时间、商品类型和交付说明。用于展示的参考价只在同类商品内计算。</p>
            <Link href="/methodology" className="mt-6 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-[color:var(--brand-strong)]">查看数据方法 <ArrowRight size={17} /></Link>
          </div>
          <div className="divide-y divide-[color:var(--line)] lg:grid lg:grid-cols-2 lg:divide-x lg:divide-y-0">
            {[
              { Icon: Database, title: "查看原始商品页", copy: "每条报价都会保留店铺、商品标题和原始购买链接。" },
              { Icon: Clock, title: "标明数据时间", copy: "每条报价都会显示最近一次观测时间，长时间未更新的报价会降低展示优先级。" },
              { Icon: ShieldCheck, title: "限制来自商品说明", copy: "限制、质保和售后提示只引用商品原文，不替商家补充或推断。" },
              { Icon: CheckCircle, title: "有误可提交纠错", copy: "分类、价格或库存有问题，可以提交纠错。" },
            ].map(({ Icon, title, copy }) => <div key={title} className="method-item p-7 lg:p-8"><Icon size={22} className="text-[color:var(--brand)]" /><h3 className="mt-5 text-lg font-semibold">{title}</h3><p className="mt-2 max-w-sm text-sm leading-6 text-[color:var(--muted)]">{copy}</p></div>)}
          </div>
        </div>
      </section>
    </main>
  );
}
