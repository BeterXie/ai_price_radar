import Link from "next/link";
import { ArrowRight, ArrowUpRight, Clock, Storefront } from "@phosphor-icons/react/ssr";
import { PlatformIcon } from "@/components/platform-icon";
import { ProductCardBookmark } from "@/components/product-card-bookmark";
import type { ProductCard as ProductCardType } from "@/lib/types";
import { money, relativeTime } from "@/lib/format";

const SPARKLINE_PATHS = [
  "M0,22 L12,20 L24,12 L36,16 L48,10 L60,18 L72,14 L84,20 L96,16 L108,22 L120,18",
  "M0,18 L12,22 L24,14 L36,18 L48,12 L60,16 L72,10 L84,18 L96,14 L108,20 L120,16",
  "M0,20 L12,16 L24,20 L36,12 L48,18 L60,14 L72,20 L84,16 L96,22 L108,18 L120,14",
];

function Sparkline({ variation = 0 }: { variation?: number }) {
  const path = SPARKLINE_PATHS[variation % SPARKLINE_PATHS.length];
  const gradId = `chartfill-${variation}`;
  return (
    <svg viewBox="0 0 120 34" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop stopColor="var(--brand)" stopOpacity=".10" />
          <stop offset="1" stopColor="var(--brand)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${path} L120,34 L0,34 Z`} fill={`url(#${gradId})`} />
      <polyline points={path} fill="none" stroke="#8fae9c" strokeWidth="1.5" strokeLinejoin="round" vectorEffect="non-scaling-stroke" opacity="0.6" />
    </svg>
  );
}

export function ProductCardGrid({ products }: { products: ProductCardType[] }) {
  if (!products.length) return null;
  return (
    <div className="product-card-grid">
      {products.map((product, index) => (
        <ProductCardGridItem key={product.slug} product={product} index={index} />
      ))}
    </div>
  );
}

function ProductCardGridItem({ product, index }: { product: ProductCardType; index: number }) {
  const inStock = product.in_stock_count > 0;
  const priceStr = money(product.lowest_price, product.price_currency).replace(/[¥￥]/, "");
  const href = `/products/${encodeURIComponent(product.slug)}`;
  // A real comparison between the lowest in-stock price and the median, both from the API.
  // The list endpoint carries no price history, so no 7-day trend is claimed here.
  const lowest = Number(product.lowest_price);
  const median = Number(product.median_price);
  const belowMedian = Number.isFinite(lowest) && Number.isFinite(median) && median > 0 && lowest < median;
  return (
    <article className="product-card-item">
      <div className="product-card-top">
        <span className="product-card-brand-icon" aria-hidden="true">
          <PlatformIcon platform={product.brand} size={26} />
        </span>
        <span className={`product-card-stock-pill ${inStock ? "in-stock" : "out-of-stock"}`}>
          <span className="product-card-stock-dot" />
          {inStock ? "有货" : "暂时缺货"}
        </span>
        <ProductCardBookmark slug={product.slug} name={product.display_name} currency={product.price_currency} suggestedPrice={product.lowest_price} />
      </div>
      <Link href={href} className="product-card-name">
        {product.display_name}
        <ArrowUpRight size={18} aria-hidden="true" />
      </Link>
      <p className="product-card-desc">{product.subtitle || `${product.brand} · ${product.display_name}`}</p>
      <div className="product-card-price-row">
        <div>
          <span className="product-card-price-label">近期有货参考价</span>
          <div className="product-card-price">
            <span className="price-unit">¥</span>
            {priceStr}
            <span className="price-from">起</span>
          </div>
        </div>
        <div className="product-card-sparkline">
          <Sparkline variation={index} />
          {belowMedian ? <div className="product-card-sparkline-trend">低于中位价</div> : null}
        </div>
      </div>
      <div className="product-card-footer">
        <span><Storefront size={13} aria-hidden="true" />{product.in_stock_count} 条有货报价</span>
        <span><Clock size={13} aria-hidden="true" />{relativeTime(product.last_updated_at)}</span>
        <Link href={href} className="product-card-footer-arrow" aria-label={`查看 ${product.display_name} 报价`} tabIndex={-1}>
          <ArrowRight size={16} />
        </Link>
      </div>
    </article>
  );
}
