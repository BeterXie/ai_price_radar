"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowSquareOut, CaretDown, Clock, Package, Storefront, Tag, Warning } from "@phosphor-icons/react";
import type { GroupOffers, Offer, OfferGroup, OfferGroupPage } from "@/lib/types";
import { DELIVERY_TYPE_LABELS, PERIOD_LABELS, SCENARIO_LABELS, WARRANTY_LABELS } from "@/lib/catalog";
import { exactTime, money, relativeTime, stockLabel } from "@/lib/format";

const OFFER_BATCH_SIZE = 30;
const publicApiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "";

function fulfillmentLabel(value: boolean | null) {
  if (value === true) return "自动发货";
  if (value === false) return "人工交付";
  return "交付方式未知";
}

function DecisionFacts({ offer }: { offer: Offer }) {
  return (
    <dl className="grid grid-cols-2 gap-x-5 gap-y-4 text-sm lg:grid-cols-4">
      <div><dt className="text-xs text-black/40">交付形态</dt><dd className="mt-1 font-medium">{DELIVERY_TYPE_LABELS[offer.delivery_type] || offer.delivery_type}</dd></div>
      <div><dt className="text-xs text-black/40">使用期限</dt><dd className="mt-1">{PERIOD_LABELS[offer.service_period] || offer.service_period}</dd></div>
      <div><dt className="text-xs text-black/40">质保</dt><dd className="mt-1">{WARRANTY_LABELS[offer.warranty] || offer.warranty}</dd></div>
      <div><dt className="text-xs text-black/40">交付方式</dt><dd className="mt-1">{fulfillmentLabel(offer.auto_delivery)}</dd></div>
      <div><dt className="text-xs text-black/40">来源更新状态</dt><dd className="mt-1 font-medium">{offer.source_health.score} / 100 · {offer.source_health.label}</dd></div>
      <div className="col-span-2 lg:col-span-3"><dt className="text-xs text-black/40">适用场景</dt><dd className="mt-1">{offer.use_scenarios.length ? offer.use_scenarios.map((item) => SCENARIO_LABELS[item] || item).join("、") : "未注明"}</dd></div>
      <div className="col-span-2 lg:col-span-4"><dt className="text-xs text-black/40">状态说明</dt><dd className="mt-1 text-black/60">{offer.source_health.reasons.join("；")}</dd></div>
    </dl>
  );
}

function ShopOfferList({ offers }: { offers: Offer[] }) {
  return (
    <div className="mt-5 overflow-hidden rounded-[12px] border hairline bg-white/70">
      {offers.map((offer) => (
        <div key={offer.id} className="grid gap-2 border-b hairline px-4 py-3 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_110px_90px_auto] sm:items-center">
          <Link href={`/shops/${offer.shop_token}`} className="flex items-center gap-2 text-sm font-medium hover:opacity-60"><Storefront size={15} />{offer.shop_name}</Link>
          <span className="text-xs text-black/50">{stockLabel(offer.stock_status)}{offer.stock_count === null ? "" : ` · 库存 ${offer.stock_count}`}</span>
          <span className="mono font-semibold">{money(offer.price, offer.currency)}</span>
          <a href={offer.source_url} target="_blank" rel="noreferrer nofollow" aria-label={`前往 ${offer.shop_name} 查看报价`} className="inline-flex items-center gap-1 text-xs hover:opacity-60">查看原站 <ArrowSquareOut size={14} /></a>
        </div>
      ))}
    </div>
  );
}

