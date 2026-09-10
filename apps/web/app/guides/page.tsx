import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, BookOpenText, MagnifyingGlass, ShieldCheck } from "@phosphor-icons/react/ssr";
import { GuideCard } from "@/components/guides/guide-card";
import { GuideJsonLd } from "@/components/guides/guide-json-ld";
import { brandGuides, deliveryGuides, generalGuides, productGuides, workflowGuides } from "@/lib/guides/registry";
import type { ProductSlug } from "@/lib/guides/types";
import { BRAND_NAMES, breadcrumbJsonLd } from "./_shared";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;
function lastValue(value: string | string[] | undefined) { return Array.isArray(value) ? value.at(-1) || "" : value || ""; }
function includesQuery(values: readonly string[], query: string) { return !query || values.join(" ").toLocaleLowerCase("zh-CN").includes(query.toLocaleLowerCase("zh-CN")); }

export async function generateMetadata({ searchParams }: { searchParams: SearchParams }): Promise<Metadata> {
  const params = await searchParams;
  return {
    title: "AI 商品购买与使用教程中心",
    description: "了解账号、代充、团队席位、卡密与 API 额度的区别，查看购买前检查、使用步骤、安全提示和售后材料准备指南。",
    alternates: { canonical: "https://ai.pricememo.cn/guides" },
    robots: { index: Object.keys(params).length === 0, follow: true },
    openGraph: { title: "AI 商品购买与使用教程中心", description: "购买前看懂交付方式，购买后确认服务和账号状态。", url: "https://ai.pricememo.cn/guides", siteName: "AI Price Radar", locale: "zh_CN", type: "website" },
  };
}

