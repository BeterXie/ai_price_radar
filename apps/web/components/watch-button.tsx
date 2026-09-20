"use client";

import { useEffect, useState } from "react";
import { Bell, BellRinging } from "@phosphor-icons/react";
import {
  AUTH_CHANGE_EVENT,
  deleteUserSubscription,
  fetchAuthMe,
  fetchUserSubscriptions,
  saveUserSubscription,
  type UserSubscriptionItem,
} from "@/lib/auth-client";

export const WATCHLIST_KEY = "ai-price-radar:watchlist:v1";
// Anonymous (not-yet-logged-in) items live under their own key so they are
// never confused with a logged-in account's cloud cache.
export const ANONYMOUS_WATCHLIST_KEY = "ai-price-radar:watchlist:anon:v1";
export const WATCHLIST_EVENT = "ai-price-radar:watchlist-change";
export const MAX_WATCHLIST_ITEMS = 20;

export function userWatchlistKey(userId: number | string): string {
  return `${WATCHLIST_KEY}:user:${userId}`;
}

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
  return Number.isFinite(amount) && amount > 0 && amount <= 99_999_999.99 ? normalized : null;
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

function parseWatchlist(raw: string | null): WatchItem[] {
  if (!raw) return [];
  try {
    const value = JSON.parse(raw);
    if (!Array.isArray(value)) return [];
    const seen = new Set<string>();
    return value.flatMap((item) => {
      const normalized = normalizeWatchItem(item);
      if (!normalized || seen.has(normalized.slug)) return [];
      seen.add(normalized.slug);
      return [normalized];
    });
  } catch {
    return [];
  }
}

/**
 * Persists a list. `cap` is only applied to the anonymous local list, which is
 * the user-facing "max N followed products" rule; the per-account mirror simply
 * reflects the server list (the API imposes no subscription limit).
 */
function persistWatchlist(key: string, items: WatchItem[], cap: number | null): boolean {
  if (typeof window === "undefined") return false;
  let normalized = items.flatMap((item) => {
    const value = normalizeWatchItem(item);
    return value ? [value] : [];
  });
  if (cap !== null) {
    normalized = normalized.slice(0, cap);
  }
  try {
    window.localStorage.setItem(key, JSON.stringify(normalized));
    window.dispatchEvent(new Event(WATCHLIST_EVENT));
    return true;
  } catch {
    return false;
  }
}

/** Anonymous (pre-login) list. Used as the one-time migration source. */
export function readAnonymousWatchlist(): WatchItem[] {
  if (typeof window === "undefined") return [];
  let items = parseWatchlist(window.localStorage.getItem(ANONYMOUS_WATCHLIST_KEY));
  if (items.length === 0) {
    // One-time absorb of the legacy shared key, then drop it so it can never
    // leak across accounts (it used to hold another user's cloud cache).
    const legacy = parseWatchlist(window.localStorage.getItem(WATCHLIST_KEY));
    if (legacy.length > 0) {
      items = legacy;
      try {
        window.localStorage.setItem(
          ANONYMOUS_WATCHLIST_KEY,
          JSON.stringify(legacy.slice(0, MAX_WATCHLIST_ITEMS))
        );
        window.localStorage.removeItem(WATCHLIST_KEY);
      } catch {
        // ignore
      }
    }
  }
  return items.slice(0, MAX_WATCHLIST_ITEMS);
}

export function writeAnonymousWatchlist(items: WatchItem[]): boolean {
  return persistWatchlist(ANONYMOUS_WATCHLIST_KEY, items, MAX_WATCHLIST_ITEMS);
}

/** Per-account cloud cache, keyed by user id so accounts cannot leak into each other. */
export function readUserWatchlist(userId: number | string): WatchItem[] {
  if (typeof window === "undefined") return [];
  return parseWatchlist(window.localStorage.getItem(userWatchlistKey(userId)));
}

export function writeUserWatchlist(userId: number | string, items: WatchItem[]): boolean {
  // No cap: this mirrors the server list, which has no limit.
  return persistWatchlist(userWatchlistKey(userId), items, null);
}

export function clearUserWatchlist(userId: number | string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(userWatchlistKey(userId));
    window.dispatchEvent(new Event(WATCHLIST_EVENT));
  } catch {
    // ignore
  }
}

/** Legacy accessors kept for callers that only deal with anonymous data. */
export function readWatchlist(): WatchItem[] {
  return readAnonymousWatchlist();
}

export function writeWatchlist(items: WatchItem[]): boolean {
  return writeAnonymousWatchlist(items);
}

function subscriptionToWatchItem(sub: UserSubscriptionItem): WatchItem {
  return {
    slug: sub.product_slug,
    name: sub.product_name,
    currency: sub.current_currency || "CNY",
    threshold: sub.target_price || "",
    added_at: sub.created_at,
  };
}

