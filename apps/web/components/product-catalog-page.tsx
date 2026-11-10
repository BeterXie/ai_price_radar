import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, ArrowUpRight, Check } from "@phosphor-icons/react/ssr";
import { AdSlot } from "@/components/ad-slot";
import { OfferGroupTable } from "@/components/offer-table";
import { OfferScopeControls } from "@/components/offer-scope-controls";
import { PlatformIcon } from "@/components/platform-icon";
import { filterValues, offerQuery, ProductWorkspace, single, type RawSearchParams } from "@/components/product-workspace";
import { ReportForm } from "@/components/report-form";
import { RelayCatalogPage } from "@/components/relay-catalog-page";
import { getCatalogGroups, getMeta, getProduct } from "@/lib/api";
import { getContextualAds } from "@/lib/contextual-ads";
import { exactTime, relativeTime } from "@/lib/format";
import { normalizeSearchQuery } from "@/lib/search";
import { getBrandSeoContent } from "@/lib/brand-seo";
import { getProductSeoContent } from "@/lib/product-seo";
import { breadcrumbJsonLd, JsonLd } from "@/components/structured-data";
import type { Meta } from "@/lib/types";
import { BRAND_TABS, type BrandName, brandCatalogPath, PRODUCT_TABS, OFFICIAL_PLAN_SOURCES, RELAY_CATALOG_HREF, STANDALONE_PRODUCTS } from "@/lib/catalog";

const EMPTY_META: Meta = { platforms: [], brands: [], source_platforms: [], product_types: [], tags: [] };

function withQuery(path: string, query: URLSearchParams) {
  const value = query.toString();
  return value ? `${path}${path.includes("?") ? "&" : "?"}${value}` : path;
}

const NARROWING_KEYS = ["source_platform", "delivery_type", "period", "warranty", "auto_delivery", "updated_within_hours", "min_price", "max_price", "in_stock"] as const;

/** True when the URL narrows the offer scope beyond the default comparable filter. */
export function hasNarrowingFilters(rawParams: RawSearchParams) {
  return Boolean(normalizeSearchQuery(single(rawParams, "q"))) || NARROWING_KEYS.some((key) => Boolean(single(rawParams, key)));
}

