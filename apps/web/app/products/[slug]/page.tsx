import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Clock, Package, Tag } from "@phosphor-icons/react/ssr";
import { OfferTable } from "@/components/offer-table";
import { PlatformIcon } from "@/components/platform-icon";
import { PriceHistory } from "@/components/price-history";
import { ReportForm } from "@/components/report-form";
import { getProduct } from "@/lib/api";
import { money, relativeTime } from "@/lib/format";

export const dynamic = "force-static";
export const revalidate = 60;

const PRODUCT_TYPE_LABELS: Record<string, string> = {
  subscription: "订阅 / 会员",
  account: "成品账号",
  api: "API / 额度",
  service: "辅助服务",
  team: "团队订阅",
};

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const product = await getProduct(slug);
  return { title: product ? `${product.display_name}价格对比` : "产品不存在", description: product?.description };
}

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) notFound();
  return (
    <main className="shell py-8 md:py-10">
      <Link href="/products" className="inline-flex items-center gap-2 text-sm text-black/55 hover:text-black"><ArrowLeft size={16} />返回报价目录</Link>
      <section className="mt-6 grid gap-8 rounded-[18px] border hairline bg-[color:var(--panel)] p-6 lg:grid-cols-[1.3fr_.7fr] lg:p-8">
        <div>
          <div className="flex flex-wrap gap-2"><span className="flex items-center gap-2 rounded-full bg-black/6 px-3 py-1 text-xs"><PlatformIcon platform={product.platform} size={14} />{product.platform}</span>{product.in_stock_count > 0 && <span className="flex items-center gap-2 rounded-full border hairline px-3 py-1 text-xs"><span className="signal-dot" />有货</span>}</div>
          <h1 className="mt-5 text-[clamp(2.6rem,5vw,4.8rem)] font-semibold leading-none tracking-[-.065em]">{product.display_name}</h1>
          <p className="mt-5 max-w-2xl leading-7 text-[color:var(--muted)]">{product.description}</p>
          <div className="mt-5 flex flex-wrap gap-2">{product.tags.map((tag) => <span key={tag} className="rounded-full border hairline px-3 py-1.5 text-xs">{tag}</span>)}</div>
        </div>
        <aside className="flex flex-col justify-end border-t hairline pt-6 lg:border-t-0 lg:border-l lg:pl-8">
          <p className="mono text-xs uppercase tracking-[.15em] text-black/45">当前最低有货价</p>
          <p className="mt-3 text-5xl font-semibold tracking-[-.065em]">{money(product.lowest_price)}</p>
          <div className="mt-6 space-y-3 text-sm text-black/55"><p className="flex items-center gap-2"><Package size={18} />{product.in_stock_count} 个有货，{product.offer_count} 个有效报价</p><p className="flex items-center gap-2"><Clock size={18} />最近更新 {relativeTime(product.last_updated_at)}</p><p className="flex items-center gap-2"><Tag size={18} />分类：{PRODUCT_TYPE_LABELS[product.product_type] || product.product_type}</p></div>
        </aside>
      </section>

      <section className="py-12">
        <div className="mb-6">
          <h2 className="text-3xl font-semibold tracking-[-.04em]">渠道报价</h2>
          <p className="mt-2 text-sm text-black/50">保留商家原始标题、分类和描述，有货与低价优先。</p>
        </div>
        <OfferTable offers={product.offers} productSlug={product.slug} totalCount={product.offer_count} />
      </section>

      <section className="grid gap-10 border-t border-black py-12 lg:grid-cols-[1.35fr_.65fr]">
        <div><h2 className="mb-5 text-3xl font-semibold tracking-[-.04em]">价格轨迹</h2><PriceHistory points={product.history} /></div>
        <aside><ReportForm /></aside>
      </section>
    </main>
  );
}
