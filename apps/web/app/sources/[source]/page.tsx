import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getProducts, getShopCards, getMeta } from "@/lib/api";
import { PageHero, SectionIntro } from "@/components/page-shell";
import { JsonLd, breadcrumbJsonLd } from "@/components/structured-data";
import { DIRECTORY_PAGE_SIZE, getTotalPages, PaginationNav, parsePage } from "@/components/pagination-nav";
import { relativeTime } from "@/lib/format";

export const dynamic = "force-dynamic";

const SITE_URL = "https://ai.pricememo.cn";
const DISABLED_SOURCES = new Set(["dujiao_next"]);

// SEO metadata per source platform
const SOURCE_META: Record<string, { title: string; description: string; h1: string; intro: string }> = {
  "16688": {
    title: "16688 AI 商品与店铺报价｜ChatGPT、Codex、Claude、Gemini、Grok",
    description:
      "查看来自 16688 公开店铺的 ChatGPT、Codex、Claude、Gemini、Grok 商品报价、库存、店铺和最近更新时间。",
    h1: "16688 AI 商品与店铺报价",
    intro:
      "AI Price Radar 汇总来自 16688 公开店铺的 ChatGPT、Codex、Claude、Gemini、Grok 等公开报价，展示价格、库存、交付方式与更新时间。",
  },
  ldxp: {
    title: "LDXP AI 商品报价",
    description: "查看来自 LDXP 公开来源的 AI 订阅商品报价、库存和更新时间。",
    h1: "LDXP AI 商品报价",
    intro: "AI Price Radar 汇总来自 LDXP 来源的 AI 订阅公开报价，展示价格、库存与更新时间。",
  },
};

const DEFAULT_META = (source: string) => ({
  title: `${source} AI 商品报价`,
  description: `查看来自 ${source} 来源的 AI 商品公开报价、库存和更新时间。`,
  h1: `${source} AI 商品报价`,
  intro: `AI Price Radar 汇总来自 ${source} 来源的 AI 订阅公开报价。`,
});

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: Promise<{ source: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}): Promise<Metadata> {
  const [{ source }, rawParams] = await Promise.all([params, searchParams]);
  if (DISABLED_SOURCES.has(source)) notFound();
  const meta = getMeta_for(source);
  const canonical = `${SITE_URL}/sources/${encodeURIComponent(source)}`;
  return {
    title: meta.title,
    description: meta.description,
    alternates: { canonical },
    robots: { index: Object.keys(rawParams).length === 0, follow: true },
    openGraph: {
      title: meta.title,
      description: meta.description,
      url: canonical,
      type: "website",
    },
  };
}

function getMeta_for(source: string) {
  return SOURCE_META[source] ?? DEFAULT_META(source);
}

