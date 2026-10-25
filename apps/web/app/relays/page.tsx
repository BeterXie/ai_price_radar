import type { Metadata } from "next";
import Link from "next/link";
import { Info, ListBullets, SquaresFour } from "@phosphor-icons/react/ssr";
import { AdSlot } from "@/components/ad-slot";
import { PlatformIcon } from "@/components/platform-icon";
import { JsonLd, breadcrumbJsonLd } from "@/components/structured-data";
import { getMeta, getRelayStations } from "@/lib/api";
import { BRAND_TABS } from "@/lib/catalog";
import { SITE_URL } from "@/lib/site";
import { RelayStationCard } from "@/components/relay-station-card";
import { RelayRefresh } from "@/components/relay-refresh";

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

export default async function RelaysPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const requestedView = Array.isArray(params.view) ? params.view.at(-1) : params.view;
  const view = requestedView === "card" ? "card" : "list";
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

      <div className="content-stage py-5 sm:py-6">
        <AdSlot placement="relay_hub" limit={2} className="mb-8" />

        {!enabled ? (
          <section className="empty-state" role="status">
            <h1 className="text-2xl font-semibold text-[color:var(--ink)]">中转站专区暂未开放</h1>
            <p className="mt-3 text-sm leading-6">运营者已暂时关闭该专区。可以先浏览报价目录中的“中转 / 反代”形态商品。</p>
            <Link href="/products?comparable=false&delivery_type=relay_api" className="button-primary mt-6">查看中转类报价</Link>
          </section>
        ) : stations.length === 0 ? (
          <section className="empty-state" role="status">
            <h1 className="text-2xl font-semibold text-[color:var(--ink)]">{relays ? "还没有收录中转站" : "中转站目录暂时无法加载"}</h1>
            <p className="mt-3 text-sm leading-6">
              {relays
                ? "如果你运营一个公开的 API 中转站，可以提交官网、Base URL 和检测密钥申请收录。"
                : "可以稍后刷新，或先浏览报价目录中的“中转 / 反代”形态商品。"}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/shops/submit?type=relay" className="button-primary">申请录入中转站</Link>
              <Link href="/products?comparable=false&delivery_type=relay_api" className="button-secondary">查看中转类报价</Link>
              {meta?.advertise_enabled ? <Link href="/advertise" className="button-secondary">申请收录 / 商务合作</Link> : null}
            </div>
          </section>
        ) : (
          <>
            <div className="relay-directory-toolbar">
              <h1>已收录中转站 <span>{stations.length}</span></h1>
              <div className="relay-directory-actions">
                <RelayRefresh />
                <Link href="/shops/submit?type=relay" className="button-secondary relay-apply">申请录入中转站</Link>
                <div role="group" aria-label="中转站展示方式" className="inline-flex items-center gap-1 rounded-xl border border-[color:var(--line)] bg-[color:var(--panel)] p-1 text-xs">
                  {(["list", "card"] as const).map((mode) => {
                    const ModeIcon = mode === "card" ? SquaresFour : ListBullets;
                    return (
                      <Link
                        key={mode}
                        href={mode === "card" ? "/relays?view=card" : "/relays"}
                        scroll={false}
                        aria-label={mode === "card" ? "卡片展示" : "列表展示"}
                        aria-current={view === mode ? "true" : undefined}
                        className={`inline-flex min-h-11 items-center gap-1.5 rounded-lg px-3 font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand)] ${view === mode ? "bg-[color:var(--brand-soft)] text-[color:var(--brand-strong)]" : "hover:bg-[color:var(--hover)] hover:text-[color:var(--foreground)]"}`}
                      >
                        <ModeIcon size={16} aria-hidden />
                        {mode === "card" ? "卡片" : "列表"}
                      </Link>
                    );
                  })}
                </div>
              </div>
            </div>
            <div className="relay-grid mt-4" data-view={view}>
              {stations.map((station) => <RelayStationCard key={station.id} station={station} view={view} />)}
            </div>
            <details className="relay-directory-notes">
              <summary>检测指标与展示说明</summary>
              <p>每小时探测当前配置的模型。站点 PING 为检测服务器到 API 的 TCP/TLS 建连耗时；可用率统计近 7 天，缓存命中率与首 Token P50 统计近 24 小时。缓存按接口返回的缓存读取 Token 占比计算，短提示可能不触发缓存；缺失数据不计为零。</p>
              <p>历史条从旧到新，绿为成功、红为异常、黄为配置诊断、灰为无样本。赞助站点带有“赞助”标识并优先展示，其余按运营者设置的顺序排列。收录不构成推荐或担保。</p>
            </details>
          </>
        )}

        <section className="evidence-callout mt-6" data-vds-layer="evidence">
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