function OfferRow({ offer, group, productSlug, productName, snapshotId, filterQuery = "" }: { offer: Offer; group?: OfferGroup; productSlug?: string; productName?: string; snapshotId?: number | null; filterQuery?: string }) {
  const [description, setDescription] = useState<string | null>(null);
  const [shopOffers, setShopOffers] = useState<Offer[] | null>(group && group.offer_count === 1 ? [offer] : null);
  const [loading, setLoading] = useState(false);
  const requestedRef = useRef(false);

  const loadDetails = async () => {
    if (requestedRef.current) return;
    requestedRef.current = true;
    setLoading(true);
    try {
      const requests: Promise<void>[] = [];
      if (offer.description_available) {
        requests.push(fetch(`${publicApiBase}/api/v1/offers/${offer.id}/description`)
          .then((response) => response.ok ? response.json() : Promise.reject(new Error(`API ${response.status}`)))
          .then((data: { original_description: string }) => setDescription(data.original_description)));
      } else {
        setDescription("");
      }
      if (group && productSlug && group.offer_count > 1) {
        const query = new URLSearchParams(filterQuery);
        if (snapshotId) query.set("snapshot", String(snapshotId));
        requests.push(fetch(`${publicApiBase}/api/v1/products/${encodeURIComponent(productSlug)}/groups/${encodeURIComponent(group.fingerprint)}?${query}`)
          .then((response) => response.ok ? response.json() : Promise.reject(new Error(`API ${response.status}`)))
          .then((data: GroupOffers) => setShopOffers(data.items)));
      }
      await Promise.all(requests);
    } catch {
      setDescription("加载失败，请稍后刷新页面重试。");
    } finally {
      setLoading(false);
    }
  };

  const shownPrice = group?.lowest_price ?? offer.price;
  const shownStock = group?.in_stock_count ?? (offer.stock_status === "in_stock" ? 1 : 0);

  return (
    <details onToggle={(event) => { if (event.currentTarget.open) void loadDetails(); }} className="group/offer bg-[color:var(--panel)] open:bg-white/70">
      <summary className="grid cursor-pointer list-none gap-4 px-5 py-5 marker:hidden lg:grid-cols-[minmax(0,1fr)_150px_150px_32px] lg:items-center [&::-webkit-details-marker]:hidden">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {productName && <span className="rounded-full border hairline px-2 py-1 text-[10px] font-medium">{productName}</span>}
            <h3 className="text-[15px] font-semibold leading-6 tracking-[-.01em]">{offer.original_name}</h3>
            {offer.is_trusted_price ? <span className="rounded-full bg-[color:var(--accent)] px-2 py-1 text-[10px] font-medium text-[color:var(--accent-ink)]">近期可参考</span> : !offer.is_comparable ? <span className="rounded-full bg-[#f1e2bd] px-2 py-1 text-[10px] font-medium text-[#6d4f09]">类型不同，不直接比价</span> : <span className="rounded-full border hairline px-2 py-1 text-[10px] text-black/50">价格异常，建议确认</span>}
            {group && group.shop_count > 1 && <span className="rounded-full border hairline px-2 py-1 text-[10px]">同款 {group.shop_count} 家店铺</span>}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-black/50">
            <span className="flex items-center gap-1.5"><Storefront size={15} />{group ? `${group.shop_count} 家店铺 · ${group.offer_count} 条报价` : offer.shop_name}</span>
            <span>{DELIVERY_TYPE_LABELS[offer.delivery_type] || offer.delivery_type}</span>
            <span>{PERIOD_LABELS[offer.service_period] || offer.service_period}</span>
            <span>{WARRANTY_LABELS[offer.warranty] || offer.warranty}</span>
          </div>
        </div>

        <div>
          <span className={`inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-medium ${shownStock > 0 ? "bg-[color:var(--accent)] text-[color:var(--accent-ink)]" : "bg-black/6 text-black/55"}`}>
            <span className="h-1.5 w-1.5 rounded-full bg-current" />{shownStock > 0 ? "有货" : stockLabel(offer.stock_status)}
          </span>
          <p className="mt-2 text-xs text-black/45">{group ? `${shownStock} 条有货报价` : offer.stock_count === null ? "库存数未知" : `库存 ${offer.stock_count}`}</p>
        </div>

        <div>
          <p className="mono text-xl font-semibold tracking-[-.04em]">{money(shownPrice, offer.currency)}</p>
          <p className="mt-1 text-xs text-black/45">{fulfillmentLabel(offer.auto_delivery)}</p>
        </div>

        <CaretDown className="transition-transform duration-150 group-open/offer:rotate-180" size={20} aria-hidden="true" />
      </summary>

      <div className="border-t hairline bg-black/[.025] px-5 py-6">
        {offer.low_price_warning && (
          <div className="mb-5 flex items-start gap-2 rounded-[10px] bg-[#f4e6c5] px-4 py-3 text-sm text-[#674b0b]"><Warning className="mt-0.5 shrink-0" size={17} weight="fill" /><span><strong>价格明显偏低：</strong>{offer.low_price_warning}</span></div>
        )}
        <DecisionFacts offer={offer} />
        {(offer.tags.length > 0 || offer.risk_flags.length > 0) && (
          <div className="mt-5 flex flex-wrap gap-2">
            {offer.tags.map((tag) => <span key={tag} className="rounded-full border hairline px-2 py-1 text-[11px]">{tag}</span>)}
            {offer.risk_flags.map((flag) => <span key={flag} className="rounded-full bg-[#f2d8d2] px-2 py-1 text-[11px] text-[color:var(--danger)]">原文含：{flag}</span>)}
          </div>
        )}

        <section className="mt-6 border-t hairline pt-5">
          <h4 className="text-sm font-semibold">商品原文</h4>
          <p className="mt-3 max-w-[90ch] whitespace-pre-wrap text-sm leading-7 text-black/65">
            {loading && description === null ? "正在加载…" : description === null ? "展开后加载商品原文。" : description || "商家没有提供可公开展示的商品描述。"}
          </p>
        </section>

        {group && (
          <section className="mt-6 border-t hairline pt-5">
            <h4 className="text-sm font-semibold">全部店铺报价</h4>
            {shopOffers ? <ShopOfferList offers={shopOffers} /> : <p className="mt-3 text-sm text-black/45">{loading ? "正在加载店铺报价…" : "展开后加载店铺报价。"}</p>}
          </section>
        )}

        {!group && (
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <a href={offer.source_url} target="_blank" rel="noreferrer nofollow" className="tactile inline-flex items-center gap-2 rounded-[10px] bg-[color:var(--ink)] px-4 py-2.5 text-sm text-white">去原站查看 <ArrowSquareOut size={16} /></a>
            <Link href={`/shops/${offer.shop_token}`} className="tactile inline-flex items-center gap-2 rounded-[10px] border border-black px-4 py-2.5 text-sm">查看店铺 <Storefront size={16} /></Link>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2 border-t hairline px-5 py-3 text-xs text-black/45">
        <span className="flex items-center gap-1.5"><Clock size={14} />数据更新于 {exactTime(group?.latest_observed_at || offer.observed_at)}</span>
        <span suppressHydrationWarning>约 {relativeTime(group?.latest_observed_at || offer.observed_at)}更新</span>
        {offer.original_category && <span className="flex items-center gap-1.5"><Tag size={14} />{offer.original_category}</span>}
      </div>
    </details>
  );
}

function TableFrame({ children, footer }: { children: React.ReactNode; footer: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-[18px] border hairline bg-[color:var(--panel)]">
      <div className="bg-black/[.025] px-5 py-3 text-xs text-black/50">
        <div className="flex items-center gap-2 lg:hidden"><Package size={15} />点开查看交付、售后和来源</div>
        <div className="hidden grid-cols-[minmax(0,1fr)_150px_150px_32px] gap-4 lg:grid"><span>同款商品与交付形态</span><span>库存</span><span>最低价</span><span>详情</span></div>
      </div>
      <div className="divide-y divide-[color:var(--line)]">{children}</div>
      {footer}
    </div>
  );
}

export function OfferGroupTable({
  groups,
  productSlug = "",
  totalCount,
  snapshotId,
  filterQuery = "",
  loadMorePath,
  showProduct = false,
}: {
  groups: OfferGroup[];
  productSlug?: string;
  totalCount: number;
  snapshotId: number | null;
  filterQuery?: string;
  loadMorePath?: string;
  showProduct?: boolean;
}) {
  const [loadedGroups, setLoadedGroups] = useState(groups);
  const [loadError, setLoadError] = useState(false);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const hasMore = !loadError && loadedGroups.length < totalCount;

  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target || !hasMore) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting || loadingRef.current) return;
      loadingRef.current = true;
      const query = new URLSearchParams(filterQuery);
      query.set("offset", String(loadedGroups.length));
      query.set("limit", String(OFFER_BATCH_SIZE));
      if (snapshotId) query.set("snapshot", String(snapshotId));
      const endpoint = loadMorePath || `/api/v1/products/${encodeURIComponent(productSlug)}/groups`;
      fetch(`${publicApiBase}${endpoint}?${query}`)
        .then((response) => response.ok ? response.json() as Promise<OfferGroupPage> : Promise.reject(new Error(`API ${response.status}`)))
        .then((page) => setLoadedGroups((current) => {
          const keys = new Set(current.map((group) => `${group.product_slug}:${group.fingerprint}`));
          return [...current, ...page.items.filter((group) => !keys.has(`${group.product_slug}:${group.fingerprint}`))];
        }))
        .catch(() => setLoadError(true))
        .finally(() => { loadingRef.current = false; });
    }, { rootMargin: "600px 0px" });
    observer.observe(target);
    return () => observer.disconnect();
  }, [filterQuery, hasMore, loadMorePath, loadedGroups.length, productSlug, snapshotId]);

  if (!groups.length) return <div className="rounded-[18px] border hairline bg-[color:var(--panel)] p-10 text-center text-[color:var(--muted)]">当前筛选条件下没有可展示的同款报价。</div>;
  return (
    <TableFrame footer={<div ref={loadMoreRef} className="border-t hairline px-5 py-4 text-center text-xs text-black/45" aria-live="polite">{loadError ? "后续报价加载失败，请刷新页面重试" : hasMore ? `继续滚动加载，已显示 ${loadedGroups.length} / ${totalCount} 款` : `已显示全部 ${totalCount} 款`}</div>}>
      {loadedGroups.map((group) => <OfferRow key={`${group.product_slug}:${group.fingerprint}`} offer={group.representative} group={group} productSlug={group.product_slug || productSlug} productName={showProduct ? group.product_name : undefined} snapshotId={snapshotId} filterQuery={filterQuery} />)}
    </TableFrame>
  );
}

export function OfferTable({ offers }: { offers: Offer[] }) {
  const [visibleCount, setVisibleCount] = useState(OFFER_BATCH_SIZE);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const visibleOffers = offers.slice(0, visibleCount);
  const hasMore = visibleCount < offers.length;

  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target || !hasMore) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) setVisibleCount((count) => Math.min(count + OFFER_BATCH_SIZE, offers.length));
    }, { rootMargin: "600px 0px" });
    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, offers.length]);

  if (!offers.length) return <div className="rounded-[18px] border hairline bg-[color:var(--panel)] p-10 text-center text-[color:var(--muted)]">当前没有可展示的报价。</div>;
  return (
    <TableFrame footer={<div ref={loadMoreRef} className="border-t hairline px-5 py-4 text-center text-xs text-black/45">{hasMore ? `继续滚动加载，已显示 ${visibleOffers.length} / ${offers.length} 条` : `已显示全部 ${offers.length} 条报价`}</div>}>
      {visibleOffers.map((offer) => <OfferRow key={offer.id} offer={offer} />)}
    </TableFrame>
  );
}
