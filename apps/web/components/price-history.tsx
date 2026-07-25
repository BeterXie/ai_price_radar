export function PriceHistory({ points }: { points: { observed_at: string; price: string | null }[] }) {
  const valid = points.filter((point) => point.price !== null).slice(-24);
  if (valid.length < 2) {
    return <div className="grid h-52 place-items-center rounded-[18px] border hairline text-sm text-black/45">历史数据积累中</div>;
  }
  const values = valid.map((point) => Number(point.price));
  const min = Math.min(...values);
  const max = Math.max(...values);
  return (
    <div className="rounded-[18px] border hairline bg-[color:var(--panel)] p-5">
      <div className="flex h-44 items-end gap-1.5" aria-label="价格历史柱状图">
        {valid.map((point, index) => {
          const value = Number(point.price);
          const height = max === min ? 55 : 20 + ((value - min) / (max - min)) * 80;
          return <div key={`${point.observed_at}-${index}`} title={`¥${value.toFixed(2)}`} className="min-w-1 flex-1 rounded-t-sm bg-[color:var(--ink)] opacity-75 transition-opacity hover:opacity-100" style={{ height: `${height}%` }} />;
        })}
      </div>
      <div className="mt-4 flex justify-between mono text-[11px] text-black/40"><span>低 ¥{min.toFixed(2)}</span><span>近 {valid.length} 次观测</span><span>高 ¥{max.toFixed(2)}</span></div>
    </div>
  );
}