export function WatchButton({
  slug,
  name,
  currency = "CNY",
  suggestedPrice = "",
}: {
  slug: string;
  name: string;
  currency?: string;
  suggestedPrice?: string | null;
}) {
  const [watched, setWatched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [userId, setUserId] = useState<number | null>(null);
  const [cloudSlugs, setCloudSlugs] = useState<Set<string> | null>(null);
  const [authStatus, setAuthStatus] = useState<"loading" | "authenticated" | "anonymous" | "error">("loading");

  useEffect(() => {
    let cancelled = false;
    const loadState = async () => {
      setAuthStatus("loading");
      try {
        const auth = await fetchAuthMe();
        if (cancelled) return;
        if (auth.authenticated && auth.user) {
          const cloud = await fetchUserSubscriptions();
          if (cancelled) return;
          const slugs = new Set(cloud.items.map((item) => item.product_slug));
          setUserId(auth.user.id);
          setCloudSlugs(slugs);
          setWatched(slugs.has(slug));
          setAuthStatus("authenticated");
          writeUserWatchlist(auth.user.id, cloud.items.map(subscriptionToWatchItem));
        } else {
          setUserId(null);
          setCloudSlugs(null);
          setWatched(readAnonymousWatchlist().some((item) => item.slug === slug));
          setAuthStatus("anonymous");
        }
      } catch {
        if (!cancelled) {
          setAuthStatus("error");
          setError("暂时无法读取登录与关注状态，请稍后重试");
        }
      }
    };

    void loadState();
    const handleAuthChange = () => void loadState();
    window.addEventListener(AUTH_CHANGE_EVENT, handleAuthChange);
    return () => {
      cancelled = true;
      window.removeEventListener(AUTH_CHANGE_EVENT, handleAuthChange);
    };
  }, [slug]);

  useEffect(() => {
    const syncAnonymousState = () => {
      if (authStatus === "anonymous") {
        setWatched(readAnonymousWatchlist().some((item) => item.slug === slug));
      }
    };
    window.addEventListener(WATCHLIST_EVENT, syncAnonymousState);
    window.addEventListener("storage", syncAnonymousState);
    return () => {
      window.removeEventListener(WATCHLIST_EVENT, syncAnonymousState);
      window.removeEventListener("storage", syncAnonymousState);
    };
  }, [authStatus, slug]);

  async function refreshCloudState(accountId: number): Promise<Set<string>> {
    const cloud = await fetchUserSubscriptions();
    const slugs = new Set(cloud.items.map((item) => item.product_slug));
    setUserId(accountId);
    setCloudSlugs(slugs);
    setWatched(slugs.has(slug));
    setAuthStatus("authenticated");
    writeUserWatchlist(accountId, cloud.items.map(subscriptionToWatchItem));
    return slugs;
  }

  async function performAddSubscription(accountId: number) {
    setError(null);
    const threshold = normalizeWatchThreshold(suggestedPrice || "") ?? "";
    try {
      const saved = await saveUserSubscription({
        product_slug: slug,
        target_price: threshold || null,
        notify_email: true,
        notify_bot: true,
      });
      writeUserWatchlist(accountId, [
        ...readUserWatchlist(accountId).filter((item) => item.slug !== slug),
        subscriptionToWatchItem(saved),
      ]);
      setUserId(accountId);
      setAuthStatus("authenticated");
      setCloudSlugs((prev) => new Set([...(prev || []), slug]));
      setWatched(true);
    } catch (err: any) {
      setError(err?.message || "关注失败，请稍后重试");
    }
  }

  async function toggle() {
    if (loading) return;
    setLoading(true);
    setError(null);

    try {
      const auth = await fetchAuthMe();
      if (!auth.authenticated || !auth.user) {
        setUserId(null);
        setCloudSlugs(null);
        setAuthStatus("anonymous");
        const current = readAnonymousWatchlist();
        const isWatched = current.some((item) => item.slug === slug);
        const next = isWatched
          ? current.filter((item) => item.slug !== slug)
          : [
              ...current,
              {
                slug,
                name,
                currency,
                threshold: normalizeWatchThreshold(suggestedPrice || "") ?? "",
                added_at: new Date().toISOString(),
              },
            ];
        if (!isWatched && current.length >= MAX_WATCHLIST_ITEMS) {
          setError(`匿名关注最多保存 ${MAX_WATCHLIST_ITEMS} 项，请先移除一项或登录同步`);
          return;
        }
        if (!writeAnonymousWatchlist(next)) {
          setError("浏览器未允许保存本地关注清单");
          return;
        }
        setWatched(!isWatched);
        return;
      }

      const accountId = auth.user.id;
      const currentCloudSlugs = userId === accountId && cloudSlugs
        ? cloudSlugs
        : await refreshCloudState(accountId);
      const isWatched = currentCloudSlugs.has(slug);
      if (isWatched) {
        try {
          await deleteUserSubscription(slug);
        } catch (err: any) {
          setError(err?.message || "取消关注失败，请稍后重试");
          return;
        }
        writeUserWatchlist(
          accountId,
          readUserWatchlist(accountId).filter((item) => item.slug !== slug)
        );
        setCloudSlugs((prev) => {
          const next = new Set(prev || []);
          next.delete(slug);
          return next;
        });
        setWatched(false);
      } else {
        await performAddSubscription(accountId);
      }
    } catch (err: any) {
      setError(err?.message || "关注状态暂时无法更新，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={toggle}
        disabled={loading || authStatus === "loading"}
        aria-pressed={watched}
        className={`tactile inline-flex items-center gap-2 rounded-[10px] px-4 py-2.5 text-sm font-medium transition ${
          watched
            ? "bg-[color:var(--accent)] text-[color:var(--accent-ink)]"
            : "border border-[color:var(--line-strong)] hover:bg-[color:var(--paper)]"
        }`}
      >
        {watched ? <BellRinging size={17} weight="fill" /> : <Bell size={17} />}
        <span>{watched ? "已关注 (降价提醒)" : "关注商品 (降价提醒)"}</span>
      </button>
      {error && (
        <p className="mt-1.5 text-xs text-[color:var(--danger)]" role="alert">
          {error}
        </p>
      )}
    </>
  );
}
