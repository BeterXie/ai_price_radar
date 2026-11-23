import Link from "next/link";
import { ArrowUpRight } from "@phosphor-icons/react/ssr";
import { AdLink } from "@/components/ad-link";
import type { RelayStationListOut } from "@/lib/types";

/** Use the live, approved relay identity and link without borrowing another model's metrics. */
export function JevRelayProduct({ data }: { data: RelayStationListOut | null }) {
  const station = data?.enabled ? data.items.find((item) => {
    try {
      const url = new URL(item.url);
      return url.protocol === "https:" && ["llmp.org", "www.llmp.org"].includes(url.hostname);
    } catch { return false; }
  }) : undefined;

  return (
    <section aria-labelledby="jev-access-title">
      <header className="jev-catalog-heading">
        <h2 id="jev-access-title">API 接入</h2>
      </header>
      {station ? (
        <article className="relay-card jev-product-card" data-sponsor="llmport" aria-labelledby="jev-product-title">
          <header className="relay-card-header">
            <span className="relay-card-mark" aria-hidden="true"><img src="/sponsors/llmport.png" width={30} height={30} alt="" /></span>
            <div>
              <h2 id="jev-product-title" className="relay-card-title"><AdLink kind="relays" id={station.id} href={station.url}>{station.name}</AdLink></h2>
              <p className="relay-brand-note">JEV API · 站长自营</p>
            </div>
          </header>
          <div className="jev-product-copy">
            <p className="jev-product-value">JEV 官方半价，毫秒级延迟</p>
            <p className="jev-product-description">通过 LLMPort 接入 JEV API，享官方价格 5 折。官key 6.2 Astra 抢先体验。注册即送 1 美元试用额度，先体验再使用。</p>
          </div>
          <footer className="jev-product-footer">
            <AdLink kind="relays" id={station.id} href={station.url} className="button-secondary relay-visit" ariaLabel="前往 LLMPort 注册试用（新窗口打开）">注册试用 <ArrowUpRight size={16} aria-hidden="true" /></AdLink>
            <p className="relay-price-source">站方提供 · 以官网为准</p>
          </footer>
        </article>
      ) : (
        <div className="catalog-empty" role="status">
          <h2>{data ? "JEV 接入暂未开放" : "JEV 接入信息暂时无法加载"}</h2>
          <p>{data ? "可以稍后再来查看。" : "请刷新页面重试。"}</p>
          <Link href="/brands/jev" className="button-secondary">刷新页面</Link>
        </div>
      )}
    </section>
  );
}
