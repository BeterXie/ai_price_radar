import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, BookOpenText, MagnifyingGlass } from "@phosphor-icons/react/ssr";
import { GuideCard } from "@/components/guides/guide-card";
import { GuideIndex } from "@/components/guides/guide-index";
import { GuideJsonLd } from "@/components/guides/guide-json-ld";
import { PageHero } from "@/components/page-shell";
import { brandGuides, deliveryGuides, generalGuides, productGuides, workflowGuides } from "@/lib/guides/registry";
import type { ProductSlug } from "@/lib/guides/types";
import { BRAND_NAMES, breadcrumbJsonLd } from "./_shared";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function lastValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value.at(-1) || "" : value || "";
}

function includesQuery(values: readonly string[], query: string) {
  if (!query) return true;
  const haystack = values.join(" ").toLocaleLowerCase("zh-CN");
  return haystack.includes(query.toLocaleLowerCase("zh-CN"));
}

export async function generateMetadata({ searchParams }: { searchParams: SearchParams }): Promise<Metadata> {
  const params = await searchParams;
  const hasQuery = Object.keys(params).length > 0;
  return {
    title: "AI 商品购买与使用教程中心",
    description: "了解账号、代充、团队席位、卡密与 API 额度的区别，查看购买前检查、使用步骤、安全提示和售后材料准备指南。",
    alternates: { canonical: "https://ai.pricememo.cn/guides" },
    robots: { index: !hasQuery, follow: true },
    openGraph: {
      title: "AI 商品购买与使用教程中心",
      description: "购买前看懂交付方式，购买后确认服务和账号状态。",
      url: "https://ai.pricememo.cn/guides",
      siteName: "AI Price Radar",
      locale: "zh_CN",
      type: "website",
    },
  };
}

