import Link from "next/link";
import { notFound } from "next/navigation";
import { Clock, Package, ShieldCheck, Stack } from "@phosphor-icons/react/ssr";
import { OfferGroupTable } from "@/components/offer-table";
import { OfferScopeControls } from "@/components/offer-scope-controls";
import { PlatformIcon } from "@/components/platform-icon";
import { filterValues, offerQuery, ProductWorkspace, single, type RawSearchParams } from "@/components/product-workspace";
import { ReportForm } from "@/components/report-form";
import { getCatalogGroups, getMeta, getProduct } from "@/lib/api";
import { exactTime, relativeTime } from "@/lib/format";

const BRAND_TABS = ["OpenAI", "Claude", "Gemini", "Grok", "X"];

const PRODUCT_TABS: Record<string, { label: string; slug: string }[]> = {
  OpenAI: [
    { label: "Free", slug: "chatgpt-account" },
    { label: "Plus", slug: "chatgpt-plus" },
    { label: "Go", slug: "chatgpt-go" },
    { label: "K12 / Team", slug: "chatgpt-k12" },
    { label: "Pro 5x", slug: "chatgpt-pro-5x" },
    { label: "Pro 20x", slug: "chatgpt-pro-20x" },
    { label: "Codex", slug: "codex-access" },
    { label: "OpenAI API", slug: "openai-api-credit" },
    { label: "辅助服务", slug: "chatgpt-access-service" },
  ],
  Claude: [
    { label: "Claude Pro", slug: "claude-pro" },
    { label: "Claude 账号", slug: "claude-account" },
    { label: "Claude API", slug: "claude-api-access" },
  ],
  Gemini: [
    { label: "Gemini Advanced", slug: "gemini-advanced" },
    { label: "Gemini 账号", slug: "gemini-account" },
    { label: "Gemini API", slug: "gemini-api-access" },
  ],
  Grok: [
    { label: "SuperGrok", slug: "grok-super" },
    { label: "Grok 账号", slug: "grok-account" },
    { label: "Grok API", slug: "grok-api-access" },
  ],
  X: [
    { label: "Basic", slug: "x-premium-basic" },
    { label: "Premium", slug: "x-premium" },
    { label: "Premium+", slug: "x-premium-plus" },
  ],
};

function withQuery(path: string, query: URLSearchParams) {
  const value = query.toString();
  return value ? `${path}?${value}` : path;
}

