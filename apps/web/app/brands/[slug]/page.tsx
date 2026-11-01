import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ProductCatalogPage } from "@/components/product-catalog-page";
import { getProducts } from "@/lib/api";
import { brandCatalogPath, brandFromSlug } from "@/lib/catalog";
import { getBrandSeoContent } from "@/lib/brand-seo";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-dynamic";
type Props = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const [{ slug }, filters] = await Promise.all([params, searchParams]);
  const brand = brandFromSlug(slug);
  if (!brand) return { title: "品牌不存在", robots: { index: false, follow: true } };
  const { title, description } = getBrandSeoContent(brand);
  const canonical = `${SITE_URL}${brandCatalogPath(brand)}`;
  const catalog = await getProducts(new URLSearchParams({ brand, limit: "100" }).toString());
  return {
    title, description,
    alternates: { canonical },
    robots: { index: catalog.offer_count > 0 && Object.keys(filters).length === 0, follow: true },
    openGraph: { title, description, url: canonical, type: "website" },
    twitter: { card: "summary_large_image", title, description },
  };
}

export default async function BrandPage({ params, searchParams }: Props) {
  const [{ slug }, filters] = await Promise.all([params, searchParams]);
  const brand = brandFromSlug(slug);
  if (!brand) notFound();
  return <ProductCatalogPage rawParams={filters} catalogBrand={brand} />;
}
