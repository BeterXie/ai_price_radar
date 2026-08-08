import type { Metadata } from "next";
import { InfoPage } from "@/components/page-shell";

export const metadata: Metadata = { title: "使用条款", description: "AI Price Radar 使用条款与免责声明。", alternates: { canonical: "/terms" } };
const items = [
  ["信息服务", "本站提供公开信息聚合、分类、统计和来源链接，不是交易平台、卖方、代理商或支付服务商。"],
  ["不构成背书", "展示、收录、纳入价格统计的标记或来源更新状态，不代表对商品真实性、商家信誉、账号合规性、交付结果或售后能力的保证。"],
  ["用户核验义务", "价格、库存和条款可能随时变化。购买前应在来源页面核验商品含义、使用期限、交付方式、退款和平台服务条款。"],
  ["合规使用", "用户不得利用本站从事侵犯账号安全、规避平台限制、欺诈、未经授权访问或其他违法活动。"],
  ["数据与接口", "公开页面和接口可能因维护、来源变化或安全需要调整。不得绕过限流、干扰服务或批量收集非公开数据。"],
  ["纠错与移除", "权利人或信息主体可提交更正与移除请求。经核验后，内容可能被修正、隐藏或保留审计记录。"],
];
export default function TermsPage() { return <InfoPage title="使用条款" meta={<span>生效日期：2026 年 7 月 29 日</span>}><div className="editorial divide-y divide-[color:var(--line)] border-y border-[color:var(--line-strong)]">{items.map(([title, copy]) => <section key={title} className="py-7"><h2>{title}</h2><p className="mt-3">{copy}</p></section>)}</div></InfoPage>; }
