import Link from "next/link";
import { Clock, Package, Tag } from "@phosphor-icons/react/ssr";
import { OfferGroupTable } from "@/components/offer-table";
import { PlatformIcon } from "@/components/platform-icon";
import { PriceHistory } from "@/components/price-history";
import { ReportForm } from "@/components/report-form";
import { exactTime, money, relativeTime } from "@/lib/format";
import type { ProductDetail } from "@/lib/types";

const PRODUCT_TYPE_LABELS: Record<string, string> = {
  subscription: "订阅 / 会员",
  account: "成品账号",
  api: "API / 额度",
  service: "辅助服务",
  team: "团队订阅",
};

export type RawSearchParams = Record<string, string | string[] | undefined>;

export function single(params: RawSearchParams, key: string) {
  const value = params[key];
  return Array.isArray(value) ? value[value.length - 1] || "" : value || "";
}

export function offerQuery(params: RawSearchParams) {
  const query = new URLSearchParams();
  query.set("comparable", single(params, "comparable") || "true");
  if (single(params, "in_stock") === "true") query.set("in_stock", "true");
  return query;
}

export function ProductWorkspace({
  product,
  rawParams,
  query,
  filterAction,
  resetHref,
  hiddenFields = {},
}: {
  product: ProductDetail;
  rawParams: RawSearchParams;
  query: URLSearchParams;
  filterAction: string;
  resetHref: string;
  hiddenFields?: Record<string, string>;
}) {
  const canonical = `https://ai.pricememo.cn/products?platform=${encodeURIComponent(product.platform)}&product=${encodeURIComponent(product.slug)}`;
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
      url: canonical,
    },
  } : null;

  return (
    <>
      {structuredData && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }} />}
      <section className="mt-5 rounded-[16px] border hairline bg-[color:var(--panel)] p-5">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px] lg:items-center">
          <div>
            <div className="flex flex-wrap gap-2"><span className="flex items-center gap-2 rounded-full bg-black/6 px-3 py-1 text-xs"><PlatformIcon platform={product.platform} size={14} />{product.platform}</span>{product.in_stock_count > 0 && <span className="flex items-center gap-2 rounded-full border hairline px-3 py-1 text-xs"><span className="signal-dot" />有货</span>}</div>
            <h1 className="mt-3 text-[clamp(2rem,4vw,3.5rem)] font-semibold leading-none tracking-[-.06em]">{product.display_name}</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[color:var(--muted)]">{product.description}</p>
          </div>
          <aside className="border-t hairline pt-4 lg:border-t-0 lg:border-l lg:pl-6">
            <p className="mono text-xs tracking-[.12em] text-black/45">可直接比较最低价</p>
            <p className="mt-1 text-4xl font-semibold tracking-[-.06em]">{money(product.lowest_price)}</p>
            {product.related_lowest_price && product.related_lowest_price !== product.lowest_price && <p className="mt-1 text-xs text-black/45">全部相关商品最低价 {money(product.related_lowest_price)}</p>}
          </aside>
        </div>
        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 border-t hairline pt-3 text-xs text-black/50">
          <p className="flex items-center gap-1.5"><Package size={15} />{product.in_stock_count} 条有货，{product.offer_count} 条有效报价</p>
          <p className="flex items-center gap-1.5"><Clock size={15} />最近更新 {relativeTime(product.last_updated_at)}</p>
          <p className="flex items-center gap-1.5"><Tag size={15} />{PRODUCT_TYPE_LABELS[product.product_type] || product.product_type}</p>
        </div>
      </section>

      <section className="py-5">
        <form action={filterAction} className="flex flex-wrap items-center justify-between gap-4 rounded-[12px] border border-black bg-white px-4 py-3">
          {Object.entries(hiddenFields).map(([name, value]) => <input key={name} type="hidden" name={name} value={value} />)}
          <fieldset className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
            <legend className="sr-only">报价范围</legend>
            <span className="font-semibold">报价范围</span>
            <label className="flex items-center gap-2"><input type="hidden" name="comparable" value="false" /><input type="checkbox" name="comparable" value="true" defaultChecked={single(rawParams, "comparable") !== "false"} className="h-4 w-4 accent-black" />仅显示可直接比较</label>
            <label className="flex items-center gap-2"><input type="checkbox" name="in_stock" value="true" defaultChecked={single(rawParams, "in_stock") === "true"} className="h-4 w-4 accent-black" />仅看有货</label>
          </fieldset>
          <div className="flex gap-2"><button className="tactile rounded-[8px] bg-[color:var(--ink)] px-4 py-2 text-sm text-white">应用</button><Link href={resetHref} className="rounded-[8px] border border-black px-4 py-2 text-sm">重置</Link></div>
        </form>
      </section>

      <section className="pb-12">
        <div className="mb-6">
          <h2 className="text-3xl font-semibold tracking-[-.04em]">同款报价</h2>
          <p className="mt-2 text-sm text-black/50">相同商品默认合并为一行；当前显示 {product.offer_group_count} 款，可展开查看全部店铺和按需加载原始描述。</p>
        </div>
        <OfferGroupTable
          key={`${product.slug}:${product.snapshot_id || "current"}:${query.toString()}`}
          groups={product.offer_groups}
          productSlug={product.slug}
          totalCount={product.offer_group_count}
          snapshotId={product.snapshot_id}
          filterQuery={query.toString()}
        />
      </section>

      <section className="grid gap-10 border-t border-black py-12 lg:grid-cols-[1.35fr_.65fr]">
        <div><h2 className="mb-5 text-3xl font-semibold tracking-[-.04em]">价格轨迹</h2><PriceHistory points={product.history} /></div>
        <aside><ReportForm /></aside>
      </section>
      <p className="border-t hairline py-5 text-xs text-black/40">数据快照：{product.snapshot_id ? `#${product.snapshot_id}` : "未编号"} · {exactTime(product.snapshot_at)}</p>
    </>
  );
}
