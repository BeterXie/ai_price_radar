import type { Metadata } from "next";
import { FactLedger, InfoPage } from "@/components/page-shell";

export const metadata: Metadata = { title: "隐私政策", description: "AI Price Memory (AI Price Radar) 的数据与隐私处理说明。", alternates: { canonical: "/privacy" } };
const items = [
  ["公开目录数据", "目录处理来自公开页面的商品名称、价格、库存、说明、来源和观测时间。不会主动采集登录凭据、付款信息、订单或客户名单。"],
  ["纠错与收录申请", "纠错表单不收集联系方式；来源收录申请需要联系邮箱，仅用于核对申请和发送状态通知，不会公开展示。公开纠错记录只包含管理员填写的摘要和商家公开回应。"],
  ["账号与通知", "使用邮箱验证码登录时，服务会保存账号邮箱、会话和必要的安全记录；用户主动绑定 QQ 机器人后，还会保存 QQ 接收标识和通知偏好。验证码、邮件和 QQ 通知通过发送队列处理，并按配置的留存周期清理。"],
  ["关注清单", "未登录关注项与目标价保存在当前浏览器 localStorage。登录后，关注商品、目标价和邮件/QQ 通知开关会保存到云端，并在浏览器保留账号隔离的缓存；匿名关注项可在登录后迁移到该账号。Atom Feed 地址会在 URL 中包含商品标识和可选目标价，请按敏感链接保管。"],
  ["访问、点击与安全日志", "服务会处理运行、安全、限流和统计所需的技术信息，包括请求时间、接口状态、会话活动、按钮或优惠活动触发、报价访问、User-Agent，以及使用站点密钥生成的 IP 哈希。反向代理生产日志不记录完整请求 URI；应用日志与点击记录按配置的留存周期清理，过期会话和临时验证码会被删除。"],
  ["可选分析服务", "仅在部署方配置 GA4 测量 ID 且您明确选择允许后，页面才会加载 Google Analytics，并发送非账号、管理或认证页面的路径、页面标题及可识别的 AI 引荐来源/关键词。拒绝不会影响功能；选择保存在当前浏览器。未配置测量 ID 时不会加载 GA4。相关数据由 Google 按其服务条款处理。"],
  ["删除与更正", "公开信息所有者可通过纠错表单提交更正、隐藏或来源移除请求，并提供足以核验的说明。"],
] as const;
export default function PrivacyPage() { return <InfoPage eyebrow="隐私与数据" title="隐私政策" description="说明公开目录、账号通知、关注清单、分析服务和技术日志会处理哪些信息。" meta={<span>生效日期：2026 年 9 月 20 日</span>}><FactLedger items={items} /></InfoPage>; }
