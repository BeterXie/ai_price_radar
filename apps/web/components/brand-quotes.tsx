"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowUpRight, Fire, Storefront, X } from "@phosphor-icons/react";
import { SITE_ID } from "@/lib/brands";
import { quoteBrand, quoteCategory, quoteInventory, quoteProductHref } from "@/lib/brand-quotes";
import { money, exactTime, relativeTime } from "@/lib/format";
import { WARRANTY_LABELS } from "@/lib/catalog";
import { fetchGroupShopOffers } from "@/lib/group-offers";
import { PlatformIcon } from "@/components/platform-icon";
import type { ContextualAds, Offer, OfferGroup } from "@/lib/types";
import { SponsorCard } from "@/components/sponsor-card";

type Quote = { offer: Offer; slug: string; name?: string; group?: OfferGroup };
type Activity = { window_days: number; end_at: string; items: { offer_id: number; click_count: number }[] };
type QuoteActivity = { count: number; endAt: string } | null;
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "";
const isMarketTable = SITE_ID === "pricememo" || SITE_ID === "aiprice";

function Visit({ offer }: { offer: Offer }) {
  if (!offer.source_url) return <span className="quote-no-link">暂无原站链接</span>;
  return <a className="quote-visit" href={offer.source_url} target="_blank" rel="nofollow noreferrer" onClick={() => {
    void fetch(`${apiBase}/api/v1/offers/${offer.id}/click`, { method: "POST", credentials: "include", keepalive: true }).catch(() => {});
  }} aria-label={`去原站下单：${offer.shop_name} · ${offer.original_name}（新窗口打开）`}>去原站下单<ArrowUpRight size={14} aria-hidden /></a>;
}

function Caution({ offer }: { offer: Offer }) {
  if (offer.is_comparable && offer.is_trusted_price) return null;
  return <span className="quote-caution">{!offer.is_comparable ? "相关商品 · 不直接比价" : "价格偏离同类报价"}</span>;
}

function Heat({ activity, grouped, failed }: { activity?: QuoteActivity; grouped: boolean; failed: boolean }) {
  return <span className="quote-heat" data-has-value={Boolean(activity)} title={`${grouped ? "本组同款商品各店铺" : "这条店铺报价"}最近 7 天访问原站次数，非销量。${activity ? `统计截至 ${exactTime(activity.endAt)}` : ""}`}><Fire size={13} aria-hidden /><span><span className="quote-heat-label">近7天访问 </span><b>{activity ? activity.count.toLocaleString("zh-CN") : failed || activity === null ? "暂不可用" : "加载中"}</b></span></span>;
}

