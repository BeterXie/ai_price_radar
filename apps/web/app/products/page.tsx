import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CaretDown, CaretUp, Clock, MagnifyingGlass, Package, Stack } from "@phosphor-icons/react/ssr";
import { PlatformIcon } from "@/components/platform-icon";
import { ProductCard } from "@/components/product-card";
import { offerQuery, ProductWorkspace } from "@/components/product-workspace";
import { DELIVERY_TYPE_LABELS } from "@/lib/catalog";
import { getProduct, getProducts } from "@/lib/api";
import { exactTime } from "@/lib/format";

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

const PLATFORM_TABS = ["OpenAI", "Claude", "Gemini", "Grok"];

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
};

export default async function ProductsPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const single = (key: string) => Array.isArray(params[key]) ? String(params[key]?.at(-1) || "") : typeof params[key] === "string" ? String(params[key]) : "";
  const activeProduct = single("product");
  const query = new URLSearchParams();
  ["q", "platform", "product", "sort", "delivery_type", "updated_within_hours", "comparable"].forEach((key) => { const value = single(key); if (value) query.set(key, value); });
  if (single("in_stock") === "true") query.set("in_stock", "true");
  const detailQuery = offerQuery(params);
  const product = activeProduct ? await getProduct(activeProduct, detailQuery.toString()) : null;
  if (activeProduct && !product) notFound();
  const data = activeProduct ? null : await getProducts(query.toString());
  const activePlatform = product?.platform || single("platform");
  const currentSort = single("sort") || "price";
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
      ) : data ? (
        <>
          <section className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-b hairline pb-4 text-sm text-black/50" aria-label="目录报价概况">
            <p className="flex items-center gap-1.5"><Package size={16} />{data.in_stock_count} 条有货报价</p>
            <p className="flex items-center gap-1.5"><Stack size={16} />{data.offer_count} 条有效报价</p>
            <p className="flex items-center gap-1.5"><Clock size={16} />更新时间 {exactTime(data.snapshot_at)}</p>
          </section>

          <form className="mt-6 rounded-[14px] border border-black bg-white p-3">
            <fieldset className="grid gap-3 md:grid-cols-[minmax(240px,1fr)_180px_150px_auto] md:items-end">
              <legend className="sr-only">报价目录筛选</legend>
              <input type="hidden" name="platform" value={activePlatform} />
              <input type="hidden" name="sort" value={currentSort} />
              <label className="flex min-w-0 items-center"><span className="sr-only">搜索标准产品或原始商品名</span><MagnifyingGlass size={20} className="shrink-0" /><input name="q" defaultValue={single("q")} placeholder="搜索标准产品或原始商品名" aria-label="搜索标准产品或原始商品名" className="w-full bg-transparent px-3 py-2 outline-none" /></label>
              <label className="text-xs text-black/55">交付形态<select name="delivery_type" defaultValue={single("delivery_type")} className="mt-1 w-full rounded-[8px] border hairline bg-transparent px-3 py-2 text-sm text-black"><option value="">全部形态</option>{Object.entries(DELIVERY_TYPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
              <label className="text-xs text-black/55">更新时间<select name="updated_within_hours" defaultValue={single("updated_within_hours")} className="mt-1 w-full rounded-[8px] border hairline bg-transparent px-3 py-2 text-sm text-black"><option value="">72 小时内</option><option value="1">1 小时内</option><option value="24">24 小时内</option></select></label>
              <button className="tactile shrink-0 rounded-[9px] bg-[color:var(--ink)] px-5 py-2.5 text-sm text-white">应用筛选</button>
              <div className="flex flex-wrap gap-5 text-sm md:col-span-4"><label className="flex items-center gap-2"><input type="hidden" name="comparable" value="false" /><input type="checkbox" name="comparable" value="true" defaultChecked={single("comparable") === "true"} className="h-4 w-4 accent-black" />仅显示可直接比较</label><label className="flex items-center gap-2"><input type="checkbox" name="in_stock" value="true" defaultChecked={single("in_stock") === "true"} className="h-4 w-4 accent-black" />仅看有货</label></div>
            </fieldset>
          </form>

          <section className="py-8">
            {data.items.length ? (
              <>
                <div className="hidden grid-cols-[40px_minmax(220px,1.4fr)_90px_100px_125px_115px_100px_24px] gap-4 border-b border-black px-0 pb-3 text-xs text-black/45 lg:grid">
                  <span>序号</span><span>标准商品</span><span>平台</span><span>类型</span>
                  <Link href={hrefFor({ sort: currentSort === "price" ? "price_desc" : "price" })} className="flex items-center gap-1.5 text-black/60 hover:text-black" aria-label={currentSort === "price" ? "按最低有货价从高到低排序" : "按最低有货价从低到高排序"}>
                    可比最低价 {currentSort === "price_desc" ? <CaretDown size={13} /> : <CaretUp size={13} />}
                  </Link>
                  <span>库存</span><span>更新时间</span><span>查看</span>
                </div>
                <div>{data.items.map((item, index) => <ProductCard key={item.slug} product={item} index={index} />)}</div>
              </>
            ) : (
              <div className="rounded-[18px] border hairline p-16 text-center"><h2 className="text-2xl font-semibold">没有匹配产品</h2><p className="mt-3 text-black/50">清除部分筛选条件后再试。</p></div>
            )}
          </section>
        </>
      ) : null}
    </main>
  );
}
