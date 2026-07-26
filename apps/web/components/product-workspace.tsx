import Link from "next/link";
import { Check, Clock, Package, Stack } from "@phosphor-icons/react/ssr";
import { OfferGroupTable } from "@/components/offer-table";
import { PriceHistory } from "@/components/price-history";
import { ReportForm } from "@/components/report-form";
import { exactTime, relativeTime } from "@/lib/format";
import type { ProductDetail } from "@/lib/types";

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
  const comparableOnly = single(rawParams, "comparable") !== "false";
  const inStockOnly = single(rawParams, "in_stock") === "true";
  const scopeHref = (comparable: boolean, inStock: boolean) => {
    const params = new URLSearchParams(hiddenFields);
    params.set("comparable", String(comparable));
    if (inStock) params.set("in_stock", "true");
    return `${filterAction}?${params.toString()}`;
  };

  return (
    <>
      {structuredData && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }} />}
      <h1 className="sr-only">{product.display_name}</h1>
      <section className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-b hairline pb-4 text-sm text-black/50" aria-label={`${product.display_name} 报价概况`}>
        <p className="flex items-center gap-1.5"><Package size={16} />{product.in_stock_count} 条有货</p>
        <p className="flex items-center gap-1.5"><Stack size={16} />{product.offer_count} 条有效报价</p>
        <p className="flex items-center gap-1.5"><Clock size={16} />最近更新 {relativeTime(product.last_updated_at)}</p>
      </section>

      <section className="py-5">
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-[12px] border border-black bg-white px-4 py-3">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm" aria-label="报价范围">
            <span className="font-semibold">报价范围</span>
            <Link href={scopeHref(!comparableOnly, inStockOnly)} aria-pressed={comparableOnly} className="flex items-center gap-2">
              <span className={`grid h-4 w-4 place-items-center border border-black ${comparableOnly ? "bg-black text-white" : "bg-white"}`}>{comparableOnly && <Check size={12} weight="bold" />}</span>
              仅显示可直接比较
            </Link>
            <Link href={scopeHref(comparableOnly, !inStockOnly)} aria-pressed={inStockOnly} className="flex items-center gap-2">
              <span className={`grid h-4 w-4 place-items-center border border-black ${inStockOnly ? "bg-black text-white" : "bg-white"}`}>{inStockOnly && <Check size={12} weight="bold" />}</span>
              仅看有货
            </Link>
          </div>
          <Link href={resetHref} className="rounded-[8px] border border-black px-4 py-2 text-sm">重置</Link>
        </div>
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
