import type { Metadata } from "next";

export const metadata: Metadata = { title: "报价整理方法", description: "了解公开报价如何采集、筛选、统计和更新。", alternates: { canonical: "/methodology" } };

const sections = [
  ["采集范围", "只处理无需登录即可访问的公开商品信息，包括原始标题、公开价格、库存状态、交付描述、来源链接和观测时间。不会采集账号凭据、订单、付款信息或客户数据。"],
  ["当前报价", "公开统计只包含已经确认分类、来源仍可访问并且近期更新的报价。过期报价不会出现在当前统计中，但来源记录会继续保留。"],
  ["可以直接比较的报价", "只有商品类型、交付方式和实际内容相近的报价，才会放在一起比较。中转、共享池、体验和辅助服务仍可展示，但不会混入标准订阅价格。"],
  ["近期有货最低价", "用于展示的最低价必须有货、价格不低于 ¥1、可以和同类型商品直接比较，并且没有明显低于同交付方式的常见价格。异常价格不会被删除，而是保留来源并提醒确认。"],
  ["常见价格与趋势", "常见价格按当前可直接比较的有货报价计算。趋势按天整理近期有货最低价、常见价格和有货数量，避免把不同商品或店铺的零散记录混成一条价格线。"],
  ["报价覆盖与来源更新", "报价覆盖综合可参考报价占比、独立来源数量和更新时间，只用于说明当前信息是否充足。来源更新状态根据最近成功更新时间和连续失败次数计算，不是商家信誉或欺诈评分。"],
  ["统计范围", "首页、目录和详情页使用同一批已发布数据。筛选后显示的报价数、可直接比较数、可参考数和有货数，都只统计当前筛选结果。"],
  ["纠错与申诉", "用户可通过报价页举报信息错误或不可购买。管理员处理时可发布不含联系方式和私密描述的公开摘要；商家也可提供公开回应。"],
];

export default function MethodologyPage() {
  return <main id="main-content" className="shell py-12"><header className="max-w-4xl border-b border-black pb-10"><p className="mono text-xs tracking-[.15em] text-black/45">报价整理方法</p><h1 className="mt-4 text-5xl font-semibold tracking-[-.06em] sm:text-6xl">这些价格是怎么筛出来的</h1><p className="mt-6 text-base leading-7 text-[color:var(--muted)]">这里说明公开报价如何采集、分类和统计。实现细节与测试位于开源仓库，规则变化会记录在版本变更日志中。</p></header><div className="grid gap-px overflow-hidden rounded-[18px] border hairline bg-[color:var(--line)] my-10 md:grid-cols-2">{sections.map(([title, copy]) => <section key={title} className="bg-[color:var(--panel)] p-6"><h2 className="text-xl font-semibold">{title}</h2><p className="mt-3 text-sm leading-7 text-black/60">{copy}</p></section>)}</div><p className="text-xs leading-6 text-black/45">这些规则只用于整理公开信息，不构成商品、商家或交易安全背书。购买前请回到商品原页面确认实时价格、库存、期限、交付和售后条件。</p></main>;
}