export function QuoteDetails({ quote, view, snapshotId, filterQuery, onClose, sponsor, standalone = false }: { quote: Quote; view: "shops" | "description"; snapshotId?: number | null; filterQuery: string; onClose?: () => void; sponsor?: ContextualAds["detail"]; standalone?: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [shops, setShops] = useState<Offer[] | null>(quote.group && quote.group.offer_count > 1 ? null : [quote.offer]);
  const [description, setDescription] = useState(quote.offer.original_description || "");
  const [failed, setFailed] = useState(false);
  const [descriptionFailed, setDescriptionFailed] = useState(false);
  const [refreshed, setRefreshed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (standalone) return;
    const node = dialog.current;
    const previous = document.activeElement as HTMLElement | null;
    node?.showModal();
    return () => { node?.close(); previous?.focus(); };
  }, [standalone]);
  useEffect(() => {
    if (standalone) return;
    let active = true;
    setFailed(false);
    setDescriptionFailed(false);
    setShops(null);
    if (quote.group && quote.group.offer_count > 1) {
      void fetchGroupShopOffers(quote.slug, quote.group.fingerprint, filterQuery, snapshotId)
        .then((result) => { if (active) { setShops(result.items); setRefreshed(result.refreshed); } })
        .catch(() => { if (active) { setFailed(true); setShops([quote.offer]); } });
    } else setShops([quote.offer]);
    if (!quote.offer.original_description && quote.offer.description_available) {
      void fetch(`${apiBase}/api/v1/offers/${quote.offer.id}/description`)
        .then((response) => response.ok ? response.json() : Promise.reject(new Error("description")))
        .then((result: { original_description: string }) => { if (active) setDescription(result.original_description); })
        .catch(() => { if (active) setDescriptionFailed(true); });
    }
    return () => { active = false; };
  }, [quote, snapshotId, filterQuery, attempt, standalone]);
  const displayedShops = standalone ? [quote.offer] : shops;
  const displayedDescription = standalone ? quote.offer.original_description : description;
  let descriptionFallback = "来源未提供商品描述。";
  if (!standalone) {
    if (descriptionFailed) descriptionFallback = "原文暂时无法加载。";
    else if (quote.offer.description_available) descriptionFallback = "正在读取原文…";
  }
  const Subheading = standalone ? "h2" : "h3";
  const shopSection = <section aria-label="店铺报价">
      <Subheading className="quote-detail-section-title">店铺报价</Subheading>
      {refreshed && <p role="status">报价已更新，下方为最新店铺数据；页面上的报价仍为打开时记录。</p>}
      {failed && <p role="alert">其他店铺暂时无法加载，先显示当前店铺。<button onClick={() => setAttempt((value) => value + 1)}>重试</button></p>}
      {displayedShops ? displayedShops.length ? <ul className="quote-shop-list">{displayedShops.map((offer) => <li key={offer.id}><div className="quote-shop-summary"><Link prefetch={false} href={`/shops/${encodeURIComponent(offer.shop_token)}`}>{offer.shop_name}</Link><div className="quote-shop-meta"><span>{quoteInventory(offer)}</span><span>{offer.source_platform_label}</span><time dateTime={offer.observed_at} title={exactTime(offer.observed_at)} suppressHydrationWarning>{relativeTime(offer.observed_at)}更新</time></div></div><strong>{money(offer.price, offer.currency)}</strong><Visit offer={offer} /></li>)}</ul> : <p role="status">当前条件下没有店铺报价。</p> : <p role="status">正在读取店铺报价…</p>}
  </section>;
  const descriptionSection = <section aria-label="商品详情">
      <Subheading className="quote-detail-section-title">商品原文</Subheading><p className="quote-description">{displayedDescription || descriptionFallback}</p>
      {descriptionFailed && <button className="quote-more" onClick={() => setAttempt((value) => value + 1)}>重试原文</button>}
      {quote.offer.risk_flags.length > 0 && <p className="quote-detail-warning">商品说明提到：{quote.offer.risk_flags.join("、")}</p>}
  </section>;
  const Heading = standalone ? "h1" : "h2";
  const content = <div className="quote-dialog-inner">
      <header><div><p>{quote.name || quoteBrand(quote.slug)} · {quoteCategory(quote.offer)}</p><Heading id="quote-dialog-title">{quote.offer.original_name}</Heading></div>{!standalone && <button type="button" autoFocus className="quote-close" onClick={onClose} aria-label="关闭报价详情"><X size={22} /></button>}</header>
      <div className={`quote-detail-overview${sponsor ? " has-sponsor" : ""}`}>
        <div className="quote-detail-facts">
          <Caution offer={quote.offer} />
          {quote.offer.low_price_warning && <p className="quote-detail-warning">{quote.offer.low_price_warning}</p>}
          <p className="quote-detail-terms">质保：{WARRANTY_LABELS[quote.offer.warranty] || quote.offer.warranty} · {quote.offer.auto_delivery === true ? "自动发货" : quote.offer.auto_delivery === false ? "人工交付" : "交付方式未提供"}</p>
        </div>
        {sponsor && <aside className="quote-detail-sponsor" aria-label="赞助内容" data-placement={sponsor.placement}><SponsorCard item={sponsor} variant="compact" /></aside>}
      </div>
      {view === "description" ? <>{descriptionSection}{shopSection}</> : <>{shopSection}{descriptionSection}</>}
    </div>;
  if (standalone) return <section className="quote-dialog quote-detail-page" aria-labelledby="quote-dialog-title">{content}</section>;
  return <dialog ref={dialog} className="quote-dialog" aria-labelledby="quote-dialog-title" onCancel={onClose} onClick={(event) => { if (event.target === event.currentTarget) onClose?.(); }}>{content}</dialog>;
}

