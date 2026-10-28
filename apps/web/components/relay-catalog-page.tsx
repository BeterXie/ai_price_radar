import Link from "next/link";
import { ListBullets, SquaresFour } from "@phosphor-icons/react/ssr";
import { AdSlot } from "@/components/ad-slot";
import { PlatformIcon } from "@/components/platform-icon";
import { JsonLd, breadcrumbJsonLd } from "@/components/structured-data";
import { getMeta, getRelayStations } from "@/lib/api";
import { BRAND_TABS, RELAY_CATALOG_HREF, STANDALONE_PRODUCTS } from "@/lib/catalog";
import { RelayStationCard } from "@/components/relay-station-card";
import { RelayRefresh } from "@/components/relay-refresh";
import { single, type RawSearchParams } from "@/components/product-workspace";

export async function RelayCatalogPage({ rawParams, basePath }: { rawParams: RawSearchParams; basePath: "/products" | "/relays" }) {
  const view = single(rawParams, "view") === "card" ? "card" : "list";
  const viewHref = (mode: "list" | "card") => {
    const query = new URLSearchParams();
    if (basePath === "/products") query.set("brand", "中转站");
    if (mode === "card") query.set("view", "card");
    return `${basePath}${query.size ? `?${query}` : ""}`;
  };
  const [relays, meta] = await Promise.all([
    getRelayStations().catch(() => null),
    getMeta().catch(() => null),
  ]);
  const enabled = relays ? relays.enabled : meta?.relay_hub_enabled !== false;
  const stations = relays?.items ?? [];
  const initialNow = Date.now();

  return (
    <main id="main-content" className="shell" data-vds-schema="v3.1" data-vds-layer="field" data-vds-action="scope-rails directory-cards evidence-disclaimer">
      <JsonLd data={breadcrumbJsonLd([
        { name: "首页", path: "/" },
        { name: "AI 商品报价", path: "/products" },
        { name: "中转站", path: "/relays" },
      ])} />
      <section className="border-b border-[color:var(--line-strong)] py-4" aria-label="平台切换">
        <nav className="filter-rail" aria-label="品牌与商品筛选">
          <span className="filter-label">品牌</span>
          <div className="filter-group">
            <Link href="/products" prefetch={true} className="filter-chip filter-all"><PlatformIcon platform="" />全部</Link>
            <div className="filter-options">
              {BRAND_TABS.map((brand) => (
                <Link key={brand} href={`/products?brand=${encodeURIComponent(brand)}`} prefetch={true} className="filter-chip">
                  <PlatformIcon platform={brand} />{brand}
                </Link>
              ))}
              {STANDALONE_PRODUCTS.map((product) => <Link key={product.slug} href={`/products/${product.slug}`} className="filter-chip"><PlatformIcon platform={product.label} />{product.label}</Link>)}
              <Link href={RELAY_CATALOG_HREF} aria-current="page" className="filter-chip"><PlatformIcon platform="中转站" />中转站</Link>
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
                        href={viewHref(mode)}
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
            <p className="mt-2 text-xs leading-6 text-[color:var(--muted)]">耗时来自糖果题：首字等待包含推理时间，最终仅输出一个整数，因此可能接近总耗时。P50 为近 24 小时样本的中位数。</p>
            <div className="relay-grid mt-4" data-view={view}>
              {stations.map((station) => <RelayStationCard key={station.id} station={station} view={view} initialNow={initialNow} />)}
            </div>
            <details className="relay-directory-notes">
              <summary>检测指标与展示说明</summary>
              <p>每小时对当前配置的模型运行一轮测试。首次请求回答固定糖果题，最终整数 21 为通过，其他整数为未通过；超时、截断或无法识别的回答单列为无法判定。通过率只反映这道题的结果，不认证模型身份或整体能力。</p>
              <p>第二次请求重复相同长输入，不附带前次答案。重复输入缓存率先逐次计算缓存读取 Token / 总输入 Token，再从近 24 小时有效样本中各去掉一个最高值和最低值，取剩余样本的算术平均；极值并列时也只各去掉一条，不足 3 次时显示样本不足。原始记录保留，旧短提示、输入不足和缺失用量不计入，明确返回零的有效样本仍参与排序。这是去极值后的测试均值，与后台按 Token 加权的业务缓存率口径不同。同一会话或固定缓存标识不能保证上游命中缓存。</p>
              <p>站点 PING 为检测服务器到 API 的 TCP/TLS 建连耗时。糖果题总耗时为最近一次首次请求从发起到响应结束的时间；糖果题首字 P50 为近 24 小时成功流式首次请求到首个答案文本的等待时间中位数，包含上游排队和推理等待。心跳与思考片段不作为首字。题目要求仅输出最终整数，所以两项耗时可能接近，不能直接视为普通短问答的响应速度。可用率统计近 7 天首次请求的成功比例。</p>
              <p>历史条从旧到新，绿为成功、红为异常、黄为配置诊断、灰为无样本。赞助站点带有“赞助”标识并优先展示，其余按运营者设置的顺序排列。收录不构成推荐或担保。</p>
              <p>如需查看店铺出售的中转类商品，可浏览 <Link href="/products?comparable=false&delivery_type=relay_api" className="underline underline-offset-4">中转 / 反代商品报价</Link>。</p>
            </details>
          </>
        )}

      </div>
    </main>
  );
}
