import Link from "next/link";
import { ArrowLeft, ArrowRight, ArrowSquareOut, Check, Clock, ShieldCheck, Stack } from "@phosphor-icons/react/ssr";
import { OfferGroupTable } from "@/components/offer-table";
import { OfferScopeControls, type OfferFilterValues } from "@/components/offer-scope-controls";
import { JsonLd } from "@/components/structured-data";
import { ProductEvidence } from "@/components/product-evidence";
import { ProductHistoryPanel } from "@/components/product-history-panel";
import { PlatformIcon } from "@/components/platform-icon";
import { ReportForm } from "@/components/report-form";
import { WatchButton } from "@/components/watch-button";
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

export function ProductWorkspace({ product, rawParams, query, filterAction, resetHref, hiddenFields = {} }: {
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
  const filters = filterValues(rawParams);
  const guideFaq = productGuide?.faq[0];
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
    citation: evidenceSources.map((source) => ({ "@type": "WebPage", "@id": source.url, name: source.title, url: source.url, publisher: { "@type": "Organization", name: source.publisher } })),
  };
  if (product.lowest_price && product.trusted_offer_count > 0) {
    structuredData.offers = { "@type": "AggregateOffer", priceCurrency: product.price_currency, lowPrice: product.lowest_price, highPrice: product.highest_price || product.lowest_price, offerCount: product.trusted_offer_count, availability: product.in_stock_count > 0 ? "https://schema.org/InStock" : "https://schema.org/OutOfStock", url: canonical };
  }

  return (
    <>
      <JsonLd data={structuredData} />
      <div className="breadcrumb"><Link href="/products"><ArrowLeft size={14} />返回报价目录</Link><span>{product.brand} · {product.product_type}</span></div>

      <section className="product-detail-heading">
        <span className={`brand-icon ${product.brand.toLowerCase()}`}><PlatformIcon platform={product.brand} size={43} /></span>
        <div><span className="eyebrow">{product.brand} · PUBLIC PRICE MEMORY</span><h1>{product.display_name}</h1><p>{seo.intro}</p></div>
        <WatchButton slug={product.slug} name={product.display_name} currency={product.price_currency} suggestedPrice={product.lowest_price} />
      </section>

      <section className="detail-stats" aria-label={`${product.display_name} 报价概况`}>
        <div><span>近期有货参考价</span><strong>{money(product.lowest_price, product.price_currency)}</strong><small>{product.trusted_offer_count} 条报价纳入统计</small></div>
        <div><span>当前有货</span><strong>{product.in_stock_count}<small> 条</small></strong><small>共 {product.offer_count} 条当前报价</small></div>
        <div><span>常见观测价</span><strong>{money(product.median_price, product.price_currency)}</strong><small>{product.source_count} 个公开来源</small></div>
        <div><span>最近更新</span><strong className="!text-[20px]">{relativeTime(product.last_updated_at)}</strong><small>{exactTime(product.snapshot_at)}</small></div>
      </section>

      {product.official_reference ? (
        <section className="notice mt-6"><ShieldCheck size={20} /><div className="flex-1"><strong>官方价格参考 · {product.official_reference.plan}</strong><p>{product.official_reference.note} · 核对时间 {product.official_reference.checked_at}</p></div><a href={product.official_reference.url} target="_blank" rel="noreferrer" className="text-button">查看官方来源 <ArrowSquareOut size={14} /></a></section>
      ) : null}

      <ProductEvidence sources={evidenceSources} />

      <section className="mt-9">
        <div className="section-heading"><div><div className="eyebrow">CURRENT OFFERS</div><h2>当前公开报价</h2><p>相同商品会合并显示。共 {product.offer_group_count} 组，展开后可查看店铺、交付方式、原文与来源。</p></div><span className="small-text muted"><Clock size={14} /> {relativeTime(product.last_updated_at)}更新</span></div>
        <OfferScopeControls action={filterAction} values={filters} resetHref={resetHref} hiddenFields={hiddenFields} />
        <div className="offer-list mt-4">
          <OfferGroupTable key={`${product.slug}:${product.snapshot_id || "current"}:${query.toString()}`} groups={product.offer_groups} productSlug={product.slug} totalCount={product.offer_group_count} snapshotId={product.snapshot_id} filterQuery={query.toString()} />
        </div>
      </section>

      {productGuide ? (
        <section className="guide-callout mt-9"><div className="callout-icon"><Check size={23} /></div><div><h3>{productGuide.title}</h3><p>{productGuide.description}</p></div><Link className="button" href={`/guides/products/${productGuide.productSlug}`}>阅读完整教程 <ArrowRight size={15} /></Link></section>
      ) : null}

      <section className="detail-bottom-grid">
        <div>
          <div className="section-heading"><div><div className="eyebrow">PRICE & STOCK HISTORY</div><h2>最近价格和库存变化</h2><p>按天整理近期有货观测价、常见观测价和有货数量。</p></div></div>
          <ProductHistoryPanel key={`${product.slug}:${single(rawParams, "source_platform")}`} slug={product.slug} sourcePlatform={single(rawParams, "source_platform")} />
        </div>
        <aside className="feedback-card"><h3>发现信息有误？</h3><p>提交价格、库存、分类或来源问题，帮助这份公开报价持续变得更准确。</p><div className="mt-5"><ReportForm /></div></aside>
      </section>

      {productGuide ? (
        <section className="article-body mt-10"><h2>购买前检查</h2><div className="three-points">{productGuide.buyingChecklist.slice(0, 3).map((item, index) => <div key={item}><span>0{index + 1}</span><h3>{["确认商品类型", "确认控制权", "保留售后材料"][index] || "购买前确认"}</h3><p>{item}</p></div>)}</div>{guideFaq ? <div className="notice"><ShieldCheck size={18} /><div><strong>{guideFaq.question}</strong><p>{guideFaq.answer}</p></div></div> : null}</section>
      ) : null}

      <section className="article-body mt-8"><h2>比较这类商品时，还要看什么？</h2>{seo.comparisonPoints.map((point, index) => <div className="step-card" key={point}><span>{String(index + 1).padStart(2, "0")}</span><div><h3>核对条件</h3><p>{point}</p></div></div>)}<h2>常见问题</h2>{seo.faqs.map((faq) => <details key={faq.question} className="faq"><summary>{faq.question}<span>＋</span></summary><p>{faq.answer}</p></details>)}</section>

      <p className="quote-disclaimer"><Stack size={13} />数据更新于 {exactTime(product.snapshot_at)}。价格、库存和交付规则请以来源页面为准。</p>
    </>
  );
}