export function BrandQuotes({ groups, offers, productSlug = "", snapshotId, filterQuery = "", footer, contextAds }: { groups?: OfferGroup[]; offers?: Offer[]; productSlug?: string; snapshotId?: number | null; filterQuery?: string; footer: ReactNode; contextAds?: ContextualAds }) {
  const quotes: Quote[] = groups ? groups.map((group) => ({ offer: group.representative, slug: group.product_slug || productSlug, name: group.product_name, group })) : (offers || []).map((offer) => ({ offer, slug: offer.product_slug || productSlug, name: offer.product_name }));
  const [selected, setSelected] = useState<{ quote: Quote; view: "shops" | "description" } | null>(null);
  const [activity, setActivity] = useState<Record<number, QuoteActivity>>({});
  const activityCache = useRef<Record<number, QuoteActivity>>({});
  const [heatFailed, setHeatFailed] = useState(false);
  const activityKey = quotes.map((quote) => quote.offer.id).join(",");
  const grouped = Boolean(groups);
  useEffect(() => {
    const controller = new AbortController();
    const missing = [...new Set(activityKey.split(",").filter(Boolean).map(Number))].filter((id) => !(id in activityCache.current));
    if (!missing.length) return;
    setHeatFailed(false);
    const timeout = setTimeout(() => { controller.abort(); setHeatFailed(true); }, 15000);
    void (async () => {
      for (let offset = 0; offset < missing.length; offset += 100) {
        const ids = missing.slice(offset, offset + 100);
        const query = new URLSearchParams({ grouped: String(grouped) });
        ids.forEach((id) => query.append("offer_id", String(id)));
        const response = await fetch(`${apiBase}/api/v1/offers/activity?${query}`, { signal: controller.signal });
        if (!response.ok) throw new Error("activity");
        const result = await response.json() as Activity;
        if (result.window_days !== 7 || !Array.isArray(result.items)) throw new Error("activity schema");
        if (controller.signal.aborted) return;
        const next = { ...activityCache.current };
        ids.forEach((id) => { next[id] = null; });
        result.items.forEach((item) => { next[item.offer_id] = { count: item.click_count, endAt: result.end_at }; });
        activityCache.current = next;
        setActivity(next);
      }
    })().catch(() => { if (!controller.signal.aborted) setHeatFailed(true); }).finally(() => clearTimeout(timeout));
    return () => { clearTimeout(timeout); controller.abort(); };
  }, [activityKey, grouped]);
  const identity = (quote: Quote) => <div className="quote-identity"><div className="quote-product-label">{quote.slug ? <Link prefetch={false} href={quoteProductHref(quote.slug, filterQuery)}>{quote.name || quoteBrand(quote.slug)}</Link> : <span>商品报价</span>}<span>{quoteCategory(quote.offer)}</span></div><h3>{quote.offer.original_name}</h3><Caution offer={quote.offer} />{isMarketTable && <span className="quote-inline-shop">{shop(quote)}</span>}</div>;
  const shop = (quote: Quote) => <Link prefetch={false} className="quote-shop" href={`/shops/${encodeURIComponent(quote.offer.shop_token)}`}>{quote.offer.shop_name}</Link>;
  const stock = (quote: Quote) => <span className={`quote-stock ${quote.offer.stock_status === "in_stock" ? "is-available" : ""}`}>{quoteInventory(quote.offer).split(/(\d+)/).map((part, index) => index % 2 ? <b className="quote-stock-count" key={index}>{part}</b> : part)}</span>;
  const heat = (quote: Quote) => <Heat activity={activity[quote.offer.id]} grouped={grouped} failed={heatFailed} />;
  const price = (quote: Quote) => <strong className="quote-price">{money(quote.offer.price, quote.offer.currency)}</strong>;
  const purchase = (quote: Quote) => quote.group && quote.group.shop_count > 1
    ? <button type="button" className="quote-visit" onClick={() => setSelected({ quote, view: "shops" })} aria-haspopup="dialog" aria-label={`去原站下单：选择 ${quote.offer.original_name} 的店铺`}>去原站下单<Storefront size={14} aria-hidden /></button>
    : <Visit offer={quote.offer} />;
  const more = (quote: Quote) => <button type="button" className={`quote-more${isMarketTable ? " quote-compare" : ""}`} onClick={() => setSelected({ quote, view: "shops" })} aria-label={`查看 ${quote.offer.original_name} 的同款店铺报价`}>{quote.group && quote.group.shop_count > 1 ? <>同款 <b className="quote-shop-count">{quote.group.shop_count}</b> 家</> : "商品详情"}</button>;
  const details = (quote: Quote) => <button type="button" className="quote-more quote-details" onClick={() => setSelected({ quote, view: "description" })} aria-label={`查看 ${quote.offer.original_name} 的商品详情`}>商品详情</button>;
  const updated = (quote: Quote) => <time className="quote-updated" dateTime={quote.offer.observed_at} title={exactTime(quote.offer.observed_at)} suppressHydrationWarning>{relativeTime(quote.offer.observed_at)}更新</time>;
  let body: ReactNode;
  if (isMarketTable) {
    body = <div className="quote-market-table"><table>
      <caption className="sr-only">商品、展示店铺价格、库存和近期热度</caption>
      <thead><tr>
        <th scope="col">商品 / 分类</th><th scope="col">店铺</th><th scope="col">报价</th><th scope="col">库存</th>
        <th scope="col">商品热度{SITE_ID === "pricememo" && <small title="最近 7 天访问原站次数，非销量">近 7 天访问</small>}</th>
        <th scope="col">来源</th>
      </tr></thead><tbody>{quotes.map((quote) =>
      <tr key={quote.offer.id}><td>{identity(quote)}{updated(quote)}</td><td>{shop(quote)}<small>{quote.offer.source_platform_label}</small></td><td>{price(quote)}</td><td>{stock(quote)}</td><td>{heat(quote)}</td><td><div className="quote-market-actions">{purchase(quote)}{quote.group && quote.group.shop_count > 1 && more(quote)}{details(quote)}</div></td></tr>
    )}</tbody></table></div>;
  } else if (SITE_ID === "aisi") {
    const brands = [...new Set(quotes.map((quote) => quoteBrand(quote.slug)))];
    body = <div className="quote-brand-sections">{brands.map((brand) => <section className="quote-brand-section" key={brand}><header><PlatformIcon platform={brand} size={25} /><h2>{brand}</h2><span>商品报价</span></header><div>{quotes.filter((quote) => quoteBrand(quote.slug) === brand).map((quote) => <article className="quote-editorial" key={quote.offer.id}><div className="quote-editorial-main">{identity(quote)}<div className="quote-editorial-seller">{shop(quote)}{updated(quote)}</div></div><div className="quote-editorial-price">{price(quote)}{stock(quote)}</div><footer>{heat(quote)}<div>{more(quote)}{purchase(quote)}</div></footer></article>)}</div></section>)}</div>;
  } else if (SITE_ID === "pricein") {
    body = <div className="quote-shelf">{quotes.map((quote) => <article className="quote-product-card" key={quote.offer.id}><header><PlatformIcon platform={quoteBrand(quote.slug)} size={23} /><span>{quoteBrand(quote.slug)}</span><span>{quote.offer.delivery_type === "subscription_recharge" ? "代充" : quote.offer.delivery_type.includes("account") ? "账号" : "其他"}</span></header>{identity(quote)}<div className="quote-card-price">{price(quote)}{stock(quote)}</div><div className="quote-card-activity">{heat(quote)}{updated(quote)}</div><div className="quote-card-seller">{shop(quote)}{purchase(quote)}</div>{more(quote)}</article>)}</div>;
  } else {
    body = <div className="quote-directory">{quotes.map((quote) => <article className="quote-directory-entry" key={quote.offer.id}><div className="quote-directory-product"><PlatformIcon platform={quoteBrand(quote.slug)} size={26} />{identity(quote)}</div><div className="quote-directory-meta">{shop(quote)}{stock(quote)}{heat(quote)}{updated(quote)}</div><aside>{price(quote)}{purchase(quote)}{more(quote)}</aside></article>)}</div>;
  }
  return <div className={`brand-quotes brand-quotes-${SITE_ID}`}><p className={SITE_ID === "pricememo" ? "sr-only" : "quote-data-note"}>价格与库存对应展示店铺。热度按{grouped ? "每组同款商品" : "每条店铺报价"}统计近 7 天原站访问次数，非销量。</p>{!isMarketTable && !(selected && contextAds?.detail) && contextAds?.feed && <aside className="context-sponsor-feed" aria-label="赞助内容" data-placement={contextAds.feed.placement}><SponsorCard item={contextAds.feed} variant="inline" /></aside>}{body}{footer}{selected && <QuoteDetails quote={selected.quote} view={selected.view} snapshotId={snapshotId} filterQuery={filterQuery} sponsor={contextAds?.detail || (isMarketTable ? contextAds?.feed : undefined)} onClose={() => setSelected(null)} />}</div>;
}
