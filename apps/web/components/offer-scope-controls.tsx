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
  return (
    <section className="py-5">
      <form action={action} method="get" className="rounded-[14px] border border-black bg-white p-4">
        {Object.entries(hiddenFields).map(([name, value]) => <input key={name} type="hidden" name={name} value={value} />)}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
          <label className="text-xs font-medium text-black/55">比较范围
            <select name="comparable" defaultValue={values.comparable} className="mt-1.5 w-full rounded-[9px] border hairline bg-white px-3 py-2.5 text-sm text-black">
              <option value="true">仅可直接比较</option><option value="false">包含相关商品</option>
            </select>
          </label>
          <label className="text-xs font-medium text-black/55">交付形态
            <select name="delivery_type" defaultValue={values.delivery_type} className="mt-1.5 w-full rounded-[9px] border hairline bg-white px-3 py-2.5 text-sm text-black">
              {DELIVERY_OPTIONS.map(([value, label]) => <option key={value || "all"} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="text-xs font-medium text-black/55">服务期限
            <select name="period" defaultValue={values.period} className="mt-1.5 w-full rounded-[9px] border hairline bg-white px-3 py-2.5 text-sm text-black">
              {PERIOD_OPTIONS.map(([value, label]) => <option key={value || "all"} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="text-xs font-medium text-black/55">质保
            <select name="warranty" defaultValue={values.warranty} className="mt-1.5 w-full rounded-[9px] border hairline bg-white px-3 py-2.5 text-sm text-black">
              <option value="">全部质保状态</option><option value="covered">有质保</option><option value="none">无质保</option><option value="unknown">质保未知</option>
            </select>
          </label>
          <label className="text-xs font-medium text-black/55">发货方式
            <select name="auto_delivery" defaultValue={values.auto_delivery} className="mt-1.5 w-full rounded-[9px] border hairline bg-white px-3 py-2.5 text-sm text-black">
              <option value="">全部</option><option value="true">自动发货</option><option value="false">人工交付</option>
            </select>
          </label>
          <label className="text-xs font-medium text-black/55">更新时间
            <select name="updated_within_hours" defaultValue={values.updated_within_hours} className="mt-1.5 w-full rounded-[9px] border hairline bg-white px-3 py-2.5 text-sm text-black">
              <option value="">有效窗口内</option><option value="6">6 小时内</option><option value="24">24 小时内</option><option value="72">3 天内</option><option value="168">7 天内</option>
            </select>
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="text-xs font-medium text-black/55">最低价
            <span className="mt-1.5 flex w-32 items-center rounded-[9px] border hairline px-3"><span>¥</span><input name="min_price" defaultValue={values.min_price} inputMode="decimal" className="w-full bg-transparent py-2.5 pl-1 text-sm outline-none" /></span>
          </label>
          <label className="text-xs font-medium text-black/55">最高价
            <span className="mt-1.5 flex w-32 items-center rounded-[9px] border hairline px-3"><span>¥</span><input name="max_price" defaultValue={values.max_price} inputMode="decimal" className="w-full bg-transparent py-2.5 pl-1 text-sm outline-none" /></span>
          </label>
          <label className="mb-2 flex items-center gap-2 text-sm"><input type="checkbox" name="in_stock" value="true" defaultChecked={values.in_stock === "true"} className="h-4 w-4 accent-black" />仅看有货</label>
          <div className="ml-auto flex gap-2">
            <Link href={resetHref} className="rounded-[9px] border border-black px-4 py-2.5 text-sm">重置</Link>
            <button type="submit" className="tactile rounded-[9px] bg-[color:var(--ink)] px-5 py-2.5 text-sm text-white">应用筛选</button>
          </div>
        </div>
      </form>
    </section>
  );
}
