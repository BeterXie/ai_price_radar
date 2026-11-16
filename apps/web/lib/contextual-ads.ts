import { getAdSlots } from "./api";
import type { AdPlacement, ContextualAds } from "./types";

/** Brand targeting is resolved on the server, including product detail routes. */
export async function getContextualAds(brand: string, fallbackPlacement?: AdPlacement): Promise<ContextualAds> {
  if (brand !== "Claude" && brand !== "OpenAI") {
    return fallbackPlacement ? { feed: (await getAdSlots(fallbackPlacement, 1)).items[0] } : {};
  }
  const prefix = brand === "Claude" ? "claude" : "openai";
  const [feed, detail, fallback] = await Promise.all([
    getAdSlots(`${prefix}_feed`, 1),
    getAdSlots(`${prefix}_detail`, 1),
    fallbackPlacement ? getAdSlots(fallbackPlacement, 1) : Promise.resolve(null),
  ]);
  return { feed: feed.items[0] || fallback?.items[0], detail: detail.items[0] };
}
