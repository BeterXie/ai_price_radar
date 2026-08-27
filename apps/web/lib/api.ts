import type { CatalogOfferGroupPage, CatalogResponse, Meta, ProductDetail, PublicCorrectionPage, ShopCard, ShopDetail, ShopListResponse } from "@/lib/types";

const internalBase = process.env.INTERNAL_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${internalBase}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${path}`);
  }
  return response.json() as Promise<T>;
}

export async function getProducts(query = ""): Promise<CatalogResponse> {
  return apiFetch(`/api/v1/products${query ? `?${query}` : ""}`);
}

export async function getCatalogGroups(query = ""): Promise<CatalogOfferGroupPage> {
  return apiFetch(`/api/v1/catalog/groups${query ? `?${query}` : ""}`);
}

export async function getProduct(slug: string, query = ""): Promise<ProductDetail | null> {
  try {
    return await apiFetch(`/api/v1/products/${encodeURIComponent(slug)}${query ? `?${query}` : ""}`);
  } catch {
    return null;
  }
}

export async function getShop(token: string): Promise<ShopDetail | null> {
  try {
    return await apiFetch(`/api/v1/shops/${encodeURIComponent(token)}`);
  } catch {
    return null;
  }
}

/** Returns a flat list of shop tokens for callers that only need identifiers. */
export async function getShopTokens(): Promise<string[]> {
  try {
    return await apiFetch<string[]>("/api/v1/shops/tokens");
  } catch {
    return [];
  }
}

/** Returns paginated ShopCard list for directory / source pages. */
export async function getShopCards(query = ""): Promise<ShopListResponse> {
  try {
    return await apiFetch<ShopListResponse>(`/api/v1/shops${query ? `?${query}` : ""}`);
  } catch {
    return { items: [], total: 0 };
  }
}

export async function getMeta(): Promise<Meta> {
  return apiFetch("/api/v1/meta");
}

export async function getCorrections(query = ""): Promise<PublicCorrectionPage> {
  return apiFetch(`/api/v1/corrections${query ? `?${query}` : ""}`);
}
