import Link from "next/link";
import { Check } from "@phosphor-icons/react/ssr";

export function OfferScopeControls({
  action,
  comparableOnly,
  inStockOnly,
  resetHref,
  hiddenFields = {},
}: {
  action: string;
  comparableOnly: boolean;
  inStockOnly: boolean;
  resetHref: string;
  hiddenFields?: Record<string, string>;
}) {
  const scopeHref = (comparable: boolean, inStock: boolean) => {
    const params = new URLSearchParams(hiddenFields);
    params.set("comparable", String(comparable));
    if (inStock) params.set("in_stock", "true");
    return `${action}?${params.toString()}`;
  };

  return (
    <section className="py-5">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[12px] border border-black bg-white px-4 py-3">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm" aria-label="报价范围">
          <span className="font-semibold">报价范围</span>
          <Link href={scopeHref(!comparableOnly, inStockOnly)} aria-pressed={comparableOnly} className="flex items-center gap-2">
            <span className={`grid h-4 w-4 place-items-center border border-black ${comparableOnly ? "bg-black text-white" : "bg-white"}`}>{comparableOnly && <Check size={12} weight="bold" />}</span>
            仅显示可直接比较
          </Link>
          <Link href={scopeHref(comparableOnly, !inStockOnly)} aria-pressed={inStockOnly} className="flex items-center gap-2">
            <span className={`grid h-4 w-4 place-items-center border border-black ${inStockOnly ? "bg-black text-white" : "bg-white"}`}>{inStockOnly && <Check size={12} weight="bold" />}</span>
            仅看有货
          </Link>
        </div>
        <Link href={resetHref} className="rounded-[8px] border border-black px-4 py-2 text-sm">重置</Link>
      </div>
    </section>
  );
}
