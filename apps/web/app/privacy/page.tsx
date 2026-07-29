import type { Metadata } from "next";
export const metadata: Metadata = { title: "隐私政策", description: "AI Price Radar 的数据与隐私处理说明。", alternates: { canonical: "/privacy" } };
const items=[
["公开目录数据","目录处理来自公开页面的商品名称、价格、库存、说明、来源和观测时间。不会主动采集登录凭据、付款信息、订单或客户名单。"],
["举报与收录申请","联系方式是选填项，只用于核对申请或回复纠错，不在公开纠错记录中展示。公开记录只包含管理员填写的摘要和商家公开回应。"],
["关注清单","关注产品与目标价保存在浏览器 localStorage。服务端生成 Atom Feed 时只读取 URL 中的产品标识和目标价，不保存账号、邮箱或关注清单。"],
["日志与安全","服务可能记录为运行、安全和限流所必需的技术日志，例如请求时间、接口状态和经过哈希处理的限流标识。"],
["删除与更正","公开信息所有者可通过纠错表单提交更正、隐藏或来源移除请求，并提供足以核验的说明。"],
];
export default function PrivacyPage(){return <main id="main-content" className="shell py-12"><header className="max-w-4xl border-b border-black pb-10"><p className="mono text-xs tracking-[.15em] text-black/45">Privacy</p><h1 className="mt-4 text-5xl font-semibold tracking-[-.06em]">隐私政策</h1><p className="mt-5 text-sm text-black/45">生效日期：2026 年 7 月 29 日</p></header><div className="max-w-4xl divide-y divide-[color:var(--line)]">{items.map(([t,c])=><section key={t} className="py-7"><h2 className="text-xl font-semibold">{t}</h2><p className="mt-3 text-sm leading-7 text-black/60">{c}</p></section>)}</div></main>}
