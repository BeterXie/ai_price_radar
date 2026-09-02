"use client";

import { useEffect, useRef, useState } from "react";
import { PriceHistory } from "@/components/price-history";
import type { PriceTrendPoint, ProductHistory } from "@/lib/types";

function isPriceValue(value: unknown) {
  return value === null || (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value)));
}

function isPriceTrendPoint(value: unknown): value is PriceTrendPoint {
  if (!value || typeof value !== "object") return false;
  const point = value as Record<string, unknown>;
  return typeof point.bucket_at === "string"
    && Number.isFinite(Date.parse(point.bucket_at))
    && typeof point.price_currency === "string"
    && point.price_currency.length > 0
    && isPriceValue(point.trusted_lowest_price)
    && isPriceValue(point.median_price)
    && Number.isInteger(point.in_stock_count)
    && Number.isInteger(point.observation_count)
    && Number(point.in_stock_count) >= 0
    && Number(point.observation_count) >= 0;
}

export function ProductHistoryPanel({
  slug,
  sourcePlatform = "",
  previewEmpty = false,
}: {
  slug: string;
  sourcePlatform?: string;
  previewEmpty?: boolean;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [trend, setTrend] = useState<PriceTrendPoint[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    setTrend(previewEmpty ? [] : null);
    setLoadError(false);
    if (previewEmpty) return;
    const target = panelRef.current;
    if (!target) return;
    let active = true;
    let requested = false;
    const controller = new AbortController();

    const load = async () => {
      if (requested) return;
      requested = true;
      try {
        const query = new URLSearchParams();
        if (sourcePlatform) query.set("source_platform", sourcePlatform);
        const suffix = query.toString() ? `?${query}` : "";
        const response = await fetch(`/api/v1/products/${encodeURIComponent(slug)}/history${suffix}`, { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error(`API ${response.status}`);
        const data = await response.json() as Partial<ProductHistory>;
        if (!Array.isArray(data.trend) || !data.trend.every(isPriceTrendPoint)) throw new Error("Invalid history response");
        if (active) setTrend(data.trend);
      } catch {
        if (active) setLoadError(true);
      }
    };

    if (!("IntersectionObserver" in window)) {
      void load();
      return () => {
        active = false;
        controller.abort();
      };
    }

    const observer = new IntersectionObserver(([entry]) => {
      if (!entry?.isIntersecting) return;
      void load();
      observer.disconnect();
    }, { rootMargin: "400px 0px" });
    observer.observe(target);
    return () => {
      active = false;
      observer.disconnect();
      controller.abort();
    };
  }, [previewEmpty, slug, sourcePlatform]);

  if (previewEmpty) return <PriceHistory points={[]} />;
  if (loadError) return <div ref={panelRef} className="empty-state grid h-56 place-items-center !p-6 text-sm" role="alert">历史数据暂时无法加载，请稍后刷新页面重试</div>;
  if (trend === null) return <div ref={panelRef} className="grid h-56 place-items-center rounded-[9px] border hairline bg-[color:var(--panel)] p-6 text-sm text-[color:var(--muted)]" role="status" aria-busy="true">正在加载历史趋势…</div>;
  return <div ref={panelRef}><PriceHistory points={trend} /></div>;
}
