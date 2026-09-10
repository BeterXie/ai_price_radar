import Link from "next/link";
import { ArrowUpRight, Clock, Package, ShieldCheck } from "@phosphor-icons/react/ssr";
import { PlatformIcon } from "@/components/platform-icon";
import { WatchButton } from "@/components/watch-button";
import type { ProductCard as ProductCardType } from "@/lib/types";
import { money, relativeTime } from "@/lib/format";

const TYPE_LABELS: Record<string, string> = {
  subscription: "订阅会员",
  account: "成品账号",
  api: "API 额度",
  service: "辅助服务",
  team: "团队席位",
};

export function ProductCard({ product }: { product: ProductCardType }) {
  const quality = Math.max(8, Math.min(100, product.data_quality_score || 0));
  return (
    <article className="product-card">
      <div className="product-card-top">
        <span className={`brand-icon ${product.brand.toLowerCase()}`}><PlatformIcon platform={product.brand} size={27} /></span>
        <span className={`pill ${product.in_stock_count > 0 ? "green" : "gray"}`}>
          <span className="status-dot" />{product.in_stock_count > 0 ? "有货" : "暂缺"}
        </span>
        <WatchButton variant="icon" slug={product.slug} name={product.display_name} currency={product.price_currency} suggestedPrice={product.lowest_price} />
      </div>

      <Link href={`/products/${encodeURIComponent(product.slug)}`} className="product-title">
        <span>{product.display_name}</span><ArrowUpRight size={16} />
      </Link>
      <p className="product-description">{product.subtitle || `${product.brand} · ${TYPE_LABELS[product.product_type] || product.product_type}`}</p>

      <div className="product-price-line">
        <div>
          <span className="price-caption">近期有货参考价</span>
          <div className="price">{money(product.lowest_price, product.price_currency)}<small>起</small></div>
        </div>
        <div className="trend" aria-label={`信息覆盖 ${product.data_quality_score} 分`}>
          <svg className="sparkline" viewBox="0 0 100 34" preserveAspectRatio="none" aria-hidden="true">
            <path d={`M0 29 C18 25, 26 27, 38 20 S58 23, 68 14 S85 16, 100 ${34 - quality * 0.22}`} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
          </svg>
          <span><ShieldCheck size={11} /> 信息覆盖 {product.data_quality_score}<i>/ 100</i></span>
        </div>
      </div>

      <div className="product-card-bottom">
        <span><Package size={12} />{product.in_stock_count} 条有货</span>
        <span>{TYPE_LABELS[product.product_type] || product.product_type} · {product.source_count} 个来源</span>
        <span><Clock size={12} />{relativeTime(product.last_updated_at)}</span>
      </div>
    </article>
  );
}
