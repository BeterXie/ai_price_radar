import { getAdSlots } from "./api";
import type { AdPlacement, AdSlotPublic, ContextualAds } from "./types";

const SIDRUNE_CLAUDE_TITLE = "Claude 多线路 0.25–4.5x";
const SIDRUNE_CLAUDE_DESCRIPTION = "Claude Code · 13 条自营线路 · 开票/对公 · 分组计费倍率，非官方折扣。";

function catalogSponsor(items: AdSlotPublic[], brand: string): AdSlotPublic | undefined {
  const isSidrune = (item: AdSlotPublic) => item.sponsor_name.trim().toLowerCase() === "sidrune ai";
  const item = items.find((candidate) => brand === "Claude" || !isSidrune(candidate));
  if (!item || !isSidrune(item)) return item;
  return {
    ...item,
    title: item.title === "Claude API / Claude Code" ? SIDRUNE_CLAUDE_TITLE : item.title,
    description: item.description || SIDRUNE_CLAUDE_DESCRIPTION,
    image_url: item.image_url || "/sponsors/sidrune.svg",
  };
}

/** Brand targeting is resolved on the server, including product detail routes. */
export async function getContextualAds(brand: string, fallbackPlacement?: AdPlacement): Promise<ContextualAds> {
  if (brand === "Claude" || brand === "OpenAI") {
    const prefix = brand === "Claude" ? "claude" : "openai";
    const [feed, detail, fallback] = await Promise.all([
      getAdSlots(`${prefix}_feed`, 1),
      getAdSlots(`${prefix}_detail`, 1),
      fallbackPlacement ? getAdSlots(fallbackPlacement, 6) : Promise.resolve(null),
    ]);
    const feedItem = catalogSponsor(feed.items, brand) || catalogSponsor(fallback?.items || [], brand);
    const detailItem = catalogSponsor(detail.items, brand);
    const toolbar = feedItem || detailItem;
    return { feed: feedItem, detail: detailItem, ...(fallbackPlacement ? { toolbar } : {}) };
  }
  if (!fallbackPlacement) return {};
  const item = catalogSponsor((await getAdSlots(fallbackPlacement, 6)).items, brand);
  return { feed: item, toolbar: item };
}
