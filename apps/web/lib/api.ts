import type { CatalogResponse, Meta, ProductDetail, ShopDetail } from "@/lib/types";

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

export async function getMeta(): Promise<Meta> {
  return apiFetch("/api/v1/meta");
}
