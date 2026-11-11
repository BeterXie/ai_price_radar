import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowUpRight } from "@phosphor-icons/react/ssr";
import { SITE_ID, IS_PRIMARY_SITE } from "@/lib/brands";
import type { ProductDetail } from "@/lib/types";
import { money, relativeTime } from "@/lib/format";
import { PlatformIcon } from "./platform-icon";

export function BrandCatalogFrame({ navigation, title, intro, children }: { navigation: ReactNode; title: string; intro: string; children: ReactNode }) {
  if (IS_PRIMARY_SITE) return <div className="catalog-layout"><aside className="catalog-sidebar">{navigation}</aside>{children}</div>;
  const heading = <header className="brand-catalog-heading"><p className="brand-eyebrow">{SITE_ID === "aiprice" ? "MARKET / QUOTES" : SITE_ID === "aisi" ? "订阅手册 / THE SELECTION" : SITE_ID === "pricein" ? "选订阅 · 比价格 · 看交付" : "01 / PRODUCT RECORDS"}</p><h1 id="catalog-page-title">{title}</h1><p>{intro}</p></header>;
  if (SITE_ID === "aiprice") return <>{heading}<div className="terminal-catalog"><aside className="catalog-sidebar"><p className="index-label">产品分区</p>{navigation}</aside>{children}</div></>;
  if (SITE_ID === "aisi") return <><div className="editorial-catalog-opening">{heading}<aside><p>价格之外，<br />也看看交付方式。</p><Link href="/methodology">如何读懂一条报价 <ArrowUpRight size={16} /></Link></aside></div><div className="editorial-catalog-nav">{navigation}</div>{children}</>;
  if (SITE_ID === "pricein") return <>{heading}<div className="shop-catalog-nav">{navigation}</div><div className="shop-catalog-body">{children}</div></>;
  return <div className="index-catalog"><aside className="catalog-sidebar"><Link href="/">← 返回索引</Link><p className="index-label">筛选 / BRANDS</p>{navigation}</aside><div>{heading}{children}</div></div>;
}

export function BrandProductOverview({ product }: { product: ProductDetail }) {
  if (IS_PRIMARY_SITE) return null;
  const identity = <div className="detail-identity"><PlatformIcon platform={product.brand} size={40} /><div><p>{product.brand}</p><h2>{product.display_name}</h2><span>{product.subtitle}</span></div></div>;
  const price = <div className="detail-price"><span>有货观测价</span><strong>{money(product.lowest_price, product.price_currency)}</strong><small>仅统计符合条件的报价</small></div>;
  const facts = <dl className="detail-facts"><div><dt>有货报价</dt><dd>{product.in_stock_count}</dd></div><div><dt>纳入统计</dt><dd>{product.trusted_offer_count}</dd></div><div><dt>报价来源</dt><dd>{product.source_count}</dd></div><div><dt>最近更新</dt><dd>{relativeTime(product.last_updated_at)}</dd></div></dl>;
  if (SITE_ID === "pricein") return <section className="brand-product-overview shop-detail"><div>{identity}{facts}</div><aside>{price}<a href="#product-offers" className="button-primary">比较店铺报价 ↓</a></aside></section>;
  if (SITE_ID === "aisi") return <section className="brand-product-overview editorial-detail"><div>{identity}<p className="detail-reading-note">先确认订阅形式与使用期限，再比较相同条件下的报价。</p></div><div>{price}{facts}</div></section>;
  return <section className={`brand-product-overview ${SITE_ID === "aiprice" ? "terminal-detail" : "index-detail"}`}>{identity}{price}{facts}</section>;
}
