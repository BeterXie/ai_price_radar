import { STANDALONE_PRODUCTS } from "@/lib/catalog";

export function standaloneProduct(slug: string) {
  return STANDALONE_PRODUCTS.find((product) => product.slug === slug);
}

export function productDisplayName(slug: string, name: string) {
  return standaloneProduct(slug)?.label || name;
}

/** Immutable snapshots may retain the old brand after product metadata changes. */
export function normalizeProductIdentity<T extends { slug: string; display_name: string; brand: string; platform: string }>(product: T): T {
  const standalone = standaloneProduct(product.slug);
  return standalone ? { ...product, display_name: standalone.label, brand: standalone.label, platform: standalone.label } : product;
}
