"use client";

import { useEffect, useRef, useState } from "react";
import type { ContextualAds, Offer, OfferGroup, OfferGroupPage } from "@/lib/types";
import { BrandQuotes } from "@/components/brand-quotes";

const OFFER_BATCH_SIZE = 30;
const publicApiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export function OfferGroupTable({
  groups,
  productSlug = "",
  totalCount,
  snapshotId,
  filterQuery = "",
  loadMorePath,
  contextAds,
}: {
  groups: OfferGroup[];
  productSlug?: string;
  totalCount: number;
  snapshotId: number | null;
  filterQuery?: string;
  loadMorePath?: string;
  contextAds?: ContextualAds;
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

  if (!groups.length) return <div className="empty-state">当前筛选条件下没有可展示的同款报价。请调整筛选条件后再试。</div>;
  return <BrandQuotes groups={loadedGroups} productSlug={productSlug} snapshotId={snapshotId} filterQuery={filterQuery} contextAds={contextAds} footer={<div ref={loadMoreRef} className="quote-list-footer" aria-live="polite">{loadError ? <><span>后续报价加载失败。</span><button type="button" onClick={() => setLoadError(false)}>重试加载</button></> : hasMore ? `已显示 ${loadedGroups.length} / ${totalCount} 组 · 继续滚动加载` : `全部 ${totalCount} 组报价`}</div>} />;
}

export function OfferTable({ offers, productSlug }: { offers: Offer[]; productSlug?: string }) {
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

  if (!offers.length) return <div className="empty-state">当前没有报价。可稍后再查看，或浏览其他商品。</div>;
  return <BrandQuotes offers={visibleOffers} productSlug={productSlug} footer={<div ref={loadMoreRef} className="quote-list-footer">{hasMore ? `已显示 ${visibleOffers.length} / ${offers.length} 条 · 继续滚动加载` : `全部 ${offers.length} 条报价`}</div>} />;
}
