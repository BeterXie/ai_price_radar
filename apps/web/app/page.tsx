import Link from "next/link";
import { ArrowRight, CheckCircle, Clock, Database, ShieldCheck } from "@phosphor-icons/react/ssr";
import { SearchBox } from "@/components/search-box";
import { ProductCard } from "@/components/product-card";
import { getProducts } from "@/lib/api";
import { exactTime } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const data = await getProducts("sort=price");
  const products = data.items.slice(0, 6);
  return (
    <main id="main-content">
      <section className="grid-noise border-b hairline">
        <div className="shell grid min-h-[620px] items-stretch lg:grid-cols-[1.45fr_.55fr]">
          <div className="flex flex-col justify-between border-r-0 hairline py-14 lg:border-r lg:pr-14 lg:py-20">
            <div>
              <p className="mono flex items-center gap-3 text-xs tracking-[.18em]"><span className="signal-dot" />公开报价情报</p>
              <h1 className="mt-8 max-w-4xl text-[clamp(3.4rem,8vw,7.8rem)] font-semibold leading-[.88] tracking-[-.075em]">别只看低价。<br /><span className="text-black/35">先看它还能不能买。</span></h1>
              <p className="mt-8 max-w-2xl text-lg leading-8 text-[color:var(--muted)]">聚合公开 AI 订阅商品，保留原始标题、库存、更新时间和来源链接。价格负责吸引注意，证据负责帮助决策。</p>
            </div>
            <div className="mt-14 max-w-3xl"><SearchBox /></div>
          </div>
          <aside className="flex flex-col justify-end py-14 lg:pl-10 lg:py-20">
            <div className="border-t border-black pt-5">
              <p className="mono text-xs tracking-[.14em] text-black/45">实时目录</p>
              <div className="mt-6 space-y-8">
                <div><p className="text-5xl font-semibold tracking-[-.06em]">{data.total}</p><p className="mt-1 text-sm text-black/50">标准产品类别</p></div>
                <div><p className="text-5xl font-semibold tracking-[-.06em]">{data.offer_count}</p><p className="mt-1 text-sm text-black/50">当前有效报价</p></div>
                <div><p className="text-5xl font-semibold tracking-[-.06em]">{data.in_stock_count}</p><p className="mt-1 text-sm text-black/50">有货报价</p></div>
              </div>
              <p className="mt-8 text-xs leading-5 text-black/35">数据快照 #{data.snapshot_id || "-"}<br />{exactTime(data.snapshot_at)}</p>
            </div>
          </aside>
        </div>
      </section>

      <section className="shell py-20">
        <div className="flex items-end justify-between gap-6 border-b border-black pb-5">
          <div><p className="mono text-xs tracking-[.14em] text-black/45">当前低价</p><h2 className="mt-3 text-4xl font-semibold tracking-[-.05em]">可直接比较的有货低价</h2></div>
          <Link href="/products" className="flex items-center gap-2 text-sm font-medium">查看全部 <ArrowRight size={17} /></Link>
        </div>
        <div>{products.map((product, index) => <ProductCard key={product.slug} product={product} index={index} />)}</div>
      </section>

      <section className="border-y border-black bg-[color:var(--accent)] text-[color:var(--accent-ink)]">
        <div className="shell grid lg:grid-cols-[.7fr_1.3fr]">
          <div className="border-b border-black py-12 lg:border-b-0 lg:border-r lg:pr-12"><p className="mono text-xs tracking-[.15em]">数据可信机制</p><h2 className="mt-5 text-5xl font-semibold leading-none tracking-[-.06em]">不替渠道背书。<br />只保留可回看的事实。</h2></div>
          <div className="grid gap-px bg-black lg:grid-cols-2">
            {[
              { Icon: Database, title: "保留来源", copy: "原始店铺、商品标题和购买链接都能回看。" },
              { Icon: Clock, title: "标记时间", copy: "长期未更新的低价不会参与最低价计算。" },
              { Icon: ShieldCheck, title: "风险用事实表达", copy: "只展示标题中出现的无售后、无质保等文字。" },
              { Icon: CheckCircle, title: "人工审核", copy: "异常分类和举报可在后台修正或隐藏。" },
            ].map(({ Icon, title, copy }) => <div key={title} className="bg-[color:var(--accent)] p-8"><Icon size={28} /><h3 className="mt-8 text-xl font-semibold">{title}</h3><p className="mt-3 max-w-sm text-sm leading-6 opacity-70">{copy}</p></div>)}
          </div>
        </div>
      </section>
    </main>
  );
}
