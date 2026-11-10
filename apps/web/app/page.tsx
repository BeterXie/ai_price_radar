import type { Metadata } from "next";
import { Suspense } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "@phosphor-icons/react/ssr";
import { SponsorShowcase } from "@/components/sponsor-showcase";
import { SearchBox } from "@/components/search-box";
import { ProductCard } from "@/components/product-card";
import { PlatformIcon } from "@/components/platform-icon";
import { getProducts } from "@/lib/api";
import { productDisplayName } from "@/lib/product-identity";
import { BRAND_TABS, brandCatalogPath, STANDALONE_PRODUCTS } from "@/lib/catalog";
import { exactTime, relativeTime } from "@/lib/format";
import { SITE_URL } from "@/lib/site";
import { BRAND, IS_PRIMARY_SITE } from "@/lib/brands";
import { BrandHome } from "@/components/brand-home";

export const dynamic = "force-dynamic";
const homeTitle = IS_PRIMARY_SITE ? "AI 订阅比价｜ChatGPT、Claude、Gemini 价格对比" : BRAND.name + "｜" + BRAND.tagline;

export const metadata: Metadata = {
  title: homeTitle,
  description: "汇总 ChatGPT、Claude、Gemini、Grok 等 AI 产品的公开报价，比较价格、库存、交付方式和更新时间。",
  alternates: { canonical: SITE_URL },
  openGraph: {
    title: homeTitle,
    description: "汇总主流 AI 产品的公开报价，比较价格、库存、交付方式和更新时间。",
    url: SITE_URL,
    siteName: BRAND.name,
    locale: "zh_CN",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: homeTitle,
    description: "查看主流 AI 产品的公开价格、库存、交付方式和更新时间。",
  },
};

export default async function HomePage() {
  const data = await getProducts("sort=quality");
  if (!IS_PRIMARY_SITE) return <BrandHome data={data} />;
  const products = data.items.slice(0, 6);

  return (
    <main id="main-content" className="home-page">
      <section className="home-search-stage shell" aria-labelledby="home-title">
        <h1 id="home-title">AI 订阅比价</h1>
        <div className="home-search"><SearchBox /></div>
        <p className="home-snapshot">
          <span><strong>{data.offer_count.toLocaleString("zh-CN")}</strong> 条报价</span>
          <span><strong>{data.in_stock_count.toLocaleString("zh-CN")}</strong> 条有货</span>
          <time dateTime={data.snapshot_at || undefined} title={exactTime(data.snapshot_at)}>
            {data.snapshot_at ? `${relativeTime(data.snapshot_at)}更新` : "暂无更新时间"}
          </time>
        </p>
      </section>

      <nav className="home-brands shell" aria-label="按品牌或商品查看报价">
        {BRAND_TABS.map((brand) => (
          <Link key={brand} href={brandCatalogPath(brand)}>
            <PlatformIcon platform={brand} size={26} />
            <span>{brand}</span>
          </Link>
        ))}
        {STANDALONE_PRODUCTS.map((product) => (
          <Link key={product.slug} href={`/products/${product.slug}`} className="home-service-link">
            <PlatformIcon platform={product.label} size={26} />
            <span>{product.label}</span>
          </Link>
        ))}
      </nav>

      <section className="home-quotes shell" aria-labelledby="home-quotes-title">
        <div className="home-section-heading">
          <h2 id="home-quotes-title">当前报价</h2>
          <Link href="/products" className="text-action">全部报价 <ArrowRight size={18} aria-hidden="true" /></Link>
        </div>
        {products.length ? (
          <div className="home-product-list">
            <div className="home-product-columns" aria-hidden="true">
              <span>商品</span><span>有货报价</span><span>更新</span><span>有货观测价</span><span />
            </div>
            {products.map((product) => <ProductCard key={product.slug} product={{ ...product, display_name: productDisplayName(product.slug, product.display_name) }} />)}
          </div>
        ) : (
          <div className="empty-state">
            <p>暂无公开报价</p>
            <Link href="/products" className="button-secondary mt-5">查看报价目录</Link>
          </div>
        )}
      </section>

      <Suspense fallback={null}>
        <SponsorShowcase />
      </Suspense>

      <nav className="home-resources shell" aria-label="更多工具与指南">
        {[
          { href: "/compare", title: "AI 模型与订阅对比" },
          { href: "/skills", title: "技能与实验室" },
          { href: "/skills/pelican-bicycle-benchmark", title: "模型评测" },
          { href: "/guides/buying-checklist", title: "购买前检查" },
          { href: "/methodology", title: "数据方法" },
        ].map(({ href, title }) => (
          <Link href={href} key={href}><span>{title}</span><ArrowUpRight size={18} aria-hidden="true" /></Link>
        ))}
      </nav>
    </main>
  );
}
