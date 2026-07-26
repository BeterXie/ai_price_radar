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
  ];
  try {
    const catalog = await getProducts("sort=price");
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