export default async function GuidesPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const query = lastValue(params.q).trim();
  const brand = lastValue(params.brand);
  const product = lastValue(params.product);
  const delivery = lastValue(params.delivery);

  const brands = Object.values(brandGuides).filter((guide) => (!brand || guide.brand === brand) && includesQuery([guide.title, guide.description, BRAND_NAMES[guide.brand]], query));
  const products = Object.values(productGuides).filter((guide) => (!brand || guide.brand === brand) && (!product || guide.productSlug === product) && (!delivery || (guide.supportedDeliveryTypes as readonly string[]).includes(delivery)) && includesQuery([guide.title, guide.description, guide.productSlug, BRAND_NAMES[guide.brand]], query));
  const deliveries = Object.values(deliveryGuides).filter((guide) => (!delivery || guide.deliveryType === delivery) && includesQuery([guide.title, guide.summary, guide.shortLabel], query));
  const general = Object.values(generalGuides).filter((guide) => includesQuery([guide.title, guide.description], query));
  const workflows = Object.values(workflowGuides).filter((guide) => {
    if (brand && brand !== "openai") return false;
    if (product) {
      const productGuide = productGuides[product as ProductSlug];
      if (!(productGuide?.workflowReferences?.some((reference) => reference.workflowSlug === guide.slug) ?? false)) return false;
    }
    if (delivery) {
      const referenced = Object.values(productGuides).some((productGuide) => productGuide.brand === "openai" && (productGuide.supportedDeliveryTypes as readonly string[]).includes(delivery) && (productGuide.workflowReferences ?? []).some((reference) => reference.workflowSlug === guide.slug));
      if (!referenced) return false;
    }
    return includesQuery([guide.title, guide.description, ...guide.flow, "Cockpit", "Sub2API", "CC Switch", "Codex++"], query);
  });

  const starter = [
    { href: "/guides/buying-checklist", title: "第一次购买 AI 产品？先看这份清单", description: "核对产品类型、交付方式、使用期限、账号控制权和售后条件。", meta: "新手必读" },
    { href: "/guides/account-control", title: "能登录，不等于拥有账号", description: "分清邮箱、密码、恢复渠道与 MFA 的控制权，保护你的数据。", meta: "账号安全" },
    { href: "/guides/subscription-verification", title: "如何确认订阅已生效？", description: "从官方账户页核对套餐、到期时间、账单与自动续费状态。", meta: "使用指南" },
  ];
  const resultCount = brands.length + products.length + deliveries.length + general.length + workflows.length;
  const guideCount = starter.length + Object.keys(brandGuides).length + Object.keys(productGuides).length + Object.keys(deliveryGuides).length + Object.keys(generalGuides).length + Object.keys(workflowGuides).length;
  const hasFilters = Boolean(query || brand || product || delivery);

  return (
    <main id="main-content" className="container" data-vds-schema="v3.1">
      <GuideJsonLd data={breadcrumbJsonLd([{ name: "首页", path: "/" }, { name: "教程中心", path: "/guides" }])} />
      <div className="page-content">
        <header className="guide-hero">
          <div>
            <span className="eyebrow">A LITTLE CLARITY GOES A LONG WAY</span>
            <h1>买之前看懂，<br /><span className="green-text">买之后会用。</span></h1>
            <p>从第一次选择，到每一天使用。<br />把复杂的产品、交付和安全问题，讲得更明白。</p>
          </div>
          <div className="guide-hero-card"><BookOpenText size={32} /><h3>你的 AI 使用说明书</h3><p>产品选择 · 交付方式 · 账号安全</p><div><strong>{Object.keys(brandGuides).length} <small>个品牌</small></strong><span /><strong>{guideCount} <small>篇指南</small></strong></div></div>
        </header>

        <form action="/guides" method="get" className="guide-search-bar">
          <div className="search-form"><MagnifyingGlass size={20} /><input name="q" type="search" defaultValue={query} placeholder="搜索产品、教程或关键词…" /><button type="submit">搜索<ArrowRight size={15} /></button></div>
          <select name="brand" defaultValue={brand} aria-label="筛选教程品牌"><option value="">全部品牌</option>{Object.values(brandGuides).map((guide) => <option key={guide.brand} value={guide.brand}>{BRAND_NAMES[guide.brand]}</option>)}</select>
          <select name="product" defaultValue={product} aria-label="筛选产品"><option value="">全部产品</option>{Object.values(productGuides).map((guide) => <option key={guide.productSlug} value={guide.productSlug}>{guide.title}</option>)}</select>
          <select name="delivery" defaultValue={delivery} aria-label="筛选交付方式"><option value="">全部交付</option>{Object.values(deliveryGuides).map((guide) => <option key={guide.deliveryType} value={guide.deliveryType}>{guide.shortLabel}</option>)}</select>
        </form>

        {!hasFilters ? <section className="guide-section"><div className="section-heading"><div><span className="eyebrow">START HERE</span><h2>第一次购买，从这里开始</h2><p>先看清买的是什么，再确认谁拥有控制权。</p></div></div><div className="guide-grid">{starter.map((item) => <GuideCard key={item.href} {...item} />)}</div></section> : null}

        <section className="guide-section">
          <div className="section-heading"><div><h2>{hasFilters ? `为你找到 ${resultCount} 篇指南` : "按产品，找到你的使用指南"}</h2><p>{hasFilters ? "筛选结果会保留原有独立 URL 与可索引内容。" : "从产品区别、购买核对，到交付后的使用与安全。"}</p></div>{hasFilters ? <Link className="text-button" href="/guides">清空筛选</Link> : null}</div>
          <div className="guide-grid">
            {brands.map((g) => <GuideCard key={`brand-${g.brand}`} href={`/guides/brands/${g.brand}`} title={g.title} description={g.description} meta={BRAND_NAMES[g.brand]} />)}
            {workflows.map((g) => <GuideCard key={`workflow-${g.slug}`} href={`/guides/workflows/${g.slug}`} title={g.title} description={g.description} meta="开发者工作流" />)}
            {products.map((g) => <GuideCard key={`product-${g.productSlug}`} href={`/guides/products/${g.productSlug}`} title={g.title} description={g.description} meta={`${BRAND_NAMES[g.brand]} · 产品教程`} />)}
            {deliveries.map((g) => <GuideCard key={`delivery-${g.deliveryType}`} href={`/guides/delivery/${g.deliveryType}`} title={g.title} description={g.summary} meta={g.shortLabel} />)}
            {general.map((g) => <GuideCard key={`general-${g.slug}`} href={`/guides/${g.slug}`} title={g.title} description={g.description} meta="通用指南" />)}
          </div>
          {hasFilters && resultCount === 0 ? <div className="empty"><MagnifyingGlass size={32} /><h3>没有找到匹配的指南</h3><p>试试其他关键词，或调整筛选条件。</p><Link className="button" href="/guides">查看全部指南</Link></div> : null}
        </section>

        <div className="notice"><ShieldCheck size={20} /><div><strong>安全永远是第一步</strong><p>不分享账号密码、验证码、恢复码或完整 API Key。教程帮助你理解流程，不承诺第三方商品的可用性。</p></div></div>
      </div>
    </main>
  );
}
