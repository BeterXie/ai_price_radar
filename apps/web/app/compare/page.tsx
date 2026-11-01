import type { Metadata } from "next";
import Link from "next/link";
import { getProducts } from "@/lib/api";
import { brandCatalogPath, OFFICIAL_PLAN_SOURCES } from "@/lib/catalog";
import { exactTime, money } from "@/lib/format";
import { SITE_URL } from "@/lib/site";
import { breadcrumbJsonLd, JsonLd } from "@/components/structured-data";

export const dynamic = "force-dynamic";
const title = "AI 模型对比｜ChatGPT、Claude、Gemini 订阅价格与选购";
const description = "对比 ChatGPT、Claude、Gemini 的订阅报价、库存、店铺来源与交付方式，查看官方套餐说明和本站模型评测，按使用场景选择 AI 产品。";
export const metadata: Metadata = {
  title, description,
  alternates: { canonical: `${SITE_URL}/compare` },
  openGraph: { title, description, url: `${SITE_URL}/compare`, type: "website" },
  twitter: { card: "summary_large_image", title, description },
};

const BRANDS = ["OpenAI", "Claude", "Gemini"] as const;
const PRODUCTS = ["chatgpt-plus", "chatgpt-pro-100", "chatgpt-pro-200", "claude-pro", "claude-max-5x", "claude-pro-20x", "gemini-plus", "gemini-pro", "gemini-ultra-5x", "gemini-ultra-20x"];

export default async function ComparePage() {
  const offerScope = new URLSearchParams({ delivery_type: "subscription_recharge", period: "one_month" });
  const catalog = await getProducts(new URLSearchParams({ products: PRODUCTS.join(","), limit: "100", comparable: "true", ...Object.fromEntries(offerScope) }).toString());
  const products = PRODUCTS.flatMap((slug) => catalog.items.filter((product) => product.slug === slug && product.offer_count > 0));
  return (
    <main id="main-content" className="shell py-8 md:py-12">
      <JsonLd data={breadcrumbJsonLd([{ name: "首页", path: "/" }, { name: "AI 模型与订阅对比", path: "/compare" }])} />
      <header className="max-w-4xl">
        <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">AI 模型与订阅对比</h1>
        <p className="mt-4 text-[color:var(--muted)] leading-7">比较 ChatGPT、Claude、Gemini，先确定要买网页订阅、独立账号还是 API 额度，再比较相同期限和交付方式的价格。这里汇总本站实际收录的报价，并提供官方套餐与模型评测入口。</p>
      </header>

      <section className="mt-10" aria-labelledby="compare-prices">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 id="compare-prices" className="text-2xl font-semibold">1 个月直充 / 代充价格对比</h2>
          <time className="text-xs text-[color:var(--muted)]" dateTime={catalog.snapshot_at || undefined}>数据更新：{exactTime(catalog.snapshot_at)}</time>
        </div>
        <p className="mt-3 max-w-4xl text-sm leading-6 text-[color:var(--muted)]">下表只统计期限标为 1 个月的直充 / 代充商品。价格来自纳入统计的有货报价；店铺、充值渠道和质保仍可能不同，点击套餐可核对原文。该价格不代表官方月费。</p>
        {products.length ? <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-left text-sm">
            <caption className="sr-only">ChatGPT、Claude、Gemini 已收录订阅套餐的价格、库存与来源</caption>
            <thead><tr className="border-b border-[color:var(--line-strong)] text-[color:var(--muted)]">
              {["套餐", "有货观测价", "有货报价", "来源数", "最近更新"].map((label) => <th key={label} scope="col" className="px-3 py-4 font-medium">{label}</th>)}
            </tr></thead>
            <tbody>{products.map((product) => <tr key={product.slug} className="border-b border-[color:var(--line)]">
              <th scope="row" className="px-3 py-4 font-medium"><Link href={`/products/${product.slug}?${offerScope}`} className="underline underline-offset-4">{product.display_name}</Link></th>
              <td className="px-3 py-4 tabular-nums">{product.trusted_offer_count > 0 ? money(product.lowest_price, product.price_currency) : "暂无有货价"}</td>
              <td className="px-3 py-4 tabular-nums">{product.in_stock_count}</td>
              <td className="px-3 py-4 tabular-nums">{product.source_count}</td>
              <td className="px-3 py-4 text-xs text-[color:var(--muted)]">{exactTime(product.last_updated_at)}</td>
            </tr>)}</tbody>
          </table>
        </div> : <p className="mt-5">当前暂无这些套餐的公开报价，请稍后再查看。</p>}
        <nav aria-label="各品牌完整比价" className="mt-5 flex flex-wrap gap-4">{BRANDS.map((brand) => <Link key={brand} href={brandCatalogPath(brand)} className="text-sm underline underline-offset-4">{brand} 比价</Link>)}</nav>
      </section>

      <section className="mt-12" aria-labelledby="compare-scope">
        <h2 id="compare-scope" className="text-2xl font-semibold">ChatGPT、Claude、Gemini 怎么比较</h2>
        <div className="mt-5 grid gap-6 md:grid-cols-3">
          <div><h3 className="font-semibold">日常问答与写作</h3><p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">用相同的真实任务比较答案准确度、文件处理、使用额度和工具支持。套餐名称不等于固定模型版本，具体可用模型以产品内说明为准。</p></div>
          <div><h3 className="font-semibold">编程与模型能力</h3><p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">比较时记录模型版本、提示词、工具权限和结果。本站的单项测试只能说明该任务表现，不能推导所有编程或推理任务的综合排名。</p><Link href="/skills/pelican-bicycle-benchmark" className="mt-3 inline-block text-sm underline underline-offset-4">查看模型评测与测试条件</Link></div>
          <div><h3 className="font-semibold">API 与自动化</h3><p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">按输入、输出、缓存命中、重试次数和成功完成任务的成本比较。网页订阅与 API 额度应分别核对；中转服务还需查看接口可用性与计费口径。</p><Link href="/relays" className="mt-3 inline-block text-sm underline underline-offset-4">查看 API 中转站</Link></div>
        </div>
      </section>

      <section className="mt-12 border-t border-[color:var(--line)] pt-8" aria-labelledby="compare-sources">
        <h2 id="compare-sources" className="text-2xl font-semibold">官方套餐与报价口径</h2>
        <p className="mt-3 max-w-4xl text-sm leading-6 text-[color:var(--muted)]">官方权益、模型访问范围和使用限额会调整，购买前应核对官方说明。本站保留商品来源和更新时间，交易价格与交付条件以店铺商品页为准。</p>
        <nav className="mt-4 flex flex-wrap gap-4" aria-label="官方套餐来源">{BRANDS.map((brand) => <a key={brand} href={OFFICIAL_PLAN_SOURCES[brand]} target="_blank" rel="noreferrer" className="text-sm underline underline-offset-4">{brand} 官方套餐</a>)}<Link href="/methodology" className="text-sm underline underline-offset-4">数据方法</Link></nav>
      </section>
    </main>
  );
}
