import type { Metadata } from "next";
import Link from "next/link";
import { InfoPage } from "@/components/page-shell";

export const metadata: Metadata = { title: "关于本站", description: "了解 AI Price Radar 如何整理公开 AI 商品报价。", alternates: { canonical: "/about" } };

const principles = [
  ["信息从哪里来", "我们保留店铺名称、商品标题、公开描述、更新时间和原始链接，方便你自行确认。"],
  ["为什么有些低价不排第一", "短期体验、共享账号、中转服务和标准订阅不是同一种商品。类型不同的报价会分别展示，避免最低价造成误导。"],
  ["发现问题怎么办", "价格、库存或分类有误时，可以提交纠错。项目代码和主要分类规则也在 GitHub 上公开维护。"],
];

export default function AboutPage() {
  return (
    <InfoPage
      title="关于 AI Price Radar"
      description={<><p>本站整理公开的 AI 订阅、账号和相关服务报价，展示价格、库存、交付方式和更新时间。</p><p className="mt-3">本站不推荐商家，也不参与交易或提供担保。购买前请核对来源页面。</p></>}
    >
      <div className="surface-panel divide-y divide-[color:var(--line)] overflow-hidden">
        {principles.map(([title, copy]) => <section key={title} className="p-6"><h2 className="text-xl font-semibold">{title}</h2><p className="mt-3 text-sm leading-7 text-[color:var(--muted)]">{copy}</p></section>)}
      </div>
      <div className="mt-8 flex flex-wrap gap-3 border-t border-[color:var(--line-strong)] pt-8">
        <Link href="/methodology" className="button-primary">查看报价整理方法</Link>
        <a href="https://github.com/BeterXie/ai_price_radar" target="_blank" rel="noreferrer" className="button-secondary">查看开源仓库</a>
      </div>
    </InfoPage>
  );
}
