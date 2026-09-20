"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowClockwise,
  BellRinging,
  CheckCircle,
  Copy,
  Rss,
  Trash,
  Envelope,
  ChatCircleDots,
  User,
  WarningCircle,
  Lightning,
  Sparkle,
  SlidersHorizontal,
} from "@phosphor-icons/react";
import type { CatalogResponse, ProductCard } from "@/lib/types";
import { money, relativeTime } from "@/lib/format";
import {
  normalizeWatchThreshold,
  readAnonymousWatchlist,
  readUserWatchlist,
  WATCHLIST_EVENT,
  type WatchItem,
  writeAnonymousWatchlist,
  writeUserWatchlist,
} from "@/components/watch-button";
import {
  AUTH_CHANGE_EVENT,
  deleteUserSubscription,
  fetchAuthMe,
  fetchUserSubscriptions,
  saveUserSubscription,
  updateUserSubscription,
  type UserSubscriptionItem,
} from "@/lib/auth-client";
import { LoginModal } from "@/components/login-modal";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export function WatchlistClient({ previewState }: { previewState?: "empty" | "loading" | "error" }) {
  const [authenticated, setAuthenticated] = useState<boolean>(false);
  const [userId, setUserId] = useState<number | null>(null);
  const [userNickname, setUserNickname] = useState<string>("");
  const [emailBound, setEmailBound] = useState<boolean>(false);
  const [botBound, setBotBound] = useState<boolean>(false);
  const [subscriptions, setSubscriptions] = useState<UserSubscriptionItem[]>([]);
  const [localItems, setLocalItems] = useState<WatchItem[]>([]);
  const [products, setProducts] = useState<Record<string, ProductCard>>({});
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [siteOrigin, setSiteOrigin] = useState("");
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [actionNotice, setActionNotice] = useState<{ type: "info" | "warning" | "success"; text: string } | null>(null);

  // Threshold draft inputs to allow smooth typing before persisting
  const [thresholdDrafts, setThresholdDrafts] = useState<Record<string, string>>({});
  // Slugs whose product card request finished without data (non-2xx, network
  // error or empty result) so the row can offer a retry instead of spinning.
  const [productLoadFailed, setProductLoadFailed] = useState<Set<string>>(new Set());
  // Bumped by the retry button to re-run the product fetch effect.
  const [productReloadNonce, setProductReloadNonce] = useState(0);
  const loadGeneration = useRef(0);

  // 1. Initial Load: Check Auth & fetch either Cloud Subscriptions or Local Items
  const loadData = useCallback(async () => {
    const generation = ++loadGeneration.current;
    setActionNotice(null);
    setLoading(true);
    setLoadFailed(false);
    setAuthenticated(false);
    setUserId(null);
    setUserNickname("");
    setEmailBound(false);
    setBotBound(false);
    setSubscriptions([]);
    setLocalItems([]);
    setProducts({});
    setThresholdDrafts({});
    try {
      const auth = await fetchAuthMe();
      if (generation !== loadGeneration.current) return;
      if (auth.authenticated && auth.user) {
        let cloudData = await fetchUserSubscriptions();
        if (generation !== loadGeneration.current) return;

        const local = readAnonymousWatchlist();
        const existingCloudSlugs = new Set(cloudData.items.map((i) => i.product_slug));
        const toMigrate = local.filter((item) => !existingCloudSlugs.has(item.slug));

        if (toMigrate.length > 0) {
          const results: boolean[] = [];
          for (const item of toMigrate) {
            try {
              await saveUserSubscription({
                product_slug: item.slug,
                target_price: item.threshold || null,
                notify_email: true,
                notify_bot: true,
              });
              results.push(true);
            } catch {
              results.push(false);
            }
          }
          if (generation !== loadGeneration.current) return;
          const succeeded = results.filter(Boolean).length;
          writeAnonymousWatchlist(toMigrate.filter((_, index) => !results[index]));
          cloudData = await fetchUserSubscriptions();
          if (generation !== loadGeneration.current) return;
          const failedCount = toMigrate.length - succeeded;
          if (succeeded > 0) {
            setActionNotice({
              type: failedCount > 0 ? "warning" : "success",
              text:
                failedCount > 0
                  ? `已同步 ${succeeded} 个关注商品至云端，${failedCount} 个失败（已保留在本地，可稍后重试）。`
                  : `已自动将您浏览器中暂存的 ${succeeded} 个关注商品同步至云端！`,
            });
          } else {
            setActionNotice({
              type: "warning",
              text: `同步失败，${failedCount} 个本地关注商品仍保留在浏览器中，请稍后重试。`,
            });
          }
        } else if (local.length > 0) {
          writeAnonymousWatchlist([]);
        }

        setAuthenticated(true);
        setUserId(auth.user.id);
        setUserNickname(auth.user.nickname || "用户");
        setEmailBound(cloudData.email_bound);
        setBotBound(cloudData.bot_bound);
        setSubscriptions(cloudData.items);
        writeUserWatchlist(
          auth.user.id,
          cloudData.items.map((sub) => ({
            slug: sub.product_slug,
            name: sub.product_name,
            currency: sub.current_currency || "CNY",
            threshold: sub.target_price || "",
            added_at: sub.created_at,
          }))
        );
      } else {
        setLocalItems(readAnonymousWatchlist());
      }
    } catch (error: any) {
      if (generation !== loadGeneration.current) return;
      setLoadFailed(true);
      setActionNotice({
        type: "warning",
        text: error?.message || "关注清单暂时无法读取，现有云端和本地记录均未被修改。",
      });
    } finally {
      if (generation === loadGeneration.current) setLoading(false);
    }
  }, []);

  // Initial load runs once. Storage listeners live in their own effect so the
  // state updates made by loadData cannot retrigger it in a loop.
  useEffect(() => {
    void loadData();
    const handleAuthChange = () => void loadData();
    window.addEventListener(AUTH_CHANGE_EVENT, handleAuthChange);
    return () => window.removeEventListener(AUTH_CHANGE_EVENT, handleAuthChange);
  }, [loadData]);

  useEffect(() => {
    setSiteOrigin(window.location.origin);
  }, []);

  useEffect(() => {
    const handleStorageChange = () => {
      if (!authenticated) {
        setLocalItems(readAnonymousWatchlist());
      }
    };
    window.addEventListener(WATCHLIST_EVENT, handleStorageChange);
    window.addEventListener("storage", handleStorageChange);
    return () => {
      window.removeEventListener(WATCHLIST_EVENT, handleStorageChange);
      window.removeEventListener("storage", handleStorageChange);
    };
  }, [authenticated]);

  // Unified items list
  const displayItems = useMemo(() => {
    if (authenticated) {
      return subscriptions.map((sub) => ({
        slug: sub.product_slug,
        name: sub.product_name,
        currency: sub.current_currency || "CNY",
        threshold: thresholdDrafts[sub.product_slug] ?? (sub.target_price || ""),
        notifyEmail: sub.notify_email,
        notifyBot: sub.notify_bot,
        isCloud: true,
      }));
    }
    return localItems.map((item) => ({
      slug: item.slug,
      name: item.name,
      currency: item.currency || "CNY",
      threshold: thresholdDrafts[item.slug] ?? (item.threshold || ""),
      notifyEmail: false,
      notifyBot: false,
      isCloud: false,
    }));
  }, [authenticated, subscriptions, localItems, thresholdDrafts]);

  // Load live product cards for price & inventory details
  useEffect(() => {
    let active = true;
    const slugs = displayItems.map((item) => item.slug);
    async function loadProducts() {
      if (displayItems.length === 0) {
        setProducts({});
        setProductLoadFailed(new Set());
        return;
      }
      setProductLoadFailed(new Set());
      const chunks: string[][] = [];
      for (let index = 0; index < slugs.length; index += 20) {
        chunks.push(slugs.slice(index, index + 20));
      }
      const responses = await Promise.all(
        chunks.map(async (chunk) => {
          try {
            const response = await fetch(
              `${API}/api/v1/products?products=${encodeURIComponent(chunk.join(","))}&sort=quality`,
              { cache: "no-store" }
            );
            if (!response.ok) return [];
            return ((await response.json()) as CatalogResponse).items;
          } catch {
            return [];
          }
        })
      );
      if (active) {
        const results = responses.flat();
        setProducts(
          Object.fromEntries(
            results.map((product) => [product.slug, product])
          )
        );
        // Track which rows ended with no data so they can show a retry state
        // instead of a permanent "loading" spinner.
        const loadedSlugs = new Set(
          results.map((product) => product.slug)
        );
        setProductLoadFailed(new Set(slugs.filter((slug) => !loadedSlugs.has(slug))));
      }
    }
    void loadProducts();
    return () => {
      active = false;
    };
  }, [displayItems.map((i) => i.slug).join(","), productReloadNonce]);

  // Atom feed URL for RSS readers
  const feed = useMemo(() => {
    if (!siteOrigin) return { url: "", count: 0, truncated: false };
    const targets: string[] = [];
    for (const item of displayItems.slice(0, 20)) {
      const next = `${item.slug}${item.threshold ? `:${item.threshold}` : ""}`;
      if ([...targets, next].join(",").length > 1000) break;
      targets.push(next);
    }
    if (!targets.length) return { url: "", count: 0, truncated: false };
    const base = API ? new URL(API, siteOrigin).origin : siteOrigin;
    const url = new URL("/api/v1/watch.atom", base);
    url.searchParams.set("targets", targets.join(","));
    return { url: url.toString(), count: targets.length, truncated: targets.length < displayItems.length };
  }, [displayItems, siteOrigin]);
  const feedUrl = feed.url;

  // Update target price
  const handleThresholdChange = (slug: string, value: string) => {
    setThresholdDrafts((prev) => ({ ...prev, [slug]: value }));
  };

  const handleThresholdCommit = async (slug: string) => {
    const draft = thresholdDrafts[slug];
    if (draft === undefined) return;

    const normalized = normalizeWatchThreshold(draft);
    if (normalized === null) {
      // Invalid number input: drop the draft so the saved value is shown again.
      setThresholdDrafts((prev) => {
        const copy = { ...prev };
        delete copy[slug];
        return copy;
      });
      return;
    }

    if (authenticated) {
      try {
        const updated = await updateUserSubscription(slug, { target_price: normalized || null });
        setSubscriptions((prev) =>
          prev.map((s) => (s.product_slug === slug ? { ...s, ...updated } : s))
        );
        // Only clear the draft on success, and only if the user has not typed
        // something newer while the request was in flight.
        setThresholdDrafts((prev) => {
          if (prev[slug] !== draft) return prev;
          const copy = { ...prev };
          delete copy[slug];
          return copy;
        });
      } catch (err: any) {
        // Restore the persisted value so the UI matches the server state.
        setThresholdDrafts((prev) => {
          const copy = { ...prev };
          delete copy[slug];
          return copy;
        });
        setActionNotice({ type: "warning", text: err.message || "更新目标价失败，已恢复为上次保存的值" });
      }
    } else {
      const next = localItems.map((item) => (item.slug === slug ? { ...item, threshold: normalized } : item));
      if (writeAnonymousWatchlist(next)) {
        setLocalItems(next);
        setThresholdDrafts((prev) => {
          if (prev[slug] !== draft) return prev;
          const copy = { ...prev };
          delete copy[slug];
          return copy;
        });
      }
    }
  };

  // Toggle Email Channel
  const handleToggleEmail = async (slug: string, currentVal: boolean) => {
    if (!authenticated) {
      setShowLoginModal(true);
      return;
    }
    if (!currentVal && !emailBound) {
      setActionNotice({
        type: "warning",
        text: "您尚未绑定接收邮箱。请前往个人中心绑定邮箱后，降价邮件提醒即可自动激活。",
      });
    }
    try {
      const updated = await updateUserSubscription(slug, { notify_email: !currentVal });
      setSubscriptions((prev) =>
        prev.map((s) => (s.product_slug === slug ? { ...s, ...updated } : s))
      );
    } catch (err: any) {
      setActionNotice({ type: "warning", text: err.message || "更新提醒渠道失败" });
    }
  };

  // Toggle Bot Channel
  const handleToggleBot = async (slug: string, currentVal: boolean) => {
    if (!authenticated) {
      setShowLoginModal(true);
      return;
    }
    if (!currentVal && !botBound) {
      setActionNotice({
        type: "warning",
        text: "您尚未连接 QQ 机器人。请前往个人中心扫码加好友，即可通过私聊接收降价推送与指令交互。",
      });
    }
    try {
      const updated = await updateUserSubscription(slug, { notify_bot: !currentVal });
      setSubscriptions((prev) =>
        prev.map((s) => (s.product_slug === slug ? { ...s, ...updated } : s))
      );
    } catch (err: any) {
      setActionNotice({ type: "warning", text: err.message || "更新提醒渠道失败" });
    }
  };

  // Remove item
  const handleRemove = async (slug: string) => {
    if (authenticated) {
      try {
        await deleteUserSubscription(slug);
        setSubscriptions((prev) => prev.filter((s) => s.product_slug !== slug));
        if (userId !== null) {
          writeUserWatchlist(
            userId,
            readUserWatchlist(userId).filter((item) => item.slug !== slug)
          );
        }
      } catch (err: any) {
        // Keep the item visible so the user can retry; the server still has it.
        setActionNotice({ type: "warning", text: err.message || "删除关注失败" });
        return;
      }
    }
    const nextLocal = readAnonymousWatchlist().filter((item) => item.slug !== slug);
    writeAnonymousWatchlist(nextLocal);
    setLocalItems(nextLocal);
  };

  // Copy Atom feed
  const copyFeed = async () => {
    if (!feedUrl) return;
    await navigator.clipboard.writeText(feedUrl);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  // Loading Skeleton
  if (previewState === "loading" || loading) {
    return (
      <section className="surface-panel p-6 sm:p-8" role="status" aria-busy="true" data-vds-layer="evidence">
        <p className="section-kicker">正在连接价格监控数据中心</p>
        <h2 className="mt-2 text-2xl font-semibold">正在同步关注清单与提醒配置…</h2>
        <div className="mt-6 grid gap-3" aria-hidden="true">
          <span className="h-16 animate-pulse rounded-[10px] bg-[color:var(--subtle)]" />
          <span className="h-16 animate-pulse rounded-[10px] bg-[color:var(--subtle)]" />
          <span className="h-16 animate-pulse rounded-[10px] bg-[color:var(--subtle)]" />
        </div>
      </section>
    );
  }

  // Error preview
  if (previewState === "error" || loadFailed) {
    return (
      <div className="empty-state" role="alert" data-vds-layer="evidence">
        <ArrowClockwise className="mx-auto" size={34} />
        <h2 className="mt-4 text-2xl font-semibold text-[color:var(--ink)]">关注清单暂时无法读取</h2>
        <p className="mt-3 text-sm leading-6">云端与本地关注记录未受影响。退出错误预览后可以重新读取。</p>
        <button type="button" onClick={() => void loadData()} className="button-primary mt-6">
          重新读取
        </button>
      </div>
    );
  }

  // Empty state
  if (previewState === "empty" || !displayItems.length) {
    return (
      <div className="space-y-6">
        {!authenticated && (
          <div className="p-5 rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--paper)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-[color:var(--ink)] flex items-center gap-2">
                <Sparkle size={16} weight="fill" className="text-[color:var(--accent)]" />
                登录开启多渠道降价提醒
              </h3>
              <p className="text-xs text-[color:var(--muted)] leading-relaxed">
                登录后关注的商品将持久化存储在云端，并可通过绑定的邮箱或 QQ 机器人实时接收降价通知。
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowLoginModal(true)}
              className="button-primary tactile px-5 py-2.5 rounded-xl text-xs font-semibold shrink-0"
            >
              <User size={15} />
              <span>立即登录 / 注册</span>
            </button>
          </div>
        )}

        <div className="empty-state" role="status">
          <BellRinging className="mx-auto text-[color:var(--muted)]" size={38} />
          <h2 className="mt-4 text-2xl font-semibold text-[color:var(--ink)]">还没有关注任何商品</h2>
          <p className="mt-3 text-sm leading-6 max-w-md mx-auto text-[color:var(--muted)]">
            浏览商品目录时，点击“关注商品 (降价提醒)”即可加入监控。设定目标价后，价格达标将第一时间发送私聊提醒。
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/products" className="button-primary tactile">
              浏览报价目录
            </Link>
            {!authenticated && (
              <button
                type="button"
                onClick={() => setShowLoginModal(true)}
                className="button-secondary tactile"
              >
                登录账号
              </button>
            )}
          </div>
        </div>

        <LoginModal
          isOpen={showLoginModal}
          onClose={() => setShowLoginModal(false)}
          onSuccess={() => void loadData()}
        />
      </div>
    );
  }

  // Count reaching threshold
  const reachedCount = displayItems.filter((item) => {
    const product = products[item.slug];
    const current = product?.lowest_price ? Number(product.lowest_price) : null;
    const threshold = item.threshold ? Number(item.threshold) : null;
    return Boolean(
      product && product.in_stock_count > 0 && threshold !== null && current !== null && current <= threshold
    );
  }).length;

  return (
    <div className="space-y-8" data-vds-layer="evidence">
      {/* 1. Login or Binding Guide Banner */}
      {!authenticated ? (
        <div className="p-5 rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--paper)] flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-[color:var(--accent)]/15 text-[color:var(--ink)]">
                <Sparkle size={12} weight="fill" />
                本地暂存模式
              </span>
              <h3 className="text-sm font-bold text-[color:var(--ink)]">
                当前为未登录状态，已关注商品仅保存在本浏览器
              </h3>
            </div>
            <p className="text-xs text-[color:var(--muted)] max-w-2xl leading-relaxed">
              登录或注册账号后，关注商品将<strong>自动同步存入云端数据库</strong>，并可通过您已绑定的<strong>邮箱</strong>与 <strong>QQ 机器人</strong>在达到目标价时为您发送即时私聊提醒。
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowLoginModal(true)}
            className="button-primary tactile px-5 py-2.5 rounded-xl text-xs font-semibold shrink-0"
          >
            <User size={15} />
            <span>立即登录同步到云端</span>
          </button>
        </div>
      ) : (!emailBound || !botBound) ? (
        <div className="p-4 rounded-2xl border border-amber-500/20 bg-amber-500/5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-0.5">
            <h4 className="text-sm font-bold text-[color:var(--ink)] flex items-center gap-1.5">
              <WarningCircle size={17} className="text-amber-600" weight="fill" />
              尚未完全开启主动通知推送
            </h4>
            <p className="text-xs text-[color:var(--muted)]">
              当前状态：邮箱推送 {emailBound ? "已开通" : "未绑定"} · QQ 机器人 {botBound ? "已连接" : "未连接"}。前往个人中心配置后即可接收实时降价私聊。
            </p>
          </div>
          <Link
            href="/account"
            className="button-secondary tactile px-4 py-2 rounded-xl text-xs font-semibold shrink-0"
          >
            前往个人中心配置 →
          </Link>
        </div>
      ) : (
        <div className="p-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs text-emerald-900">
            <CheckCircle size={18} weight="fill" className="text-emerald-600 shrink-0" />
            <span>
              <strong>云端价格监控就绪</strong>：监控变动将自动通过您的有效邮箱及已连接的 QQ 机器人私聊推送。
            </span>
          </div>
          <Link href="/account" className="text-xs font-semibold text-emerald-800 hover:underline shrink-0">
            管理推送渠道
          </Link>
        </div>
      )}

      {/* Action Notice Alert */}
      {actionNotice && (
        <div
          className={`p-4 rounded-xl border text-xs flex items-center justify-between gap-3 ${
            actionNotice.type === "success"
              ? "border-emerald-500/30 bg-emerald-50 text-emerald-900"
              : actionNotice.type === "warning"
              ? "border-amber-500/30 bg-amber-50 text-amber-900"
              : "border-[color:var(--line-strong)] bg-[color:var(--subtle)] text-[color:var(--ink)]"
          }`}
        >
          <div className="flex items-center gap-2">
            {actionNotice.type === "success" && <CheckCircle size={16} weight="fill" />}
            {actionNotice.type === "warning" && <WarningCircle size={16} weight="fill" />}
            <span>{actionNotice.text}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionNotice(null)}
            className="text-[11px] underline opacity-70 hover:opacity-100"
          >
            关闭
          </button>
        </div>
      )}

      {/* 2. Overview Strip */}
      <section className="data-strip grid-cols-2 sm:grid-cols-4" aria-label="关注清单与提醒概况">
        <div className="data-cell">
          <p className="data-label">监控商品数量</p>
          <p className="data-value">{displayItems.length}</p>
        </div>
        <div className="data-cell">
          <p className="data-label">达到提醒条件</p>
          <p className="data-value">{reachedCount}</p>
        </div>
        <div className="data-cell">
          <p className="data-label">邮件推送渠道</p>
          <p className="data-value !text-sm flex items-center gap-1 mt-1">
            {!authenticated ? (
              <span className="text-[color:var(--muted)]">需登录</span>
            ) : emailBound ? (
              <span className="text-emerald-700 font-semibold flex items-center gap-1">
                <CheckCircle size={14} weight="fill" />已开启
              </span>
            ) : (
              <Link href="/account" className="text-amber-700 font-medium hover:underline text-xs">
                未绑定 (去配置)
              </Link>
            )}
          </p>
        </div>
        <div className="data-cell">
          <p className="data-label">机器人私聊渠道</p>
          <p className="data-value !text-sm flex items-center gap-1 mt-1">
            {!authenticated ? (
              <span className="text-[color:var(--muted)]">需登录</span>
            ) : botBound ? (
              <span className="text-sky-700 font-semibold flex items-center gap-1">
                <CheckCircle size={14} weight="fill" />已连接
              </span>
            ) : (
              <Link href="/account" className="text-sky-700 font-medium hover:underline text-xs">
                未扫码 (去加好友)
              </Link>
            )}
          </p>
        </div>
      </section>

      {/* 3. Subscriptions Table */}
      <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
        <div className="grid gap-3 border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4 text-xs font-semibold text-[color:var(--muted)] md:grid-cols-[1fr_130px_160px_170px_80px]">
          <span>商品与当前观测状态</span>
          <span>近期有货观测价</span>
          <span>降价提醒目标价</span>
          <span>推送提醒渠道</span>
          <span className="text-right">操作</span>
        </div>

        <div className="divide-y divide-[color:var(--line)]">
          {displayItems.map((item) => {
            const product = products[item.slug];
            const current = product?.lowest_price ? Number(product.lowest_price) : null;
            const threshold = item.threshold ? Number(item.threshold) : null;
            const reached = Boolean(
              product && product.in_stock_count > 0 && threshold !== null && current !== null && current <= threshold
            );

            return (
              <div
                key={item.slug}
                className="watchlist-row grid gap-4 px-5 py-5 md:grid-cols-[1fr_130px_160px_170px_80px] md:items-center hover:bg-[color:var(--paper)]/50 transition-colors"
              >
                {/* Product Title and Stock Info */}
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={`/products/${encodeURIComponent(item.slug)}`}
                      className="font-semibold text-sm hover:underline text-[color:var(--ink)]"
                    >
                      {product?.display_name || item.name}
                    </Link>
                    {reached ? (
                      <span className="status-pill status-success !py-0.5 !text-[10px] inline-flex items-center gap-1">
                        <CheckCircle size={12} weight="fill" />
                        达到降价条件
                      </span>
                    ) : (
                      <span className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded bg-[color:var(--subtle)] border border-[color:var(--line)] text-[color:var(--muted)]">
                        监控中
                      </span>
                    )}
                  </div>
                  <p className="mt-1.5 text-xs text-[color:var(--muted)]">
                    {product ? (
                      <>
                        <span className={product.in_stock_count > 0 ? "text-emerald-700 font-medium" : "text-amber-700"}>
                          {product.in_stock_count > 0 ? `${product.in_stock_count} 平台有现货` : "暂无现货"}
                        </span>
                        {" · "}
                        <span>{product.trusted_offer_count} 条有效报价</span>
                        {" · "}
                        <span>{relativeTime(product.last_updated_at)} 更新</span>
                      </>
                    ) : productLoadFailed.has(item.slug) ? (
                      <span className="text-amber-700">
                        观测数据加载失败，
                        <button
                          type="button"
                          className="underline hover:text-[color:var(--ink)]"
                          onClick={() => setProductReloadNonce((value) => value + 1)}
                        >
                          点此重试
                        </button>
                      </span>
                    ) : (
                      "正在加载观测数据…"
                    )}
                  </p>
                </div>

                {/* Lowest Live Price */}
                <div className="font-semibold text-sm text-[color:var(--ink)]">
                  {product ? money(product.lowest_price, product.price_currency) : "暂无"}
                </div>

                {/* Target Price Input */}
                <div>
                  <label className="block text-xs">
                    <span className="sr-only">{item.name} 提醒目标价</span>
                    <span className="flex min-h-10 items-center rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3 text-xs focus-within:border-[color:var(--ink)]">
                      <span className="text-[color:var(--muted)] font-medium pr-1">
                        {product?.price_currency || item.currency || "¥"}
                      </span>
                      <input
                        value={item.threshold}
                        onChange={(e) => handleThresholdChange(item.slug, e.target.value)}
                        onBlur={() => void handleThresholdCommit(item.slug)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            (e.target as HTMLInputElement).blur();
                          }
                        }}
                        inputMode="decimal"
                        placeholder="不限 (有降即推)"
                        className="w-full bg-transparent py-2 text-xs outline-none text-[color:var(--ink)] placeholder:text-[color:var(--muted)]/60 font-mono"
                      />
                    </span>
                  </label>
                  <p className="mt-1 text-[10px] text-[color:var(--muted)]">
                    {item.threshold ? "现货低于此价时推送" : "现货出现任意降价即推"}
                  </p>
                </div>

                {/* Channel Toggles (Email & Bot) */}
                <div className="flex items-center gap-2">
                  {/* Email Toggle */}
                  <button
                    type="button"
                    onClick={() => void handleToggleEmail(item.slug, item.notifyEmail)}
                    title={
                      !authenticated
                        ? "点击登录并开启邮件提醒"
                        : item.notifyEmail
                        ? "邮件推送已开启 (点击关闭)"
                        : "邮件推送已关闭 (点击开启)"
                    }
                    className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition ${
                      item.notifyEmail
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-800"
                        : "border-[color:var(--line)] bg-[color:var(--subtle)] text-[color:var(--muted)] opacity-60 hover:opacity-100"
                    }`}
                  >
                    <Envelope size={13} weight={item.notifyEmail ? "fill" : "regular"} />
                    <span>邮件</span>
                  </button>

                  {/* Bot Toggle */}
                  <button
                    type="button"
                    onClick={() => void handleToggleBot(item.slug, item.notifyBot)}
                    title={
                      !authenticated
                        ? "点击登录并开启机器人私聊提醒"
                        : item.notifyBot
                        ? "QQ 机器人推送已开启 (点击关闭)"
                        : "QQ 机器人推送已关闭 (点击开启)"
                    }
                    className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition ${
                      item.notifyBot
                        ? "border-sky-500/40 bg-sky-500/10 text-sky-800"
                        : "border-[color:var(--line)] bg-[color:var(--subtle)] text-[color:var(--muted)] opacity-60 hover:opacity-100"
                    }`}
                  >
                    <ChatCircleDots size={13} weight={item.notifyBot ? "fill" : "regular"} />
                    <span>机器人</span>
                  </button>
                </div>

                {/* Remove Action */}
                <div className="text-right">
                  <button
                    type="button"
                    onClick={() => void handleRemove(item.slug)}
                    className="button-tertiary !px-2 !py-1 text-xs text-[color:var(--danger)] inline-flex items-center gap-1 hover:bg-rose-50 rounded-lg"
                  >
                    <Trash size={15} />
                    <span>移除</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 4. Atom / RSS Reader Subscription Feed */}
      <section className="surface-subtle p-6 rounded-2xl border border-[color:var(--line)]">
        <div className="flex items-start gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-800 flex items-center justify-center shrink-0">
            <Rss size={20} />
          </div>
          <div>
            <h2 className="text-base font-semibold text-[color:var(--ink)]">
              备用追踪：Atom / RSS 离线阅读器订阅
            </h2>
            <p className="mt-1.5 max-w-3xl text-xs leading-relaxed text-[color:var(--muted)]">
              除了上述通过云端已绑定的邮箱和 QQ 机器人直接接收推送之外，您也可以将下方专属地址添加到支持 Atom / RSS 的客户端（如 NetNewsWire、Feedly 或自建服务），在阅读器中同步追踪最新报价与现货动态。
              {feed.truncated ? ` 当前 Feed 按接口上限包含前 ${feed.count} 个关注项。` : ""}
            </p>
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-2.5 sm:flex-row">
          <input
            readOnly
            value={feedUrl}
            aria-label="Atom Feed 地址"
            className="field min-w-0 flex-1 text-xs font-mono bg-[color:var(--panel)]"
          />
          <button
            type="button"
            onClick={copyFeed}
            className="button-primary tactile shrink-0 text-xs px-4 py-2.5 rounded-xl font-medium inline-flex items-center gap-1.5"
          >
            <Copy size={15} />
            <span>{copied ? "已复制到剪贴板" : "复制 Atom 地址"}</span>
          </button>
        </div>
      </section>

      {/* Login Modal */}
      <LoginModal
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
        onSuccess={() => void loadData()}
      />
    </div>
  );
}
