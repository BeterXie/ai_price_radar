import type { Metadata } from "next";
import Link from "next/link";
import { ArrowSquareOut, ArrowsLeftRight, CaretDown, Info, ShieldCheck } from "@phosphor-icons/react/ssr";
import { AdLink } from "@/components/ad-link";
import { AdSlot } from "@/components/ad-slot";
import { PageHero, SectionIntro } from "@/components/page-shell";
import { PlatformIcon } from "@/components/platform-icon";
import { JsonLd, breadcrumbJsonLd } from "@/components/structured-data";
import { getMeta, getRelayStations } from "@/lib/api";
import { BRAND_TABS } from "@/lib/catalog";
import { relativeTime } from "@/lib/format";
import { SITE_URL } from "@/lib/site";
import type { RelayStationPublic } from "@/lib/types";

export const dynamic = "force-dynamic";

const canonical = `${SITE_URL}/relays`;

export const metadata: Metadata = {
  title: "API 中转站目录｜模型覆盖、计费方式与入口",
  description: "整理公开 AI API 中转站的模型覆盖、计费方式与价格说明，作为 OpenAI、Claude、Gemini 报价目录的补充入口。中转站信息由站点运营者维护，不构成推荐或担保。",
  alternates: { canonical },
  openGraph: {
    title: "API 中转站目录 · AI Price Memory",
    description: "公开 AI API 中转站的模型覆盖、计费方式与价格说明。",
    url: canonical,
    type: "website",
  },
};

function RelayCard({ station }: { station: RelayStationPublic }) {
  const host = (() => {
    try {
      return station.url ? new URL(station.url).hostname : "";
    } catch {
      return "";
    }
  })();
  return (
    <article className="relay-card" data-sponsored={station.is_sponsored ? "true" : "false"}>
      <div className="relay-card-main">
        <div className="relay-card-header">
          <span className="relay-card-mark" aria-hidden="true"><ArrowsLeftRight size={24} /></span>
          <div className="min-w-0">
            <h3 className="relay-card-title">
              {station.url ? (
                <AdLink kind="relays" id={station.id} href={station.url} className="hover:underline underline-offset-4">
                  {station.name}
                </AdLink>
              ) : station.name}
            </h3>
            {host ? <p className="relay-card-host mono">{host}</p> : null}
          </div>
          {station.is_sponsored ? <span className="ad-badge shrink-0">赞助</span> : null}
        </div>
        {station.tagline ? <p className="relay-card-tagline">{station.tagline}</p> : null}
        {station.supported_models.length > 0 ? (
          <section className="relay-models" aria-label="模型覆盖">
            <h4 className="relay-section-label">支持模型 <span>{station.supported_models.length}</span></h4>
            <div className="relay-chip-row" aria-label="支持的模型">
              {station.supported_models.slice(0, 10).map((model) => (
                <span key={model} className="relay-chip mono">{model}</span>
              ))}
            </div>
            {station.supported_models.length > 10 ? (
              <details className="relay-models-more">
                <summary>查看其余 {station.supported_models.length - 10} 个模型</summary>
                <div className="relay-chip-row">
                  {station.supported_models.slice(10).map((model) => <span key={model} className="relay-chip mono">{model}</span>)}
                </div>
              </details>
            ) : null}
          </section>
        ) : null}
        {station.tags.length > 0 ? (
          <div className="relay-tags" aria-label="特性标签">
            {station.tags.map((tag) => <span key={tag}>{tag}</span>)}
          </div>
        ) : null}
      </div>
      <div className="relay-card-aside">
        <dl className="relay-facts">
          <div><dt>价格说明</dt><dd className="relay-price">{station.price_note || "暂未提供价格说明"}</dd></div>
          {station.billing_note ? <div><dt>计费方式</dt><dd>{station.billing_note}</dd></div> : null}
        </dl>
        <p className="relay-price-source">站点提供的报价，以来源页面为准</p>
        {station.url ? (
          <AdLink kind="relays" id={station.id} href={station.url} className="button-primary tactile relay-visit" ariaLabel={`前往 ${station.name}（新窗口打开）`}>
            前往中转站 <ArrowSquareOut size={15} />
          </AdLink>
        ) : null}
      </div>
      <div className="relay-card-footer">
        {station.description ? (
          <details className="relay-description">
            <summary>站点详细介绍 <CaretDown size={14} aria-hidden="true" /></summary>
            <p className="relay-card-desc">{station.description}</p>
          </details>
        ) : null}
        <span className="relay-updated">
          {station.updated_at ? `资料更新于 ${relativeTime(station.updated_at)}` : "资料由站点运营者维护"}
        </span>
      </div>
    </article>
  );
}

