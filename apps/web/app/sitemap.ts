import type { MetadataRoute } from "next";
import { getMeta, getProducts, getShopTokens } from "@/lib/api";
import { brandGuides, deliveryGuides, generalGuides, productGuides, workflowGuides } from "@/lib/guides/registry";

export const dynamic = "force-dynamic";

const SITE_URL = "https://ai.pricememo.cn";
const GUIDE_LAST_MODIFIED = new Date("2026-08-03");

function validDate(value: string | null | undefined) {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticPages: MetadataRoute.Sitemap = [
    { url: SITE_URL },
    { url: `${SITE_URL}/products` },
    { url: `${SITE_URL}/shops` },
    { url: `${SITE_URL}/sources` },
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
    ...Object.keys(workflowGuides).map((slug) => ({ url: `${SITE_URL}/guides/workflows/${encodeURIComponent(slug)}`, lastModified: GUIDE_LAST_MODIFIED })),
  ];

  // Keep each upstream request independent. A temporary failure in one catalog
  // should not make the whole dynamic sitemap disappear for this crawl.
  const [catalog, shopTokens, meta] = await Promise.all([
    getProducts("sort=quality").catch(() => null),
    getShopTokens().catch(() => [] as string[]),
    getMeta().catch(() => null),
  ]);

  const snapshotAt = validDate(catalog?.snapshot_at);
  if (snapshotAt) {
    staticPages[0].lastModified = snapshotAt;
    staticPages[1].lastModified = snapshotAt;
  }

  const sourceCatalogs = meta
    ? (
        await Promise.all(
          meta.source_platforms.map(async (platform) => {
            const sourceCatalog = await getProducts(
              `source_platform=${encodeURIComponent(platform.id)}&sort=quality`,
            ).catch(() => null);
            return sourceCatalog ? { platform, catalog: sourceCatalog } : null;
          }),
        )
      ).filter((entry): entry is NonNullable<typeof entry> => entry !== null)
    : [];

  // Source platform pages – only include platforms with active offers.
  const sourcePlatformPages: MetadataRoute.Sitemap = sourceCatalogs
    .filter(({ catalog: sourceCatalog }) => sourceCatalog.offer_count > 0)
    .map(({ platform }) => ({
      url: `${SITE_URL}/sources/${encodeURIComponent(platform.id)}`,
      lastModified: snapshotAt,
    }));

  // Shop pages – only shops with public offers.
  const shopPages: MetadataRoute.Sitemap = shopTokens.map((token) => ({
    url: `${SITE_URL}/shops/${encodeURIComponent(token)}`,
    lastModified: snapshotAt,
  }));

  // Product pages are emitted only when the global catalog request succeeded.
  const productPages: MetadataRoute.Sitemap = catalog
    ? catalog.items
        .filter((product) => product.offer_count > 0)
        .map((product) => ({
          url: `${SITE_URL}/products/${encodeURIComponent(product.slug)}`,
          lastModified: validDate(product.last_updated_at) || snapshotAt,
        }))
    : [];

  // Only emit source/product URLs that exist in that source's own catalog.
  const sourceProductPages: MetadataRoute.Sitemap = sourceCatalogs.flatMap(({ platform, catalog: sourceCatalog }) =>
    sourceCatalog.items
      .filter((product) => product.offer_count >= 2)
      .map((product) => ({
        url: `${SITE_URL}/sources/${encodeURIComponent(platform.id)}/products/${encodeURIComponent(product.slug)}`,
        lastModified: validDate(product.last_updated_at) || snapshotAt,
      })),
  );

  return [
    ...staticPages,
    ...guidePages,
    ...sourcePlatformPages,
    ...shopPages,
    ...productPages,
    ...sourceProductPages,
  ];
}
