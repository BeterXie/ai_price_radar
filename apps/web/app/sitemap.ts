import type { MetadataRoute } from "next";
import { getProducts } from "@/lib/api";
import { brandGuides, deliveryGuides, generalGuides, productGuides } from "@/lib/guides/registry";

export const dynamic = "force-dynamic";

const SITE_URL = "https://ai.pricememo.cn";
const GUIDE_LAST_MODIFIED = new Date("2026-08-03");

function validDate(value: string | null) {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticPages: MetadataRoute.Sitemap = [
    { url: SITE_URL },
    { url: `${SITE_URL}/products` },
    { url: `${SITE_URL}/tools/json-to-cockpit`, lastModified: GUIDE_LAST_MODIFIED },
    { url: `${SITE_URL}/shops/submit` },
    { url: `${SITE_URL}/watchlist` },
    { url: `${SITE_URL}/methodology` },
    { url: `${SITE_URL}/corrections` },
    { url: `${SITE_URL}/developers` },
    { url: `${SITE_URL}/about` },
    { url: `${SITE_URL}/privacy` },
    { url: `${SITE_URL}/terms` },
    { url: `${SITE_URL}/security` },
  ];
  const guidePages: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/guides`, lastModified: GUIDE_LAST_MODIFIED },
    ...Object.keys(brandGuides).map((brand) => ({ url: `${SITE_URL}/guides/brands/${encodeURIComponent(brand)}`, lastModified: GUIDE_LAST_MODIFIED })),
    ...Object.keys(productGuides).map((productSlug) => ({ url: `${SITE_URL}/guides/products/${encodeURIComponent(productSlug)}`, lastModified: GUIDE_LAST_MODIFIED })),
    ...Object.keys(deliveryGuides).map((deliveryType) => ({ url: `${SITE_URL}/guides/delivery/${encodeURIComponent(deliveryType)}`, lastModified: GUIDE_LAST_MODIFIED })),
    ...Object.keys(generalGuides).map((slug) => ({ url: `${SITE_URL}/guides/${encodeURIComponent(slug)}`, lastModified: GUIDE_LAST_MODIFIED })),
  ];
  try {
    const catalog = await getProducts("sort=quality");
    const snapshotAt = validDate(catalog.snapshot_at);
    staticPages[0].lastModified = snapshotAt;
    staticPages[1].lastModified = snapshotAt;
    return [
      ...staticPages,
      ...guidePages,
      ...catalog.items
        .filter((product) => product.offer_count > 0)
        .map((product) => ({
          url: `${SITE_URL}/products/${encodeURIComponent(product.slug)}`,
          lastModified: validDate(product.last_updated_at) || snapshotAt,
        })),
    ];
  } catch {
    return [...staticPages, ...guidePages];
  }
}
