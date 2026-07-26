import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Clock, Package, Tag } from "@phosphor-icons/react/ssr";
import { OfferGroupTable } from "@/components/offer-table";
import { PlatformIcon } from "@/components/platform-icon";
import { PriceHistory } from "@/components/price-history";
import { ReportForm } from "@/components/report-form";
import { DELIVERY_TYPE_LABELS, PERIOD_LABELS, WARRANTY_LABELS } from "@/lib/catalog";
import { getProduct } from "@/lib/api";
import { exactTime, money, relativeTime } from "@/lib/format";

export const dynamic = "force-dynamic";

const SITE_URL = "https://ai.pricememo.cn";
const PRODUCT_TYPE_LABELS: Record<string, string> = {
  subscription: "订阅 / 会员",
  account: "成品账号",
  api: "API / 额度",
  service: "辅助服务",
  team: "团队订阅",
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function single(params: Record<string, string | string[] | undefined>, key: string) {
  const value = params[key];
  return Array.isArray(value) ? value[value.length - 1] || "" : value || "";
}

function offerQuery(params: Record<string, string | string[] | undefined>) {
  const query = new URLSearchParams();
  ["delivery_type", "period", "warranty", "auto_delivery", "updated_within_hours", "exclude"].forEach((key) => {
    const value = single(params, key);
    if (value) query.set(key, value);
  });
  query.set("comparable", single(params, "comparable") || "true");
  if (single(params, "in_stock") === "true") query.set("in_stock", "true");
  return query;
}

export async function generateMetadata({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: SearchParams }): Promise<Metadata> {
  const [{ slug }, rawParams] = await Promise.all([params, searchParams]);
  const product = await getProduct(slug, "comparable=true");
  const canonical = `${SITE_URL}/products/${encodeURIComponent(slug)}`;
  const hasFilters = Object.keys(rawParams).length > 0;
  return {
    title: product ? `${product.display_name}价格对比` : "产品不存在",
    description: product?.description,
    alternates: { canonical },
    robots: hasFilters ? { index: false, follow: true } : { index: true, follow: true },
    openGraph: product ? { title: `${product.display_name}价格对比`, description: product.description, url: canonical, type: "website" } : undefined,
  };
}

export default async function ProductPage({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: SearchParams }) {
  const [{ slug }, rawParams] = await Promise.all([params, searchParams]);
  const query = offerQuery(rawParams);
  const product = await getProduct(slug, query.toString());
  if (!product) notFound();

  const structuredData = product.lowest_price ? {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.display_name,
    description: product.description,
    category: product.product_type,
    brand: { "@type": "Brand", name: product.platform },
    offers: {
      "@type": "AggregateOffer",
      priceCurrency: "CNY",
      lowPrice: product.lowest_price,
      highPrice: product.highest_price || product.lowest_price,
      offerCount: product.comparable_offer_count,
      availability: product.in_stock_count > 0 ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
      url: `${SITE_URL}/products/${encodeURIComponent(product.slug)}`,
    },
  } : null;

  return (
    <main id="main-content" className="shell py-8 md:py-10">
      {structuredData && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }} />}
      <Link href="/products" className="inline-flex items-center gap-2 text-sm text-black/55 hover:text-black"><ArrowLeft size={16} />返回报价目录</Link>
      <section className="mt-6 grid gap-8 rounded-[18px] border hairline bg-[color:var(--panel)] p-6 lg:grid-cols-[1.3fr_.7fr] lg:p-8">
        <div>
          <div className="flex flex-wrap gap-2"><span className="flex items-center gap-2 rounded-full bg-black/6 px-3 py-1 text-xs"><PlatformIcon platform={product.platform} size={14} />{product.platform}</span>{product.in_stock_count > 0 && <span className="flex items-center gap-2 rounded-full border hairline px-3 py-1 text-xs"><span className="signal-dot" />有货</span>}</div>
          <h1 className="mt-5 text-[clamp(2.6rem,5vw,4.8rem)] font-semibold leading-none tracking-[-.065em]">{product.display_name}</h1>
          <p className="mt-5 max-w-2xl leading-7 text-[color:var(--muted)]">{product.description}</p>
          <div className="mt-5 flex flex-wrap gap-2">{product.tags.map((tag) => <span key={tag} className="rounded-full border hairline px-3 py-1.5 text-xs">{tag}</span>)}</div>
        </div>
        <aside className="flex flex-col justify-end border-t hairline pt-6 lg:border-t-0 lg:border-l lg:pl-8">
          <p className="mono text-xs uppercase tracking-[.15em] text-black/45">可直接比较最低价</p>
          <p className="mt-3 text-5xl font-semibold tracking-[-.065em]">{money(product.lowest_price)}</p>
          {product.related_lowest_price && product.related_lowest_price !== product.lowest_price && <p className="mt-2 text-sm text-black/45">全部相关商品最低价 {money(product.related_lowest_price)}</p>}
          <div className="mt-6 space-y-3 text-sm text-black/55">
            <p className="flex items-center gap-2"><Package size={18} />{product.in_stock_count} 条有货，{product.offer_count} 条有效报价</p>
            <p className="flex items-center gap-2"><Clock size={18} />最近更新 {relativeTime(product.last_updated_at)}</p>
            <p className="flex items-center gap-2"><Tag size={18} />分类：{PRODUCT_TYPE_LABELS[product.product_type] || product.product_type}</p>
          </div>
        </aside>
      </section>

      <section className="grid gap-3 border-b hairline py-6 sm:grid-cols-2 lg:grid-cols-4" aria-label="不同交付形态最低价">
        {product.price_breakdown.filter((item) => item.lowest_price).map((item) => (
          <div key={item.delivery_type} className="rounded-[12px] border hairline bg-[color:var(--panel)] p-4">
            <p className="text-xs text-black/45">{DELIVERY_TYPE_LABELS[item.delivery_type] || item.delivery_type}</p>
            <p className="mono mt-2 text-2xl font-semibold">{money(item.lowest_price)}</p>
            <p className="mt-1 text-xs text-black/40">{item.in_stock_count} 条有货</p>
          </div>
        ))}
      </section>

      <section className="py-8">
        <form className="rounded-[14px] border border-black bg-white p-4">
          <fieldset>
            <legend className="px-1 text-sm font-semibold">筛选同类报价</legend>
            <div className="mt-3 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
              <label className="text-xs text-black/55">交付形态<select name="delivery_type" defaultValue={single(rawParams, "delivery_type")} className="mt-1 w-full rounded-[8px] border hairline bg-transparent px-3 py-2 text-sm text-black"><option value="">全部形态</option>{Object.entries(DELIVERY_TYPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
              <label className="text-xs text-black/55">使用期限<select name="period" defaultValue={single(rawParams, "period")} className="mt-1 w-full rounded-[8px] border hairline bg-transparent px-3 py-2 text-sm text-black"><option value="">全部期限</option>{Object.entries(PERIOD_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
              <label className="text-xs text-black/55">质保<select name="warranty" defaultValue={single(rawParams, "warranty")} className="mt-1 w-full rounded-[8px] border hairline bg-transparent px-3 py-2 text-sm text-black"><option value="">全部质保</option>{Object.entries(WARRANTY_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
              <label className="text-xs text-black/55">更新时间<select name="updated_within_hours" defaultValue={single(rawParams, "updated_within_hours")} className="mt-1 w-full rounded-[8px] border hairline bg-transparent px-3 py-2 text-sm text-black"><option value="">72 小时有效期内</option><option value="1">1 小时内</option><option value="24">24 小时内</option><option value="168">7 天内</option></select></label>
              <label className="text-xs text-black/55">发货方式<select name="auto_delivery" defaultValue={single(rawParams, "auto_delivery")} className="mt-1 w-full rounded-[8px] border hairline bg-transparent px-3 py-2 text-sm text-black"><option value="">不限</option><option value="true">自动发货</option><option value="false">人工交付</option></select></label>
              <label className="text-xs text-black/55 lg:col-span-2">排除词<input name="exclude" defaultValue={single(rawParams, "exclude")} placeholder="例如：号池,中转,接码,日抛" aria-label="排除标题中包含的词，多个词用逗号分隔" className="mt-1 w-full rounded-[8px] border hairline bg-transparent px-3 py-2 text-sm text-black" /></label>
              <div className="flex flex-wrap items-end gap-4 pb-2 text-sm">
                <label className="flex items-center gap-2"><input type="hidden" name="comparable" value="false" /><input type="checkbox" name="comparable" value="true" defaultChecked={single(rawParams, "comparable") !== "false"} className="h-4 w-4 accent-black" />仅显示可直接比较</label>
                <label className="flex items-center gap-2"><input type="checkbox" name="in_stock" value="true" defaultChecked={single(rawParams, "in_stock") === "true"} className="h-4 w-4 accent-black" />仅看有货</label>
              </div>
            </div>
          </fieldset>
          <div className="mt-4 flex gap-3"><button className="tactile rounded-[9px] bg-[color:var(--ink)] px-5 py-2.5 text-sm text-white">应用筛选</button><Link href={`/products/${product.slug}`} className="rounded-[9px] border border-black px-5 py-2.5 text-sm">重置</Link></div>
        </form>
      </section>

      <section className="pb-12">
        <div className="mb-6">
          <h2 className="text-3xl font-semibold tracking-[-.04em]">同款报价</h2>
          <p className="mt-2 text-sm text-black/50">相同商品默认合并为一行；当前显示 {product.offer_group_count} 款，可展开查看全部店铺和按需加载原始描述。</p>
        </div>
        <OfferGroupTable groups={product.offer_groups} productSlug={product.slug} totalCount={product.offer_group_count} snapshotId={product.snapshot_id} filterQuery={query.toString()} />
      </section>

      <section className="grid gap-10 border-t border-black py-12 lg:grid-cols-[1.35fr_.65fr]">
        <div><h2 className="mb-5 text-3xl font-semibold tracking-[-.04em]">价格轨迹</h2><PriceHistory points={product.history} /></div>
        <aside><ReportForm /></aside>
      </section>
      <p className="border-t hairline py-5 text-xs text-black/40">数据快照：{product.snapshot_id ? `#${product.snapshot_id}` : "未编号"} · {exactTime(product.snapshot_at)}</p>
    </main>
  );
}
