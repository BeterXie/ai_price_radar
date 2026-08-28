import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getMeta, getShopCards } from "@/lib/api";
import { PageHero } from "@/components/page-shell";
import { DIRECTORY_PAGE_SIZE, getTotalPages, PaginationNav, parsePage } from "@/components/pagination-nav";
import { relativeTime } from "@/lib/format";

export const dynamic = "force-dynamic";

const SITE_URL = "https://ai.pricememo.cn";

export const metadata: Metadata = {
  title: "AI 来源店铺目录",
  description: "查看 AI Price Radar 收录的公开 AI 商品店铺，包含 16688、LDXP 等平台来源的报价数、库存和最近更新时间。",
  alternates: { canonical: `${SITE_URL}/shops` },
  robots: { index: true, follow: true },
};

export default async function ShopsPage({
  searchParams,
}: {
  searchParams: Promise<{ source_platform?: string; page?: string }>;
}) {
  const { source_platform = "", page: rawPage = "1" } = await searchParams;
  const page = parsePage(rawPage);
  const pageHref = (targetPage: number) => {
    const params = new URLSearchParams();
    if (source_platform) params.set("source_platform", source_platform);
    params.set("page", String(targetPage));
    return `/shops?${params.toString()}`;
  };
  const queryParams = new URLSearchParams({
    sort: "offer_count",
    offset: String((page - 1) * DIRECTORY_PAGE_SIZE),
    limit: String(DIRECTORY_PAGE_SIZE),
  });
  if (source_platform) queryParams.set("source_platform", source_platform);
  const [{ items: shops, total }, meta] = await Promise.all([
    getShopCards(queryParams.toString()),
    getMeta(),
  ]);
  const totalPages = getTotalPages(total, DIRECTORY_PAGE_SIZE);
  if (page > totalPages) redirect(pageHref(totalPages));

  return (
    <main id="main-content" className="shell">
      <PageHero
        eyebrow="来源目录"
        title="AI 来源店铺目录"
        description={`当前共收录 ${total} 家有公开报价的店铺`}
      />

      {/* Platform filter */}
      <section className="mt-6 flex flex-wrap gap-2">
        <Link
          href="/shops"
          className={`rounded-full px-3 py-1 text-sm border ${!source_platform ? "bg-black text-white border-black" : "border-black/20 hover:border-black/40"}`}
        >
          全部
        </Link>
        {meta.source_platforms.map(({ id, label }) => (
          <Link
            key={id}
            href={`/shops?source_platform=${encodeURIComponent(id)}`}
            className={`rounded-full px-3 py-1 text-sm border ${source_platform === id ? "bg-black text-white border-black" : "border-black/20 hover:border-black/40"}`}
          >
            {label}
          </Link>
        ))}
      </section>

      {/* Shop list */}
      <section className="mt-8">
        {shops.length === 0 ? (
          <p className="text-black/50 py-12 text-center">暂无符合条件的店铺</p>
        ) : (
          <div className="divide-y divide-black/8">
            {shops.map((shop) => (
              <div key={shop.token} className="py-4 flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <Link href={`/shops/${encodeURIComponent(shop.token)}`} className="font-medium hover:underline">
                    {shop.name}
                  </Link>
                  <p className="mt-0.5 text-xs text-black/40">
                    {shop.source_platform_label} · 来源编号：{shop.token}
                    {shop.product_slugs.length > 0 && (
                      <> · 涉及：{shop.product_slugs.slice(0, 4).join("、")}{shop.product_slugs.length > 4 ? " 等" : ""}</>
                    )}
                  </p>
                </div>
                <div className="shrink-0 text-right text-sm">
                  <p className="font-medium">{shop.offer_count} 条报价</p>
                  <p className="text-xs text-black/40">
                    有货 {shop.in_stock_count} · {relativeTime(shop.last_seen_at || shop.last_success_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
      <PaginationNav page={page} totalPages={totalPages} hrefForPage={pageHref} ariaLabel="店铺目录分页" />
    </main>
  );
}