export async function ProductCatalogPage({ rawParams, productSlug = "" }: { rawParams: RawSearchParams; productSlug?: string }) {
  const detailQuery = offerQuery(rawParams);
  const [product, meta] = await Promise.all([
    productSlug ? getProduct(productSlug, detailQuery.toString()) : Promise.resolve(null),
    getMeta(),
  ]);
  if (productSlug && !product) notFound();

  const activeBrand = product?.brand || single(rawParams, "brand") || single(rawParams, "platform");
  const activeSourcePlatform = single(rawParams, "source_platform");
  const catalogQuery = new URLSearchParams(detailQuery);
  if (activeBrand) catalogQuery.set("brand", activeBrand);
  const catalog = product ? null : await getCatalogGroups(catalogQuery.toString());
  const productTabBrand = activeBrand || "OpenAI";
  const productTabs = PRODUCT_TABS[productTabBrand] || [];
  const scopeQuery = new URLSearchParams(detailQuery);
  const filters = filterValues(rawParams);
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
  const navigationHref = withQuery(product ? `/products/${encodeURIComponent(product.slug)}` : "/products", navigationQuery);
  const hiddenFields = {
    ...(!product && activeBrand ? { brand: activeBrand } : {}),
    ...(activeSourcePlatform ? { source_platform: activeSourcePlatform } : {}),
  };

  return (
    <main id="main-content" className="shell py-8 md:py-10">
      <section className="border-b hairline pb-4" aria-label="报价快捷筛选">
        <nav className="flex items-center gap-1 overflow-x-auto" aria-label="品牌筛选">
          <span className="mr-2 shrink-0 text-xs text-black/45">品牌</span>
          <Link href={catalogHref()} aria-current={!activeBrand ? "page" : undefined} className={`flex shrink-0 items-center gap-2 rounded-full px-3 py-2 text-sm ${!activeBrand ? "bg-[color:var(--ink)] text-white" : "hover:bg-black/5"}`}>
            <PlatformIcon platform="" />全部
          </Link>
          {BRAND_TABS.map((brand) => (
            <Link key={brand} href={catalogHref(brand)} aria-current={activeBrand === brand ? "page" : undefined} className={`flex shrink-0 items-center gap-2 rounded-full px-3 py-2 text-sm ${activeBrand === brand ? "bg-[color:var(--ink)] text-white" : "hover:bg-black/5"}`}>
              <PlatformIcon platform={brand} />{brand}
            </Link>
          ))}
        </nav>
        <nav className="mt-3 flex items-center gap-1 overflow-x-auto border-t hairline pt-3" aria-label="商品类型筛选">
          <span className="mr-2 shrink-0 text-xs text-black/45">商品类型</span>
          <Link href={catalogHref(activeBrand)} aria-current={!product ? "page" : undefined} className={`shrink-0 rounded-full px-3 py-2 text-sm ${!product ? "bg-[color:var(--ink)] text-white" : "hover:bg-black/5"}`}>
            全部商品
          </Link>
          {productTabs.map((tab) => (
            <Link
              key={tab.slug}
              href={productHref(tab.slug)}
              aria-current={product?.slug === tab.slug ? "page" : undefined}
              className={`shrink-0 rounded-full px-3 py-2 text-sm ${product?.slug === tab.slug ? "bg-[color:var(--ink)] text-white" : "hover:bg-black/5"}`}
            >
              {tab.label}
            </Link>
          ))}
        </nav>
        <nav className="mt-3 flex items-center gap-1 overflow-x-auto border-t hairline pt-3" aria-label="来源平台筛选">
          <span className="mr-2 shrink-0 text-xs text-black/45">来源平台</span>
          <Link href={sourceHref()} aria-current={!activeSourcePlatform ? "page" : undefined} className={`shrink-0 rounded-full px-3 py-2 text-sm ${!activeSourcePlatform ? "bg-[color:var(--ink)] text-white" : "hover:bg-black/5"}`}>全部来源</Link>
          {meta.source_platforms.map((source) => (
            <Link key={source.id} href={sourceHref(source.id)} aria-current={activeSourcePlatform === source.id ? "page" : undefined} className={`shrink-0 rounded-full px-3 py-2 text-sm ${activeSourcePlatform === source.id ? "bg-[color:var(--ink)] text-white" : "hover:bg-black/5"}`}>{source.label}</Link>
          ))}
        </nav>
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
          <h1 className="sr-only">{activeBrand ? `${activeBrand} AI 商品公开报价` : "AI 商品公开报价目录"}</h1>
          <section className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-b hairline pb-4 text-sm text-black/50" aria-label="目录报价概况">
            <p className="flex items-center gap-1.5"><ShieldCheck size={16} />{catalog.trusted_offer_count} 条可参考报价</p>
            <p className="flex items-center gap-1.5"><Package size={16} />{catalog.in_stock_count} 条有货报价</p>
            <p className="flex items-center gap-1.5"><Stack size={16} />{catalog.offer_total} 条当前报价 · {catalog.comparable_offer_count} 条可直接比较</p>
            <p className="flex items-center gap-1.5"><Clock size={16} />最近更新 {relativeTime(catalog.last_updated_at)}</p>
          </section>

          <OfferScopeControls
            action="/products"
            values={filters}
            hiddenFields={hiddenFields}
            resetHref={navigationHref}
          />

          <section className="pb-12">
            <div className="mb-6">
              <h2 className="text-3xl font-semibold tracking-[-.04em]">在售报价</h2>
              <p className="mt-2 text-sm text-black/50">相同商品会合并展示。当前共有 {catalog.total} 款，点开即可查看不同店铺、交付方式和商品原文。</p>
              <p className="mt-1 text-xs text-black/35">统计仅包含当前筛选结果，价格和库存以最近一次更新为准。</p>
            </div>
            <OfferGroupTable
              key={`${activeBrand || "all"}:${catalog.snapshot_id || "current"}:${catalogQuery.toString()}`}
              groups={catalog.items}
              totalCount={catalog.total}
              snapshotId={catalog.snapshot_id}
              filterQuery={catalogQuery.toString()}
              loadMorePath="/api/v1/catalog/groups"
              showProduct
            />
          </section>
          <section className="border-t border-black py-12"><div className="max-w-2xl"><ReportForm /></div></section>
          <p className="border-t hairline py-5 text-xs text-black/40">数据更新于：{exactTime(catalog.snapshot_at)}</p>
        </>
      ) : null}
    </main>
  );
}
