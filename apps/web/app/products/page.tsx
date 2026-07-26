import type { Metadata } from "next";
import { permanentRedirect } from "next/navigation";
import { ProductCatalogPage } from "@/components/product-catalog-page";
import { getProduct } from "@/lib/api";
import { getProductSeoContent } from "@/lib/product-seo";

export const dynamic = "force-dynamic";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function lastValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value.at(-1) || "" : value || "";
}

export async function generateMetadata({ searchParams }: { searchParams: SearchParams }): Promise<Metadata> {
  const params = await searchParams;
  const slug = lastValue(params.product);
  if (slug) {
    const product = await getProduct(slug, "comparable=true");
    if (!product) return { title: "产品不存在", robots: { index: false, follow: true } };
    const seo = getProductSeoContent(product.slug, product.display_name, product.description);
    const canonical = `https://ai.pricememo.cn/products/${encodeURIComponent(product.slug)}`;
    return {
      title: `${product.display_name}价格对比`,
      description: seo.metaDescription,
      alternates: { canonical },
      robots: { index: false, follow: true },
      openGraph: { title: `${product.display_name}价格对比`, description: seo.metaDescription, url: canonical, type: "website" },
    };
  }
  return {
    title: "全部 AI 商品报价",
    description: "浏览 ChatGPT、Claude、Gemini、Grok 与 X Premium 公开报价，比较库存、交付方式、更新时间和来源。",
    alternates: { canonical: "https://ai.pricememo.cn/products" },
    robots: Object.keys(params).length ? { index: false, follow: true } : { index: true, follow: true },
    openGraph: {
      title: "全部 AI 商品报价",
      description: "浏览主流 AI 账号、订阅、充值与 API 服务的公开报价和库存。",
      url: "https://ai.pricememo.cn/products",
      type: "website",
    },
  };
}

export default async function ProductsPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const slug = lastValue(params.product);
  if (slug) {
    const query = new URLSearchParams();
    for (const [key, rawValue] of Object.entries(params)) {
      if (["platform", "product"].includes(key)) continue;
      const value = lastValue(rawValue);
      if (value) query.set(key, value);
    }
    const suffix = query.toString();
    permanentRedirect(`/products/${encodeURIComponent(slug)}${suffix ? `?${suffix}` : ""}`);
  }
  return <ProductCatalogPage rawParams={params} />;
}
