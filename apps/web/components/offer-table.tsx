"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ContextualAds, Offer, OfferGroup } from "@/lib/types";
import { BrandQuotes } from "@/components/brand-quotes";
import { loadMoreGroups, OFFER_BATCH_SIZE, type GroupList } from "@/lib/offer-pagination";

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
  const [page, setPage] = useState<GroupList>({ items: groups, total: totalCount, snapshotId, refreshed: false });
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const hasMore = page.items.length < page.total;
  useEffect(() => () => requestRef.current?.abort(), []);

  const loadMore = useCallback(async () => {
    if (requestRef.current || !hasMore) return;
    const controller = new AbortController();
    requestRef.current = controller;
    setStatus("loading");
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const endpoint = loadMorePath || `/api/v1/products/${encodeURIComponent(productSlug)}/groups`;
      const next = await loadMoreGroups(page, endpoint, filterQuery, controller.signal);
      if (!controller.signal.aborted) setPage(next);
      setStatus("idle");
    } catch {
      setStatus("error");
    } finally {
      clearTimeout(timeout);
      requestRef.current = null;
    }
  }, [filterQuery, hasMore, loadMorePath, page, productSlug]);

  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target || !hasMore || status !== "idle" || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) void loadMore();
    }, { rootMargin: "600px 0px" });
    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, loadMore, status]);

  if (!groups.length) return <div className="empty-state">当前筛选条件下没有可展示的同款报价。请调整筛选条件后再试。</div>;
  return <BrandQuotes groups={page.items} productSlug={productSlug} snapshotId={page.snapshotId} filterQuery={filterQuery} contextAds={contextAds} footer={<div ref={loadMoreRef} className="quote-list-footer" aria-live="polite" aria-busy={status === "loading"}>{page.refreshed && <p>报价已更新，已载入最新列表。</p>}<span>{hasMore ? `已显示 ${page.items.length} / ${page.total} 组` : `全部 ${page.items.length} 组报价`}</span>{hasMore && <>{status === "error" && <span> · 后续报价加载失败</span>}<button type="button" disabled={status === "loading"} onClick={() => void loadMore()}>{status === "loading" ? "正在加载…" : status === "error" ? "重试加载" : "加载更多"}</button></>}</div>} />;
}

export function OfferTable({ offers, productSlug }: { offers: Offer[]; productSlug?: string }) {
  const [visibleCount, setVisibleCount] = useState(OFFER_BATCH_SIZE);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const visibleOffers = offers.slice(0, visibleCount);
  const hasMore = visibleCount < offers.length;

  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target || !hasMore || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) setVisibleCount((count) => Math.min(count + OFFER_BATCH_SIZE, offers.length));
    }, { rootMargin: "600px 0px" });
    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, offers.length, visibleCount]);

  if (!offers.length) return <div className="empty-state">当前没有报价。可稍后再查看，或浏览其他商品。</div>;
  return <BrandQuotes offers={visibleOffers} productSlug={productSlug} footer={<div ref={loadMoreRef} className="quote-list-footer">{hasMore ? <><span>已显示 {visibleOffers.length} / {offers.length} 条</span><button type="button" onClick={() => setVisibleCount((count) => Math.min(count + OFFER_BATCH_SIZE, offers.length))}>加载更多</button></> : `全部 ${offers.length} 条报价`}</div>} />;
}
