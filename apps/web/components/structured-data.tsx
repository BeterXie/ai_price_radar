type JsonLdObject = Record<string, unknown>;
type JsonLdValue = JsonLdObject | readonly JsonLdObject[];

function serializeJsonLd(value: JsonLdValue): string {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}

export function JsonLd({ data }: { data: JsonLdValue }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeJsonLd(data) }} />;
}

export function SiteStructuredData() {
  const organizationId = `${SITE_URL}/#organization`;
  const websiteId = `${SITE_URL}/#website`;

  return (
    <JsonLd
      data={{
        "@context": "https://schema.org",
        "@graph": [
          {
            "@type": "Organization",
            "@id": organizationId,
            name: "AI Price Memory",
            alternateName: ["AI Price Radar", "PriceMemo"],
            url: SITE_URL,
            logo: {
              "@type": "ImageObject",
              url: `${SITE_URL}/brand/logo-icon.png`,
            },
            sameAs: ["https://github.com/BeterXie/ai_price_radar"],
            description: "整理公开 AI 商品报价、来源、库存和更新时间的价格信息项目。",
            knowsAbout: ["AI 订阅价格", "公开商品报价", "商品来源和更新时间"],
          },
          {
            "@type": "WebSite",
            "@id": websiteId,
            url: SITE_URL,
            name: "AI Price Memory",
            alternateName: ["AI Price Radar", "PriceMemo"],
            inLanguage: "zh-CN",
            publisher: { "@id": organizationId },
            potentialAction: {
              "@type": "SearchAction",
              target: {
                "@type": "EntryPoint",
                urlTemplate: `${SITE_URL}/products?q={search_term_string}`,
              },
              "query-input": "required name=search_term_string",
            },
          },
        ],
      }}
    />
  );
}

export function breadcrumbJsonLd(items: readonly { name: string; path: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: `${SITE_URL}${item.path}`,
    })),
  };
}
import { SITE_URL } from "@/lib/site";