export default async function RelaysPage() {
  const [relays, meta] = await Promise.all([
    getRelayStations().catch(() => null),
    getMeta().catch(() => null),
  ]);
  const enabled = relays ? relays.enabled : meta?.relay_hub_enabled !== false;
  const stations = relays?.items ?? [];

  return (
    <main id="main-content" className="shell" data-vds-schema="v3.1" data-vds-layer="field" data-vds-action="scope-rails directory-cards evidence-disclaimer">
      <JsonLd data={breadcrumbJsonLd([
        { name: "首页", path: "/" },
        { name: "AI 商品报价", path: "/products" },
        { name: "中转站", path: "/relays" },
      ])} />
      <PageHero
        compact
        eyebrow="平台 · 中转站"
        title="API 中转站"
        description={<>中转站把 OpenAI、Claude、Gemini 等模型接口统一转发并按量计费，适合开发者与高频 API 用户。这里列出的站点由运营者在后台维护，用来补充报价目录里“中转 / 反代”形态的商品；<strong>收录不等于推荐或担保</strong>，充值前请自行核对余额有效期、倍率与退款规则。</>}
        meta={<>
          <span className="inline-flex items-center gap-1.5"><ArrowsLeftRight size={15} />{stations.length} 个中转站</span>
          <span className="inline-flex items-center gap-1.5"><ShieldCheck size={15} />链接仅接受公开 HTTPS 地址</span>
        </>}
      />

      <section className="border-b border-[color:var(--line-strong)] py-4" aria-label="平台切换">
        <nav className="filter-rail" aria-label="品牌筛选">
          <span className="filter-label">品牌</span>
          <div className="filter-group">
            <Link href="/products" prefetch={true} className="filter-chip filter-all"><PlatformIcon platform="" />全部</Link>
            <div className="filter-options">
              {BRAND_TABS.map((brand) => (
                <Link key={brand} href={`/products?brand=${encodeURIComponent(brand)}`} prefetch={true} className="filter-chip">
                  <PlatformIcon platform={brand} />{brand}
                </Link>
              ))}
              <Link href="/relays" aria-current="page" className="filter-chip"><PlatformIcon platform="中转站" />中转站</Link>
            </div>
          </div>
        </nav>
      </section>

      <div className="content-stage py-10 sm:py-12">
        <AdSlot placement="relay_hub" limit={2} className="mb-8" />

        {!enabled ? (
          <section className="empty-state" role="status">
            <h2 className="text-2xl font-semibold text-[color:var(--ink)]">中转站专区暂未开放</h2>
            <p className="mt-3 text-sm leading-6">运营者已暂时关闭该专区。可以先浏览报价目录中的“中转 / 反代”形态商品。</p>
            <Link href="/products?comparable=false&delivery_type=relay_api" className="button-primary mt-6">查看中转类报价</Link>
          </section>
        ) : stations.length === 0 ? (
          <section className="empty-state" role="status">
            <h2 className="text-2xl font-semibold text-[color:var(--ink)]">{relays ? "还没有收录中转站" : "中转站目录暂时无法加载"}</h2>
            <p className="mt-3 text-sm leading-6">
              {relays
                ? "运营者尚未在后台添加中转站。如果你运营一个公开的 API 中转站，欢迎通过商务合作渠道联系收录。"
                : "可以稍后刷新，或先浏览报价目录中的“中转 / 反代”形态商品。"}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/products?comparable=false&delivery_type=relay_api" className="button-primary">查看中转类报价</Link>
              {meta?.advertise_enabled ? <Link href="/advertise" className="button-secondary">申请收录 / 商务合作</Link> : null}
            </div>
          </section>
        ) : (
          <>
            <SectionIntro
              title="已收录中转站"
              description={<>赞助站点会带有明确的“赞助”标识并排在前面；其余按运营者设置的顺序展示。模型列表以站点公开说明为准，实际可用性可能随时变化。</>}
            />
            <div className="relay-grid mt-6">
              {stations.map((station) => <RelayCard key={station.id} station={station} />)}
            </div>
          </>
        )}

        <section className="evidence-callout mt-12" data-vds-layer="evidence">
          <div className="flex items-start gap-3">
            <Info size={20} className="mt-0.5 shrink-0 text-[color:var(--info)]" />
            <div className="text-sm leading-6 text-[color:var(--muted)]">
              <p className="font-semibold text-[color:var(--ink)]">中转站与报价目录的关系</p>
              <p className="mt-1">报价目录只统计能直接比较的标准商品（官方直充、成品账号等），中转 / 反代形态的商品不参与主最低价。若想在目录中查看店铺出售的中转类商品，可以切换“比较范围”为“包含相关商品”，或直接打开 <Link href="/products?comparable=false&delivery_type=relay_api" className="underline underline-offset-4">中转 / 反代报价</Link>。</p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