export async function ProductCatalogPage({ rawParams, productSlug = "", catalogBrand = "" }: { rawParams: RawSearchParams; productSlug?: string; catalogBrand?: BrandName | "" }) {
  if (catalogBrand) rawParams = { ...rawParams, brand: catalogBrand, platform: catalogBrand };
  const basePath = catalogBrand ? brandCatalogPath(catalogBrand) : "/products";
  if (!productSlug && (single(rawParams, "brand") || single(rawParams, "platform")) === "中转站") {
    return <RelayCatalogPage rawParams={rawParams} basePath="/products" />;
  }
  if (!productSlug) {
    const service = STANDALONE_PRODUCTS.find((item) => item.label === (single(rawParams, "brand") || single(rawParams, "platform")));
    if (service) productSlug = service.slug;
  }
  let detailQuery = offerQuery(rawParams);
  const searchQuery = normalizeSearchQuery(single(rawParams, "q"));
  const [initialProduct, metaResult] = await Promise.all([
    productSlug ? getProduct(productSlug, detailQuery.toString()) : Promise.resolve(null),
    getMeta().catch(() => null),
  ]);
  const meta = metaResult || EMPTY_META;
  if (productSlug && !initialProduct) notFound();
  let product = initialProduct;
  // Widen a product's default scope only when it has related offers and the
  // visitor has not explicitly narrowed the scope. Keep the explanation in
  // ProductWorkspace so related offers cannot be mistaken for comparable ones.
  let scopeExpanded = false;
  if (
    product &&
    product.offer_group_count === 0 &&
    single(rawParams, "comparable") === "" &&
    !hasNarrowingFilters(rawParams)
  ) {
    const widened = new URLSearchParams(detailQuery);
    widened.delete("comparable");
    const fallback = await getProduct(product.slug, widened.toString()).catch(() => null);
    if (fallback && fallback.offer_group_count > 0) {
      product = fallback;
      detailQuery = widened;
      scopeExpanded = true;
    }
  }

  const activeBrand = product?.brand || single(rawParams, "brand") || single(rawParams, "platform");
  const activeSourcePlatform = single(rawParams, "source_platform");
  const catalogQuery = new URLSearchParams(detailQuery);
  catalogQuery.delete("platform");
  if (activeBrand) catalogQuery.set("brand", activeBrand);
  if (searchQuery) catalogQuery.set("q", searchQuery);
  let catalogLoadFailed = false;
  const [contextAds, catalog] = await Promise.all([
    getContextualAds(activeBrand),
    product ? Promise.resolve(null) : getCatalogGroups(catalogQuery.toString()).catch(() => {
      catalogLoadFailed = true;
      return null;
    }),
  ]);
  const productTabBrand = BRAND_TABS.includes(activeBrand as BrandName)
    ? activeBrand as BrandName
    : null;
  const productTabs = productTabBrand ? PRODUCT_TABS[productTabBrand] : [];
  const officialTabs = productTabs.filter((tab) => !tab.other);
  const otherTabs = productTabs.filter((tab) => tab.other);
  const officialSource = productTabBrand ? OFFICIAL_PLAN_SOURCES[productTabBrand] : undefined;
  const filters = filterValues(rawParams);
  if (scopeExpanded) filters.comparable = "false";
  // Page URLs retain comparable=false; the API intentionally omits it when
  // including related offers. Reusing the API query here would lose that choice.
  const scopeQuery = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
  // Default scope must link to indexable canonical pages, not noindex variants.
  if (scopeQuery.get("comparable") === "true") scopeQuery.delete("comparable");
  if (activeSourcePlatform) scopeQuery.set("source_platform", activeSourcePlatform);
  if (searchQuery) scopeQuery.set("q", searchQuery);
  const hasActiveFilters = Boolean(searchQuery || activeSourcePlatform || hasNarrowingFilters(rawParams) || filters.comparable === "false");
  const catalogHref = (brand = "") => {
    return withQuery(brandCatalogPath(brand), scopeQuery);
  };
  const productHref = (slug: string) => withQuery(`/products/${encodeURIComponent(slug)}`, scopeQuery);
  const sourceHref = (sourcePlatform = "") => {
    const next = new URLSearchParams(scopeQuery);
    if (sourcePlatform) next.set("source_platform", sourcePlatform);
    else next.delete("source_platform");
    if (!product && activeBrand && !catalogBrand) next.set("brand", activeBrand);
    return withQuery(product ? `/products/${encodeURIComponent(product.slug)}` : basePath, next);
  };
  const navigationQuery = new URLSearchParams();
  if (!product && activeBrand && !catalogBrand) navigationQuery.set("brand", activeBrand);
  if (activeSourcePlatform) navigationQuery.set("source_platform", activeSourcePlatform);
  if (searchQuery) navigationQuery.set("q", searchQuery);
  const navigationHref = withQuery(product ? `/products/${encodeURIComponent(product.slug)}` : basePath, navigationQuery);
  const clearFiltersHref = brandCatalogPath(activeBrand);
  const relatedQuery = new URLSearchParams(scopeQuery);
  relatedQuery.set("comparable", "false");
  const relatedHref = withQuery(brandCatalogPath(activeBrand), relatedQuery);
  const stockQuery = new URLSearchParams(scopeQuery);
  if (activeBrand && !catalogBrand) stockQuery.set("brand", activeBrand);
  if (filters.in_stock === "true") stockQuery.delete("in_stock");
  else stockQuery.set("in_stock", "true");
  const hiddenFields = {
    ...(!product && activeBrand && !catalogBrand ? { brand: activeBrand } : {}),
    ...(activeSourcePlatform ? { source_platform: activeSourcePlatform } : {}),
    ...(searchQuery ? { q: searchQuery } : {}),
  };
  const headingTitle = product ? `${product.display_name} 比价` : searchQuery ? `“${searchQuery}”的报价` : activeBrand ? `${activeBrand} 比价` : "AI 订阅比价";
  const intro = product ? getProductSeoContent(product.slug, product.display_name, product.description).intro
    : productTabBrand ? getBrandSeoContent(productTabBrand).description : "比较公开商品的价格、库存、交付方式和更新时间。";

  return (
    <main id="main-content" className="catalog-page shell">
      {catalogBrand ? <JsonLd data={breadcrumbJsonLd([{ name: "首页", path: "/" }, { name: `${catalogBrand} 比价`, path: basePath }])} /> : null}

      <div className="catalog-layout">
        <aside className="catalog-sidebar">
          <nav className="catalog-brands" aria-label="品牌与商品筛选">
            <Link href={catalogHref()} aria-current={!activeBrand ? "page" : undefined}><PlatformIcon platform="" size={19} />全部品牌</Link>
            {BRAND_TABS.map((brand) => (
              <Link key={brand} href={catalogHref(brand)} aria-current={activeBrand === brand ? "page" : undefined}>
                <PlatformIcon platform={brand} size={19} />{brand}
              </Link>
            ))}
            {STANDALONE_PRODUCTS.map((service) => (
              <Link key={service.slug} href={productHref(service.slug)} className="catalog-service-link" aria-current={product?.slug === service.slug ? "page" : undefined}>
                <PlatformIcon platform={service.label} size={19} />{service.label}
              </Link>
            ))}
            {meta.relay_hub_enabled !== false ? (
              <Link href={RELAY_CATALOG_HREF} className="catalog-relay-link"><PlatformIcon platform="中转站" size={19} />中转站<ArrowUpRight size={14} aria-hidden="true" /></Link>
            ) : null}
          </nav>
        </aside>

        <div className="catalog-content">
          <header className="mb-5 border-b border-[color:var(--line)] pb-4">
            <h1 className="text-2xl font-semibold tracking-tight">{headingTitle}</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-[color:var(--muted)]">{intro}</p>
            <Link href="/compare" className="mt-2 inline-block text-sm underline underline-offset-4">比较 ChatGPT、Claude 与 Gemini</Link>
          </header>
          {productTabs.length > 0 ? (
            <div className="catalog-plans">
              <nav aria-label="商品类型筛选" className="catalog-plan-row">
                <span className="catalog-plan-label">{officialTabs.length ? "官方套餐" : "商品类别"}</span>
                <div className="catalog-plan-options">
                  <Link href={catalogHref(activeBrand)} aria-current={!product ? "page" : undefined} className="filter-chip">全部</Link>
                  {(officialTabs.length ? officialTabs : otherTabs).map((tab) => (
                    <Link key={tab.slug} href={productHref(tab.slug)} aria-current={product?.slug === tab.slug ? "page" : undefined} className="filter-chip">{tab.label}</Link>
                  ))}
                </div>
                {officialSource ? <a href={officialSource} target="_blank" rel="noreferrer" className="catalog-official-link">官网套餐 <ArrowUpRight size={14} aria-hidden="true" /></a> : null}
              </nav>
              {officialTabs.length > 0 && otherTabs.length > 0 ? (
                <details className="catalog-other-plans" open={otherTabs.some((tab) => tab.slug === product?.slug)}>
                  <summary>其他商品</summary>
                  <nav aria-label="其他商品筛选" className="catalog-plan-options">
                    {otherTabs.map((tab) => (
                      <Link key={tab.slug} href={productHref(tab.slug)} aria-current={product?.slug === tab.slug ? "page" : undefined} className="filter-chip">{tab.label}</Link>
                    ))}
                  </nav>
                </details>
              ) : null}
            </div>
          ) : null}

          <div className="catalog-source-row">
            <nav className="catalog-sources" aria-label="来源平台筛选">
              <Link href={sourceHref()} aria-current={!activeSourcePlatform ? "page" : undefined}>全部来源</Link>
              {meta.source_platforms.map((source) => (
                <Link key={source.id} href={sourceHref(source.id)} aria-current={activeSourcePlatform === source.id ? "page" : undefined}>{source.label}</Link>
              ))}
            </nav>
            {!metaResult ? <span className="catalog-source-error" role="status">来源选项暂不可用</span> : null}
          </div>

          {product ? (
            <ProductWorkspace product={product} rawParams={rawParams} query={detailQuery} filterAction={`/products/${encodeURIComponent(product.slug)}`} resetHref={navigationHref} hiddenFields={hiddenFields} scopeExpanded={scopeExpanded} contextAds={contextAds} />
          ) : (
            <>
              <OfferScopeControls
                action={basePath}
                values={filters}
                hiddenFields={hiddenFields}
                resetHref={navigationHref}
                compact
                quickFilter={<Link href={withQuery(basePath, stockQuery)} className="catalog-stock-toggle" aria-current={filters.in_stock === "true" ? "page" : undefined}><span aria-hidden="true">{filters.in_stock === "true" ? <Check size={12} weight="bold" /> : null}</span>仅看有货</Link>}
              />
              {catalog ? (
                <>
                  <AdSlot placement="catalog_top" limit={2} variant="compact" className="catalog-ad" />
                  <section className="catalog-results" aria-labelledby="catalog-results-title">
                    <div className="catalog-results-heading">
                      <h2 id="catalog-results-title">{filters.comparable === "false" ? "全部报价" : "可比报价"}<span>{catalog.total.toLocaleString("zh-CN")} 组</span></h2>
                      <time dateTime={catalog.last_updated_at || undefined} title={exactTime(catalog.last_updated_at)}>{catalog.last_updated_at ? `${relativeTime(catalog.last_updated_at)}更新` : "暂无更新"}</time>
                    </div>
                    {catalog.items.length > 0 ? (
                      <OfferGroupTable key={`${activeBrand || "all"}:${catalog.snapshot_id || "current"}:${catalogQuery.toString()}`} groups={catalog.items} totalCount={catalog.total} snapshotId={catalog.snapshot_id} filterQuery={catalogQuery.toString()} loadMorePath="/api/v1/catalog/groups" showProduct compact contextAds={contextAds} />
                    ) : (
                      <div className="catalog-empty">
                        <h3>{hasActiveFilters ? "没有匹配的报价" : "暂无可比报价"}</h3>
                        <p>{hasActiveFilters ? "试试减少筛选条件，或更换关键词。" : "可以稍后再来，或查看其他商品。"}</p>
                        <div className="flex flex-wrap justify-center gap-3">
                          {searchQuery && activeBrand ? <Link href={catalogHref()} className="button-primary">搜索全部品牌<ArrowRight size={16} aria-hidden="true" /></Link> : null}
                          <Link href={hasActiveFilters ? clearFiltersHref : relatedHref} className="button-secondary">{hasActiveFilters ? "清除筛选" : "查看相关报价"}<ArrowRight size={16} aria-hidden="true" /></Link>
                        </div>
                      </div>
                    )}
                    {!catalog.items.length && productTabs.length > 0 ? (
                      <nav className="catalog-empty-products" aria-label={`${activeBrand} 商品`}>
                        {productTabs.map((tab) => <Link key={tab.slug} href={productHref(tab.slug)}>{tab.label}<ArrowRight size={15} aria-hidden="true" /></Link>)}
                      </nav>
                    ) : null}
                  </section>
                  <div className="catalog-bottom">
                    <details className="catalog-report"><summary>反馈报价问题</summary><div className="catalog-report-form"><ReportForm /></div></details>
                    <time dateTime={catalog.snapshot_at || undefined}>{exactTime(catalog.snapshot_at)}</time>
                  </div>
                </>
              ) : catalogLoadFailed ? (
                <section className="catalog-empty" role="alert">
                  <h2>报价暂时无法加载</h2>
                  <p>筛选条件已保留，请稍后重试。</p>
                  <Link href={catalogHref(activeBrand)} className="button-primary">重新读取报价</Link>
                </section>
              ) : null}
            </>
          )}
        </div>
      </div>
    </main>
  );
}
