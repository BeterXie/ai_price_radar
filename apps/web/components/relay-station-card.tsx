"use client";

import { useEffect, useState } from "react";
import { ArrowSquareOut, CaretDown } from "@phosphor-icons/react/ssr";
import { AdLink } from "@/components/ad-link";
import { RelayHealthPanel, RelayHealthStatus, RelayProbeIdentity } from "@/components/relay-health";
import { RelayStationIcon } from "@/components/relay-station-icon";
import { RelayModelCatalog } from "@/components/relay-model-catalog";
import { exactTime, relativeTime } from "@/lib/format";
import { relayGroups } from "@/lib/relay-groups";
import type { RelayStationPublic } from "@/lib/types";

export function RelayStationCard({ station, view = "card", initialNow }: { station: RelayStationPublic; view?: "card" | "list"; initialNow: number }) {
  const [now, setNow] = useState(initialNow);
  useEffect(() => { setNow(Date.now()); }, [initialNow]);
  const isList = view === "list";
  const groups = relayGroups(station);
  const [selectedId, setSelectedId] = useState("");
  const group = groups.find((item) => item.id === selectedId) || groups[0];
  const automatic = station.model_catalog?.group_catalog;
  const groupPicker = <div className="relay-group-picker flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs" aria-label={`${station.name} 分组倍率`}>
    {group ? <>
      <select aria-label={`${station.name} 分组`} value={group.id} onChange={(event) => setSelectedId(event.target.value)} className="max-w-44 min-w-0 rounded border border-[color:var(--line)] bg-[color:var(--panel)] px-1.5 py-1 text-xs">
        {groups.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
      <span className="whitespace-nowrap font-semibold">{group.ratio === null ? "倍率未公开" : `${group.ratio.toLocaleString("zh-CN", { maximumFractionDigits: 6 })}×`}</span>
      {group.effective_ratio !== null && group.effective_ratio !== undefined && group.effective_ratio !== group.ratio ? <span className="whitespace-nowrap text-[color:var(--muted)]">当前生效 {group.effective_ratio.toLocaleString("zh-CN", { maximumFractionDigits: 6 })}×</span> : null}
      <span className="text-[color:var(--muted)]">{group.source}{group.source !== "站方填写" && automatic?.status !== "ok" ? " · 上次资料" : ""}</span>
    </> : <span className="text-[color:var(--muted)]">分组倍率待补充</span>}
  </div>;
  let host = "";
  try { host = station.url ? new URL(station.url).hostname : ""; } catch { /* The API omits unsafe public URLs. */ }
  const hasDetails = Boolean(host || station.updated_at || station.description || station.tagline || station.supported_models.length || station.model_catalog?.checked_at || groups.length || station.tags.length || station.price_note || station.billing_note);
  const pricing = (
    <section className="relay-pricing" aria-label="站点报价">
      <h4 className="relay-section-heading">站点报价</h4>
      <p className="relay-price">{station.price_note || "价格待补充"}</p>
      {station.billing_note ? <p className="relay-billing"><span>计费方式</span>{station.billing_note}</p> : null}
      <p className="relay-price-source">站方提供 · 以官网价格为准</p>
    </section>
  );
  const visit = station.url ? <AdLink kind="relays" id={station.id} href={station.url} className="button-secondary relay-visit" ariaLabel={`前往 ${station.name}（新窗口打开）`}>前往官网 <ArrowSquareOut size={14} /></AdLink> : null;
  const updated = <span className="relay-updated">资料更新 {station.updated_at ? <time dateTime={station.updated_at} title={exactTime(station.updated_at)}>{relativeTime(station.updated_at, now)}</time> : "待确认"}</span>;
  return (
    <article id={`relay-${station.id}`} className={`relay-card${isList ? " relay-list-item" : ""}`} data-sponsored={station.is_sponsored ? "true" : "false"} aria-labelledby={`relay-${station.id}-title`}>
      <div className={isList ? "relay-list-summary" : "relay-card-summary"}>
        <header className="relay-card-header">
          <RelayStationIcon key={station.url} id={station.id} name={station.name} website={station.url} />
          <div className="min-w-0 flex-1">
            <h3 id={`relay-${station.id}-title`} className="relay-card-title" title={station.name}>
              {station.url ? <AdLink kind="relays" id={station.id} href={station.url} className="hover:underline underline-offset-4">{station.name}</AdLink> : station.name}
            </h3>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <RelayProbeIdentity health={station.health} />
              {station.model_catalog?.synced_at ? <span className="text-xs text-[color:var(--muted)]">{station.model_catalog.models.length}{station.model_catalog.truncated ? "+" : ""} 个模型</span> : null}
            </div>
          </div>
        </header>
        {isList ? (
          <>
            <div className="relay-list-overview">
              <div className="min-w-0">
                {groupPicker}
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
      {!isList ? <div className="col-span-full mt-2 min-w-0">{groupPicker}</div> : null}
      <RelayHealthPanel health={station.health} now={now} />
      {hasDetails ? (
        <details className="relay-description">
          <summary><span className="relay-details-label">{isList ? "报价与详情" : station.price_note || "报价与详情"}</span><CaretDown size={14} aria-hidden="true" /></summary>
          {pricing}
          {host ? <p className="relay-card-host mono">{host}</p> : null}
          {!station.model_catalog?.synced_at && station.supported_models.length > 0 ? <div className="relay-chip-row mt-3" aria-label="站方填写的模型">{station.supported_models.map((model) => <span key={model} className="relay-chip mono">{model}</span>)}</div> : null}
          {group ? <div className="mt-2 text-xs text-[color:var(--muted)]">
            <p>{group.description}</p>
            <p>分组倍率为站内计费系数，最终费用以官网为准。{group.source === "公开价格接口" || group.source === "模型广场" ? "公开分组不代表当前密钥均可使用。" : ""}探活数据来自已配置密钥，切换分组仅查看资料。</p>
            {group.source !== "站方填写" && automatic?.synced_at ? <p>分组同步于 <time dateTime={automatic.synced_at} title={exactTime(automatic.synced_at)}>{relativeTime(automatic.synced_at, now)}</time></p> : null}
          </div> : null}
          <RelayModelCatalog key={group?.id || "all"} catalog={station.model_catalog} group={group} now={now} />
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
