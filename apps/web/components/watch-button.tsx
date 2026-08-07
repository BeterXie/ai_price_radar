"use client";

import { useEffect, useState } from "react";
import { Bell, BellRinging } from "@phosphor-icons/react";

export const WATCHLIST_KEY = "ai-price-radar:watchlist:v1";
export const WATCHLIST_EVENT = "ai-price-radar:watchlist-change";

export type WatchItem = {
  slug: string;
  name: string;
  currency?: string;
  threshold: string;
  added_at: string;
};

export function readWatchlist(): WatchItem[] {
  if (typeof window === "undefined") return [];
  try {
    const value = JSON.parse(window.localStorage.getItem(WATCHLIST_KEY) || "[]");
    return Array.isArray(value)
      ? value.filter((item): item is WatchItem => Boolean(item && typeof item.slug === "string" && typeof item.name === "string"))
      : [];
  } catch {
    return [];
  }
}

export function writeWatchlist(items: WatchItem[]) {
  window.localStorage.setItem(WATCHLIST_KEY, JSON.stringify(items));
  window.dispatchEvent(new Event(WATCHLIST_EVENT));
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
      writeWatchlist(current.filter((item) => item.slug !== slug));
      return;
    }
    writeWatchlist([
      ...current,
      {
        slug,
        name,
        currency,
        threshold: suggestedPrice || "",
        added_at: new Date().toISOString(),
      },
    ]);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={watched}
      className={`tactile inline-flex items-center gap-2 rounded-[10px] px-4 py-2.5 text-sm font-medium ${watched ? "bg-[color:var(--accent)] text-[color:var(--accent-ink)]" : "border border-[color:var(--line-strong)]"}`}
    >
      {watched ? <BellRinging size={17} weight="fill" /> : <Bell size={17} />}
      {watched ? "已关注" : "关注价格与库存"}
    </button>
  );
}