export default async function SourcePage({
  params,
  searchParams,
}: {
  params: Promise<{ source: string }>;
  searchParams: Promise<{ page?: string }>;
}) {
  const { source } = await params;
  if (DISABLED_SOURCES.has(source)) notFound();
  const { page: rawPage = "1" } = await searchParams;
  const page = parsePage(rawPage);

  // Validate that this source platform actually exists
  const apiMeta = await getMeta();
  const platformExists = apiMeta.source_platforms.some((p) => p.id === source);
  if (!platformExists) notFound();

  const pageMeta = getMeta_for(source);
  const canonical = `${SITE_URL}/sources/${encodeURIComponent(source)}`;
  const pageHref = (targetPage: number) => `/sources/${encodeURIComponent(source)}?page=${targetPage}`;
  const shopQuery = new URLSearchParams({
    source_platform: source,
    sort: "offer_count",
    offset: String((page - 1) * DIRECTORY_PAGE_SIZE),
    limit: String(DIRECTORY_PAGE_SIZE),
  });
  const [catalog, shopsData] = await Promise.all([
    getProducts(`source_platform=${encodeURIComponent(source)}&sort=quality`),
    getShopCards(shopQuery.toString()),
  ]);

  const shops = shopsData.items;
  const products = catalog.items.filter((p) => p.offer_count > 0);
  const totalPages = getTotalPages(shopsData.total, DIRECTORY_PAGE_SIZE);
  if (page > totalPages) redirect(pageHref(totalPages));
  const structuredData = [
    breadcrumbJsonLd([
      { name: "首页", path: "/" },
      { name: "来源平台", path: "/sources" },
      { name: pageMeta.h1, path: `/sources/${encodeURIComponent(source)}` },
    ]),
    {
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      "@id": canonical,
      url: canonical,
      name: pageMeta.h1,
      description: pageMeta.intro,
      isPartOf: { "@id": "https://ai.pricememo.cn/#website" },
      mainEntity: {
        "@type": "ItemList",
        numberOfItems: products.length,
        itemListElement: products.map((product, index) => ({
          "@type": "ListItem",
          position: index + 1,
          name: product.display_name,
          url: `${SITE_URL}/sources/${encodeURIComponent(source)}/products/${encodeURIComponent(product.slug)}`,
        })),
      },
    },
  ];

  return (
    <main id="main-content" className="shell">
      <JsonLd data={structuredData} />
      <PageHero
        eyebrow={`来源平台 · ${source}`}
        title={pageMeta.h1}
        description={pageMeta.intro}
      />

      {/* Stats */}
      <section aria-labelledby="source-stats-title" className="mt-6 grid grid-cols-3 gap-4 rounded-xl border border-black/10 p-5">
        <h2 id="source-stats-title" className="sr-only">来源平台数据概况</h2>
        <div>
          <p className="text-2xl font-semibold">{catalog.offer_count}</p>
          <p className="text-xs text-black/50 mt-1">当前有效报价</p>
        </div>
        <div>
          <p className="text-2xl font-semibold">{shopsData.total}</p>
          <p className="text-xs text-black/50 mt-1">当前店铺数</p>
        </div>
        <div>
          <p className="text-2xl font-semibold">{catalog.in_stock_count}</p>
          <p className="text-xs text-black/50 mt-1">有货报价数</p>
        </div>
      </section>

      {/* Products */}
      {products.length > 0 && (
        <section className="mt-10">
          <SectionIntro eyebrow="标准产品" title="热门标准产品" description="点击产品名查看该来源下的完整报价列表。" />
          <div className="mt-4 flex flex-wrap gap-2">
            {products.map((product) => (
              <Link
                key={product.slug}
                href={`/sources/${encodeURIComponent(source)}/products/${encodeURIComponent(product.slug)}`}
                className="rounded-full border border-black/15 px-3 py-1.5 text-sm hover:border-black/40 transition-colors"
              >
                {product.display_name}
                <span className="ml-1.5 text-xs text-black/40">{product.offer_count}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Shops */}
      {shops.length > 0 && (
        <section className="mt-10">
          <SectionIntro eyebrow="来源店铺" title={`当前店铺 · ${shopsData.total}`} description="点击店铺名查看该店铺的完整报价详情。" />
          <div className="mt-4 divide-y divide-black/8">
            {shops.map((shop) => (
              <div key={shop.token} className="py-4 flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <Link href={`/shops/${encodeURIComponent(shop.token)}`} className="font-medium hover:underline">
                    {shop.name}
                  </Link>
                  <p className="mt-0.5 text-xs text-black/40">
                    {shop.token}
                    {shop.product_slugs.length > 0 && (
                      <> · {shop.product_slugs.slice(0, 3).join("、")}{shop.product_slugs.length > 3 ? " 等" : ""}</>
                    )}
                  </p>
                </div>
                <div className="shrink-0 text-right text-sm">
                  <p className="font-medium">{shop.offer_count} 条报价</p>
                  <p className="text-xs text-black/40">
                    {relativeTime(shop.last_seen_at || shop.last_success_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
      <PaginationNav page={page} totalPages={totalPages} hrefForPage={pageHref} ariaLabel="来源店铺分页" />
    </main>
  );
}
