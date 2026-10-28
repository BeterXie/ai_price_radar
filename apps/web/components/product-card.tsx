import Link from "next/link";
import { ArrowUpRight } from "@phosphor-icons/react/ssr";
import { PlatformIcon } from "@/components/platform-icon";
import type { ProductCard as ProductCardType } from "@/lib/types";
import { exactTime, money, relativeTime } from "@/lib/format";

export function ProductCard({ product }: { product: ProductCardType }) {
  return (
    <Link href={`/products/${encodeURIComponent(product.slug)}`} className="home-product-row">
      <div className="home-product-name">
        <span className="home-product-icon"><PlatformIcon platform={product.brand} size={24} /></span>
        <div>
          <h3>{product.display_name}</h3>
          <p>{product.subtitle}</p>
        </div>
      </div>
      <span className={`home-product-stock ${product.in_stock_count > 0 ? "is-available" : ""}`}>
        <span className="sr-only">有货报价 </span>{product.in_stock_count > 0 ? <>{product.in_stock_count} 条<span className="home-stock-label">有货</span></> : "暂无现货"}
      </span>
      <time className="home-product-updated" dateTime={product.last_updated_at || undefined} title={exactTime(product.last_updated_at)}>
        {relativeTime(product.last_updated_at)}
      </time>
      <span className="home-product-price"><span className="sr-only">有货观测价 </span>{money(product.lowest_price, product.price_currency)}</span>
      <ArrowUpRight className="home-product-arrow" size={19} aria-hidden="true" />
    </Link>
  );
}
