import { getAdSlots } from "./api";
import type { ContextualAds } from "./types";

/** Brand targeting is resolved on the server, including product detail routes. */
export async function getContextualAds(brand: string): Promise<ContextualAds> {
  if (brand !== "Claude" && brand !== "OpenAI") return {};
  const prefix = brand === "Claude" ? "claude" : "openai";
  const [feed, detail] = await Promise.all([
    getAdSlots(`${prefix}_feed`, 1),
    getAdSlots(`${prefix}_detail`, 1),
  ]);
  return { feed: feed.items[0], detail: detail.items[0] };
}
