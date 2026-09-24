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
import { getSnapshotCatalog } from "@/lib/snapshot-catalog";

// Keep the final fallback identical to next.config.ts and snapshot-catalog.ts:
// local development assumes the API runs on the host at 127.0.0.1:8000.
const internalBase = process.env.INTERNAL_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly path: string) {
    super(`API ${status}: ${path}`);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(path: string, retries = 2, init?: RequestInit): Promise<T> {
  let attempt = 0;
  const options: RequestInit = {
    ...(init?.next ? {} : { cache: "no-store" }),
    ...init,
  };
  while (true) {
    try {
      const response = await fetch(`${internalBase}${path}`, {
        ...options,
        signal: options.signal || AbortSignal.timeout(6000),
      });
      if (!response.ok) {
        const retryable = response.status === 429 || response.status >= 500;
        if (retryable && attempt < retries) {
          attempt += 1;
          const retryAfter = Number(response.headers.get("retry-after"));
          const delayMs = Number.isFinite(retryAfter) && retryAfter > 0
            ? Math.min(retryAfter * 1000, 5000)
            : 100 * attempt;
          await new Promise((resolve) => setTimeout(resolve, delayMs));
          continue;
        }
        throw new ApiError(response.status, path);
      }
      return (await response.json()) as T;
    } catch (error) {
      if (error instanceof ApiError || attempt >= retries) {
        throw error;
      }
      attempt += 1;
      await new Promise((resolve) => setTimeout(resolve, 100 * attempt));
    }
  }
}

export async function getProducts(query = ""): Promise<CatalogResponse> {
  const clean = query.trim();
  if (!clean || clean === "sort=quality") {
    // getSnapshotCatalog applies the same quality ordering as the API path,
    // so the two branches return consistent ordering for the same request.
    const snapshotData = await getSnapshotCatalog().catch(() => null);
    if (snapshotData && snapshotData.items.length > 0) {
      return snapshotData;
    }
  }
  return apiFetch(`/api/v1/products${query ? `?${query}` : ""}`, 2, { next: { revalidate: 30 } });
}

export async function getCatalogGroups(query = ""): Promise<CatalogOfferGroupPage> {
  return apiFetch(`/api/v1/catalog/groups${query ? `?${query}` : ""}`, 2, { next: { revalidate: 30 } });
}

export const getProduct = cache(async function getProduct(slug: string, query = ""): Promise<ProductDetail | null> {
  try {
    return await apiFetch(`/api/v1/products/${encodeURIComponent(slug)}${query ? `?${query}` : ""}`, 2, {
      next: { revalidate: 30 },
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
});

export async function getShop(token: string, query = ""): Promise<ShopDetail | null> {
  try {
    return await apiFetch(`/api/v1/shops/${encodeURIComponent(token)}${query ? `?${query}` : ""}`, 2, { next: { revalidate: 60 } });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

/** Returns a flat list of shop tokens for callers that only need identifiers. */
export async function getShopTokens(): Promise<string[]> {
  return apiFetch<string[]>("/api/v1/shops", 2, { next: { revalidate: 120 } });
}

/** Returns paginated ShopCard list for directory / source pages. */
export async function getShopCards(query = ""): Promise<ShopListResponse> {
  return apiFetch<ShopListResponse>(`/api/v1/shops/cards${query ? `?${query}` : ""}`, 2, { next: { revalidate: 60 } });
}

export const getMeta = cache(async function getMeta(): Promise<Meta> {
  return apiFetch("/api/v1/meta", 0, {
    next: { revalidate: 300 },
    signal: AbortSignal.timeout(1200),
  });
});

/** Live ad slots for a placement. Never throws: a failed ad read must not break a page. */
export async function getAdSlots(placement: string, limit = 3): Promise<AdSlotListOut> {
  try {
    return await apiFetch<AdSlotListOut>(
      `/api/v1/ads?placement=${encodeURIComponent(placement)}&limit=${limit}`,
      0,
      { next: { revalidate: 60 }, signal: AbortSignal.timeout(1500) },
    );
  } catch {
    return { items: [], enabled: false };
  }
}

export async function getRelayStations(): Promise<RelayStationListOut> {
  return apiFetch<RelayStationListOut>("/api/v1/relays", 2, { next: { revalidate: 60 } });
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

export async function recordSkillCopy(slug: string): Promise<boolean> {
  try {
    const response = await fetch(`/api/v1/skills/${encodeURIComponent(slug)}/copy`, {
      method: "POST",
    });
    return response.ok;
  } catch {
    return false;
  }
}
