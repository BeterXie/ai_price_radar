import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, CheckCircle, Clock, Database, ShieldCheck } from "@phosphor-icons/react/ssr";
import { SearchBox } from "@/components/search-box";
import { ProductCard } from "@/components/product-card";
import { getProducts } from "@/lib/api";
import { exactTime } from "@/lib/format";

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
      <section className="grid-noise border-b hairline">
        <div className="shell grid min-h-[620px] items-stretch lg:grid-cols-[1.45fr_.55fr]">
          <div className="flex flex-col justify-between border-r-0 hairline py-14 lg:border-r lg:pr-14 lg:py-20">
            <div>
              <p className="mono flex items-center gap-3 text-xs tracking-[.18em]"><span className="signal-dot" />AI 订阅比价</p>
              <h1 className="mt-8 max-w-4xl text-[clamp(3.4rem,8vw,7.8rem)] font-semibold leading-[.88] tracking-[-.075em]">先确认有货，<br /><span className="text-black/35">再比较价格。</span></h1>
              <p className="mt-8 max-w-2xl text-lg leading-8 text-[color:var(--muted)]">把不同店铺的 AI 订阅和账号报价整理到一起。价格、库存、交付方式和最近更新时间，都可以直接比较。</p>
            </div>
            <div className="mt-14 max-w-3xl"><SearchBox /></div>
          </div>
          <aside className="flex flex-col justify-end py-14 lg:pl-10 lg:py-20">
            <div className="border-t border-black pt-5">
              <p className="mono text-xs tracking-[.14em] text-black/45">当前收录</p>
              <div className="mt-6 space-y-8">
                <div><p className="text-5xl font-semibold tracking-[-.06em]">{data.total}</p><p className="mt-1 text-sm text-black/50">种商品</p></div>
                <div><p className="text-5xl font-semibold tracking-[-.06em]">{data.offer_count}</p><p className="mt-1 text-sm text-black/50">条报价</p></div>
                <div><p className="text-5xl font-semibold tracking-[-.06em]">{data.in_stock_count}</p><p className="mt-1 text-sm text-black/50">条有货报价</p></div>
              </div>
              <p className="mt-8 text-xs leading-5 text-black/35">数据更新于：{exactTime(data.snapshot_at)}</p>
            </div>
          </aside>
        </div>
      </section>

      <section className="shell py-20">
        <div className="flex items-end justify-between gap-6 border-b border-black pb-5">
          <div><p className="mono text-xs tracking-[.14em] text-black/45">价格排行</p><h2 className="mt-3 text-4xl font-semibold tracking-[-.05em]">近期有货低价</h2><p className="mt-3 max-w-2xl text-sm leading-6 text-black/45">优先展示近期更新、仍有库存的同类型报价。明显异常或长时间未更新的价格不会排在最前面。</p></div>
          <Link href="/products" className="flex items-center gap-2 text-sm font-medium">查看全部报价 <ArrowRight size={17} /></Link>
        </div>
        <div>{products.map((product, index) => <ProductCard key={product.slug} product={product} index={index} />)}</div>
      </section>

      <section className="border-y border-black bg-[color:var(--accent)] text-[color:var(--accent-ink)]">
        <div className="shell grid lg:grid-cols-[.7fr_1.3fr]">
          <div className="border-b border-black py-12 lg:border-b-0 lg:border-r lg:pr-12"><p className="mono text-xs tracking-[.15em]">报价是怎么整理的</p><h2 className="mt-5 text-5xl font-semibold leading-none tracking-[-.06em]">信息尽量说清楚，<br />选择留给你。</h2></div>
          <div className="grid gap-px bg-black lg:grid-cols-2">
            {[
              { Icon: Database, title: "能找到来源", copy: "每条报价都会保留店铺、商品标题和原始购买链接。" },
              { Icon: Clock, title: "显示更新时间", copy: "长时间没有更新的报价，会降低展示优先级。" },
              { Icon: ShieldCheck, title: "风险提示有出处", copy: "只提示商品原文中明确写出的限制、质保和售后说明。" },
              { Icon: CheckCircle, title: "发现错误可反馈", copy: "分类、价格或库存有问题，可以随时提交纠错。" },
            ].map(({ Icon, title, copy }) => <div key={title} className="bg-[color:var(--accent)] p-8"><Icon size={28} /><h3 className="mt-8 text-xl font-semibold">{title}</h3><p className="mt-3 max-w-sm text-sm leading-6 opacity-70">{copy}</p></div>)}
          </div>
        </div>
      </section>
    </main>
  );
}
