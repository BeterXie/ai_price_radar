import { ALL_PRODUCTS, DELIVERY_TYPE_LABELS, PERIOD_LABELS } from "./catalog";
import type { Offer } from "./types";

export function quoteBrand(slug: string): string {
  return ALL_PRODUCTS.find((product) => product.slug === slug)?.brand || "其他商品";
}

export function quoteCategory(offer: Offer): string {
  const delivery = offer.delivery_type === "session_token" ? "账号凭据" : DELIVERY_TYPE_LABELS[offer.delivery_type] || "其他商品";
  return `${delivery} · ${PERIOD_LABELS[offer.service_period] || "期限未注明"}`;
}

/** Keep zero stock distinct from missing inventory and never use a group's stock as a seller's. */
export function quoteInventory(offer: Offer): string {
  if (offer.stock_status === "out_of_stock") return "缺货";
  if (offer.stock_status === "in_stock") return offer.stock_count === null ? "有货 · 数量未提供" : `有货 · ${offer.stock_count}`;
  return offer.stock_count === null ? "库存未知" : `库存 ${offer.stock_count} · 状态待确认`;
}

export function quoteProductHref(slug: string, filterQuery: string): string {
  const query = new URLSearchParams(filterQuery);
  for (const key of ["brand", "platform", "product", "offset", "limit", "snapshot"]) query.delete(key);
  if (query.get("comparable") === "true") query.delete("comparable");
  else if (!query.has("comparable")) query.set("comparable", "false");
  return `/products/${encodeURIComponent(slug)}${query.size ? `?${query}` : ""}`;
}
