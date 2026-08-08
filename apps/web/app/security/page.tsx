import type { Metadata } from "next";
import { InfoPage } from "@/components/page-shell";

export const metadata: Metadata = { title: "安全说明", description: "安全报告范围与负责任披露说明。", alternates: { canonical: "/security" } };

const items = [
  ["报告范围", "欢迎报告认证绕过、敏感信息泄露、服务端请求伪造、注入、跨站脚本、权限控制和依赖供应链问题。请不要访问他人数据、破坏服务或执行大规模扫描。"],
  ["提交方式", "通过 GitHub Security Advisory 私下报告，附上受影响版本、复现步骤、影响范围和建议修复。不要在公开 Issue 中发布可直接利用的细节。"],
  ["数据源边界", "商家 Feed 只接受 HTTPS 公网地址，并拒绝本地、私网和保留 IP；导入器限制响应体积并按统一数据模型校验。"],
];

export default function SecurityPage() {
  return <InfoPage title="安全与负责任披露" description="请通过私密渠道提交可复现的安全问题，并尽量减少测试影响。"><div className="editorial surface-panel divide-y divide-[color:var(--line)] overflow-hidden">{items.map(([title, copy]) => <section key={title} className="p-6 sm:p-7"><h2>{title}</h2><p className="mt-3">{copy}</p></section>)}</div></InfoPage>;
}
