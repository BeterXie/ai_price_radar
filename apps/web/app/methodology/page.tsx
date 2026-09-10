import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Clock, Globe, ShieldCheck, Stack, Users } from "@phosphor-icons/react/ssr";

export const metadata: Metadata = { title: "报价整理方法", description: "了解公开报价如何采集、筛选、统计和更新。", alternates: { canonical: "/methodology" } };

const methods = [
  { Icon: Globe, title: "01 / 保留原始来源", text: "只处理无需登录即可访问的公开商品信息，并保留公开店铺、商品标题、来源链接与观测时间。" },
  { Icon: Stack, title: "02 / 先分类，再比价", text: "只有商品类型、交付方式与实际内容相近的报价才会放在一起比较，避免把 API、共享服务与标准订阅混算。" },
  { Icon: Clock, title: "03 / 标明观测时间", text: "当前报价来自已发布数据快照。长时间未更新或来源不可访问的信息不会继续影响当前统计。" },
  { Icon: ShieldCheck, title: "04 / 不替商家作承诺", text: "限制、质保和售后以商品原文为准。信息覆盖与来源更新状态不是商家信誉或交易安全评级。" },
];

const numbers = [
  ["近期有货观测价", "满足统计条件、近期有货且可直接比较的同币种报价中的最低观测值，不代表最终成交价。"],
  ["当前 / 有货报价数量", "只统计当前筛选范围内的已发布记录；来源页面的实际库存仍可能在下一次采集前发生变化。"],
  ["信息覆盖", "综合纳入统计的报价占比、独立来源数量和更新时间，用于说明当前信息是否充足。"],
  ["常见价格与趋势", "按天整理同币种的近期有货观测价、常见价格和有货数量，避免把不同商品或币种混成一条价格线。"],
] as const;

export default function MethodologyPage() {
  return (
    <main className="container">
      <div className="page-content">
        <header className="page-intro">
          <span className="eyebrow">OUR DATA, EXPLAINED</span>
          <h1>每一条报价，<br /><span className="green-text">都应该说得清楚。</span></h1>
          <p>我们聚合公开信息，不参与交易。理解数据如何整理，也就更懂得如何使用。</p>
        </header>
        <section className="method-grid">{methods.map(({ Icon, title, text }) => <div className="method-card" key={title}><Icon size={28} /><h3>{title}</h3><p>{text}</p></div>)}</section>
        <div className="section-heading"><div><h2>你看到的数字，代表什么？</h2><p>统一口径，比单一低价更重要。</p></div></div>
        <section className="method-table">{numbers.map(([title, text]) => <div key={title}><strong>{title}</strong><p>{text}</p></div>)}</section>
        <div className="notice amber"><ShieldCheck size={19} /><div><strong>统计不是交易背书</strong><p>页面展示最近一次采集结果。购买前请回到来源页面重新确认价格、库存、期限、交付和售后条件。</p></div></div>
        <section className="guide-callout"><div className="callout-icon"><Users size={25} /></div><div><h3>透明的信息，需要一起维护。</h3><p>欢迎提交公开来源，也欢迎在报价详情中提出纠错。</p></div><Link className="button" href="/shops/submit">提交商品来源<ArrowRight size={16} /></Link></section>
      </div>
    </main>
  );
}
