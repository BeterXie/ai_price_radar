import Link from "next/link";
import { ArrowUpRight, Clock, Package, ShieldCheck } from "@phosphor-icons/react/ssr";
import { PlatformIcon } from "@/components/platform-icon";
import type { ProductCard as ProductCardType } from "@/lib/types";
import { money, relativeTime } from "@/lib/format";

export function ProductCard({ product }: { product: ProductCardType }) {
  const typeLabel: Record<string, string> = {
    subscription: "订阅 / 会员",
    account: "成品账号",
    api: "API / 额度",
    service: "辅助服务",
    team: "团队订阅",
  };
  return (
    <Link
      href={`/products/${encodeURIComponent(product.slug)}`}
      className="product-row group"
    >
      <div className="product-row-identity">
        <span className="product-brand-icon" aria-hidden="true"><PlatformIcon platform={product.brand} size={24} /></span>
        <div className="min-w-0">
          <p className="product-category">{product.brand} · {typeLabel[product.product_type] || product.product_type}</p>
          <h3 className="mt-1 text-xl font-semibold tracking-[-.025em] group-hover:underline group-hover:underline-offset-4">{product.display_name}</h3>
          <p className="mt-1 text-sm text-[color:var(--muted)]">{product.subtitle}</p>
        </div>
      </div>
      <div className="product-row-evidence">
        <p><Package size={16} aria-hidden="true" /><span>{product.trusted_offer_count} 条纳入统计 / <strong>{product.in_stock_count} 条有货</strong></span></p>
        <p className="coverage-value"><ShieldCheck size={16} aria-hidden="true" /><span>信息覆盖 {product.data_quality_score} 分 · {product.data_quality_label}</span></p>
        <p><Clock size={16} aria-hidden="true" /><span>{relativeTime(product.last_updated_at)}更新</span></p>
        <div className="product-row-tags flex md:hidden">
          {product.tags.slice(0, 4).map((tag) => <span key={tag} className="rounded-full border hairline px-2 py-1 text-xs">{tag}</span>)}
        </div>
      </div>
      <div className="product-row-price">
        <p className="text-xs text-[color:var(--muted)]">有货观测价</p>
        <p className="product-price-value">{money(product.lowest_price, product.price_currency)}</p>
        {product.related_lowest_price && product.related_lowest_price !== product.lowest_price && <p className="mt-1 text-xs text-[color:var(--muted)]">相关商品另有 {money(product.related_lowest_price, product.price_currency)} 起</p>}
      </div>
      <ArrowUpRight size={20} className="product-row-arrow" aria-hidden="true" />
    </Link>
  );
}
