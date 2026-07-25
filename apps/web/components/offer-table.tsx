"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowSquareOut, CaretDown, Clock, Package, Storefront, Tag } from "@phosphor-icons/react";
import type { Offer, OfferPage } from "@/lib/types";
import { money, relativeTime, stockLabel } from "@/lib/format";

const OFFER_BATCH_SIZE = 30;
const publicApiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "";

function exactTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function deliveryLabel(value: boolean | null) {
  if (value === true) return "自动发货";
  if (value === false) return "人工交付";
  return "交付方式未知";
}

function OfferRow({ offer }: { offer: Offer }) {
  return (
    <details className="group/offer bg-[color:var(--panel)] open:bg-white/70">
      <summary className="grid cursor-pointer list-none gap-4 px-5 py-5 marker:hidden lg:grid-cols-[minmax(0,1fr)_150px_150px_32px] lg:items-center [&::-webkit-details-marker]:hidden">
        <div className="min-w-0">
          <h3 className="text-[15px] font-semibold leading-6 tracking-[-.01em]">{offer.original_name}</h3>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-black/50">
            <span className="flex items-center gap-1.5"><Storefront size={15} />{offer.shop_name}</span>
            {offer.original_category && <span className="flex items-center gap-1.5"><Tag size={15} />{offer.original_category}</span>}
            {offer.goods_type && <span>{offer.goods_type}</span>}
          </div>
        </div>

        <div>
          <span className={`inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-medium ${offer.stock_status === "in_stock" ? "bg-[color:var(--accent)] text-[color:var(--accent-ink)]" : "bg-black/6 text-black/55"}`}>
            <span className="h-1.5 w-1.5 rounded-full bg-current" />{stockLabel(offer.stock_status)}
          </span>
          <p className="mt-2 text-xs text-black/45">{offer.stock_count === null ? "库存数未知" : `库存 ${offer.stock_count}`}</p>
        </div>

        <div>
          <p className="mono text-xl font-semibold tracking-[-.04em]">{money(offer.price, offer.currency)}</p>
          {offer.market_price && offer.market_price !== offer.price && (
            <p className="mt-1 text-xs text-black/40 line-through">标价 {money(offer.market_price, offer.currency)}</p>
          )}
          <p className="mt-1 text-xs text-black/45">{deliveryLabel(offer.auto_delivery)}</p>
        </div>

        <CaretDown className="transition-transform duration-150 group-open/offer:rotate-180" size={20} aria-hidden="true" />
      </summary>

      <div className="grid gap-6 border-t hairline bg-black/[.025] px-5 py-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(260px,.6fr)]">
        <section>
          <h4 className="text-sm font-semibold">商家原始描述</h4>
          <p className="mt-3 max-w-[80ch] whitespace-pre-wrap text-sm leading-7 text-black/65">
            {offer.original_description || "商家没有提供可公开展示的商品描述。"}
          </p>
          <p className="mt-4 text-xs leading-5 text-black/40">描述由原页面转换为纯文本，仅用于核对商品内容。</p>
        </section>

        <section>
          <dl className="grid grid-cols-2 gap-x-5 gap-y-4 text-sm">
            <div><dt className="text-xs text-black/40">原始分类</dt><dd className="mt-1">{offer.original_category || "未填写"}</dd></div>
            <div><dt className="text-xs text-black/40">商品类型</dt><dd className="mt-1">{offer.goods_type || "未填写"}</dd></div>
            <div><dt className="text-xs text-black/40">首次发现</dt><dd className="mt-1">{exactTime(offer.first_seen_at)}</dd></div>
            <div><dt className="text-xs text-black/40">最后发现</dt><dd className="mt-1">{exactTime(offer.last_seen_at)}</dd></div>
          </dl>

          {(offer.tags.length > 0 || offer.risk_flags.length > 0) && (
            <div className="mt-5 flex flex-wrap gap-2">
              {offer.tags.map((tag) => <span key={tag} className="rounded-full border hairline px-2 py-1 text-[11px]">{tag}</span>)}
              {offer.risk_flags.map((flag) => <span key={flag} className="rounded-full bg-[#f2d8d2] px-2 py-1 text-[11px] text-[color:var(--danger)]">原文含：{flag}</span>)}
            </div>
          )}

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <a href={offer.source_url} target="_blank" rel="noreferrer nofollow" className="tactile inline-flex items-center gap-2 rounded-[10px] bg-[color:var(--ink)] px-4 py-2.5 text-sm text-white">
              原站核验 <ArrowSquareOut size={16} />
            </a>
            <Link href={`/shops/${offer.shop_token}`} className="tactile inline-flex items-center gap-2 rounded-[10px] border border-black px-4 py-2.5 text-sm">
              查看店铺 <Storefront size={16} />
            </Link>
          </div>
        </section>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2 border-t hairline px-5 py-3 text-xs text-black/45">
        <span className="flex items-center gap-1.5"><Clock size={14} />扫描于 {exactTime(offer.observed_at)}</span>
        <span>约 {relativeTime(offer.observed_at)}更新</span>
      </div>
    </details>
  );
}

