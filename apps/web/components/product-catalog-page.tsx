import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, List, Package, ShieldCheck, SquaresFour } from "@phosphor-icons/react/ssr";
import { ProductCard } from "@/components/product-card";
import { ProductWorkspace, filterValues, offerQuery, single, type RawSearchParams } from "@/components/product-workspace";
import { SearchBox } from "@/components/search-box";
import { PlatformIcon } from "@/components/platform-icon";
import { getMeta, getProduct, getProducts } from "@/lib/api";

const BRAND_TABS = ["OpenAI", "Claude", "Gemini", "Grok", "X"];
const TYPE_TABS = [
  ["", "全部商品"],
  ["subscription", "订阅会员"],
  ["account", "成品账号"],
  ["api", "API 额度"],
  ["team", "团队席位"],
  ["service", "辅助服务"],
] as const;

function hrefWith(rawParams: RawSearchParams, changes: Record<string, string | null>) {
  const query = new URLSearchParams();
  for (const [key, raw] of Object.entries(rawParams)) {
    if (key === "product") continue;
    const value = Array.isArray(raw) ? raw.at(-1) || "" : raw || "";
    if (value) query.set(key, value);
  }
  for (const [key, value] of Object.entries(changes)) {
    if (value) query.set(key, value);
    else query.delete(key);
  }
  const suffix = query.toString();
  return suffix ? `/products?${suffix}` : "/products";
}

export async function ProductCatalogPage({ rawParams, productSlug = "" }: { rawParams: RawSearchParams; productSlug?: string }) {
  const detailQuery = offerQuery(rawParams);
  if (productSlug) {
    const product = await getProduct(productSlug, detailQuery.toString());
    if (!product) notFound();
    const resetHref = `/products/${encodeURIComponent(product.slug)}`;
    return (
      <main id="main-content" className="container">
        <div className="page-content detail-page">
          <ProductWorkspace product={product} rawParams={rawParams} query={detailQuery} filterAction={`/products/${encodeURIComponent(product.slug)}`} resetHref={resetHref} hiddenFields={{}} />
        </div>
      </main>
    );
  }

  const q = single(rawParams, "q").trim();
  const brand = single(rawParams, "brand") || single(rawParams, "platform");
  const productType = single(rawParams, "product_type");
  const sourcePlatform = single(rawParams, "source_platform");
  const sort = single(rawParams, "sort") || "quality";
  const view = single(rawParams, "view") === "list" ? "list" : "grid";
  const inStock = single(rawParams, "in_stock") === "true";
  const query = offerQuery(rawParams);
  query.delete("platform");
  if (q) query.set("q", q);
  if (brand) query.set("brand", brand);
  if (productType) query.set("product_type", productType);
  if (sourcePlatform) query.set("source_platform", sourcePlatform);
  if (inStock) query.set("in_stock", "true");
  query.set("sort", ["quality", "price", "price_desc", "updated", "offers"].includes(sort) ? sort : "quality");

  const [catalog, meta] = await Promise.all([getProducts(query.toString()), getMeta().catch(() => null)]);
  const items = catalog.items;

  return (
    <main id="main-content" className="container">
      <div className="page-content">
        <div className="page-intro"><span className="eyebrow">THE AI PRICE DIRECTORY</span><h1>好产品，值得认真比较。</h1><p>先选品牌与商品，再按交付方式、来源和更新时间寻找适合你的公开报价。</p></div>
        <SearchBox defaultValue={q} compact />

        <div className="filter-panel">
          <div className="filter-line"><span>品牌</span><div className="tabs"><Link className={!brand ? "active" : ""} href={hrefWith(rawParams, { brand: null, platform: null })}>全部</Link>{BRAND_TABS.map((item) => <Link key={item} className={brand === item ? "active" : ""} href={hrefWith(rawParams, { brand: item, platform: null })}><span className="brand-icon small"><PlatformIcon platform={item} size={14} /></span>{item}</Link>)}</div></div>
          <div className="filter-line"><span>商品类型</span><div className="tabs">{TYPE_TABS.map(([value, label]) => <Link key={label} className={productType === value || (!productType && !value) ? "active" : ""} href={hrefWith(rawParams, { product_type: value || null })}>{label}</Link>)}</div></div>
          {meta?.source_platforms?.length ? <div className="filter-line"><span>来源</span><div className="tabs"><Link className={!sourcePlatform ? "active" : ""} href={hrefWith(rawParams, { source_platform: null })}>全部来源</Link>{meta.source_platforms.filter((source) => source.id !== "dujiao_next").map((source) => <Link key={source.id} className={sourcePlatform === source.id ? "active" : ""} href={hrefWith(rawParams, { source_platform: source.id })}>{source.label}</Link>)}</div></div> : null}
        </div>

        <div className="results-toolbar">
          <span>找到 <strong>{catalog.total}</strong> 款产品 {q ? <>· 搜索“{q}”</> : null}<Link className="text-button subtle" href="/products">重置筛选</Link></span>
          <div>
            <Link className="toggle-label" href={hrefWith(rawParams, { in_stock: inStock ? null : "true" })}><span className={`toggle ${inStock ? "is-on" : ""}`} />仅看有货</Link>
            <form action="/products" method="get" className="inline-items">
              {q ? <input type="hidden" name="q" value={q} /> : null}
              {brand ? <input type="hidden" name="brand" value={brand} /> : null}
              {productType ? <input type="hidden" name="product_type" value={productType} /> : null}
              {sourcePlatform ? <input type="hidden" name="source_platform" value={sourcePlatform} /> : null}
              {inStock ? <input type="hidden" name="in_stock" value="true" /> : null}
              <select aria-label="排序方式" name="sort" defaultValue={sort}><option value="quality">综合排序</option><option value="price">价格从低到高</option><option value="price_desc">价格从高到低</option><option value="updated">最近更新</option><option value="offers">报价数量</option></select>
              <button className="text-button" type="submit">应用</button>
            </form>
            <div className="view-switch"><Link className={view === "grid" ? "active" : ""} href={hrefWith(rawParams, { view: null })} aria-label="网格视图"><SquaresFour size={17} /></Link><Link className={view === "list" ? "active" : ""} href={hrefWith(rawParams, { view: "list" })} aria-label="列表视图"><List size={17} /></Link></div>
          </div>
        </div>

        {items.length ? <div className={`product-grid ${view === "list" ? "list-view" : ""}`}>{items.map((product) => <ProductCard key={product.slug} product={product} />)}</div> : <div className="empty"><Package size={32} /><h3>没有找到匹配的产品</h3><p>试试其他关键词，或调整筛选条件。</p><Link href="/products" className="button">清空筛选</Link></div>}

        <div className="quote-disclaimer"><ShieldCheck size={14} />不同交付方式、周期与质保条件的价格不应直接比较。进入产品详情页可查看店铺、商品原文、来源和更新时间。</div>
        <section className="guide-callout"><div className="callout-icon"><Package size={24} /></div><div><h3>需要逐条查看店铺报价？</h3><p>进入任意产品详情即可展开同款商品的全部店铺、交付条件与原始来源。</p></div>{items[0] ? <Link className="button" href={`/products/${encodeURIComponent(items[0].slug)}`}>查看产品详情 <ArrowRight size={15} /></Link> : null}</section>
      </div>
    </main>
  );
}
