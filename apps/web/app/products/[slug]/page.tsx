import type { Metadata } from "next";
import { ProductCatalogPage } from "@/components/product-catalog-page";
import { getProduct } from "@/lib/api";
import { getProductSeoContent } from "@/lib/product-seo";

export const dynamic = "force-dynamic";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export async function generateMetadata({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: SearchParams }): Promise<Metadata> {
  const [{ slug }, rawParams] = await Promise.all([params, searchParams]);
  const product = await getProduct(slug, "comparable=true");
  if (!product) return { title: "产品不存在", robots: { index: false, follow: true } };
  const seo = getProductSeoContent(product.slug, product.display_name, product.description);
  const canonical = `https://ai.pricememo.cn/products/${encodeURIComponent(product.slug)}`;
  const indexable = product.offer_count > 0 && Object.keys(rawParams).length === 0;
  return {
    title: `${product.display_name}价格对比`,
    description: seo.metaDescription,
    alternates: { canonical },
    robots: { index: indexable, follow: true },
    openGraph: {
      title: `${product.display_name}价格对比`,
      description: seo.metaDescription,
      url: canonical,
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: `${product.display_name}价格对比`,
      description: seo.metaDescription,
    },
  };
}

export default async function ProductPage({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: SearchParams }) {
  const [{ slug }, rawParams] = await Promise.all([params, searchParams]);
  return <ProductCatalogPage rawParams={rawParams} productSlug={slug} />;
}
