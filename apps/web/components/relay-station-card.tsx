import { ArrowSquareOut, CaretDown } from "@phosphor-icons/react/ssr";
import { AdLink } from "@/components/ad-link";
import { RelayHealthPanel, RelayHealthStatus, RelayProbeIdentity } from "@/components/relay-health";
import { RelayStationIcon } from "@/components/relay-station-icon";
import { exactTime, relativeTime } from "@/lib/format";
import type { RelayStationPublic } from "@/lib/types";

export function RelayStationCard({ station, view = "card" }: { station: RelayStationPublic; view?: "card" | "list" }) {
  const isList = view === "list";
  let host = "";
  try { host = station.url ? new URL(station.url).hostname : ""; } catch { /* The API omits unsafe public URLs. */ }
  const hasDetails = Boolean(host || station.updated_at || station.description || station.tagline || station.supported_models.length || station.tags.length || station.price_note || station.billing_note);
  const pricing = (
    <section className="relay-pricing" aria-label="站点报价">
      <h4 className="relay-section-heading">站点报价</h4>
      <p className="relay-price">{station.price_note || "价格待补充"}</p>
      {station.billing_note ? <p className="relay-billing"><span>计费方式</span>{station.billing_note}</p> : null}
      <p className="relay-price-source">站方提供 · 以官网价格为准</p>
    </section>
  );
  const visit = station.url ? <AdLink kind="relays" id={station.id} href={station.url} className="button-secondary relay-visit" ariaLabel={`前往 ${station.name}（新窗口打开）`}>前往官网 <ArrowSquareOut size={14} /></AdLink> : null;
  const updated = <span className="relay-updated">资料更新 {station.updated_at ? <time dateTime={station.updated_at} title={exactTime(station.updated_at)}>{relativeTime(station.updated_at)}</time> : "待确认"}</span>;
  return (
    <article className={`relay-card${isList ? " relay-list-item" : ""}`} data-sponsored={station.is_sponsored ? "true" : "false"} aria-labelledby={`relay-${station.id}-title`}>
      <div className={isList ? "relay-list-summary" : "relay-card-summary"}>
        <header className="relay-card-header">
          <RelayStationIcon id={station.id} name={station.name} website={station.url} />
          <div className="min-w-0 flex-1">
            <h3 id={`relay-${station.id}-title`} className="relay-card-title" title={station.name}>
              {station.url ? <AdLink kind="relays" id={station.id} href={station.url} className="hover:underline underline-offset-4">{station.name}</AdLink> : station.name}
            </h3>
            <RelayProbeIdentity health={station.health} />
          </div>
        </header>
        {isList ? (
          <>
            <div className="relay-list-overview">
              <div className="min-w-0">
                <p className="relay-list-price" title={station.price_note || undefined}>{station.price_note || "价格待补充"}</p>
                {station.billing_note ? <p className="relay-list-billing" title={station.billing_note}>{station.billing_note}</p> : null}
              </div>
            </div>
          </>
        ) : null}
        <div className="relay-station-status">
          {station.is_sponsored ? <span className="ad-badge">赞助</span> : null}
          <RelayHealthStatus health={station.health} />
          {isList ? visit : null}
        </div>
      </div>
      <RelayHealthPanel health={station.health} />
      {hasDetails ? (
        <details className="relay-description">
          <summary><span className="relay-details-label">{isList ? "报价与详情" : station.price_note || "报价与详情"}</span><CaretDown size={14} aria-hidden="true" /></summary>
          {pricing}
          {host ? <p className="relay-card-host mono">{host}</p> : null}
          {station.supported_models.length > 0 ? <div className="relay-chip-row mt-3" aria-label="支持的模型">{station.supported_models.map((model) => <span key={model} className="relay-chip mono">{model}</span>)}</div> : null}
          {station.tagline ? <p className="relay-card-desc">{station.tagline}</p> : null}
          {station.tags.length > 0 ? <p className="relay-card-desc">特性：{station.tags.join("、")}</p> : null}
          {station.description ? <p className="relay-card-desc">{station.description}</p> : null}
          <p className="mt-3">{updated}</p>
        </details>
      ) : null}
      {!isList ? <footer className="relay-card-footer">{visit}</footer> : null}
    </article>
  );
}
