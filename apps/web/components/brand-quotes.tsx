"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowUpRight, Fire, X } from "@phosphor-icons/react";
import { SITE_ID } from "@/lib/brands";
import { quoteBrand, quoteCategory, quoteInventory, quoteProductHref } from "@/lib/brand-quotes";
import { money, exactTime, relativeTime } from "@/lib/format";
import { WARRANTY_LABELS } from "@/lib/catalog";
import { fetchGroupShopOffers } from "@/lib/group-offers";
import { PlatformIcon } from "@/components/platform-icon";
import type { ContextualAds, Offer, OfferGroup } from "@/lib/types";
import { SponsorCard } from "@/components/sponsor-card";

type Quote = { offer: Offer; slug: string; name?: string; group?: OfferGroup };
type Activity = { window_days: number; start_at: string; end_at: string; items: { product_slug: string; click_count: number }[] };
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "";

function Visit({ offer }: { offer: Offer }) {
  if (!offer.source_url) return <span className="quote-no-link">暂无原站链接</span>;
  return <a className="quote-visit" href={offer.source_url} target="_blank" rel="nofollow noreferrer" onClick={() => {
    void fetch(`${apiBase}/api/v1/offers/${offer.id}/click`, { method: "POST", credentials: "include", keepalive: true }).catch(() => {});
  }} aria-label={`前往 ${offer.shop_name} 查看 ${offer.original_name}`}>去原站<ArrowUpRight size={14} aria-hidden /></a>;
}

function Caution({ offer }: { offer: Offer }) {
  if (offer.is_comparable && offer.is_trusted_price) return null;
  return <span className="quote-caution">{!offer.is_comparable ? "相关商品 · 不直接比价" : "价格偏离同类报价"}</span>;
}

function Heat({ slug, activity, failed }: { slug: string; activity: Activity | null; failed: boolean }) {
  const value = activity?.items.find((item) => item.product_slug === slug)?.click_count;
  return <span className="quote-heat" title={activity ? `同一商品最近 7 天访问原站次数；所有店铺合计，非销量。统计截至 ${exactTime(activity.end_at)}` : "按商品汇总最近 7 天原站访问次数；非销量"}><Fire size={13} aria-hidden /><span>商品近7天 <b>{value !== undefined ? value.toLocaleString("zh-CN") : failed || activity ? "暂不可用" : "加载中"}</b></span></span>;
}

