import type { Metadata } from "next";
import Link from "next/link";
import { getMeta } from "@/lib/api";
import { PageHero } from "@/components/page-shell";
import { JsonLd, breadcrumbJsonLd } from "@/components/structured-data";

export const dynamic = "force-dynamic";

const SITE_URL = "https://ai.pricememo.cn";

export const metadata: Metadata = {
  title: "来源平台",
  description: "AI Price Radar 收录的公开 AI 商品来源平台，包含 16688、LDXP 等平台的店铺与报价数据。",
  alternates: { canonical: `${SITE_URL}/sources` },
  robots: { index: true, follow: true },
};

export default async function SourcesPage() {
  const meta = await getMeta();
  const platforms = meta.source_platforms;
  const canonical = `${SITE_URL}/sources`;
  const structuredData = [
    breadcrumbJsonLd([
      { name: "首页", path: "/" },
      { name: "来源平台", path: "/sources" },
    ]),
    {
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      "@id": canonical,
      url: canonical,
      name: "来源平台",
      description: "AI Price Radar 收录的公开 AI 商品来源平台。",
      isPartOf: { "@id": "https://ai.pricememo.cn/#website" },
      mainEntity: {
        "@type": "ItemList",
        numberOfItems: platforms.length,
        itemListElement: platforms.map((platform, index) => ({
          "@type": "ListItem",
          position: index + 1,
          name: platform.label,
          url: `${SITE_URL}/sources/${encodeURIComponent(platform.id)}`,
        })),
      },
    },
  ];

  return (
    <main id="main-content" className="shell">
      <JsonLd data={structuredData} />
      <PageHero
        eyebrow="数据来源"
        title="来源平台"
        description="AI Price Radar 从以下公开平台采集 AI 商品报价信息。"
      />

      <section aria-labelledby="source-platforms-title" className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <h2 id="source-platforms-title" className="sr-only">收录的来源平台</h2>
        {platforms.map((platform) => (
          <Link
            key={platform.id}
            href={`/sources/${encodeURIComponent(platform.id)}`}
            className="rounded-xl border border-black/10 p-5 hover:border-black/30 transition-colors"
          >
            <p className="font-semibold">{platform.label}</p>
            <p className="mt-1 text-xs text-black/40">{platform.id}</p>
            <p className="mt-3 text-sm text-black/60 hover:text-black">查看该平台报价 →</p>
          </Link>
        ))}
      </section>
    </main>
  );
}
