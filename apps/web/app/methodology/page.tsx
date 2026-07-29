import type { Metadata } from "next";

export const metadata: Metadata = { title: "数据方法", description: "了解报价采集、可信价格、统计口径、来源健康和纠错机制。", alternates: { canonical: "/methodology" } };

const sections = [
  ["采集范围", "只处理无需登录即可访问的公开商品信息，包括原始标题、公开价格、库存状态、交付描述、来源链接和观测时间。不会采集账号凭据、订单、付款信息或客户数据。"],
  ["有效报价", "报价必须已审核、仍处于当前发布快照、来源可见且观测时间没有超过有效窗口。失效报价保留在审计数据中，但不进入公开统计。"],
  ["可比报价", "只有产品分类、交付形态和商品含义足以与标准产品直接比较的报价，才参与可比价格统计。中转、共享池、体验、辅助服务等相关商品仍可展示，但不会混入标准订阅主价格。"],
  ["可信最低价", "可信价格必须有货、价格大于等于 ¥1、属于可比报价，并且没有显著低于同交付形态中位价。异常低价不会被删除，而是保留来源并标记待核验。"],
  ["中位价与趋势", "中位价按当前有效的可比有货报价计算。趋势按日聚合可信最低价、中位价、有货观测数和观测总数，避免把不同商品或店铺的零散历史点误画成一条连续价格。"],
  ["数据质量", "产品数据质量综合可信报价占比、独立来源数量和更新时间，仅用于描述数据完整度。来源健康根据最近成功扫描时间、连续失败次数和可观测扫描状态计算，不是商家信誉或欺诈评分。"],
  ["统计口径", "首页、目录和详情页均基于同一已发布快照与有效时间窗口。筛选后显示的报价数、可比数、可信数和有货数都只统计当前筛选结果。"],
  ["纠错与申诉", "用户可通过报价页举报信息错误或不可购买。管理员处理时可发布不含联系方式和私密描述的公开摘要；商家也可提供公开回应。"],
];

export default function MethodologyPage() {
  return <main id="main-content" className="shell py-12"><header className="max-w-4xl border-b border-black pb-10"><p className="mono text-xs tracking-[.15em] text-black/45">Methodology</p><h1 className="mt-4 text-5xl font-semibold tracking-[-.06em] sm:text-6xl">价格必须能解释，统计必须能复核</h1><p className="mt-6 text-base leading-7 text-[color:var(--muted)]">下面是公开页面采用的数据口径。实现细节与测试位于开源仓库，规则变化会记录在版本变更日志中。</p></header><div className="grid gap-px overflow-hidden rounded-[18px] border hairline bg-[color:var(--line)] my-10 md:grid-cols-2">{sections.map(([title, copy]) => <section key={title} className="bg-[color:var(--panel)] p-6"><h2 className="text-xl font-semibold">{title}</h2><p className="mt-3 text-sm leading-7 text-black/60">{copy}</p></section>)}</div><p className="text-xs leading-6 text-black/45">方法论描述事实处理规则，不构成商品、商家或交易安全背书。购买前应回到来源页面核验实时价格、库存、期限、交付和售后条件。</p></main>;
}