function QuoteDetails({ quote, snapshotId, filterQuery, onClose, sponsor }: { quote: Quote; snapshotId?: number | null; filterQuery: string; onClose: () => void; sponsor?: ContextualAds["detail"] }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [shops, setShops] = useState<Offer[] | null>(null);
  const [description, setDescription] = useState(quote.offer.original_description || "");
  const [failed, setFailed] = useState(false);
  const [descriptionFailed, setDescriptionFailed] = useState(false);
  const [refreshed, setRefreshed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const node = dialog.current;
    const previous = document.activeElement as HTMLElement | null;
    node?.showModal();
    return () => { node?.close(); previous?.focus(); };
  }, []);
  useEffect(() => {
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
  }, [quote, snapshotId, filterQuery, attempt]);
  return <dialog ref={dialog} className="quote-dialog" aria-labelledby="quote-dialog-title" onCancel={onClose} onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="quote-dialog-inner">
      <header><div><p>{quote.name || quoteBrand(quote.slug)} · {quoteCategory(quote.offer)}</p><h2 id="quote-dialog-title">{quote.offer.original_name}</h2></div><button type="button" autoFocus className="quote-close" onClick={onClose} aria-label="关闭报价详情"><X size={22} /></button></header>
      <Caution offer={quote.offer} />
      {quote.offer.low_price_warning && <p className="quote-detail-warning">{quote.offer.low_price_warning}</p>}
      <p className="quote-detail-terms">质保：{WARRANTY_LABELS[quote.offer.warranty] || quote.offer.warranty} · {quote.offer.auto_delivery === true ? "自动发货" : quote.offer.auto_delivery === false ? "人工交付" : "交付方式未提供"}</p>
      <h3>店铺报价</h3>
      {refreshed && <p role="status">报价已更新，下方为最新店铺数据；页面上的报价仍为打开时记录。</p>}
      {failed && <p role="alert">其他店铺暂时无法加载，先显示当前店铺。<button onClick={() => setAttempt((value) => value + 1)}>重试</button></p>}
      {shops ? shops.length ? <ul className="quote-shop-list">{shops.map((offer) => <li key={offer.id}><div><Link href={`/shops/${encodeURIComponent(offer.shop_token)}`}>{offer.shop_name}</Link><small>{quoteInventory(offer)} · {offer.source_platform_label}</small><time dateTime={offer.observed_at}>{exactTime(offer.observed_at)}</time></div><strong>{money(offer.price, offer.currency)}</strong><Visit offer={offer} /></li>)}</ul> : <p role="status">当前条件下没有店铺报价。</p> : <p role="status">正在读取店铺报价…</p>}
      <h3>商品原文</h3><p className="quote-description">{description || (descriptionFailed ? "原文暂时无法加载。" : quote.offer.description_available ? "正在读取原文…" : "来源未提供商品描述。")}</p>
      {descriptionFailed && <button className="quote-more" onClick={() => setAttempt((value) => value + 1)}>重试原文</button>}
      {quote.offer.risk_flags.length > 0 && <p className="quote-detail-warning">商品说明提到：{quote.offer.risk_flags.join("、")}</p>}
      {sponsor && <aside className="context-sponsor-detail" aria-label="赞助内容" data-placement="claude_detail"><SponsorCard item={sponsor} variant="inline" /></aside>}
    </div>
  </dialog>;
}

