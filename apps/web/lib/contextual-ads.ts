import { getAdSlots } from "./api";
import type { ContextualAds } from "./types";

/** Brand targeting is resolved on the server, including product detail routes. */
export async function getContextualAds(brand: string): Promise<ContextualAds> {
  if (brand !== "Claude") return {};
  const [feed, detail] = await Promise.all([
    getAdSlots("claude_feed", 1),
    getAdSlots("claude_detail", 1),
  ]);
  return { feed: feed.items[0], detail: detail.items[0] };
}