export default async function GuidesPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const query = lastValue(params.q).trim();
  const brand = lastValue(params.brand);
  const product = lastValue(params.product);
  const delivery = lastValue(params.delivery);

  const brands = Object.values(brandGuides).filter((guide) =>
    (!brand || guide.brand === brand) && includesQuery([guide.title, guide.description, BRAND_NAMES[guide.brand]], query),
  );
  const products = Object.values(productGuides).filter((guide) =>
    (!brand || guide.brand === brand) &&
    (!product || guide.productSlug === product) &&
    (!delivery || (guide.supportedDeliveryTypes as readonly string[]).includes(delivery)) &&
    includesQuery([guide.title, guide.description, guide.productSlug, BRAND_NAMES[guide.brand]], query),
  );
  const deliveries = Object.values(deliveryGuides).filter((guide) =>
    (!delivery || guide.deliveryType === delivery) && includesQuery([guide.title, guide.summary, guide.shortLabel], query),
  );
  const general = Object.values(generalGuides).filter((guide) => includesQuery([guide.title, guide.description], query));
  const workflows = Object.values(workflowGuides).filter((guide) => {
    if (brand && brand !== "openai") return false;
    if (product) {
      const productGuide = productGuides[product as ProductSlug];
      const referenced = productGuide?.workflowReferences?.some(
        (reference) => reference.workflowSlug === guide.slug,
      ) ?? false;
      if (!referenced) return false;
    }
    if (delivery) {
      const referencedByDelivery = Object.values(productGuides).some(
        (productGuide) =>
          productGuide.brand === "openai" &&
          (productGuide.supportedDeliveryTypes as readonly string[]).includes(delivery) &&
          (productGuide.workflowReferences ?? []).some(
            (reference) => reference.workflowSlug === guide.slug,
          ),
      );
      if (!referencedByDelivery) return false;
    }
    return includesQuery(
      [
        guide.title,
        guide.description,
        ...guide.flow,
        "Cockpit",
        "Sub2API",
        "CC Switch",
        "Codex++",
      ],
      query,
    );
  });
  const hasFilters = Boolean(query || brand || product || delivery);
  const guideCount = Object.keys(brandGuides).length
    + Object.keys(productGuides).length
    + Object.keys(deliveryGuides).length
    + Object.keys(generalGuides).length
    + Object.keys(workflowGuides).length;

  return (
    <main id="main-content" data-vds-schema="v3.1" data-vds-layer="field" data-vds-action="guide-orientation searchable-index evidence-cards responsive-filtering">
      <GuideJsonLd data={breadcrumbJsonLd([{ name: "首页", path: "/" }, { name: "教程中心", path: "/guides" }])} />
      <div className="shell">
        <PageHero
          eyebrow="购买与使用教程"
          title="购买前看懂，购买后会用"
        description="先分清买到的是账号、充值、团队席位、兑换码还是 API 额度，再按交付方式查看操作步骤和安全提醒。具体交付和售后以商品原页面为准。"
          compact
          aside={<div className="radar-field p-6">
            <BookOpenText size={27} aria-hidden="true" />
            <p className="mt-5 section-kicker">当前教程目录</p>
            <p className="mt-2 text-4xl font-semibold tracking-[-.055em]">{1 + guideCount}</p>
            <p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">覆盖 {Object.keys(brandGuides).length} 个品牌、{Object.keys(productGuides).length} 个产品、{Object.keys(deliveryGuides).length} 种交付方式、{Object.keys(generalGuides).length} 篇通用指南和 {Object.keys(workflowGuides).length} 个工作流。</p>
          </div>}
        />
      </div>

      <div className="shell py-10 sm:py-12">
        <section aria-labelledby="guide-search-title" className="surface-panel p-5 sm:p-6" data-vds-layer="evidence">
          <div className="flex items-center gap-3">
            <MagnifyingGlass size={22} aria-hidden="true" />
            <h2 id="guide-search-title" className="text-xl font-semibold">搜索和筛选教程</h2>
          </div>
          <form action="/guides" method="get" className="mt-5 grid gap-4 lg:grid-cols-[minmax(220px,1.5fr)_1fr_1.25fr_1.15fr_auto] lg:items-end">
            <label className="grid gap-2 text-sm font-medium">
              关键词
              <input name="q" type="search" defaultValue={query} placeholder="例如 API Key、成品账号" className="field placeholder:text-black/55" />
            </label>
            <label className="grid gap-2 text-sm font-medium">
              品牌
              <select name="brand" defaultValue={brand} className="field">
                <option value="">全部品牌</option>
                {Object.values(brandGuides).map((guide) => <option key={guide.brand} value={guide.brand}>{BRAND_NAMES[guide.brand]}</option>)}
              </select>
            </label>
            <label className="grid gap-2 text-sm font-medium">
              产品
              <select name="product" defaultValue={product} className="field">
                <option value="">全部产品</option>
                {Object.values(productGuides).map((guide) => <option key={guide.productSlug} value={guide.productSlug}>{guide.title}</option>)}
              </select>
            </label>
            <label className="grid gap-2 text-sm font-medium">
              交付方式
              <select name="delivery" defaultValue={delivery} className="field">
                <option value="">全部交付方式</option>
                {Object.values(deliveryGuides).map((guide) => <option key={guide.deliveryType} value={guide.deliveryType}>{guide.shortLabel}</option>)}
              </select>
            </label>
            <button type="submit" className="button-primary tactile">筛选</button>
          </form>
          {hasFilters ? (
            <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-black/55">
              <span>找到 {brands.length + products.length + deliveries.length + general.length + workflows.length} 篇相关教程</span>
              <Link href="/guides" className="button-tertiary">清空筛选</Link>
            </div>
          ) : null}
        </section>

        <GuideIndex title="第一次购买先看" description="先确认买的是什么、账号由谁控制，以及交付后能否自行修改资料。">
          <GuideCard href="/guides/buying-checklist" title="购买前检查" description="核对产品、交付方式、期限、质保和售后条件。" meta="通用指南" />
          <GuideCard href="/guides/account-control" title="判断账号控制权" description="分清登录凭据、邮箱、恢复渠道和 MFA 的控制方。" meta="账号安全" />
          <GuideCard href="/guides/subscription-verification" title="确认订阅状态" description="从官方账户页确认套餐、期限、账单和续费状态。" meta="状态确认" />
        </GuideIndex>

        <GuideIndex id="brands" title="全部品牌" description="查看品牌产品范围、套餐选择、常见交付和官方帮助入口。" empty={brands.length === 0}>
          {brands.map((guide) => <GuideCard key={guide.brand} href={`/guides/brands/${guide.brand}`} title={guide.title} description={guide.description} meta={BRAND_NAMES[guide.brand]} />)}
        </GuideIndex>

        <GuideIndex id="workflows" title="OpenAI 与 Codex 使用工作流" description="从账号或 API 交付开始，选择 Cockpit、Sub2API、CC Switch 或 Codex++ 完成实际接入。" empty={workflows.length === 0}>
          {workflows.map((guide) => (
            <GuideCard key={guide.slug} href={`/guides/workflows/${guide.slug}`} title={guide.title} description={guide.description} meta="OpenAI / Codex 工作流" />
          ))}
        </GuideIndex>

        <GuideIndex id="products" title="全部产品教程" description="按稳定产品分类查看购买前确认、交付方式和使用步骤。" empty={products.length === 0}>
          {products.map((guide) => <GuideCard key={guide.productSlug} href={`/guides/products/${guide.productSlug}`} title={guide.title} description={guide.description} meta={`${BRAND_NAMES[guide.brand]} / ${guide.productSlug}`} />)}
        </GuideIndex>

        <GuideIndex id="delivery" title="交付方式解释" description="同一种交付方式可能出现在多个品牌中，先理解控制权和数据边界。" empty={deliveries.length === 0}>
          {deliveries.map((guide) => <GuideCard key={guide.deliveryType} href={`/guides/delivery/${guide.deliveryType}`} title={guide.title} description={guide.summary} meta={guide.shortLabel} />)}
        </GuideIndex>

        <GuideIndex id="general" title="安全和售后指南" description="排查登录与激活问题，整理售后材料，保护账号、密钥和隐私。" empty={general.length === 0}>
          {general.map((guide) => <GuideCard key={guide.slug} href={`/guides/${guide.slug}`} title={guide.title} description={guide.description} meta="通用指南" />)}
        </GuideIndex>

        <Link href="/products" className="tactile flex min-h-14 items-center justify-between border-y border-[color:var(--line-strong)] py-4 text-sm font-semibold text-[color:var(--brand-strong)]">
          返回报价目录
          <ArrowRight size={18} aria-hidden="true" />
        </Link>
      </div>
    </main>
  );
}
