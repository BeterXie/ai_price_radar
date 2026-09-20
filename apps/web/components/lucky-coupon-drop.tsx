"use client";

import React, { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  ArrowSquareOut,
  Check,
  CheckCircle,
  Copy,
  Gift,
  Sparkle,
  Ticket,
  User,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import { fetchAuthMe, claimLuckyDrop, fetchCouponDropStatus, recordCouponDropTrigger } from "@/lib/auth-client";
import type { ShopCoupon } from "@/lib/types";
import { LoginModal } from "@/components/login-modal";
import { safeExternalHttpsUrl } from "@/lib/safe-url";
import { releaseGlobalOverlay, tryAcquireGlobalOverlay } from "@/lib/global-overlay";

const STORAGE_KEY_DISMISSED = "apr:coupon_drop_dismissed_v1";
const STORAGE_KEY_NON_HOME_CLICKED = "apr:coupon_drop_non_home_click_v1";
const STORAGE_KEY_LAST_EVAL = "apr:coupon_drop_last_eval_time_v1";
const COOLDOWN_MS = 12 * 60 * 60 * 1000; // 12 hours after dismiss
const EVAL_COOLDOWN_MS = 60 * 1000; // At most 1 probability evaluation per minute
const OVERLAY_OWNER = "coupon-drop";

export function LuckyCouponDrop() {
  const pathname = usePathname();
  const [visible, setVisible] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [claiming, setClaiming] = useState(false);
  const [claimToken, setClaimToken] = useState("");
  const [claimedCoupon, setClaimedCoupon] = useState<ShopCoupon | null>(null);
  const [claimMessage, setClaimMessage] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState<boolean | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const dialogRef = React.useRef<HTMLDivElement | null>(null);
  const copiedTimerRef = React.useRef<number | undefined>(undefined);
  const copyFailedTimerRef = React.useRef<number | undefined>(undefined);

  const resetRoundState = React.useCallback(() => {
    setVisible(false);
    setModalOpen(false);
    setClaiming(false);
    setClaimToken("");
    setClaimedCoupon(null);
    setClaimMessage(null);
    setIsSuccess(null);
    setShowLoginModal(false);
    setCopied(false);
    setCopyFailed(false);
    releaseGlobalOverlay(OVERLAY_OWNER);
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    let clickCleanup: (() => void) | undefined;

    // Disabled paths must not render the overlay at all, and navigating to one
    // has to tear down anything already on screen.
    const isDisabledPath =
      pathname.startsWith("/admin") || pathname.startsWith("/account");
    if (isDisabledPath) {
      resetRoundState();
      return () => {
        cancelled = true;
      };
    }

    // Easter egg is disabled on homepage ("除首页外其他页面存在真实页面点击动作以后才能正常触发概率")
    const isHomePage = pathname === "/" || pathname === "";
    if (isHomePage) {
      resetRoundState();
      return () => {
        cancelled = true;
      };
    }

    // If already visible or opened in modal, keep displaying without re-rolling
    if (visible || modalOpen) {
      return () => {
        cancelled = true;
      };
    }

    const pageEnteredAt = Date.now();

    async function evaluateDrop() {
      if (cancelled || typeof window === "undefined") return;

      try {
        // 1. Check dismiss cooldown (12h)
        const lastDismissed = localStorage.getItem(STORAGE_KEY_DISMISSED);
        if (lastDismissed) {
          const diff = Date.now() - parseInt(lastDismissed, 10);
          if (diff < COOLDOWN_MS) return;
        }

        // 2. Frequency limit: At most 1 probability evaluation per minute
        const lastEval =
          sessionStorage.getItem(STORAGE_KEY_LAST_EVAL) ||
          localStorage.getItem(STORAGE_KEY_LAST_EVAL);
        if (lastEval) {
          const diff = Date.now() - parseInt(lastEval, 10);
          if (diff < EVAL_COOLDOWN_MS) {
            return;
          }
        }

        // Mark current evaluation time immediately so rapid navigation doesn't bypass limit
        const nowStr = Date.now().toString();
        try {
          sessionStorage.setItem(STORAGE_KEY_LAST_EVAL, nowStr);
          localStorage.setItem(STORAGE_KEY_LAST_EVAL, nowStr);
        } catch {
          // ignore
        }

        // 3. Query backend status first so disabled/out-of-stock states stay quiet.
        const dropStatus = await fetchCouponDropStatus().catch(() => null);
        if (cancelled) return;
        if (
          !dropStatus ||
          !dropStatus.enabled ||
          !dropStatus.has_stock ||
          dropStatus.probability <= 0
        ) {
          return;
        }

        // 4. The server performs the draw and returns a signed, single-use
        // claim capability. Client randomness is never an authorization boundary.
        const qualification = await recordCouponDropTrigger(pathname).catch(() => null);
        if (cancelled || !qualification?.eligible || !qualification.claim_token) {
          return;
        }

        // 5. Trigger egg only after a server-authorized draw.
        if (!cancelled) {
          resetRoundState();
          if (!tryAcquireGlobalOverlay(OVERLAY_OWNER)) return;
          setClaimToken(qualification.claim_token);
          setVisible(true);
        }
      } catch {
        return;
      }
    }

    function scheduleDropEvaluation() {
      if (timer) window.clearTimeout(timer);
      // Wait until at least 10s after entering page (or at least 3s buffer if already past 10s)
      const elapsed = Date.now() - pageEnteredAt;
      const delay = Math.max(3000, 10_000 - elapsed);
      timer = window.setTimeout(() => {
        void evaluateDrop();
      }, delay);
    }

    // Check if real click action on non-home page was already registered in session
    let hasNonHomeClick = false;
    try {
      hasNonHomeClick = sessionStorage.getItem(STORAGE_KEY_NON_HOME_CLICKED) === "1";
    } catch {
      // ignore
    }

    if (hasNonHomeClick) {
      // Threshold already met; schedule drop evaluation after browsing delay
      scheduleDropEvaluation();
    } else {
      // Threshold not met yet: listen for real user click event on this non-home page
      const handleUserClick = (e: MouseEvent) => {
        if (!e.isTrusted) return;
        try {
          sessionStorage.setItem(STORAGE_KEY_NON_HOME_CLICKED, "1");
        } catch {
          // ignore
        }
        window.removeEventListener("click", handleUserClick, true);
        scheduleDropEvaluation();
      };

      window.addEventListener("click", handleUserClick, { capture: true, passive: true });
      clickCleanup = () => {
        window.removeEventListener("click", handleUserClick, true);
      };
    }

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
      if (clickCleanup) clickCleanup();
    };
  }, [pathname, visible, modalOpen, resetRoundState]);


  const handleDismiss = () => {
    try {
      localStorage.setItem(STORAGE_KEY_DISMISSED, Date.now().toString());
    } catch {
      // ignore
    }
    resetRoundState();
  };

  // Unmount-time cleanup for the copy feedback timers.
  useEffect(() => {
    return () => {
      if (copiedTimerRef.current !== undefined) window.clearTimeout(copiedTimerRef.current);
      if (copyFailedTimerRef.current !== undefined) window.clearTimeout(copyFailedTimerRef.current);
      releaseGlobalOverlay(OVERLAY_OWNER);
    };
  }, []);

  // Dialog a11y: focus the dialog on open, close on Escape, and keep Tab focus
  // cycling inside the dialog while it is open.
  useEffect(() => {
    if (!modalOpen) return;
    dialogRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        handleDismiss();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const current = document.activeElement;
      if (!(current instanceof Node) || !dialogRef.current.contains(current)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
        return;
      }
      if (event.shiftKey && current === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && current === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [modalOpen]);

  const handleOpenClick = () => {
    setModalOpen(true);
  };

  const handleClaim = async () => {
    setClaiming(true);
    setClaimMessage(null);
    try {
      const auth = await fetchAuthMe();
      if (!auth.authenticated || !auth.user) {
        setModalOpen(false);
        setShowLoginModal(true);
        setClaiming(false);
        return;
      }

      if (!claimToken) {
        setIsSuccess(false);
        setClaimMessage("掉落资格已失效，请重新参与活动");
        return;
      }
      const res = await claimLuckyDrop(claimToken);
      setIsSuccess(res.success);
      setClaimMessage(res.message);
      if (res.coupon) {
        setClaimedCoupon(res.coupon);
      }
    } catch (err: any) {
      setIsSuccess(false);
      setClaimMessage(err.message || "领取失败，请稍后重试");
    } finally {
      setClaiming(false);
    }
  };

  const handleCopy = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setCopyFailed(false);
      if (copiedTimerRef.current !== undefined) window.clearTimeout(copiedTimerRef.current);
      copiedTimerRef.current = window.setTimeout(() => setCopied(false), 2500);
    } catch {
      // Clipboard permission can be denied; tell the user to copy manually
      // instead of falsely reporting success.
      setCopyFailed(true);
      setCopied(false);
      if (copyFailedTimerRef.current !== undefined) window.clearTimeout(copyFailedTimerRef.current);
      copyFailedTimerRef.current = window.setTimeout(() => setCopyFailed(false), 4000);
    }
  };

  if (!visible) return null;
  const claimedShopUrl = safeExternalHttpsUrl(claimedCoupon?.shop_url);

  return (
    <>
      {/* Floating Lucky Egg Bubble in Bottom-Right */}
      {!modalOpen && !showLoginModal && (
        <aside
          aria-label="店铺专享优惠券"
          className="fixed bottom-20 right-4 sm:right-6 z-40 animate-in slide-in-from-bottom-5 fade-in duration-300"
        >
          <div className="relative group">
            {/* Close small cross */}
            <button
              type="button"
              onClick={handleDismiss}
              aria-label="暂时关闭提示"
              className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-[color:var(--panel)] border border-[color:var(--line)] shadow-xs flex items-center justify-center text-[color:var(--muted)] hover:text-[color:var(--ink)] transition text-xs z-10"
            >
              <X size={11} />
            </button>

            {/* Clickable Floating Pill */}
            <button
              type="button"
              onClick={handleOpenClick}
              className="tactile flex items-center gap-2.5 px-3.5 py-2.5 rounded-2xl bg-[color:var(--panel)] border border-amber-500/30 shadow-lg shadow-amber-500/10 hover:border-amber-500/60 hover:shadow-xl transition text-left"
            >
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-amber-500 to-amber-400 text-white flex items-center justify-center shrink-0 shadow-xs animate-bounce">
                <Gift size={18} weight="fill" />
              </div>
              <div className="pr-1">
                <div className="flex items-center gap-1 text-[11px] font-bold text-amber-700">
                  <Sparkle size={12} weight="fill" />
                  <span>店铺立减券掉落中</span>
                </div>
                <p className="text-xs font-semibold text-[color:var(--ink)] leading-snug">
                  发现店铺立减券，点击查看！
                </p>
              </div>
            </button>
          </div>
        </aside>
      )}

      {/* Interactive Modal Card */}
      {modalOpen && !showLoginModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 animate-in fade-in duration-200"
        >
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/45 backdrop-blur-xs transition-opacity"
            onClick={handleDismiss}
            aria-hidden="true"
          />

          {/* Dialog Body */}
          <div
            ref={dialogRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label="店铺专享优惠券"
            className="relative w-full max-w-md overflow-hidden rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-6 shadow-2xl z-10 space-y-4 outline-none"
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-3">
              <div className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-800">
                <Gift size={14} weight="fill" />
                <span>比价锦鲤福利 · 合作店铺立减券</span>
              </div>
              <button
                type="button"
                onClick={handleDismiss}
                aria-label="关闭弹窗"
                className="grid h-8 w-8 place-items-center rounded-lg text-[color:var(--muted)] hover:bg-[color:var(--paper)] hover:text-[color:var(--ink)] transition"
              >
                <X size={18} />
              </button>
            </div>

            <div>
              <h3 className="text-xl font-extrabold text-[color:var(--ink)] tracking-tight">
                🎉 触发店铺立减券！
              </h3>
              <p className="text-xs text-[color:var(--muted)] mt-1 leading-relaxed">
                感谢您对 AI Price Memory 的支持。领取后即可获得一张合作店铺的立减优惠券，具体店铺与面额以领取结果为准。
              </p>
              <p className="text-[10px] text-[color:var(--muted)] mt-1.5">
                优惠券由对应店铺提供，不影响 PriceMemo 的报价排序。
              </p>
            </div>

            {/* Coupon Preview / Claim Result */}
            {claimedCoupon ? (
              <div className="p-4 rounded-xl border border-amber-500/30 bg-gradient-to-br from-amber-500/[0.05] to-amber-500/[0.15] space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-baseline gap-1 text-amber-700">
                      <span className="text-sm font-bold">¥</span>
                      <span className="text-3xl font-black">{claimedCoupon.discount_amount}</span>
                      <span className="text-xs font-semibold ml-2 px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-900">
                        满 {claimedCoupon.min_spend} 元可用
                      </span>
                    </div>
                    <p className="text-xs font-bold text-[color:var(--ink)] mt-1">{claimedCoupon.name}</p>
                    {claimedCoupon.shop_name && (
                      <p className="text-[11px] text-[color:var(--muted)] mt-0.5">
                        适用店铺：{claimedCoupon.shop_name}
                      </p>
                    )}
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-800 font-semibold">
                    已保存
                  </span>
                </div>

                <div className="pt-2 border-t border-amber-500/20 flex items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-[color:var(--muted)]">券码:</span>
                    <code className="px-2 py-1 rounded bg-[color:var(--panel)] border border-[color:var(--line)] font-mono font-bold text-sm tracking-wider text-[color:var(--ink)]">
                      {claimedCoupon.code}
                    </code>
                    <button
                      type="button"
                      onClick={() => handleCopy(claimedCoupon.code)}
                      className="button-secondary tactile p-1.5 rounded-lg text-xs hover:text-amber-700 inline-flex items-center gap-1"
                    >
                      {copied ? (
                        <Check size={14} className="text-emerald-700" weight="bold" />
                      ) : copyFailed ? (
                        <WarningCircle size={14} className="text-rose-700" weight="fill" />
                      ) : (
                        <Copy size={14} />
                      )}
                      <span className="text-[11px]">
                        {copied ? "已复制" : copyFailed ? "请手动复制" : "复制"}
                      </span>
                    </button>
                  </div>
                </div>

                <div className="text-[10px] text-[color:var(--muted)] flex items-center justify-between">
                  <span>有效期至：{new Date(claimedCoupon.expires_at).toLocaleDateString()}</span>
                  <Link href="/account" className="text-amber-700 hover:underline">
                    查看我的优惠券 →
                  </Link>
                </div>
              </div>
            ) : (
              /* Voucher banner before claim. The claim endpoint draws from the
                 pool of unassigned coupons, so no fixed shop or amount is
                 promised here — the details come back with the claim result. */
              <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-amber-500 text-white flex items-center justify-center font-bold text-lg shrink-0">
                    <Gift size={22} weight="fill" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-[color:var(--ink)]">店铺立减券（随机掉落）</h4>
                    <p className="text-[11px] text-[color:var(--muted)] mt-0.5">面额与适用店铺以领取结果为准 · 限量领取</p>
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-[10px] font-semibold text-amber-800 bg-amber-500/20 px-2 py-0.5 rounded-full">
                    每日限 1 张
                  </span>
                </div>
              </div>
            )}

            {/* Message alert if any */}
            {claimMessage && !claimedCoupon && (
              <div
                className={`p-3 rounded-xl text-xs flex items-center gap-2 ${
                  isSuccess
                    ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-800"
                    : "bg-rose-500/10 border border-rose-500/20 text-rose-800"
                }`}
              >
                {isSuccess ? (
                  <CheckCircle size={16} weight="fill" className="shrink-0" />
                ) : (
                  <WarningCircle size={16} weight="fill" className="shrink-0" />
                )}
                <span>{claimMessage}</span>
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-col gap-2.5 pt-2">
              {!claimedCoupon ? (
                <button
                  type="button"
                  onClick={handleClaim}
                  disabled={claiming}
                  className="button-primary tactile w-full py-3 rounded-xl text-sm font-semibold inline-flex items-center justify-center gap-2"
                >
                  <Sparkle size={16} weight="fill" />
                  <span>{claiming ? "正在领取..." : "一键领取并存入卡包"}</span>
                </button>
              ) : (
                <div className="flex gap-2.5">
                  {claimedShopUrl ? (
                    <a
                    href={claimedShopUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="button-primary tactile flex-1 py-2.5 rounded-xl text-xs sm:text-sm font-semibold inline-flex items-center justify-center gap-1.5 text-center"
                  >
                    <span>去 {claimedCoupon.shop_name || "合作店铺"} 下单</span>
                    <ArrowSquareOut size={15} />
                    </a>
                  ) : null}
                  <button
                    type="button"
                    onClick={handleDismiss}
                    className="button-secondary tactile flex-1 px-4 py-2.5 rounded-xl text-xs font-semibold text-[color:var(--muted)]"
                  >
                    完成
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Login modal fallback if user is not logged in */}
      <LoginModal
        isOpen={showLoginModal}
        onClose={() => {
          setShowLoginModal(false);
          if (visible) setModalOpen(true);
        }}
        onSuccess={() => {
          setShowLoginModal(false);
          setModalOpen(true);
          void handleClaim();
        }}
      />
    </>
  );
}
