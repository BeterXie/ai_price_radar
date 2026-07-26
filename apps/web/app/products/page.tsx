import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Clock, Package, Stack } from "@phosphor-icons/react/ssr";
import { OfferGroupTable } from "@/components/offer-table";
import { OfferScopeControls } from "@/components/offer-scope-controls";
import { PlatformIcon } from "@/components/platform-icon";
import { offerQuery, ProductWorkspace } from "@/components/product-workspace";
import { ReportForm } from "@/components/report-form";
import { getCatalogGroups, getProduct } from "@/lib/api";
import { exactTime, relativeTime } from "@/lib/format";

export const dynamic = "force-dynamic";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export async function generateMetadata({ searchParams }: { searchParams: SearchParams }): Promise<Metadata> {
  const params = await searchParams;
  const value = params.product;
  const slug = Array.isArray(value) ? value.at(-1) || "" : value || "";
  if (slug) {
    const product = await getProduct(slug, "comparable=true");
    if (!product) return { title: "产品不存在", robots: { index: false, follow: true } };
    const canonical = `https://ai.pricememo.cn/products?platform=${encodeURIComponent(product.platform)}&product=${encodeURIComponent(product.slug)}`;
    const hasOfferFilters = Object.keys(params).some((key) => !["platform", "product"].includes(key));
    return {
      title: `${product.display_name}价格对比`,
      description: product.description,
      alternates: { canonical },
      robots: hasOfferFilters ? { index: false, follow: true } : { index: true, follow: true },
      openGraph: { title: `${product.display_name}价格对比`, description: product.description, url: canonical, type: "website" },
    };
  }
  return {
    title: "全部报价",
    alternates: { canonical: "https://ai.pricememo.cn/products" },
    robots: Object.keys(params).length ? { index: false, follow: true } : { index: true, follow: true },
  };
}

const PLATFORM_TABS = ["OpenAI", "Claude", "Gemini", "Grok", "X"];

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

export default async function ProductsPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const single = (key: string) => Array.isArray(params[key]) ? String(params[key]?.at(-1) || "") : typeof params[key] === "string" ? String(params[key]) : "";
  const activeProduct = single("product");
  const query = new URLSearchParams();
  ["platform", "product", "comparable"].forEach((key) => { const value = single(key); if (value) query.set(key, value); });
  if (single("in_stock") === "true") query.set("in_stock", "true");
  const detailQuery = offerQuery(params);
  const product = activeProduct ? await getProduct(activeProduct, detailQuery.toString()) : null;
  if (activeProduct && !product) notFound();
  const activePlatform = product?.platform || single("platform");
  const catalogQuery = new URLSearchParams(detailQuery);
  if (activePlatform) catalogQuery.set("platform", activePlatform);
  const catalog = activeProduct ? null : await getCatalogGroups(catalogQuery.toString());
  const productTabPlatform = activePlatform || "OpenAI";
  const productTabs = PRODUCT_TABS[productTabPlatform] || [];
  const hrefFor = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(query);
    for (const [key, value] of Object.entries(updates)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    const value = next.toString();
    return value ? `/products?${value}` : "/products";
  };

  return (
    <main id="main-content" className="shell py-8 md:py-10">
      <section className="border-b hairline pb-4" aria-label="报价快捷筛选">
        <nav className="flex items-center gap-1 overflow-x-auto" aria-label="平台筛选">
          <span className="mr-2 shrink-0 text-xs text-black/45">平台</span>
          <Link href={hrefFor({ platform: null, product: null })} aria-current={!activePlatform ? "page" : undefined} className={`flex shrink-0 items-center gap-2 rounded-full px-3 py-2 text-sm ${!activePlatform ? "bg-[color:var(--ink)] text-white" : "hover:bg-black/5"}`}>
            <PlatformIcon platform="" />全部
          </Link>
          {PLATFORM_TABS.map((platform) => (
            <Link key={platform} href={hrefFor({ platform, product: null })} aria-current={activePlatform === platform ? "page" : undefined} className={`flex shrink-0 items-center gap-2 rounded-full px-3 py-2 text-sm ${activePlatform === platform ? "bg-[color:var(--ink)] text-white" : "hover:bg-black/5"}`}>
              <PlatformIcon platform={platform} />{platform}
            </Link>
          ))}
        </nav>
        <nav className="mt-3 flex items-center gap-1 overflow-x-auto border-t hairline pt-3" aria-label="标准商品筛选">
          <span className="mr-2 shrink-0 text-xs text-black/45">标准商品</span>
          <Link href={hrefFor({ product: null })} aria-current={!activeProduct ? "page" : undefined} className={`shrink-0 rounded-full px-3 py-2 text-sm ${!activeProduct ? "bg-[color:var(--ink)] text-white" : "hover:bg-black/5"}`}>
            全部商品
          </Link>
          {productTabs.map((product) => (
            <Link
              key={product.slug}
              href={hrefFor({ platform: productTabPlatform, product: product.slug, q: null, sort: null })}
              aria-current={activeProduct === product.slug ? "page" : undefined}
              className={`shrink-0 rounded-full px-3 py-2 text-sm ${activeProduct === product.slug ? "bg-[color:var(--ink)] text-white" : "hover:bg-black/5"}`}
            >
              {product.label}
            </Link>
          ))}
        </nav>
      </section>
      {product ? (
        <ProductWorkspace
          product={product}
          rawParams={params}
          query={detailQuery}
          filterAction="/products"
          hiddenFields={{ platform: product.platform, product: product.slug }}
          resetHref={`/products?platform=${encodeURIComponent(product.platform)}&product=${encodeURIComponent(product.slug)}`}
        />
      ) : catalog ? (
        <>
          <section className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-b hairline pb-4 text-sm text-black/50" aria-label="目录报价概况">
            <p className="flex items-center gap-1.5"><Package size={16} />{catalog.in_stock_count} 条有货报价</p>
            <p className="flex items-center gap-1.5"><Stack size={16} />{catalog.offer_total} 条有效报价</p>
            <p className="flex items-center gap-1.5"><Clock size={16} />最近更新 {relativeTime(catalog.last_updated_at)}</p>
          </section>

          <OfferScopeControls
            action="/products"
            comparableOnly={single("comparable") !== "false"}
            inStockOnly={single("in_stock") === "true"}
            hiddenFields={activePlatform ? { platform: activePlatform } : {}}
            resetHref={activePlatform ? `/products?platform=${encodeURIComponent(activePlatform)}` : "/products"}
          />

          <section className="pb-12">
            <div className="mb-6">
              <h2 className="text-3xl font-semibold tracking-[-.04em]">同款报价</h2>
              <p className="mt-2 text-sm text-black/50">跨标准商品按同款合并；当前显示 {catalog.total} 款，可展开查看全部店铺和按需加载原始描述。</p>
            </div>
            <OfferGroupTable
              key={`${activePlatform || "all"}:${catalog.snapshot_id || "current"}:${catalogQuery.toString()}`}
              groups={catalog.items}
              totalCount={catalog.total}
              snapshotId={catalog.snapshot_id}
              filterQuery={catalogQuery.toString()}
              loadMorePath="/api/v1/catalog/groups"
              showProduct
            />
          </section>
          <section className="border-t border-black py-12"><div className="max-w-2xl"><ReportForm /></div></section>
          <p className="border-t hairline py-5 text-xs text-black/40">数据快照：{catalog.snapshot_id ? `#${catalog.snapshot_id}` : "未编号"} · {exactTime(catalog.snapshot_at)}</p>
        </>
      ) : null}
    </main>
  );
}
