import type { CatalogResponse, ProductCard } from "@/lib/types";

type CachedSnapshot = {
  data: any;
  cachedAt: number;
};

let memoryCache: CachedSnapshot | null = null;
const CACHE_TTL_MS = 15_000; // 15 seconds memory cache

/**
 * Applies the same ordering the API uses for `sort=quality` (see
 * apps/api/app/services/catalog.py `list_product_cards`): data quality score,
 * then trusted offer count, then source count, then lowest price ascending.
 * Without this the snapshot path would fall back to the exporter's Product.id
 * order and disagree with the API fallback for the same request.
 */
export function sortByQuality(cards: ProductCard[]): ProductCard[] {
  const priceOf = (card: ProductCard): number => {
    const value =
      card.lowest_price !== null && card.lowest_price !== undefined
        ? Number(card.lowest_price)
        : Number.NaN;
    return Number.isFinite(value) ? value : Number.POSITIVE_INFINITY;
  };

  return [...cards].sort((a, b) => {
    if (b.data_quality_score !== a.data_quality_score) {
      return b.data_quality_score - a.data_quality_score;
    }
    if (b.trusted_offer_count !== a.trusted_offer_count) {
      return b.trusted_offer_count - a.trusted_offer_count;
    }
    if (b.source_count !== a.source_count) {
      return b.source_count - a.source_count;
    }
    return priceOf(a) - priceOf(b);
  });
}

async function loadLatestSnapshot(): Promise<any | null> {
  const now = Date.now();
  if (memoryCache && now - memoryCache.cachedAt < CACHE_TTL_MS) {
    return memoryCache.data;
  }

  const base =
    process.env.INTERNAL_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "https://ai.pricememo.cn";

  try {
    const latestRes = await fetch(`${base}/data/latest.json`, {
      next: { revalidate: 30 },
    });
    if (!latestRes.ok) return null;
    const latest = await latestRes.json();
    if (!latest || !latest.snapshot_id) return null;

    const snapRes = await fetch(`${base}/data/v1/snapshots/${latest.snapshot_id}.json`, {
      next: { revalidate: 300 },
    });
    if (!snapRes.ok) return null;
    const snapshot = await snapRes.json();
    memoryCache = { data: snapshot, cachedAt: now };
    return snapshot;
  } catch {
    return null;
  }
}


/**
 * Returns full CatalogResponse directly from the immutable snapshot.
 * Bypasses FastAPI and PostgreSQL queries completely.
 */
export async function getSnapshotCatalog(): Promise<CatalogResponse | null> {
  try {
    const snapshot = await loadLatestSnapshot();
    if (!snapshot || !Array.isArray(snapshot.products)) return null;

    const items: ProductCard[] = snapshot.products.map((p: any) => ({
      slug: p.slug,
      platform: p.platform,
      brand: p.brand || p.platform,
      display_name: p.display_name,
      subtitle: p.subtitle || "",
      product_type: p.product_type || "other",
      price_currency: p.price_currency || "CNY",
      lowest_price: p.lowest_price || (p.min_price !== null && p.min_price !== undefined ? String(p.min_price) : null),
      related_lowest_price: p.related_lowest_price || null,
      offer_count: p.offer_count || 0,
      in_stock_count: p.in_stock_count || 0,
      comparable_offer_count: p.comparable_offer_count || 0,
      trusted_offer_count: p.trusted_offer_count || 0,
      median_price: p.median_price || null,
      source_count: p.source_count || 0,
      data_quality_score: p.data_quality_score || 0,
      data_quality_label: p.data_quality_label || "数据不足",
      official_reference: p.official_reference || null,
      last_updated_at: p.last_updated_at || snapshot.published_at || null,
      tags: Array.isArray(p.tags) ? p.tags : [],
    }));

    return {
      items: sortByQuality(items),
      total: snapshot.total || items.length,
      offer_count: snapshot.offer_count || 0,
      in_stock_count: snapshot.in_stock_count || 0,
      comparable_offer_count: snapshot.comparable_offer_count || 0,
      trusted_offer_count: snapshot.trusted_offer_count || 0,
      metrics_note: snapshot.metrics_note || "",
      snapshot_id: Number(snapshot.snapshot_id) || null,
      snapshot_at: snapshot.published_at || null,
    };
  } catch {
    return null;
  }
}
