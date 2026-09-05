import Link from "next/link";
import { ArrowSquareOut, Check, Clock, Package, ShieldCheck, Stack } from "@phosphor-icons/react/ssr";
import { OfferGroupTable } from "@/components/offer-table";
import { OfferScopeControls, type OfferFilterValues } from "@/components/offer-scope-controls";
import { JsonLd } from "@/components/structured-data";
import { ProductEvidence } from "@/components/product-evidence";
import { ProductHistoryPanel } from "@/components/product-history-panel";
import { ReportForm } from "@/components/report-form";
import { WatchButton } from "@/components/watch-button";
import { DELIVERY_TYPE_LABELS } from "@/lib/catalog";
import { exactTime, money, relativeTime } from "@/lib/format";
import { getProductGuide } from "@/lib/guides/registry";
import { getProductEvidenceSources, getProductSeoContent } from "@/lib/product-seo";
import type { ProductDetail } from "@/lib/types";

export type RawSearchParams = Record<string, string | string[] | undefined>;

export function single(params: RawSearchParams, key: string) {
  const value = params[key];
  return Array.isArray(value) ? value[value.length - 1] || "" : value || "";
}

const FILTER_KEYS = ["delivery_type", "period", "warranty", "auto_delivery", "updated_within_hours", "min_price", "max_price", "source_platform"] as const;

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
  const productGuide = getProductGuide(product.slug);
  const evidenceSources = getProductEvidenceSources(product.brand, product.official_reference, productGuide?.officialSources);
  const structuredData: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "Product",
    "@id": `${canonical}#product`,
    name: product.display_name,
    description: seo.intro,
    url: canonical,
    mainEntityOfPage: canonical,
    inLanguage: "zh-CN",
    isPartOf: { "@id": "https://ai.pricememo.cn/#website" },
    image: `${canonical}/opengraph-image`,
    category: product.product_type,
    brand: { "@type": "Brand", name: product.brand },
    citation: evidenceSources.map((source) => ({
      "@type": "WebPage",
      "@id": source.url,
      name: source.title,
      url: source.url,
      publisher: { "@type": "Organization", name: source.publisher },
    })),
  };
  if (product.lowest_price && product.trusted_offer_count > 0) {
    structuredData.offers = {
      "@type": "AggregateOffer",
      priceCurrency: product.price_currency,
      lowPrice: product.lowest_price,
      highPrice: product.highest_price || product.lowest_price,
      offerCount: product.trusted_offer_count,
      availability: product.in_stock_count > 0 ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
      url: canonical,
    };
  }
  const filters = filterValues(rawParams);
  const guideFaq = productGuide?.faq[0];

  return (
    <>
      <JsonLd data={structuredData} />
      <section className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-[color:var(--line)] pb-4 text-sm text-[color:var(--muted)]" aria-label={`${product.display_name} 报价概况`}>
        <p className="flex items-center gap-1.5"><ShieldCheck size={16} />{product.trusted_offer_count} 条纳入统计</p>
        <p className="flex items-center gap-1.5"><Package size={16} />{product.in_stock_count} 条有货</p>
        <p className="flex items-center gap-1.5"><Stack size={16} />{product.offer_count} 条当前报价</p>
        <p className="flex items-center gap-1.5"><Clock size={16} />最近更新 {relativeTime(product.last_updated_at)}</p>
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-[1fr_auto] lg:items-stretch">
        <div className="data-strip sm:grid-cols-3">
          <div className="data-cell"><p className="data-label">近期有货观测价</p><p className="data-value">{money(product.lowest_price, product.price_currency)}</p></div>
          <div className="data-cell"><p className="data-label">常见观测价</p><p className="data-value">{money(product.median_price, product.price_currency)}</p></div>
          <div className="data-cell"><p className="data-label">信息覆盖</p><p className="data-value">{product.data_quality_score}<span className="ml-1 text-sm font-normal text-[color:var(--muted)]">/ 100，{product.data_quality_label}</span></p><p className="mt-1 text-xs text-[color:var(--muted)]">{product.source_count} 个来源</p></div>
        </div>
        <WatchButton slug={product.slug} name={product.display_name} currency={product.price_currency} suggestedPrice={product.lowest_price} />
      </section>

      {product.official_reference && (
        <section className="evidence-callout mt-4" data-vds-layer="evidence">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div><p className="section-kicker">官方价格参考 · 更新于 {product.official_reference.checked_at}</p><h2 className="mt-2 text-xl font-semibold">{product.official_reference.plan} · {product.official_reference.currency} {product.official_reference.price} / 月</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-[color:var(--muted)]">{product.official_reference.note}</p></div>
            <a href={product.official_reference.url} target="_blank" rel="noreferrer" className="button-secondary shrink-0">查看官方来源 <ArrowSquareOut size={16} /></a>
          </div>
        </section>
      )}

      <ProductEvidence sources={evidenceSources} />

      <OfferScopeControls action={filterAction} values={filters} resetHref={resetHref} hiddenFields={hiddenFields} />

      <section className="pb-12">
        <div className="mb-5 border-b border-[color:var(--line-strong)] pb-5">
          <h2 className="text-3xl font-semibold tracking-[-.04em]">报价</h2>
          <p className="mt-2 text-sm text-[color:var(--muted)]">相同商品会合并显示。共 {product.offer_group_count} 组报价，展开后可查看店铺、交付方式和商品原文。</p>
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

      {productGuide && (
        <section className="surface-subtle mb-12 p-5 md:p-7" aria-labelledby="buying-and-usage-guide">
          <div className="grid gap-7 lg:grid-cols-[1.05fr_.95fr]">
            <div>
              <p className="section-kicker">产品教程</p>
              <h2 id="buying-and-usage-guide" className="mt-3 text-2xl font-semibold tracking-[-.035em]">购买与使用</h2>
              <h3 className="mt-5 text-lg font-semibold">{productGuide.title}</h3>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-[color:var(--muted)]">{productGuide.description}</p>
              <div className="mt-5 flex flex-wrap gap-2" aria-label="教程支持的交付类型">
                {productGuide.supportedDeliveryTypes.map((deliveryType) => (
                  <span key={deliveryType} className="rounded-full border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-2.5 py-1 text-xs">
                    {DELIVERY_TYPE_LABELS[deliveryType] || deliveryType}
                  </span>
                ))}
              </div>
            </div>
          <div className="grid gap-5">
              <div>
                <h3 className="text-sm font-semibold">购买前提示</h3>
                <ul className="mt-3 grid gap-2 text-sm leading-6 text-[color:var(--muted)]">
                  {productGuide.buyingChecklist.slice(0, 3).map((item) => <li key={item} className="flex items-start gap-2"><span className="mt-1 grid size-5 shrink-0 place-items-center rounded-full bg-[color:var(--accent)] text-[color:var(--accent-ink)]"><Check size={12} weight="bold" /></span><span>{item}</span></li>)}
                </ul>
              </div>
              {guideFaq && (
                <div>
                  <h3 className="text-sm font-semibold">常见问题</h3>
                  <p className="mt-2 text-sm font-medium">{guideFaq.question}</p>
                  <p className="mt-1 text-sm leading-6 text-[color:var(--muted)]">{guideFaq.answer}</p>
                </div>
              )}
            </div>
          </div>
          <div className="mt-6 flex flex-wrap gap-3 border-t border-[color:var(--line-strong)] pt-5">
            <Link href={`/guides/products/${productGuide.productSlug}`} className="button-primary tactile">查看完整使用教程</Link>
            <Link href="/guides" className="button-secondary tactile">查看全部教程</Link>
          </div>
        </section>
      )}

      <section className="border-t border-[color:var(--line-strong)] py-12" aria-labelledby="product-comparison-guide">
        <div className="max-w-5xl">
          <h2 id="product-comparison-guide" className="text-3xl font-semibold tracking-[-.04em]">购买前检查</h2>
          <ul className="decision-list mt-6 grid text-sm leading-6 text-[color:var(--muted)] md:grid-cols-2">
            {seo.comparisonPoints.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
          <div className="mt-10 border-t hairline">
            <h3 className="py-5 text-xl font-semibold">常见问题</h3>
            {seo.faqs.map((faq) => (
              <details key={faq.question} className="group border-t hairline py-4 first:border-t-0">
                <summary className="cursor-pointer font-medium">{faq.question}</summary>
                <p className="mt-3 max-w-4xl text-sm leading-6 text-[color:var(--muted)]">{faq.answer}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-10 border-t border-[color:var(--line-strong)] py-12 lg:grid-cols-[1.35fr_.65fr]">
        <div><h2 className="mb-2 text-3xl font-semibold tracking-[-.04em]">最近价格和库存变化</h2><p className="mb-5 text-sm text-[color:var(--muted)]">按天显示近期有货观测价、常见观测价和有货数量。</p><ProductHistoryPanel key={`${product.slug}:${single(rawParams, "source_platform")}`} slug={product.slug} sourcePlatform={single(rawParams, "source_platform")} /></div>
        <aside><ReportForm /></aside>
      </section>
      <p className="border-t hairline py-5 text-xs text-black/40">数据更新于：{exactTime(product.snapshot_at)}</p>
    </>
  );
}
