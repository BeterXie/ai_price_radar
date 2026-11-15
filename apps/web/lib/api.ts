import type {
  AdSlotListOut,
  CatalogOfferGroupPage,
  CatalogResponse,
  CommunitySkillDetail,
  CommunitySkillPage,
  Meta,
  ProductDetail,
  PublicCorrectionPage,
  RelayStationListOut,
  ShopCard,
  ShopDetail,
  ShopListResponse,
} from "@/lib/types";


import { cache } from "react";
import { setTimeout as delay } from "node:timers/promises";
import { IS_PRIMARY_SITE, promoApiPath } from "@/lib/brands";
import { getSiteSettings } from "@/lib/site-content";
import { getSnapshotCatalog } from "@/lib/snapshot-catalog";
import { normalizeProductIdentity } from "@/lib/product-identity";
import { canonicalProductSlug } from "@/lib/catalog";

// Keep the final fallback identical to next.config.ts and snapshot-catalog.ts:
// local development assumes the API runs on the host at 127.0.0.1:8000.
const internalBase = process.env.INTERNAL_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly path: string) {
    super(`API ${status}: ${path}`);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, retries = 1, init?: RequestInit): Promise<T> {
  const deadline = AbortSignal.timeout(6000);
  const budget = init?.signal ? AbortSignal.any([deadline, init.signal]) : deadline;
  const options: RequestInit = {
    ...(init?.next ? {} : { cache: "no-store" }),
    ...init,
  };
  const safeToRetry = ["GET", "HEAD"].includes((options.method || "GET").toUpperCase());
  const maxRetries = safeToRetry ? Math.min(Math.max(retries, 0), 1) : 0;
  const expiresAt = Date.now() + 6000;
  for (let attempt = 0; ; attempt += 1) {
    budget.throwIfAborted();
    let delayMs = 100;
    try {
      const response = await fetch(internalBase + path, {
        ...options,
        // A cold query can exceed three seconds while remaining within budget.
        // Aborting it early and retrying repeats database work already in flight.
        signal: budget,
      });
      if (response.ok) return (await response.json()) as T;
      const retryAfter = Number(response.headers?.get("retry-after"));
      if (Number.isFinite(retryAfter) && retryAfter > 0) delayMs = retryAfter * 1000;
      await response.body?.cancel();
      if (!(response.status === 429 || response.status >= 500) ||
          attempt >= maxRetries || delayMs >= expiresAt - Date.now()) {
        throw new ApiError(response.status, path);
      }
    } catch (error) {
      if (error instanceof ApiError || attempt >= maxRetries || budget.aborted) throw error;
    }
    await delay(delayMs, undefined, { signal: budget });
  }
}

export async function getProducts(query = ""): Promise<CatalogResponse> {
  const params = new URLSearchParams(query);
  if (params.has("products")) {
    const slugs = params.getAll("products").flatMap((value) => value.split(",").map((slug) => canonicalProductSlug(slug.trim())));
    params.set("products", [...new Set(slugs)].join(","));
    query = params.toString();
  }
  const clean = query.trim();
  if (!clean || clean === "sort=quality") {
    // Old immutable snapshots still contain separate Pro 5x/20x categories.
    // Use the live catalog until a canonical snapshot is published.
    const snapshotData = await getSnapshotCatalog().catch(() => null);
    if (snapshotData && snapshotData.items.length > 0 && snapshotData.items.every((item) => canonicalProductSlug(item.slug) === item.slug)) {
      return { ...snapshotData, items: snapshotData.items.map(normalizeProductIdentity) };
    }
  }
  const data = await apiFetch<CatalogResponse>(`/api/v1/products${query ? `?${query}` : ""}`, 1, { next: { revalidate: 30 } });
  return { ...data, items: data.items.map(normalizeProductIdentity) };
}

export async function getCatalogGroups(query = ""): Promise<CatalogOfferGroupPage> {
  return apiFetch(`/api/v1/catalog/groups${query ? `?${query}` : ""}`, 1, { next: { revalidate: 30 } });
}

export const getProduct = cache(async function getProduct(slug: string, query = ""): Promise<ProductDetail | null> {
  try {
    const product = await apiFetch<ProductDetail>(`/api/v1/products/${encodeURIComponent(canonicalProductSlug(slug))}${query ? `?${query}` : ""}`, 1, {
      next: { revalidate: 30 },
    });
    return normalizeProductIdentity(product);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
});

export async function getShop(token: string, query = ""): Promise<ShopDetail | null> {
  // Page params can retain URL escapes while metadata receives the decoded token.
  try {
    token = decodeURIComponent(token);
  } catch {
    return null;
  }
  try {
    return await apiFetch(`/api/v1/shops/${encodeURIComponent(token)}${query ? `?${query}` : ""}`, 1, { next: { revalidate: 60 } });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

/** Returns a flat list of shop tokens for callers that only need identifiers. */
export async function getShopTokens(): Promise<string[]> {
  return apiFetch<string[]>("/api/v1/shops", 1, { next: { revalidate: 120 } });
}

/** Returns paginated ShopCard list for directory / source pages. */
export async function getShopCards(query = ""): Promise<ShopListResponse> {
  return apiFetch<ShopListResponse>(`/api/v1/shops/cards${query ? `?${query}` : ""}`, 1, { next: { revalidate: 60 } });
}

export const getMeta = cache(async function getMeta(): Promise<Meta> {
  // Metadata is required by pages and the sitemap. Use the shared bounded
  // read budget so cold database/cache reads can finish during a release.
  const meta = await apiFetch<Meta>("/api/v1/meta", 1, {
    next: { revalidate: 300 },
  });
  if (IS_PRIMARY_SITE) return meta;
  const settings = await getSiteSettings();
  return { ...meta, advertise_enabled: settings.advertise_enabled, relay_hub_enabled: settings.relay_hub_enabled,
    site_notice: { enabled: Boolean(settings.notice_title), badge: "公告", title: settings.notice_title, content: settings.notice_content, link_text: settings.notice_link ? "查看详情" : "", link_url: settings.notice_link },
    community_notice: { title: "", desc: "", qq_group: "", btn_text: "", ...meta.community_notice, enabled: false },
  };
});

/** Live ad slots for a placement. Never throws: a failed ad read must not break a page. */
export async function getAdSlots(placement: string, limit = 3): Promise<AdSlotListOut> {
  try {
    return await apiFetch<AdSlotListOut>(
      promoApiPath(`/ads?placement=${encodeURIComponent(placement)}&limit=${limit}`),
      0,
      { next: { revalidate: 60 }, signal: AbortSignal.timeout(1500) },
    );
  } catch {
    return { items: [], enabled: false };
  }
}

export async function getRelayStations(): Promise<RelayStationListOut> {
  return apiFetch<RelayStationListOut>(promoApiPath("/relays"), 1, { cache: "no-store" });
}

export async function getCorrections(query = ""): Promise<PublicCorrectionPage> {
  return apiFetch(`/api/v1/corrections${query ? `?${query}` : ""}`);
}

export async function getSkills(query = ""): Promise<CommunitySkillPage | null> {
  try {
    return await apiFetch<CommunitySkillPage>(`/api/v1/skills${query ? `?${query}` : ""}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export const getSkillDetail = cache(async function getSkillDetail(slug: string): Promise<CommunitySkillDetail | null> {
  try {
    return await apiFetch<CommunitySkillDetail>(`/api/v1/skills/${encodeURIComponent(slug)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
});
