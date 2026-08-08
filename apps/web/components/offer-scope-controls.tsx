import Link from "next/link";

export type OfferFilterValues = {
  comparable: string;
  in_stock: string;
  warranty: string;
  delivery_type: string;
  period: string;
  auto_delivery: string;
  updated_within_hours: string;
  min_price: string;
  max_price: string;
};

const DELIVERY_OPTIONS = [
  ["", "全部交付形态"],
  ["subscription_recharge", "订阅 / 直充 / 代充"],
  ["finished_account", "成品账号"],
  ["semi_finished_account", "半成品账号"],
  ["team_seat", "团队席位"],
  ["card_code", "卡密 / 兑换码"],
  ["api_credit", "API 额度"],
  ["relay_api", "中转 / 反代"],
  ["shared_pool", "共享号池"],
  ["trial_account", "体验 / 日抛"],
  ["verification_service", "验证辅助"],
  ["unknown", "形态未知"],
];

const PERIOD_OPTIONS = [
  ["", "全部期限"], ["one_day", "1 天"], ["one_week", "1 周"], ["one_month", "1 个月"],
  ["three_months", "3 个月"], ["six_months", "6 个月"], ["one_year", "1 年"], ["unknown", "期限未知"],
];

function FilterForm({
  action,
  values,
  hiddenFields,
}: {
  action: string;
  values: OfferFilterValues;
  hiddenFields: Record<string, string>;
}) {
  return (
    <form action={action} method="get" className="offer-filter-form surface-panel p-4">
      {Object.entries(hiddenFields).map(([name, value]) => <input key={name} type="hidden" name={name} value={value} />)}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
        <label className="text-xs font-medium text-black/55">比较范围
          <select name="comparable" defaultValue={values.comparable} className="field mt-1.5 text-sm">
            <option value="true">仅可直接比较</option><option value="false">包含相关商品</option>
          </select>
        </label>
        <label className="text-xs font-medium text-black/55">交付形态
          <select name="delivery_type" defaultValue={values.delivery_type} className="field mt-1.5 text-sm">
            {DELIVERY_OPTIONS.map(([value, label]) => <option key={value || "all"} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="text-xs font-medium text-black/55">服务期限
          <select name="period" defaultValue={values.period} className="field mt-1.5 text-sm">
            {PERIOD_OPTIONS.map(([value, label]) => <option key={value || "all"} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="text-xs font-medium text-black/55">质保
          <select name="warranty" defaultValue={values.warranty} className="field mt-1.5 text-sm">
            <option value="">全部质保状态</option><option value="covered">有质保</option><option value="none">无质保</option><option value="unknown">质保未知</option>
          </select>
        </label>
        <label className="text-xs font-medium text-black/55">发货方式
          <select name="auto_delivery" defaultValue={values.auto_delivery} className="field mt-1.5 text-sm">
            <option value="">全部</option><option value="true">自动发货</option><option value="false">人工交付</option>
          </select>
        </label>
        <label className="text-xs font-medium text-black/55">更新时间
          <select name="updated_within_hours" defaultValue={values.updated_within_hours} className="field mt-1.5 text-sm">
            <option value="">全部更新时间</option><option value="6">6 小时内</option><option value="24">24 小时内</option><option value="72">3 天内</option><option value="168">7 天内</option>
          </select>
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <label className="text-xs font-medium text-black/55">最低价
          <span className="mt-1.5 flex w-32 items-center rounded-[9px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3"><span>¥</span><input name="min_price" defaultValue={values.min_price} inputMode="decimal" className="w-full bg-transparent py-2.5 pl-1 text-sm outline-none" /></span>
        </label>
        <label className="text-xs font-medium text-black/55">最高价
          <span className="mt-1.5 flex w-32 items-center rounded-[9px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3"><span>¥</span><input name="max_price" defaultValue={values.max_price} inputMode="decimal" className="w-full bg-transparent py-2.5 pl-1 text-sm outline-none" /></span>
        </label>
        <label className="mb-2 flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" name="in_stock" value="true" defaultChecked={values.in_stock === "true"} className="h-5 w-5 accent-[color:var(--brand-strong)]" />仅看有货</label>
        <button type="submit" className="button-primary tactile ml-auto">应用筛选</button>
      </div>
    </form>
  );
}

export function OfferScopeControls({
  action,
  values,
  resetHref,
  hiddenFields = {},
}: {
  action: string;
  values: OfferFilterValues;
  resetHref: string;
  hiddenFields?: Record<string, string>;
}) {
  const activeFilterCount = Object.entries(values).filter(([name, value]) => name === "comparable" ? value === "false" : Boolean(value)).length;
  return (
    <section className="offer-filters py-5" aria-labelledby="offer-filter-title">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div><h2 id="offer-filter-title" className="text-sm font-semibold">报价筛选</h2><p className="mt-1 text-xs text-[color:var(--muted)]">下方条件只筛选当前品牌、商品和来源。</p></div>
        <Link href={resetHref} className="button-tertiary !min-h-9 !px-3 text-xs">重置筛选</Link>
      </div>
      <div className="hidden md:block"><FilterForm action={action} values={values} hiddenFields={hiddenFields} /></div>
      <details className="offer-filter-disclosure md:hidden">
        <summary>筛选报价 <span>{activeFilterCount ? `${activeFilterCount} 项已选` : "全部条件"}</span></summary>
        <div className="mt-3"><FilterForm action={action} values={values} hiddenFields={hiddenFields} /></div>
      </details>
    </section>
  );
}
