import type { Metadata } from "next";
import { SITE_URL } from "@/lib/site";
import { permanentRedirect } from "next/navigation";
import { canonicalProductSlug } from "@/lib/catalog";
import { ProductCatalogPage } from "@/components/product-catalog-page";
import { getProduct } from "@/lib/api";
import { getProductSeoContent } from "@/lib/product-seo";

export const revalidate = 30;

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export async function generateMetadata({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: SearchParams }): Promise<Metadata> {
  const [{ slug }, rawParams] = await Promise.all([params, searchParams]);
  const product = await getProduct(slug, "comparable=true");
  if (!product) return { title: "产品不存在", robots: { index: false, follow: true } };
  const seo = getProductSeoContent(product.slug, product.display_name, product.description);
  const canonical = `${SITE_URL}/products/${encodeURIComponent(product.slug)}`;
  const indexable = product.offer_count > 0 && Object.keys(rawParams).length === 0;
  return {
    title: `${product.display_name} 比价｜价格、库存与店铺`,
    description: seo.metaDescription,
    alternates: { canonical },
    robots: { index: indexable, follow: true },
    openGraph: {
      title: `${product.display_name} 比价｜价格、库存与店铺`,
      description: seo.metaDescription,
      url: canonical,
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: `${product.display_name} 比价｜价格、库存与店铺`,
      description: seo.metaDescription,
    },
  };
}

export default async function ProductPage({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: SearchParams }) {
  const [{ slug }, rawParams] = await Promise.all([params, searchParams]);
  const canonicalSlug = canonicalProductSlug(slug);
  if (canonicalSlug !== slug) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(rawParams)) {
      for (const entry of Array.isArray(value) ? value : value === undefined ? [] : [value]) query.append(key, entry);
    }
    const suffix = query.toString();
    permanentRedirect(`/products/${encodeURIComponent(canonicalSlug)}${suffix ? `?${suffix}` : ""}`);
  }
  return <ProductCatalogPage rawParams={rawParams} productSlug={canonicalSlug} />;
}
