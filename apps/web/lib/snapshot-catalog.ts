import { promises as fs } from "node:fs";
import path from "node:path";
import type { CatalogResponse, ProductCard } from "@/lib/types";

const CHECK_INTERVAL_MS = 30_000;
const STALE_GRACE_MS = 5 * 60_000;
const MAX_CATALOG_BYTES = 512 * 1024;

let current: CatalogResponse | null = null;
let currentDirectory = "";
let nextCheckAt = 0;
let confirmedAt = 0;
let loading: Promise<CatalogResponse | null> | null = null;

/** Same quality ordering as the API, including unknown prices sorting last. */
export function sortByQuality(cards: ProductCard[]): ProductCard[] {
  const priceOf = (card: ProductCard): number => {
    const value = card.lowest_price == null ? Number.NaN : Number(card.lowest_price);
    return Number.isFinite(value) ? value : Number.POSITIVE_INFINITY;
  };
  return [...cards].sort((a, b) =>
    b.data_quality_score - a.data_quality_score ||
    b.trusted_offer_count - a.trusted_offer_count ||
    b.source_count - a.source_count ||
    priceOf(a) - priceOf(b)
  );
}

async function readSmallJson(filename: string, maxBytes: number): Promise<unknown> {
  if ((await fs.stat(filename)).size > maxBytes) throw new Error("Catalog file exceeds size limit");
  const bytes = await fs.readFile(filename);
  if (bytes.length > maxBytes) throw new Error("Catalog file exceeds size limit");
  return JSON.parse(bytes.toString("utf8"));
}

function parseCatalog(value: unknown, id: number): CatalogResponse {
  const data = value as CatalogResponse & { schema_version?: string };
  if (!data || data.schema_version !== "price-radar.catalog.v1" ||
      data.snapshot_id !== id || !Array.isArray(data.items) ||
      data.total !== data.items.length || !data.snapshot_at ||
      !Number.isFinite(Date.parse(data.snapshot_at)) ||
      data.items.some((item) => !item || typeof item.slug !== "string" ||
        typeof item.display_name !== "string" || "offers" in item || "top_5_offers" in item)) {
    throw new Error("Invalid catalog summary");
  }
  return { ...data, items: sortByQuality(data.items) };
}

async function refresh(directory: string): Promise<CatalogResponse | null> {
  try {
    const pointer = await readSmallJson(path.join(directory, "latest.json"), 64 * 1024) as { snapshot_id?: unknown };
    const rawId = String(pointer?.snapshot_id ?? "");
    const id = Number(rawId);
    if (!/^[0-9]+$/.test(rawId) || !Number.isSafeInteger(id) || id <= 0) {
      throw new Error("Invalid snapshot ID");
    }
    if (current?.snapshot_id !== id) {
      const data = await readSmallJson(path.join(directory, "v1", "catalogs", rawId + ".json"), MAX_CATALOG_BYTES);
      current = parseCatalog(data, id);
    }
    confirmedAt = Date.now();
    return current;
  } catch {
    // Keep the last good catalog briefly. The caller uses the normal API after
    // the grace period, rather than serving stale prices indefinitely.
    return current && Date.now() - confirmedAt <= STALE_GRACE_MS ? current : null;
  } finally {
    nextCheckAt = Date.now() + CHECK_INTERVAL_MS;
  }
}

/** Read shared card summaries without an API call or full-snapshot fetch. */
export async function getSnapshotCatalog(): Promise<CatalogResponse | null> {
  const directory = process.env.PUBLIC_DATA_DIR || path.join(process.cwd(), "public", "data");
  if (directory !== currentDirectory) {
    currentDirectory = directory;
    current = null;
    nextCheckAt = confirmedAt = 0;
  }
  if (loading) return loading;
  if (Date.now() < nextCheckAt) {
    return current && Date.now() - confirmedAt <= STALE_GRACE_MS ? current : null;
  }
  loading = refresh(directory);
  try {
    return await loading;
  } finally {
    loading = null;
  }
}
