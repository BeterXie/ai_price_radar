import type { OfferGroup, OfferGroupPage } from "./types";

export const OFFER_BATCH_SIZE = 30;
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "";
const key = (group: OfferGroup) => `${group.product_slug}:${group.fingerprint}`;

export type GroupList = { items: OfferGroup[]; total: number; snapshotId: number | null; refreshed: boolean };

export async function loadMoreGroups(current: GroupList, endpoint: string, filterQuery: string, signal: AbortSignal): Promise<GroupList> {
  const load = async (offset: number, snapshotId: number | null) => {
    const query = new URLSearchParams(filterQuery);
    query.delete("snapshot");
    query.set("offset", String(offset));
    query.set("limit", String(OFFER_BATCH_SIZE));
    if (snapshotId) query.set("snapshot", String(snapshotId));
    const response = await fetch(`${apiBase}${endpoint}?${query}`, { signal, cache: "no-store" });
    if (!response.ok) throw new Error(`API ${response.status}`);
    const page = await response.json() as OfferGroupPage;
    if (!Array.isArray(page.items) || !Number.isInteger(page.total) || page.total < 0 || (page.snapshot_id !== null && !Number.isInteger(page.snapshot_id))) throw new Error("Invalid group page");
    return page;
  };
  let page: OfferGroupPage | undefined;
  try {
    page = await load(current.items.length, current.snapshotId);
  } catch (error) {
    // Only an expired snapshot is recoverable here. Network failures use retry.
    if (signal.aborted || !(error instanceof Error) || error.message !== "API 404" || !current.snapshotId) throw error;
  }
  const seen = new Set(current.items.map(key));
  const additions = page?.items.filter((group) => {
    if (seen.has(key(group))) return false;
    seen.add(key(group));
    return true;
  }) || [];
  if (page && page.snapshot_id === current.snapshotId && additions.length) {
    return { ...current, items: [...current.items, ...additions], total: page.total };
  }
  // Refresh from offset zero: old and new snapshots must never be spliced together.
  const latest = await load(0, null);
  if (!latest.items.length && latest.total > 0) throw new Error("No new groups returned");
  if (latest.snapshot_id === current.snapshotId && latest.total > current.items.length && !additions.length) {
    throw new Error("No new groups returned");
  }
  return { items: latest.items, total: latest.total, snapshotId: latest.snapshot_id, refreshed: true };
}
