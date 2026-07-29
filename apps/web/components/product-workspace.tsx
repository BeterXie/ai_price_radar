import { ArrowSquareOut, Clock, Package, ShieldCheck, Stack } from "@phosphor-icons/react/ssr";
import { OfferGroupTable } from "@/components/offer-table";
import { OfferScopeControls, type OfferFilterValues } from "@/components/offer-scope-controls";
import { PriceHistory } from "@/components/price-history";
import { ReportForm } from "@/components/report-form";
import { WatchButton } from "@/components/watch-button";
import { exactTime, relativeTime } from "@/lib/format";
import { getProductSeoContent } from "@/lib/product-seo";
import type { ProductDetail } from "@/lib/types";

export type RawSearchParams = Record<string, string | string[] | undefined>;

export function single(params: RawSearchParams, key: string) {
  const value = params[key];
  return Array.isArray(value) ? value[value.length - 1] || "" : value || "";
}

const FILTER_KEYS = ["delivery_type", "period", "warranty", "auto_delivery", "updated_within_hours", "min_price", "max_price"] as const;

export function offerQuery(params: RawSearchParams) {
  const query = new URLSearchParams();
  query.set("comparable", single(params, "comparable") === "false" ? "false" : "true");
  if (single(params, "in_stock") === "true") query.set("in_stock", "true");
  for (const key of FILTER_KEYS) {
    const value = single(params, key);
    if (value) query.set(key, value);
  }
  return query;
}

export function filterValues(params: RawSearchParams): OfferFilterValues {
  return {
    comparable: single(params, "comparable") === "false" ? "false" : "true",
    in_stock: single(params, "in_stock"),
    warranty: single(params, "warranty"),
    delivery_type: single(params, "delivery_type"),
    period: single(params, "period"),
    auto_delivery: single(params, "auto_delivery"),
    updated_within_hours: single(params, "updated_within_hours"),
    min_price: single(params, "min_price"),
    max_price: single(params, "max_price"),
  };
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
  const canonical = `https://ai.pricememo.cn/products/${encodeURIComponent(product.slug)}`;
  const seo = getProductSeoContent(product.slug, product.display_name, product.description);
  const structuredData = product.lowest_price && product.trusted_offer_count > 0 ? {
    "@context": "https://schema.org",
    "@type": "Product",
    "@id": `${canonical}#product`,
    name: product.display_name,
    description: seo.metaDescription,
    image: `${canonical}/opengraph-image`,
    category: product.product_type,
    brand: { "@type": "Brand", name: product.platform },
    offers: {
      "@type": "AggregateOffer",
      priceCurrency: "CNY",
      lowPrice: product.lowest_price,
      highPrice: product.highest_price || product.lowest_price,
      offerCount: product.trusted_offer_count,
      url: canonical,
    },
  } : null;
  const filters = filterValues(rawParams);

  return (
    <>
      {structuredData && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }} />}
      <h1 className="sr-only">{product.display_name}价格对比</h1>
      <section className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-b hairline pb-4 text-sm text-black/50" aria-label={`${product.display_name} 报价概况`}>
        <p className="flex items-center gap-1.5"><ShieldCheck size={16} />{product.trusted_offer_count} 条可信报价</p>
        <p className="flex items-center gap-1.5"><Package size={16} />{product.in_stock_count} 条有货</p>
        <p className="flex items-center gap-1.5"><Stack size={16} />{product.offer_count} 条有效报价</p>
        <p className="flex items-center gap-1.5"><Clock size={16} />最近更新 {relativeTime(product.last_updated_at)}</p>
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-[1fr_auto] lg:items-start">
        <div className="grid gap-px overflow-hidden rounded-[16px] border hairline bg-[color:var(--line)] sm:grid-cols-3">
          <div className="bg-[color:var(--panel)] p-4"><p className="text-xs text-black/45">可信最低价</p><p className="mt-2 text-2xl font-semibold">{product.lowest_price ? `¥${Number(product.lowest_price).toFixed(2)}` : "暂无"}</p></div>
          <div className="bg-[color:var(--panel)] p-4"><p className="text-xs text-black/45">可比中位价</p><p className="mt-2 text-2xl font-semibold">{product.median_price ? `¥${Number(product.median_price).toFixed(2)}` : "暂无"}</p></div>
          <div className="bg-[color:var(--panel)] p-4"><p className="text-xs text-black/45">数据质量</p><p className="mt-2 text-2xl font-semibold">{product.data_quality_score}<span className="ml-1 text-sm font-normal text-black/45">/ 100 · {product.data_quality_label}</span></p><p className="mt-1 text-xs text-black/40">{product.source_count} 个来源</p></div>
        </div>
        <WatchButton slug={product.slug} name={product.display_name} suggestedPrice={product.lowest_price} />
      </section>

      {product.official_reference && (
        <section className="mt-4 rounded-[16px] border border-black bg-white p-5">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div><p className="mono text-xs tracking-[.12em] text-black/45">官方价格参考 · 核验于 {product.official_reference.checked_at}</p><h2 className="mt-2 text-xl font-semibold">{product.official_reference.plan} · {product.official_reference.currency} {product.official_reference.price} / 月</h2><p className="mt-2 max-w-3xl text-xs leading-5 text-black/50">{product.official_reference.note}</p></div>
            <a href={product.official_reference.url} target="_blank" rel="noreferrer" className="inline-flex shrink-0 items-center gap-2 rounded-[10px] border border-black px-4 py-2.5 text-sm">查看官方来源 <ArrowSquareOut size={16} /></a>
          </div>
        </section>
      )}

      <OfferScopeControls action={filterAction} values={filters} resetHref={resetHref} hiddenFields={hiddenFields} />

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

      <section className="border-t border-black py-12" aria-labelledby="product-comparison-guide">
        <div className="max-w-5xl">
          <h2 id="product-comparison-guide" className="text-3xl font-semibold tracking-[-.04em]">如何比较 {product.display_name} 报价</h2>
          <ul className="mt-6 grid gap-4 text-sm leading-6 text-[color:var(--muted)] md:grid-cols-2">
            {seo.comparisonPoints.map((point) => (
              <li key={point} className="border-l-2 border-[color:var(--accent)] pl-4">{point}</li>
            ))}
          </ul>
          <div className="mt-10 border-t hairline">
            <h2 className="py-5 text-xl font-semibold">常见问题</h2>
            {seo.faqs.map((faq) => (
              <details key={faq.question} className="group border-t hairline py-4 first:border-t-0">
                <summary className="cursor-pointer font-medium">{faq.question}</summary>
                <p className="mt-3 max-w-4xl text-sm leading-6 text-[color:var(--muted)]">{faq.answer}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-10 border-t border-black py-12 lg:grid-cols-[1.35fr_.65fr]">
        <div><h2 className="mb-2 text-3xl font-semibold tracking-[-.04em]">价格与库存趋势</h2><p className="mb-5 text-sm text-black/50">按日聚合可信最低价、中位价和有货观测数量，避免把不同报价的原始观测混成一条价格线。</p><PriceHistory points={product.trend} /></div>
        <aside><ReportForm /></aside>
      </section>
      <p className="border-t hairline py-5 text-xs text-black/40">数据快照：{product.snapshot_id ? `#${product.snapshot_id}` : "未编号"} · {exactTime(product.snapshot_at)}</p>
    </>
  );
}
