import type { Metadata } from "next";
import { FactLedger, InfoPage } from "@/components/page-shell";

export const metadata: Metadata = { title: "隐私政策", description: "AI Price Radar 的数据与隐私处理说明。", alternates: { canonical: "/privacy" } };
const items = [
  ["公开目录数据", "目录处理来自公开页面的商品名称、价格、库存、说明、来源和观测时间。不会主动采集登录凭据、付款信息、订单或客户名单。"],
  ["纠错与收录申请", "纠错表单不收集联系方式；来源收录申请需要联系邮箱，仅用于核对申请和发送状态通知，不会公开展示。公开纠错记录只包含管理员填写的摘要和商家公开回应。"],
  ["关注清单", "关注产品与目标价保存在浏览器 localStorage。服务端生成 Atom Feed 时只读取 URL 中的产品标识和目标价，不保存账号、邮箱或关注清单。"],
  ["日志与安全", "服务可能记录为运行、安全和限流所必需的技术日志，例如请求时间、接口状态和经过哈希处理的限流标识。"],
  ["删除与更正", "公开信息所有者可通过纠错表单提交更正、隐藏或来源移除请求，并提供足以核验的说明。"],
] as const;
export default function PrivacyPage() { return <InfoPage eyebrow="隐私与数据" title="隐私政策" description="说明公开目录、纠错申请、关注清单和技术日志会处理哪些信息。" meta={<span>生效日期：2026 年 7 月 29 日</span>}><FactLedger items={items} /></InfoPage>; }
