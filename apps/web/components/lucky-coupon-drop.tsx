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
import { fetchAuthMe, claimLuckyDrop, fetchCouponDropStatus } from "@/lib/auth-client";
import type { ShopCoupon } from "@/lib/types";
import { LoginModal } from "@/components/login-modal";

const STORAGE_KEY_DISMISSED = "apr:coupon_drop_dismissed_v1";
const COOLDOWN_MS = 12 * 60 * 60 * 1000; // 12 hours

export function LuckyCouponDrop() {
  const pathname = usePathname();
  const [visible, setVisible] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [claiming, setClaiming] = useState(false);
  const [claimedCoupon, setClaimedCoupon] = useState<ShopCoupon | null>(null);
  const [claimMessage, setClaimMessage] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState<boolean | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function checkDrop() {
      try {
        if (typeof window === "undefined") return;
        // Do not display on admin or account pages
        if (pathname.startsWith("/admin") || pathname.startsWith("/account")) return;

        const lastDismissed = localStorage.getItem(STORAGE_KEY_DISMISSED);
        if (lastDismissed) {
          const diff = Date.now() - parseInt(lastDismissed, 10);
          if (diff < COOLDOWN_MS) return;
        }

        // Query backend drop status & dynamic probability based on stock
        const dropStatus = await fetchCouponDropStatus().catch(() => null);
        if (cancelled) return;
        if (!dropStatus || !dropStatus.enabled || !dropStatus.has_stock || dropStatus.probability <= 0) {
          return;
        }

        // Dynamic roll (0 to 100)
        const roll = Math.random() * 100;
        if (roll > dropStatus.probability) {
          return;
        }

        // Delay 10 seconds after page load before displaying the floating lucky egg
        timer = window.setTimeout(() => {
          if (!cancelled) {
            setVisible(true);
          }
        }, 10_000);
      } catch {
        return;
      }
    }

    checkDrop();

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [pathname]);


  const handleDismiss = () => {
    try {
      localStorage.setItem(STORAGE_KEY_DISMISSED, Date.now().toString());
    } catch {
      // ignore
    }
    setVisible(false);
    setModalOpen(false);
  };

  const handleOpenClick = () => {
    setModalOpen(true);
  };

  const handleClaim = async () => {
    setClaiming(true);
    setClaimMessage(null);
    try {
      const auth = await fetchAuthMe();
      if (!auth.authenticated || !auth.user) {
        setShowLoginModal(true);
        setClaiming(false);
        return;
      }

      const res = await claimLuckyDrop();
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

  const handleCopy = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  if (!visible) return null;

  return (
    <>
      {/* Floating Lucky Egg Bubble in Bottom-Right */}
      {!modalOpen && (
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
                  <span>彩头AI · 店铺立减券</span>
                </div>
                <p className="text-xs font-semibold text-[color:var(--ink)] leading-snug">
                  发现满 15 减 5 元立减券！
                </p>
              </div>
            </button>
          </div>
        </aside>
      )}

      {/* Interactive Modal Card */}
      {modalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 animate-in fade-in duration-200"
        >
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/45 backdrop-blur-xs transition-opacity"
            onClick={handleDismiss}
            aria-hidden="true"
          />

          {/* Dialog Body */}
          <div className="relative w-full max-w-md overflow-hidden rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-6 shadow-2xl z-10 space-y-4">
            {/* Header */}
            <div className="flex items-start justify-between gap-3">
              <div className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-800">
                <Gift size={14} weight="fill" />
                <span>比价锦鲤福利 · 彩头AI直营小铺</span>
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
                🎉 触发店铺专享满减券！
              </h3>
              <p className="text-xs text-[color:var(--muted)] mt-1 leading-relaxed">
                感谢您对 Price Radar 的支持，彩头AI官方店铺为您提供独家立减优惠，购买即刻享受折扣。
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
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-800 font-semibold">
                    已存入卡包
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
                      {copied ? <Check size={14} className="text-emerald-700" weight="bold" /> : <Copy size={14} />}
                      <span className="text-[11px]">{copied ? "已复制" : "复制"}</span>
                    </button>
                  </div>
                </div>

                <div className="text-[10px] text-[color:var(--muted)] flex items-center justify-between">
                  <span>有效期至：{new Date(claimedCoupon.expires_at).toLocaleDateString()}</span>
                  <Link href="/account" className="text-amber-700 hover:underline">
                    查看我的卡包 →
                  </Link>
                </div>
              </div>
            ) : (
              /* Voucher Banner before claim */
              <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-amber-500 text-white flex items-center justify-center font-bold text-lg shrink-0">
                    ¥5
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-[color:var(--ink)]">满 15 元立减 5 元券</h4>
                    <p className="text-[11px] text-[color:var(--muted)] mt-0.5">全店商品可用 · 限量领取</p>
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
                  <a
                    href={claimedCoupon.shop_url || "https://wzyp.cn/shop/pricememo"}
                    target="_blank"
                    rel="noreferrer"
                    className="button-primary tactile flex-1 py-2.5 rounded-xl text-xs sm:text-sm font-semibold inline-flex items-center justify-center gap-1.5 text-center"
                  >
                    <span>去彩头AI店铺下单</span>
                    <ArrowSquareOut size={15} />
                  </a>
                  <button
                    type="button"
                    onClick={handleDismiss}
                    className="button-secondary tactile px-4 py-2.5 rounded-xl text-xs font-semibold text-[color:var(--muted)]"
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
        onClose={() => setShowLoginModal(false)}
        onSuccess={() => {
          setShowLoginModal(false);
          handleClaim();
        }}
      />
    </>
  );
}
