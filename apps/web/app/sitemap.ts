import type { MetadataRoute } from "next";
import { getMeta, getProducts, getShopTokens, getSkills } from "@/lib/api";
import type { CatalogResponse, CommunitySkillPage, ProductCard } from "@/lib/types";
import { SITE_URL } from "@/lib/site";

import { brandGuides, deliveryGuides, generalGuides, productGuides, workflowGuides } from "@/lib/guides/registry";

// The sitemap reflects API-backed catalog, source, shop, and skill data. Keep
// it runtime-generated so a production image can build without a live API.
export const dynamic = "force-dynamic";

const GUIDE_LAST_MODIFIED = new Date("2026-08-03");
const API_PAGE_SIZE = 100;
const MAX_API_OFFSET = 10000;
const MAX_SITEMAP_URLS = 50000;

async function getAllProducts(
  base: URLSearchParams = new URLSearchParams(),
  requiredSnapshotId: number | null = null,
): Promise<CatalogResponse> {
  const items: ProductCard[] = [];
  let offset = 0;
  let snapshotId = requiredSnapshotId;
  let firstPage: CatalogResponse | null = null;

  while (true) {
    const query = new URLSearchParams(base);
    query.set("sort", "quality");
    query.set("offset", String(offset));
    query.set("limit", String(API_PAGE_SIZE));
    if (snapshotId !== null) query.set("snapshot", String(snapshotId));
    const page = await getProducts(query.toString());
    firstPage ||= page;
    if (snapshotId === null) snapshotId = page.snapshot_id;
    if (page.snapshot_id !== snapshotId) throw new Error("Sitemap product pages crossed catalog snapshots");
    items.push(...page.items);
    if (items.length >= page.total) break;
    if (page.items.length === 0 || offset + page.items.length > MAX_API_OFFSET) {
      throw new Error("Sitemap product catalog exceeds the supported API pagination range");
    }
    offset += page.items.length;
  }

  if (!firstPage) throw new Error("Sitemap product catalog returned no page");
  return { ...firstPage, items, total: items.length, snapshot_id: snapshotId };
}

async function getAllSkills(): Promise<CommunitySkillPage> {
  let pageNumber = 1;
  let firstPage: CommunitySkillPage | null = null;
  const items: CommunitySkillPage["items"] = [];
  while (true) {
    const page = await getSkills(`page=${pageNumber}&page_size=${API_PAGE_SIZE}`);
    if (!page) throw new Error("Sitemap skills endpoint returned not found");
    firstPage ||= page;
    items.push(...page.items);
    if (items.length >= page.total) return { ...firstPage, items, total: items.length };
    if (page.items.length === 0) throw new Error("Sitemap skills pagination stopped before total");
    pageNumber += 1;
  }
}

async function mapWithConcurrency<T, R>(
  values: readonly T[],
  concurrency: number,
  worker: (value: T) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(values.length);
  let nextIndex = 0;
  await Promise.all(Array.from({ length: Math.min(concurrency, values.length) }, async () => {
    while (nextIndex < values.length) {
      const index = nextIndex++;
      results[index] = await worker(values[index]);
    }
  }));
  return results;
}

function validDate(value: string | null | undefined) {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticPages: MetadataRoute.Sitemap = [
    { url: SITE_URL },
    { url: `${SITE_URL}/products` },
    { url: `${SITE_URL}/skills` },
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

  const [catalog, shopTokens, meta, skillsData] = await Promise.all([
    getAllProducts(),
    getShopTokens(),
    getMeta(),
    getAllSkills(),
  ]);


  const snapshotAt = validDate(catalog?.snapshot_at);
  if (snapshotAt) {
    staticPages[0].lastModified = snapshotAt;
    staticPages[1].lastModified = snapshotAt;
  }

  if (meta?.advertise_enabled) {
    staticPages.push({ url: `${SITE_URL}/advertise`, lastModified: snapshotAt });
  }

  const sourceCatalogs = await mapWithConcurrency(meta.source_platforms, 4, async (platform) => {
    const query = new URLSearchParams({ source_platform: platform.id });
    const sourceCatalog = await getAllProducts(query, catalog.snapshot_id);
    return { platform, catalog: sourceCatalog };
  });

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
  const productPages: MetadataRoute.Sitemap = catalog.items
    .filter((product) => product.offer_count > 0)
    .map((product) => ({
      url: `${SITE_URL}/products/${encodeURIComponent(product.slug)}`,
      lastModified: validDate(product.last_updated_at) || snapshotAt,
    }));

  // Only emit source/product URLs that exist in that source's own catalog.
  const sourceProductPages: MetadataRoute.Sitemap = sourceCatalogs.flatMap(({ platform, catalog: sourceCatalog }) =>
    sourceCatalog.items
      .filter((product) => product.offer_count >= 2)
      .map((product) => ({
        url: `${SITE_URL}/sources/${encodeURIComponent(platform.id)}/products/${encodeURIComponent(product.slug)}`,
        lastModified: validDate(product.last_updated_at) || snapshotAt,
      })),
  );

  // Community Skills & Degradation Benchmark Lab pages
  const skillPages: MetadataRoute.Sitemap = skillsData.items.map((skill) => ({
    url: `${SITE_URL}/skills/${encodeURIComponent(skill.slug)}`,
    lastModified: validDate(skill.updated_at) || snapshotAt,
  }));

  const entries: MetadataRoute.Sitemap = [
    ...staticPages,
    ...guidePages,
    ...sourcePlatformPages,
    ...shopPages,
    ...productPages,
    ...sourceProductPages,
    ...skillPages,
  ];
  if (entries.length > MAX_SITEMAP_URLS) {
    throw new Error(`Sitemap has ${entries.length} URLs and must be split before it can be served`);
  }
  return entries;
}
