import { money } from "@/lib/format";
import type { PriceTrendPoint } from "@/lib/types";

function formatPrice(value: number, currency: string) {
  return money(value, currency);
}

function linePath(values: (number | null)[], min: number, max: number, width: number, height: number) {
  const span = Math.max(1, max - min);
  const step = values.length > 1 ? width / (values.length - 1) : width;
  let path = "";
  let drawing = false;
  values.forEach((value, index) => {
    if (value === null) {
      drawing = false;
      return;
    }
    const x = index * step;
    const y = height - ((value - min) / span) * height;
    path += `${drawing ? " L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`;
    drawing = true;
  });
  return path;
}

export function PriceHistory({ points }: { points: PriceTrendPoint[] }) {
  const recent = points.slice(-90);
  const currency = recent[0]?.price_currency || "CNY";
  const priceValues = recent.flatMap((point) => [point.trusted_lowest_price, point.median_price])
    .filter((value): value is string => value !== null)
    .map(Number)
    .filter(Number.isFinite);
  if (recent.length < 2 || priceValues.length < 2) {
    return <div className="empty-state grid h-56 place-items-center !p-6 text-sm">历史数据不足，暂时无法显示趋势</div>;
  }

  const min = Math.min(...priceValues);
  const max = Math.max(...priceValues);
  const width = 760;
  const height = 190;
  const lowest = recent.map((point) => {
    if (point.trusted_lowest_price === null) return null;
    const value = Number(point.trusted_lowest_price);
    return Number.isFinite(value) ? value : null;
  });
  const medians = recent.map((point) => {
    if (point.median_price === null) return null;
    const value = Number(point.median_price);
    return Number.isFinite(value) ? value : null;
  });
  const stockValues = recent.map((point) => Number.isFinite(point.in_stock_count) && point.in_stock_count >= 0 ? Math.floor(point.in_stock_count) : 0);
  const stockMax = Math.max(1, ...stockValues);
  const firstDate = new Date(recent[0].bucket_at).toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
  const lastDate = new Date(recent.at(-1)!.bucket_at).toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
  const lastLowest = [...lowest].reverse().find((value): value is number => value !== null);
  const lastMedian = [...medians].reverse().find((value): value is number => value !== null);

  return (
    <figure className="rounded-[9px] border hairline bg-[color:var(--panel)] p-5">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap gap-4">
          <span className="flex items-center gap-2"><span className="h-0.5 w-5 bg-[color:var(--info)]" />近期有货观测价 {lastLowest === undefined ? "暂无" : formatPrice(lastLowest, currency)}</span>
          <span className="flex items-center gap-2"><span className="h-0.5 w-5 border-t-2 border-dashed border-[color:var(--line-strong)]" />常见观测价 {lastMedian === undefined ? "暂无" : formatPrice(lastMedian, currency)}</span>
          <span className="flex items-center gap-2"><span className="h-3 w-3 bg-[color:var(--accent)]" />有货观测</span>
        </div>
        <span className="text-black/40">最近 {recent.length} 天</span>
      </div>
      <div className="relative overflow-hidden" aria-label={`价格趋势，范围 ${formatPrice(min, currency)} 至 ${formatPrice(max, currency)}`}>
        <svg viewBox={`0 0 ${width} ${height + 40}`} role="img" className="h-auto w-full" preserveAspectRatio="none">
          {[0, 0.5, 1].map((ratio) => <line key={ratio} x1="0" x2={width} y1={ratio * height} y2={ratio * height} stroke="currentColor" opacity="0.08" />)}
          {recent.map((point, index) => {
            const barWidth = Math.max(2, width / recent.length - 2);
            const x = recent.length > 1 ? index * (width / (recent.length - 1)) - barWidth / 2 : 0;
            const barHeight = Math.max(2, (stockValues[index] / stockMax) * 34);
            return <rect key={`${point.bucket_at}-stock`} x={Math.max(0, x)} y={height + 36 - barHeight} width={barWidth} height={barHeight} fill="var(--accent)" opacity="0.9" />;
          })}
          <path d={linePath(medians, min, max, width, height)} fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="7 6" opacity="0.45" vectorEffect="non-scaling-stroke" />
          <path d={linePath(lowest, min, max, width, height)} fill="none" stroke="var(--info)" strokeWidth="3" vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
      <figcaption className="mt-3 flex justify-between text-[11px] font-medium text-[color:var(--muted)]"><span>{firstDate}</span><span>范围 {formatPrice(min, currency)} – {formatPrice(max, currency)}</span><span>{lastDate}</span></figcaption>
    </figure>
  );
}