export function BrandQuotes({ groups, offers, productSlug = "", snapshotId, filterQuery = "", footer, contextAds }: { groups?: OfferGroup[]; offers?: Offer[]; productSlug?: string; snapshotId?: number | null; filterQuery?: string; footer: ReactNode; contextAds?: ContextualAds }) {
  const quotes: Quote[] = groups ? groups.map((group) => ({ offer: group.representative, slug: group.product_slug || productSlug, name: group.product_name, group })) : (offers || []).map((offer) => ({ offer, slug: offer.product_slug || productSlug, name: offer.product_name }));
  const [selected, setSelected] = useState<Quote | null>(null);
  const [activity, setActivity] = useState<Activity | null>(null);
  const [heatFailed, setHeatFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void fetch(`${apiBase}/api/v1/catalog/activity`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("activity")))
      .then((result: Activity) => { if (result.window_days !== 7 || !Array.isArray(result.items)) throw new Error("activity schema"); setActivity(result); })
      .catch(() => { if (!controller.signal.aborted) setHeatFailed(true); });
    return () => controller.abort();
  }, []);
  const identity = (quote: Quote) => <div className="quote-identity"><div className="quote-product-label">{quote.slug ? <Link href={quoteProductHref(quote.slug, filterQuery)}>{quote.name || quoteBrand(quote.slug)}</Link> : <span>商品报价</span>}<span>{quoteCategory(quote.offer)}</span></div><h3>{quote.offer.original_name}</h3><Caution offer={quote.offer} />{SITE_ID === "aiprice" && <span className="quote-inline-shop">{shop(quote)}</span>}</div>;
  const shop = (quote: Quote) => <Link className="quote-shop" href={`/shops/${encodeURIComponent(quote.offer.shop_token)}`}>{quote.offer.shop_name}</Link>;
  const stock = (quote: Quote) => <span className={`quote-stock ${quote.offer.stock_status === "in_stock" ? "is-available" : ""}`}>{quoteInventory(quote.offer)}</span>;
  const heat = (quote: Quote) => <Heat slug={quote.slug} activity={activity} failed={heatFailed} />;
  const price = (quote: Quote) => <strong className="quote-price">{money(quote.offer.price, quote.offer.currency)}</strong>;
  const more = (quote: Quote) => <button type="button" className="quote-more" onClick={() => setSelected(quote)} aria-label={`查看 ${quote.offer.original_name} 的详情与店铺`}>{quote.group && quote.group.shop_count > 1 ? `同款 ${quote.group.shop_count} 家` : "商品详情"}</button>;
  const updated = (quote: Quote) => <time className="quote-updated" dateTime={quote.offer.observed_at} title={exactTime(quote.offer.observed_at)} suppressHydrationWarning>{relativeTime(quote.offer.observed_at)}更新</time>;
  let body: ReactNode;
  if (SITE_ID === "aiprice") {
    body = <div className="quote-market-table"><table><caption className="sr-only">商品、展示店铺价格、库存和近期热度</caption><thead><tr><th>商品 / 分类</th><th>店铺</th><th>报价</th><th>库存</th><th>商品热度</th><th>来源</th></tr></thead><tbody>{quotes.map((quote) => <tr key={quote.offer.id}><td>{identity(quote)}{updated(quote)}</td><td>{shop(quote)}<small>{quote.offer.source_platform_label}</small></td><td>{price(quote)}</td><td>{stock(quote)}</td><td>{heat(quote)}</td><td><Visit offer={quote.offer} />{more(quote)}</td></tr>)}</tbody></table></div>;
  } else if (SITE_ID === "aisi") {
    const brands = [...new Set(quotes.map((quote) => quoteBrand(quote.slug)))];
    body = <div className="quote-brand-sections">{brands.map((brand) => <section className="quote-brand-section" key={brand}><header><PlatformIcon platform={brand} size={25} /><h2>{brand}</h2><span>商品报价</span></header><div>{quotes.filter((quote) => quoteBrand(quote.slug) === brand).map((quote) => <article className="quote-editorial" key={quote.offer.id}><div className="quote-editorial-main">{identity(quote)}<div className="quote-editorial-seller">{shop(quote)}{updated(quote)}</div></div><div className="quote-editorial-price">{price(quote)}{stock(quote)}</div><footer>{heat(quote)}<div>{more(quote)}<Visit offer={quote.offer} /></div></footer></article>)}</div></section>)}</div>;
  } else if (SITE_ID === "pricein") {
    body = <div className="quote-shelf">{quotes.map((quote) => <article className="quote-product-card" key={quote.offer.id}><header><PlatformIcon platform={quoteBrand(quote.slug)} size={23} /><span>{quoteBrand(quote.slug)}</span><span>{quote.offer.delivery_type === "subscription_recharge" ? "代充" : quote.offer.delivery_type.includes("account") ? "账号" : "其他"}</span></header>{identity(quote)}<div className="quote-card-price">{price(quote)}{stock(quote)}</div><div className="quote-card-activity">{heat(quote)}{updated(quote)}</div><div className="quote-card-seller">{shop(quote)}<Visit offer={quote.offer} /></div>{more(quote)}</article>)}</div>;
  } else {
    body = <div className="quote-directory">{quotes.map((quote) => <article className="quote-directory-entry" key={quote.offer.id}><div className="quote-directory-product"><PlatformIcon platform={quoteBrand(quote.slug)} size={26} />{identity(quote)}</div><div className="quote-directory-meta">{shop(quote)}{stock(quote)}{heat(quote)}{updated(quote)}</div><aside>{price(quote)}<Visit offer={quote.offer} />{more(quote)}</aside></article>)}</div>;
  }
  return <div className={`brand-quotes brand-quotes-${SITE_ID}`}><p className="quote-data-note">价格与库存对应展示店铺。热度为同一商品近 7 天原站访问次数，非销量。</p>{!(selected && contextAds?.detail) && contextAds?.feed && <aside className="context-sponsor-feed" aria-label="赞助内容" data-placement="claude_feed"><SponsorCard item={contextAds.feed} variant="inline" /></aside>}{body}{footer}{selected && <QuoteDetails quote={selected} snapshotId={snapshotId} filterQuery={filterQuery} sponsor={contextAds?.detail} onClose={() => setSelected(null)} />}</div>;
}
