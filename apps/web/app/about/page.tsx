import type { Metadata } from "next";
import Link from "next/link";
export const metadata: Metadata = { title: "关于本站", description: "了解 AI Price Radar 如何整理公开 AI 商品报价。", alternates: { canonical: "/about" } };

export default function AboutPage() {
  return (
    <main id="main-content" className="shell py-12">
      <header className="max-w-4xl border-b border-black pb-10">
        <p className="mono text-xs tracking-[.15em] text-black/45">关于 AI Price Radar</p>
        <h1 className="mt-4 text-5xl font-semibold tracking-[-.06em] sm:text-6xl">帮你更快看懂一条 AI 商品报价</h1>
        <div className="mt-6 space-y-4 text-lg leading-8 text-[color:var(--muted)]">
          <p>不同店铺的商品名称、交付方式和售后说明经常不一样，只比较价格很容易买错。</p>
          <p>AI Price Radar 把公开的 AI 订阅、账号和相关服务整理到一起，让你更方便地查看价格、库存、交付方式和最近更新时间。</p>
          <p>本站不推荐商家，也不替任何交易提供担保。购买前，请回到商品原页面确认最新信息。</p>
        </div>
      </header>
      <div className="grid gap-8 py-10 md:grid-cols-3">
        <section><h2 className="text-xl font-semibold">信息从哪里来</h2><p className="mt-3 text-sm leading-7 text-black/60">我们保留店铺名称、商品标题、公开描述、更新时间和原始链接，方便你自行确认。</p></section>
        <section><h2 className="text-xl font-semibold">为什么有些低价不排第一</h2><p className="mt-3 text-sm leading-7 text-black/60">短期体验、共享账号、中转服务和标准订阅不是同一种商品。类型不同的报价会分别展示，避免最低价造成误导。</p></section>
        <section><h2 className="text-xl font-semibold">发现问题怎么办</h2><p className="mt-3 text-sm leading-7 text-black/60">价格、库存或分类有误时，可以提交纠错。项目代码和主要分类规则也在 GitHub 上公开维护。</p></section>
      </div>
      <div className="flex flex-wrap gap-3 border-t hairline pt-8">
        <Link href="/methodology" className="rounded-[10px] bg-[color:var(--ink)] px-5 py-3 text-sm text-white">查看报价整理方法</Link>
        <a href="https://github.com/BeterXie/ai_price_radar" target="_blank" rel="noreferrer" className="rounded-[10px] border border-black px-5 py-3 text-sm">查看开源仓库</a>
      </div>
    </main>
  );
}
