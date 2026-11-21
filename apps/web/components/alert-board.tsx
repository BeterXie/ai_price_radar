"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, Clock, MagnifyingGlass } from "@phosphor-icons/react";
import { ALERT_VIEWS, alertMoney, alertTime, currentAlertRows, nextAlertExpiry, serverAlignedNow, type AlertReport, type AlertView } from "@/lib/alert-report";

export function AlertBoard({ report, view, initialNow }: { report: AlertReport; view: AlertView; initialNow: number }) {
  const [now, setNow] = useState(initialNow);
  const [search, setSearch] = useState("");
  const [visibleCount, setVisibleCount] = useState(50);
  useEffect(() => {
    let started = performance.now();
    let serverNow = initialNow;
    let cancelled = false;
    let timer: number;
    const tick = () => {
      window.clearTimeout(timer);
      const alignedNow = serverAlignedNow(serverNow, performance.now() - started);
      setNow(alignedNow);
      timer = window.setTimeout(tick, Math.max(1, nextAlertExpiry(report, alignedNow) - alignedNow));
    };
    const calibrate = async () => {
      try {
        const response = await fetch("/alerts/clock", { cache: "no-store", signal: AbortSignal.timeout(4000) });
        if (!response.ok) return;
        const data = await response.json();
        if (cancelled || !Number.isFinite(data.now)) return;
        const receivedAt = performance.now();
        serverNow = Math.max(serverAlignedNow(serverNow, receivedAt - started), data.now);
        started = receivedAt;
        tick();
      } catch { /* Keep monotonic server time until the next refresh. */ }
    };
    const visible = () => { if (document.visibilityState === "visible") { tick(); void calibrate(); } };
    tick();
    void calibrate();
    document.addEventListener("visibilitychange", visible);
    return () => { cancelled = true; window.clearTimeout(timer); document.removeEventListener("visibilitychange", visible); };
  }, [report, initialNow]);
  const effectiveNow = Math.max(now, initialNow);
  const visibleRows = useMemo(() => ({
    drops: currentAlertRows(report, "drops", effectiveNow), rises: currentAlertRows(report, "rises", effectiveNow),
    team: currentAlertRows(report, "team", effectiveNow),
  }), [report, effectiveNow]);
  const rows = visibleRows[view];
  const query = search.trim().normalize("NFKC").toLocaleLowerCase();
  const items = rows.filter((row) => !query || `${row.product_name} ${row.shop_name}`.normalize("NFKC").toLocaleLowerCase().includes(query));
  const isTeam = view === "team";
  const stale = effectiveNow - Date.parse(report.published_at) > 2 * 3_600_000;
  return <>
    <div className="alert-tabs" role="navigation" aria-label="提醒榜单">
      {ALERT_VIEWS.map(({ key, label }) => <Link key={key} href={`/alerts?view=${key}`} aria-current={view === key ? "page" : undefined}>
        {label}<span>{visibleRows[key].length}</span>
      </Link>)}
    </div>
    <div className="alert-toolbar">
      <p>{isTeam ? "头车 ≤ ¥30 · 其他车 ≤ ¥20 · 价格从低到高" : view === "drops" ? "按降幅排序 · 同名同币种只展示最低价" : "按涨幅排序 · 同名同币种只展示最低价"}</p>
      <label className="alert-search"><MagnifyingGlass size={18} aria-hidden="true" /><span className="sr-only">筛选商品或商家</span>
        <input type="search" placeholder="筛选商品或商家" value={search} onChange={(e) => setSearch(e.target.value)} />
      </label>
    </div>
    {stale && <p className="alert-stale" role="status">报价已有一段时间未更新，请核对商品详情中的最新库存。</p>}
    <div className="alert-list" data-view={view}>
      <div className="alert-list-heading" aria-hidden="true"><span>商品 / 商家</span><span>{isTeam ? "结束时间（北京）" : "价格变动"}</span><span>快照价格</span><span /></div>
      {items.slice(0, visibleCount).map((row, index) => <article className="alert-row" key={row.offer_id}>
        <span className="alert-rank" aria-label={`第 ${index + 1} 项`}>{String(index + 1).padStart(2, "0")}</span>
        <div className="alert-product">
          <h2><Link href={`/offers/${row.offer_id}`}>{row.product_name}</Link></h2>
          <div className="alert-product-meta"><span>{row.shop_name}</span><span className="alert-stock">快照有货</span>{isTeam && <span>{row.is_head_car ? "头车" : "其他 Team 车"}</span>}</div>
        </div>
        <div className={`alert-change ${view}`}>
          {isTeam ? <><Clock size={17} aria-hidden="true" /><time dateTime={row.ends_at}>{alertTime(row.ends_at!)}</time><small>结束时间</small></> : <>
            {view === "drops" ? <ArrowDownRight size={18} aria-hidden="true" /> : <ArrowUpRight size={18} aria-hidden="true" />}
            <strong>{view === "drops" ? "降" : "涨"} {Number(row.old_price) === 0 ? alertMoney(Math.abs(Number(row.diff)), row.currency) : `${Math.abs(row.percent_change!)}%`}</strong>
            <small>{view === "drops" ? "省" : "增加"} {alertMoney(Math.abs(Number(row.diff)), row.currency)}</small>
          </>}
        </div>
        <div className="alert-price"><strong>{alertMoney(row.price, row.currency)}</strong>{!isTeam && <del>{alertMoney(row.old_price!, row.currency)}</del>}</div>
        <Link className="alert-offer-link" href={`/offers/${row.offer_id}`} aria-label={`查看${row.product_name}商品详情`}><span>查看商品</span><ArrowUpRight size={18} aria-hidden="true" /></Link>
      </article>)}
      {!items.length && <div className="alert-empty" role="status"><h2>{query ? "没有匹配的商品" : isTeam ? "暂时没有符合条件的 Team 车" : view === "drops" ? "最新一轮暂无降价商品" : "最新一轮暂无涨价商品"}</h2>
        <p>{query ? "试试其他商品名或商家名。" : isTeam ? "已结束或结束时间不明确的商品不进入提醒榜。" : "下一次报价更新后，这里会同步刷新。"}</p>
        {query ? <button className="button-secondary" onClick={() => setSearch("")}>清除筛选</button> : <Link className="button-secondary" href="/products">查看全部报价</Link>}
      </div>}
    </div>
    {items.length > visibleCount && <button className="button-secondary mt-6" onClick={() => setVisibleCount((count) => count + 50)}>继续查看 · 还有 {items.length - visibleCount} 条</button>}
    <p className="alert-footnote">{isTeam ? "同名、同结束时间的商品只保留最低价。结束时间从商家标题识别，具体规则请查看商品详情。" : "变动比较同一商家同一商品的前后报价，不代表历史最低价。"} 价格与库存以来源页面为准。</p>
  </>;
}