export function OfferTable({ offers, productSlug, totalCount = offers.length }: { offers: Offer[]; productSlug?: string; totalCount?: number }) {
  const [loadedOffers, setLoadedOffers] = useState(offers);
  const [visibleCount, setVisibleCount] = useState(OFFER_BATCH_SIZE);
  const [loadError, setLoadError] = useState(false);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const isRemote = Boolean(productSlug);
  const visibleOffers = isRemote ? loadedOffers : offers.slice(0, visibleCount);
  const hasMore = !loadError && visibleOffers.length < totalCount;

  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target || !hasMore) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting || loadingRef.current) return;
        if (!productSlug) {
          setVisibleCount((count) => Math.min(count + OFFER_BATCH_SIZE, offers.length));
          return;
        }

        loadingRef.current = true;
        fetch(`${publicApiBase}/api/v1/products/${encodeURIComponent(productSlug)}/offers?offset=${loadedOffers.length}&limit=${OFFER_BATCH_SIZE}`)
          .then((response) => {
            if (!response.ok) throw new Error(`API ${response.status}`);
            return response.json() as Promise<OfferPage>;
          })
          .then((page) => {
            setLoadedOffers((current) => {
              const existingIds = new Set(current.map((offer) => offer.id));
              return [...current, ...page.items.filter((offer) => !existingIds.has(offer.id))];
            });
          })
          .catch(() => setLoadError(true))
          .finally(() => { loadingRef.current = false; });
      },
      { rootMargin: "600px 0px" },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, loadedOffers.length, offers.length, productSlug]);

  if (!offers.length) {
    return <div className="rounded-[18px] border hairline bg-[color:var(--panel)] p-10 text-center text-[color:var(--muted)]">当前没有通过审核且仍在有效期内的报价。</div>;
  }

  return (
    <div className="overflow-hidden rounded-[18px] border hairline bg-[color:var(--panel)]">
      <div className="bg-black/[.025] px-5 py-3 text-xs text-black/50">
        <div className="flex items-center gap-2 lg:hidden"><Package size={15} />点击报价查看原始描述</div>
        <div className="hidden grid-cols-[minmax(0,1fr)_150px_150px_32px] gap-4 lg:grid">
          <span>原始商品与来源</span><span>库存</span><span>价格与交付</span><span>详情</span>
        </div>
      </div>
      <div className="divide-y divide-[color:var(--line)]">
        {visibleOffers.map((offer) => <OfferRow key={offer.id} offer={offer} />)}
      </div>
      <div ref={loadMoreRef} className="border-t hairline px-5 py-4 text-center text-xs text-black/45" aria-live="polite">
        {loadError ? "后续报价加载失败，请刷新页面重试" : hasMore ? `继续滚动加载，已显示 ${visibleOffers.length} / ${totalCount} 条` : `已显示全部 ${totalCount} 条报价`}
      </div>
    </div>
  );
}
