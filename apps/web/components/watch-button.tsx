"use client";

import { useEffect, useState } from "react";
import { Bell, BellRinging } from "@phosphor-icons/react";

export const WATCHLIST_KEY = "ai-price-radar:watchlist:v1";
export const WATCHLIST_EVENT = "ai-price-radar:watchlist-change";
export const MAX_WATCHLIST_ITEMS = 20;

export type WatchItem = {
  slug: string;
  name: string;
  currency?: string;
  threshold: string;
  added_at: string;
};

export function normalizeWatchThreshold(value: string): string | null {
  const normalized = value.trim();
  if (!normalized) return "";
  if (!/^(?:0|[1-9]\d*)(?:\.\d{0,2})?$/.test(normalized)) return null;
  const amount = Number(normalized);
  return Number.isFinite(amount) && amount > 0 ? normalized : null;
}

function normalizeWatchItem(value: unknown): WatchItem | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Partial<WatchItem>;
  if (typeof item.slug !== "string" || !item.slug.trim() || typeof item.name !== "string" || !item.name.trim()) return null;
  if (typeof item.added_at !== "string" || !item.added_at.trim()) return null;
  const threshold = normalizeWatchThreshold(typeof item.threshold === "string" ? item.threshold : "");
  if (threshold === null) return null;
  return {
    slug: item.slug,
    name: item.name,
    currency: typeof item.currency === "string" && item.currency.trim() ? item.currency : "CNY",
    threshold,
    added_at: item.added_at,
  };
}

export function readWatchlist(): WatchItem[] {
  if (typeof window === "undefined") return [];
  try {
    const value = JSON.parse(window.localStorage.getItem(WATCHLIST_KEY) || "[]");
    if (!Array.isArray(value)) return [];
    const seen = new Set<string>();
    return value.flatMap((item) => {
      const normalized = normalizeWatchItem(item);
      if (!normalized || seen.has(normalized.slug)) return [];
      seen.add(normalized.slug);
      return [normalized];
    }).slice(0, MAX_WATCHLIST_ITEMS);
  } catch {
    return [];
  }
}

export function writeWatchlist(items: WatchItem[]): boolean {
  const normalized = items.flatMap((item) => {
    const value = normalizeWatchItem(item);
    return value ? [value] : [];
  }).slice(0, MAX_WATCHLIST_ITEMS);
  try {
    window.localStorage.setItem(WATCHLIST_KEY, JSON.stringify(normalized));
    window.dispatchEvent(new Event(WATCHLIST_EVENT));
    return true;
  } catch {
    return false;
  }
}

export function WatchButton({ slug, name, currency = "CNY", suggestedPrice = "" }: { slug: string; name: string; currency?: string; suggestedPrice?: string | null }) {
  const [watched, setWatched] = useState(false);

  useEffect(() => {
    const sync = () => setWatched(readWatchlist().some((item) => item.slug === slug));
    sync();
    window.addEventListener(WATCHLIST_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(WATCHLIST_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [slug]);

  function toggle() {
    const current = readWatchlist();
    if (current.some((item) => item.slug === slug)) {
      const next = current.filter((item) => item.slug !== slug);
      if (writeWatchlist(next)) setWatched(false);
      return;
    }
    if (current.length >= MAX_WATCHLIST_ITEMS) return;
    const threshold = normalizeWatchThreshold(suggestedPrice || "") ?? "";
    const next = [
      ...current,
      {
        slug,
        name,
        currency,
        threshold,
        added_at: new Date().toISOString(),
      },
    ];
    if (writeWatchlist(next)) setWatched(true);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={watched}
      className={`tactile inline-flex items-center gap-2 rounded-[10px] px-4 py-2.5 text-sm font-medium ${watched ? "bg-[color:var(--accent)] text-[color:var(--accent-ink)]" : "border border-[color:var(--line-strong)]"}`}
    >
      {watched ? <BellRinging size={17} weight="fill" /> : <Bell size={17} />}
      {watched ? "已加入清单" : "加入关注清单"}
    </button>
  );
}
