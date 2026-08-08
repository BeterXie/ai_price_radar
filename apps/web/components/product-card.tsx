import Link from "next/link";
import { ArrowUpRight, Clock, Package, ShieldCheck } from "@phosphor-icons/react/ssr";
import { PlatformIcon } from "@/components/platform-icon";
import type { ProductCard as ProductCardType } from "@/lib/types";
import { money, relativeTime } from "@/lib/format";

export function ProductCard({ product, index = 0 }: { product: ProductCardType; index?: number }) {
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
      className="product-row group grid gap-4 py-6 xl:grid-cols-[40px_minmax(220px,1.4fr)_90px_100px_125px_130px_120px_100px_24px] xl:items-center"
    >
      <div className="mono text-xs text-black/35">{String(index + 1).padStart(2, "0")}</div>
      <div>
        <div className="flex flex-wrap items-center gap-2 xl:hidden">
          <span className="flex items-center gap-1.5 rounded-full bg-black/6 px-2.5 py-1 text-[11px]"><PlatformIcon platform={product.brand} size={13} />{product.brand}</span>
          <span className="rounded-full border hairline px-2.5 py-1 text-[11px]">{typeLabel[product.product_type] || product.product_type}</span>
          {product.in_stock_count > 0 && <span className="flex items-center gap-2 text-xs font-medium"><span className="signal-dot" />有货</span>}
        </div>
        <h3 className="mt-3 text-xl font-semibold tracking-[-.035em] group-hover:underline group-hover:decoration-[color:var(--accent)] group-hover:decoration-4 group-hover:underline-offset-4">{product.display_name}</h3>
        <p className="mt-1 text-sm text-[color:var(--muted)]">{product.subtitle}</p>
        <div className="mt-3 flex flex-wrap gap-2 md:hidden">
          {product.tags.slice(0, 4).map((tag) => <span key={tag} className="rounded-full border hairline px-2 py-1 text-xs">{tag}</span>)}
        </div>
      </div>
      <div className="hidden items-center gap-2 text-sm xl:flex"><PlatformIcon platform={product.brand} />{product.brand}</div>
      <div className="hidden text-sm text-[color:var(--muted)] xl:block">{typeLabel[product.product_type] || product.product_type}</div>
      <div>
        <p className="text-xs text-black/40 xl:hidden">近期有货最低价</p>
        <p className="mt-2 text-2xl font-semibold tracking-[-.04em]">{money(product.lowest_price, product.price_currency)}</p>
        {product.related_lowest_price && product.related_lowest_price !== product.lowest_price && <p className="mt-1 text-[11px] text-black/40">全部有货 {money(product.related_lowest_price, product.price_currency)} 起</p>}
      </div>
      <p className="flex items-center gap-2 text-sm text-[color:var(--muted)]"><Package size={16} /> {product.trusted_offer_count} 条纳入统计 / {product.in_stock_count} 条有货</p>
      <p className="flex items-center gap-2 text-sm text-[color:var(--muted)]"><ShieldCheck size={16} /> 信息覆盖 {product.data_quality_score} 分 · {product.data_quality_label}<br className="hidden" /></p>
      <p className="flex items-center gap-2 text-sm text-[color:var(--muted)]"><Clock size={16} /> {relativeTime(product.last_updated_at)}</p>
      <ArrowUpRight size={22} className="transition-transform group-hover:-translate-y-1 group-hover:translate-x-1" />
    </Link>
  );
}
