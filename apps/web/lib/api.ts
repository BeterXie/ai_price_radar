import type { CatalogOfferGroupPage, CatalogResponse, Meta, ProductDetail, PublicCorrectionPage, ShopCard, ShopDetail, ShopListResponse } from "@/lib/types";

const internalBase = process.env.INTERNAL_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly path: string) {
    super(`API ${status}: ${path}`);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${internalBase}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new ApiError(response.status, path);
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
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function getShop(token: string): Promise<ShopDetail | null> {
  try {
    return await apiFetch(`/api/v1/shops/${encodeURIComponent(token)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

/** Returns a flat list of shop tokens for callers that only need identifiers. */
export async function getShopTokens(): Promise<string[]> {
  return apiFetch<string[]>("/api/v1/shops");
}

/** Returns paginated ShopCard list for directory / source pages. */
export async function getShopCards(query = ""): Promise<ShopListResponse> {
  return apiFetch<ShopListResponse>(`/api/v1/shops/cards${query ? `?${query}` : ""}`);
}

export async function getMeta(): Promise<Meta> {
  return apiFetch("/api/v1/meta");
}

export async function getCorrections(query = ""): Promise<PublicCorrectionPage> {
  return apiFetch(`/api/v1/corrections${query ? `?${query}` : ""}`);
}
