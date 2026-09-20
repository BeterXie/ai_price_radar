import Link from "next/link";
import { notFound } from "next/navigation";
import { Clock, Package, ShieldCheck, Stack } from "@phosphor-icons/react/ssr";
import { OfferGroupTable } from "@/components/offer-table";
import { OfferScopeControls } from "@/components/offer-scope-controls";
import { SectionIntro } from "@/components/page-shell";
import { PlatformIcon } from "@/components/platform-icon";
import { filterValues, offerQuery, ProductWorkspace, single, type RawSearchParams } from "@/components/product-workspace";
import { ReportForm } from "@/components/report-form";
import { SearchBox } from "@/components/search-box";
import { getCatalogGroups, getMeta, getProduct } from "@/lib/api";
import { exactTime, relativeTime } from "@/lib/format";
import { getProductSeoContent } from "@/lib/product-seo";

import { BRAND_TABS, type BrandName, PRODUCT_TABS } from "@/lib/catalog";

const EMPTY_META = { platforms: [], brands: [], source_platforms: [], product_types: [], tags: [] };

function withQuery(path: string, query: URLSearchParams) {
  const value = query.toString();
  return value ? `${path}?${value}` : path;
}

export async function ProductCatalogPage({ rawParams, productSlug = "" }: { rawParams: RawSearchParams; productSlug?: string }) {
  const detailQuery = offerQuery(rawParams);
  const searchQuery = single(rawParams, "q").trim();
  const [product, metaResult] = await Promise.all([
    productSlug ? getProduct(productSlug, detailQuery.toString()) : Promise.resolve(null),
    getMeta().catch(() => null),
  ]);
  const meta = metaResult || EMPTY_META;
  if (productSlug && !product) notFound();

  const activeBrand = product?.brand || single(rawParams, "brand") || single(rawParams, "platform");
  const activeSourcePlatform = single(rawParams, "source_platform");
  const catalogQuery = new URLSearchParams(detailQuery);
  catalogQuery.delete("platform");
  if (activeBrand) catalogQuery.set("brand", activeBrand);
  if (searchQuery) catalogQuery.set("q", searchQuery);
  let catalogLoadFailed = false;
  const catalog = product ? null : await getCatalogGroups(catalogQuery.toString()).catch(() => {
    catalogLoadFailed = true;
    return null;
  });
  const productTabBrand = activeBrand && Object.prototype.hasOwnProperty.call(PRODUCT_TABS, activeBrand)
    ? activeBrand as BrandName
    : null;
  const productTabs = productTabBrand ? PRODUCT_TABS[productTabBrand] : [];
  const scopeQuery = new URLSearchParams(detailQuery);
  if (searchQuery) scopeQuery.set("q", searchQuery);
  const filters = filterValues(rawParams);
  // Any narrowing (keyword / platform / price / stock …) makes an empty result
  // ambiguous: it may just mean "no match for these filters", not "no offers".
  // `comparable` defaults to "true" and is therefore only a filter when "false".
  const hasActiveFilters = Boolean(
    searchQuery ||
      activeSourcePlatform ||
      filters.delivery_type ||
      filters.period ||
      filters.warranty ||
      filters.auto_delivery ||
      filters.updated_within_hours ||
      filters.min_price ||
      filters.max_price ||
      filters.in_stock ||
      filters.comparable === "false"
  );
  const catalogHref = (brand = "") => {
    const next = new URLSearchParams(scopeQuery);
    next.delete("platform");
    if (brand) next.set("brand", brand);
    else next.delete("brand");
    return withQuery("/products", next);
  };
  const productHref = (slug: string) => withQuery(`/products/${encodeURIComponent(slug)}`, scopeQuery);
  const sourceHref = (sourcePlatform = "") => {
    const next = new URLSearchParams(scopeQuery);
    if (sourcePlatform) next.set("source_platform", sourcePlatform);
    else next.delete("source_platform");
    if (!product && activeBrand) next.set("brand", activeBrand);
    return withQuery(product ? `/products/${encodeURIComponent(product.slug)}` : "/products", next);
  };
  const navigationQuery = new URLSearchParams();
  if (!product && activeBrand) navigationQuery.set("brand", activeBrand);
  if (activeSourcePlatform) navigationQuery.set("source_platform", activeSourcePlatform);
  if (!product && searchQuery) navigationQuery.set("q", searchQuery);
  const navigationHref = withQuery(product ? `/products/${encodeURIComponent(product.slug)}` : "/products", navigationQuery);
  const hiddenFields = {
    ...(!product && activeBrand ? { brand: activeBrand } : {}),
    ...(activeSourcePlatform ? { source_platform: activeSourcePlatform } : {}),
    ...(!product && searchQuery ? { q: searchQuery } : {}),
  };
  const updatedWithinLabel: Record<string, string> = { "6": "6 小时内", "24": "24 小时内", "72": "3 天内", "168": "7 天内" };
  let headingTitle = "AI 商品报价";
  let headingDescription = "按品牌、商品类型、交付方式、库存和更新时间筛选公开报价。";
  if (activeBrand) headingTitle = `${activeBrand} 报价`;
  if (searchQuery) {
    headingTitle = `“${searchQuery}”的报价`;
    headingDescription = "匹配商品名称与来源商品标题。继续按品牌、库存、交付方式和更新时间缩小范围。";
  }
  if (product) {
    headingTitle = `${product.display_name} 报价`;
    headingDescription = getProductSeoContent(product.slug, product.display_name, product.description).intro;
  }

  return (
    <main id="main-content" className="shell" data-vds-schema="v3.1" data-vds-layer="field" data-vds-action="scope-rails selected-summary grouped-ledger responsive-filter-disclosure">
      <header className="catalog-heading">
        <div className="catalog-heading-copy">
          <p className="text-xs font-semibold text-[color:var(--brand-strong)]">{product ? product.brand : activeBrand || "全部品牌"}</p>
          <h1 data-vds-role="title">{headingTitle}</h1>
          <p id={product ? "product-description" : undefined} data-vds-role="explanation">{headingDescription}</p>
        </div>
        {!product ? <div className="catalog-heading-search"><SearchBox defaultValue={searchQuery} /></div> : null}
      </header>

      <section className="border-b border-[color:var(--line-strong)] py-4" aria-label="报价快捷筛选">
        <nav className="filter-rail" aria-label="品牌筛选">
          <span className="filter-label">品牌</span>
          <Link href={catalogHref()} prefetch={true} aria-current={!activeBrand ? "page" : undefined} className="filter-chip">
            <PlatformIcon platform="" />全部
          </Link>
          {BRAND_TABS.map((brand) => (
            <Link key={brand} href={catalogHref(brand)} prefetch={true} aria-current={activeBrand === brand ? "page" : undefined} className="filter-chip">
              <PlatformIcon platform={brand} />{brand}
            </Link>
          ))}
        </nav>
        <nav className="filter-rail mt-2 border-t border-[color:var(--line)] pt-2" aria-label="商品类型筛选">
          <span className="filter-label">商品类型</span>
          <Link href={catalogHref(activeBrand)} prefetch={true} aria-current={!product ? "page" : undefined} className="filter-chip">
            全部商品
          </Link>
          {productTabs.map((tab) => (
            <Link
              key={tab.slug}
              href={productHref(tab.slug)}
              prefetch={true}
              aria-current={product?.slug === tab.slug ? "page" : undefined}
              className="filter-chip"
            >
              {tab.label}
            </Link>
          ))}
        </nav>
        <nav className="filter-rail mt-2 border-t border-[color:var(--line)] pt-2" aria-label="来源平台筛选">
          <span className="filter-label">来源平台</span>
          <Link href={sourceHref()} prefetch={true} aria-current={!activeSourcePlatform ? "page" : undefined} className="filter-chip">全部来源</Link>
          {meta.source_platforms.filter((source) => source.id !== "dujiao_next").map((source) => (
            <Link key={source.id} href={sourceHref(source.id)} prefetch={true} aria-current={activeSourcePlatform === source.id ? "page" : undefined} className="filter-chip">{source.label}</Link>
          ))}
          {!metaResult ? <span className="ml-2 text-xs text-[color:var(--muted)]">来源选项暂不可用，可继续浏览当前报价</span> : null}
        </nav>
      </section>
      <section className="catalog-scope-bar" aria-labelledby="selected-scope-title" data-vds-layer="inscription">
        <div className="catalog-scope-copy">
          <strong id="selected-scope-title">已选条件</strong>
          这些条件会同时作用于下面的报价。
        </div>
        <div className="catalog-scope-values" data-vds-role="evidence">
          <div className="catalog-scope-value"><span>商品</span><strong>{product?.display_name || searchQuery || "全部商品"}</strong></div>
          <div className="catalog-scope-value"><span>品牌</span><strong>{activeBrand || "全部品牌"}</strong></div>
          <div className="catalog-scope-value"><span>库存</span><strong>{filters.in_stock === "true" ? "仅看有货" : "全部库存"}</strong></div>
          <div className="catalog-scope-value"><span>更新时间</span><strong>{updatedWithinLabel[filters.updated_within_hours] || "全部时间"}</strong></div>
        </div>
      </section>
      {product ? (
        <ProductWorkspace
          product={product}
          rawParams={rawParams}
          query={detailQuery}
          filterAction={`/products/${encodeURIComponent(product.slug)}`}
          resetHref={navigationHref}
          hiddenFields={hiddenFields}
        />
      ) : catalog ? (
        <>
          <section className="catalog-stats" aria-label="目录报价概况">
            <p><ShieldCheck size={15} /><span>{catalog.trusted_offer_count} 条纳入统计</span></p>
            <p><Package size={15} /><span>{catalog.in_stock_count} 条有货</span></p>
            <p><Stack size={15} /><span>{catalog.offer_total} 条报价，其中 {catalog.comparable_offer_count} 条可比较</span></p>
            <p><Clock size={15} /><span>更新于 {relativeTime(catalog.last_updated_at)}</span></p>
          </section>

          <OfferScopeControls
            action="/products"
            values={filters}
            hiddenFields={hiddenFields}
            resetHref={navigationHref}
            defaultOpen={false}
          />

          <section className="pb-12">
            {catalog.items.length > 0 ? (
              <>
                <SectionIntro title="当前报价" description={<>相同商品会合并显示。当前筛选结果共 {catalog.total} 组报价，展开后可查看店铺、交付方式和商品原文。</>} />
                <div className="mt-4">
                  <OfferGroupTable
                    key={`${activeBrand || "all"}:${catalog.snapshot_id || "current"}:${catalogQuery.toString()}`}
                    groups={catalog.items}
                    totalCount={catalog.total}
                    snapshotId={catalog.snapshot_id}
                    filterQuery={catalogQuery.toString()}
                    loadMorePath="/api/v1/catalog/groups"
                    showProduct
                  />
                </div>
              </>
            ) : activeBrand && productTabs.length > 0 ? (
              <>
                <SectionIntro
                  title={hasActiveFilters ? `${activeBrand} 筛选结果` : `${activeBrand} 监测商品`}
                  description={
                    hasActiveFilters ? (
                      <>当前筛选条件下没有匹配的报价。可调整或清除下方筛选条件重新查看；也可以直接浏览该品牌下的监测商品台账：</>
                    ) : (
                      <>当前快照暂无可比现货报价，监控爬虫正在持续扫描相关店铺。点击可查看各商品详情台账、历史报价趋势或订阅到价提醒：</>
                    )
                  }
                />
                <div className="mt-4 rounded-2xl border border-[color:var(--line)] bg-[color:var(--subtle)]/40 p-6">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-[color:var(--ink)]">
                      {activeBrand} 包含的监测商品
                    </h3>
                    <Link
                      href="/shops/submit"
                      className="inline-flex items-center gap-1 rounded-full border border-[color:var(--brand)] bg-[color:var(--brand)]/10 px-3 py-1 text-xs font-medium text-[color:var(--brand)] hover:bg-[color:var(--brand)]/20 transition"
                    >
                      <span>提交该品牌店铺报价</span>
                      <span>→</span>
                    </Link>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {productTabs.map((tab) => (
                      <Link
                        key={tab.slug}
                        href={`/products/${encodeURIComponent(tab.slug)}`}
                        className="group flex flex-col justify-between rounded-xl border border-[color:var(--line)] bg-[color:var(--panel)] p-4 shadow-sm transition hover:border-[color:var(--brand)] hover:shadow-md"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <PlatformIcon platform={activeBrand} size={16} />
                            <span className="font-semibold group-hover:text-[color:var(--brand)]">{tab.label}</span>
                          </div>
                          <p className="mt-1 text-xs text-[color:var(--muted)]">
                            查看历史报价与到价提醒
                          </p>
                        </div>
                        <div className="mt-3 flex items-center justify-between text-xs text-[color:var(--brand-strong)] font-medium">
                          <span>进入商品台账 →</span>
                          <span className="text-[color:var(--muted)] font-normal">监控中</span>
                        </div>
                      </Link>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <>
                <SectionIntro title="当前报价" description={<>相同商品会合并显示。当前筛选结果共 {catalog.total} 组报价，展开后可查看店铺、交付方式和商品原文。</>} />
                <div className="mt-4">
                  <OfferGroupTable
                    key={`${activeBrand || "all"}:${catalog.snapshot_id || "current"}:${catalogQuery.toString()}`}
                    groups={catalog.items}
                    totalCount={catalog.total}
                    snapshotId={catalog.snapshot_id}
                    filterQuery={catalogQuery.toString()}
                    loadMorePath="/api/v1/catalog/groups"
                    showProduct
                  />
                </div>
              </>
            )}
          </section>
          <section className="border-t border-[color:var(--line-strong)] py-12"><div className="max-w-2xl"><ReportForm /></div></section>
          <p className="border-t hairline py-5 text-xs text-black/40">数据更新于：{exactTime(catalog.snapshot_at)}</p>
        </>
      ) : catalogLoadFailed ? (
        <section className="empty-state my-10" role="alert" data-vds-layer="evidence">
          <h2 className="text-2xl font-semibold text-[color:var(--ink)]">当前报价暂时无法加载</h2>
          <p className="mt-3 text-sm leading-6">筛选条件没有丢失。可以退出错误预览后重新读取当前报价。</p>
          <Link href={navigationHref} className="button-primary mt-6">重新读取报价</Link>
        </section>
      ) : null}
    </main>
  );
}
