import { ArrowSquareOut, CaretDown } from "@phosphor-icons/react/ssr";
import { AdLink } from "@/components/ad-link";
import { RelayHealthPanel } from "@/components/relay-health";
import { RelayStationIcon } from "@/components/relay-station-icon";
import { exactTime, relativeTime } from "@/lib/format";
import type { RelayStationPublic } from "@/lib/types";

export function RelayStationCard({ station }: { station: RelayStationPublic }) {
  let host = "";
  try { host = station.url ? new URL(station.url).hostname : ""; } catch { /* The API omits unsafe public URLs. */ }
  const hasDetails = Boolean(station.description || station.tagline || station.supported_models.length || station.tags.length > 3 || station.health?.probe_model);
  return (
    <article className="relay-card" data-sponsored={station.is_sponsored ? "true" : "false"} aria-labelledby={`relay-${station.id}-title`}>
      <header className="relay-card-header">
        <RelayStationIcon id={station.id} name={station.name} website={station.url} />
        <div className="min-w-0 flex-1">
          <h3 id={`relay-${station.id}-title`} className="relay-card-title">
            {station.url ? <AdLink kind="relays" id={station.id} href={station.url} className="hover:underline underline-offset-4">{station.name}</AdLink> : station.name}
          </h3>
          {host ? <p className="relay-card-host mono">{host}</p> : null}
        </div>
        {station.is_sponsored ? <span className="ad-badge">赞助</span> : null}
      </header>
      <div className="relay-card-comparison">
        <section className="relay-pricing" aria-label="站点报价">
          <h4 className="relay-section-heading">站点报价</h4>
          <p className="relay-price">{station.price_note || "价格待补充"}</p>
          {station.billing_note ? <p className="relay-billing"><span>计费方式</span>{station.billing_note}</p> : null}
          <p className="relay-price-source">站方提供 · 以官网价格为准</p>
        </section>
        <RelayHealthPanel health={station.health} />
      </div>
      {station.tags.length > 0 ? <div className="relay-tags" aria-label="特性标签">{station.tags.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}{station.tags.length > 3 ? <span>+{station.tags.length - 3}</span> : null}</div> : null}
      {hasDetails ? (
        <details className="relay-description">
          <summary>{station.supported_models.length > 0 ? `${station.supported_models.length} 个模型与站点介绍` : "站点详细介绍"} <CaretDown size={14} aria-hidden="true" /></summary>
          {station.supported_models.length > 0 ? <div className="relay-chip-row mt-3" aria-label="支持的模型">{station.supported_models.map((model) => <span key={model} className="relay-chip mono">{model}</span>)}</div> : null}
          {station.health?.probe_model ? <p className="relay-card-desc">检测模型：{station.health.probe_model}。绿色为成功、红色为异常、黄色为配置诊断，灰色表示无样本；配置诊断不计入成功率。</p> : null}
          {station.tagline ? <p className="relay-card-desc">{station.tagline}</p> : null}
          {station.tags.length > 3 ? <p className="relay-card-desc">特性：{station.tags.slice(3).join("、")}</p> : null}
          {station.description ? <p className="relay-card-desc">{station.description}</p> : null}
        </details>
      ) : null}
      <footer className="relay-card-footer">
        <span className="relay-updated">资料更新 {station.updated_at ? <time dateTime={station.updated_at} title={exactTime(station.updated_at)}>{relativeTime(station.updated_at)}</time> : "待确认"}</span>
        {station.url ? <AdLink kind="relays" id={station.id} href={station.url} className="button-secondary relay-visit" ariaLabel={`前往 ${station.name}（新窗口打开）`}>前往官网 <ArrowSquareOut size={14} /></AdLink> : null}
      </footer>
    </article>
  );
}
