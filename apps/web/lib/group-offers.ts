import type { GroupOffers, Offer } from "./types";

const publicApiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export async function fetchGroupShopOffers(
  productSlug: string,
  fingerprint: string,
  filterQuery: string,
  snapshotId?: number | null,
): Promise<{ items: Offer[]; refreshed: boolean }> {
  const filters = new URLSearchParams(filterQuery);
  filters.delete("snapshot");
  const path = `/api/v1/products/${encodeURIComponent(productSlug)}/groups/${encodeURIComponent(fingerprint)}`;

  const load = async (snapshot?: number): Promise<Offer[]> => {
    const params = new URLSearchParams(filters);
    if (snapshot) params.set("snapshot", String(snapshot));
    const query = params.toString();
    const response = await fetch(`${publicApiBase}${path}${query ? `?${query}` : ""}`);
    if (!response.ok) throw new Error(`API ${response.status}`);
    const data = (await response.json()) as GroupOffers;
    return data.items || [];
  };

  if (snapshotId) {
    try {
      const items = await load(snapshotId);
      if (items.length > 0) return { items, refreshed: false };
    } catch {
      // Published snapshots can lose their offers when the next snapshot takes over.
    }
    return { items: await load(), refreshed: true };
  }

  return { items: await load(), refreshed: false };
}
