"use client";

import { useEffect, useState } from "react";
import { Bookmark } from "@phosphor-icons/react";
import { MAX_WATCHLIST_ITEMS, readWatchlist, WATCHLIST_EVENT, writeWatchlist } from "@/components/watch-button";

export function ProductCardBookmark({ slug, name, currency = "CNY", suggestedPrice = "" }: { slug: string; name: string; currency?: string; suggestedPrice?: string | null }) {
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
      if (writeWatchlist(current.filter((item) => item.slug !== slug))) setWatched(false);
      return;
    }
    if (current.length >= MAX_WATCHLIST_ITEMS) return;
    const next = [
      ...current,
      { slug, name, currency, threshold: suggestedPrice || "", added_at: new Date().toISOString() },
    ];
    if (writeWatchlist(next)) setWatched(true);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={watched}
      aria-label={watched ? `取消关注 ${name}` : `关注 ${name}`}
      className={`product-card-bookmark${watched ? " is-saved" : ""}`}
    >
      <Bookmark size={15} weight={watched ? "fill" : "regular"} />
    </button>
  );
}
