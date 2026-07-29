import type { MetadataRoute } from "next";
import { getProducts } from "@/lib/api";

export const dynamic = "force-dynamic";

const SITE_URL = "https://ai.pricememo.cn";

function validDate(value: string | null) {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticPages: MetadataRoute.Sitemap = [
    { url: SITE_URL },
    { url: `${SITE_URL}/products` },
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
  try {
    const catalog = await getProducts("sort=quality");
    const snapshotAt = validDate(catalog.snapshot_at);
    staticPages[0].lastModified = snapshotAt;
    staticPages[1].lastModified = snapshotAt;
    return [
      ...staticPages,
      ...catalog.items
        .filter((product) => product.offer_count > 0)
        .map((product) => ({
          url: `${SITE_URL}/products/${encodeURIComponent(product.slug)}`,
          lastModified: validDate(product.last_updated_at) || snapshotAt,
        })),
    ];
  } catch {
    return staticPages;
  }
}
