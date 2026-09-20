"use client";

import React, { useEffect, useState, useRef } from "react";
import Link from "next/link";
import QRCode from "qrcode";
import {
  ArrowSquareOut,
  Bell,
  Check,
  CheckCircle,
  ChatCircleDots,
  Copy,
  Envelope,
  Gift,
  SignOut,
  Sparkle,
  Ticket,
  User,
  WarningCircle,
  QrCode,
  SlidersHorizontal,
  Lightning,
} from "@phosphor-icons/react";
import type { UserProfileResponse, UserBotBinding, QQBotBindingStartResponse, ShopCoupon } from "@/lib/types";
import {
  fetchUserProfile,
  logout,
  startQQBotBinding,
  checkQQBotBinding,
  updateQQNotificationPreferences,
  unbindQQBot,
  bindCurrentLoggedInQQ,
  fetchUserCoupons,
  redeemCoupon,
} from "@/lib/auth-client";
import { LoginModal } from "@/components/login-modal";

export function AccountClient() {
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<UserProfileResponse | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);

  // Coupon wallet states
  const [coupons, setCoupons] = useState<ShopCoupon[]>([]);
  const [couponsLoading, setCouponsLoading] = useState(false);
  const [redeemCode, setRedeemCode] = useState("");
  const [redeemLoading, setRedeemLoading] = useState(false);
  const [redeemMsg, setRedeemMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [copyFailedCode, setCopyFailedCode] = useState<string | null>(null);

  // Binding states
  const [bindSession, setBindSession] = useState<QQBotBindingStartResponse | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [qrError, setQrError] = useState(false);
  const [bindStarting, setBindStarting] = useState(false);
  const [bindError, setBindError] = useState<string | null>(null);
  const [bindSuccess, setBindSuccess] = useState<string | null>(null);
  const [prefSaving, setPrefSaving] = useState(false);

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await fetchUserProfile();
      setProfile(data);
      if (data?.user) {
        fetchUserCoupons()
          .then((res) => setCoupons(res.items || []))
          .catch(() => setCoupons([]));
      }
    } catch {
      setProfile(null);
      setCoupons([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Generate QR Code data URL when session starts
  useEffect(() => {
    setQrError(false);
    if (!bindSession?.qrcode_url) {
      setQrDataUrl(null);
      return;
    }
    let cancelled = false;
    QRCode.toDataURL(bindSession.qrcode_url, {
      width: 240,
      margin: 1,
      color: {
        dark: "#171914",
        light: "#ffffff",
      },
    })
      .then((url) => {
        if (!cancelled) setQrDataUrl(url);
      })
      .catch((err) => {
        console.error("Failed to render QR Code:", err);
        if (!cancelled) setQrError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [bindSession?.qrcode_url]);

  // Poll binding session. Polling is sequential (no overlapping requests) and
  // ignores responses once the session has been replaced or cleared, so an old
  // EXPIRED/BOUND reply can never wipe a freshly created session.
  useEffect(() => {
    if (!bindSession) return;

    let cancelled = false;
    const sessionId = bindSession.session_id;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      try {
        const res = await checkQQBotBinding(sessionId);
        if (cancelled) return;
        if (res.status === "BOUND") {
          setBindSession(null);
          setBindSuccess("🎉 恭喜！手机 QQ 扫码绑定成功！已为您开启价格变动通知。");
          loadData();
          return;
        }
        if (res.status === "EXPIRED") {
          setBindError("二维码已过期，请重新点击刷新");
          setBindSession(null);
          return;
        }
      } catch {
        // transient error, continue polling
      }
      if (!cancelled) {
        timer = setTimeout(poll, 2000);
      }
    };

    timer = setTimeout(poll, 2000);
    pollTimerRef.current = timer;
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      if (pollTimerRef.current === timer) pollTimerRef.current = null;
    };
  }, [bindSession]);

  const handleLogout = async () => {
    try {
      await logout();
      window.location.href = "/";
    } catch {
      window.location.reload();
    }
  };

  const handleStartBind = async () => {
    setBindStarting(true);
    setBindError(null);
    setBindSuccess(null);
    try {
      const session = await startQQBotBinding();
      setBindSession(session);
    } catch (err: any) {
      setBindError(err.message || "生成二维码失败");
    } finally {
      setBindStarting(false);
    }
  };

  const handleBindCurrentQQ = async () => {
    setBindStarting(true);
    setBindError(null);
    setBindSuccess(null);
    try {
      const res = await bindCurrentLoggedInQQ();
      if (res.success) {
        // Switching binding method must stop the hidden QR session, otherwise
        // it keeps polling and can report EXPIRED after this binding succeeded.
        setBindSession(null);
        setBindSuccess("🎉 已成功一键绑定您当前登录的 QQ！");
        loadData();
      }
    } catch (err: any) {
      setBindError(err.message || "绑定失败");
    } finally {
      setBindStarting(false);
    }
  };

  const handleTogglePref = async (field: "notify_price_drop" | "notify_price_hike" | "is_active", currentVal: boolean) => {
    if (!profile?.qq_bot_binding || prefSaving) return;
    setPrefSaving(true);
    try {
      const updated = await updateQQNotificationPreferences({
        [field]: !currentVal,
      });
      setProfile((prev) => (prev ? { ...prev, qq_bot_binding: updated } : null));
    } catch (err: any) {
      alert(err.message || "更新设置失败");
    } finally {
      setPrefSaving(false);
    }
  };

  const handleUnbind = async () => {
    if (!confirm("确定要解绑 QQ 机器人吗？解绑后将无法收到价格变动推送。")) return;
    try {
      await unbindQQBot();
      setBindSuccess("已成功解绑 QQ 机器人");
      loadData();
    } catch (err: any) {
      alert(err.message || "解绑失败");
    }
  };

  const handleRedeem = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = redeemCode.trim();
    if (!trimmed) return;
    setRedeemLoading(true);
    setRedeemMsg(null);
    let redeemed = false;
    try {
      const res = await redeemCoupon(trimmed);
      if (res.success) {
        redeemed = true;
        setRedeemMsg({ type: "success", text: res.message });
        setRedeemCode("");
        // Card-pack refresh is a separate concern: a failure here must not
        // turn a successful redemption into an error (the coupon and quota
        // are already allocated server-side).
        try {
          const updated = await fetchUserCoupons();
          setCoupons(updated.items || []);
        } catch {
          setRedeemMsg({
            type: "success",
            text: `${res.message}（卡包刷新失败，请手动刷新页面查看）`,
          });
        }
      } else {
        setRedeemMsg({ type: "error", text: res.message });
      }
    } catch (err: any) {
      if (!redeemed) {
        setRedeemMsg({ type: "error", text: err.message || "兑换失败，请稍后重试" });
      }
    } finally {
      setRedeemLoading(false);
    }
  };

  const handleCopy = async (code: string) => {
    try {
      // Clipboard write can reject (permissions, insecure context); only
      // report success once it actually resolved.
      await navigator.clipboard.writeText(code);
      setCopiedCode(code);
      setCopyFailedCode(null);
      setTimeout(() => setCopiedCode(null), 2500);
    } catch {
      setCopyFailedCode(code);
      setTimeout(() => setCopyFailedCode(null), 4000);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-[color:var(--muted)]">
        <div className="w-8 h-8 border-2 border-[color:var(--ink)] border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-sm font-medium">正在读取账户信息...</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="empty-state max-w-xl mx-auto py-12 px-6 text-center">
        <div className="w-16 h-16 rounded-2xl bg-[color:var(--subtle)] border border-[color:var(--line)] flex items-center justify-center mx-auto mb-5 text-[color:var(--ink)]">
          <User size={30} />
        </div>
        <h2 className="text-2xl font-bold text-[color:var(--ink)] mb-2">您尚未登录</h2>
        <p className="text-[color:var(--muted)] text-sm mb-7 leading-relaxed max-w-md mx-auto">
          登录后可管理账号信息、开启商品降价提醒，并绑定 QQ 机器人享受私聊自动推送。
        </p>
        <button
          type="button"
          onClick={() => setShowLoginModal(true)}
          className="button-primary tactile px-6 py-3 rounded-xl text-sm font-semibold inline-flex items-center gap-2"
        >
          <User size={18} />
          <span>立即登录 / 注册</span>
        </button>

        <LoginModal
          isOpen={showLoginModal}
          onClose={() => setShowLoginModal(false)}
          onSuccess={() => loadData()}
        />
      </div>
    );
  }

  const { user, qq_bot_binding } = profile;

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {bindSuccess && (
        <div className="p-4 rounded-xl border border-[color:var(--success)]/30 bg-[color:var(--success-soft)] text-[color:var(--success)] text-sm flex items-center gap-3">
          <CheckCircle size={20} className="shrink-0" weight="fill" />
          <span>{bindSuccess}</span>
        </div>
      )}

      {bindError && (
        <div className="p-4 rounded-xl border border-[color:var(--danger)]/30 bg-[color:var(--danger-soft)] text-[color:var(--danger)] text-sm flex items-center gap-3">
          <WarningCircle size={20} className="shrink-0" weight="fill" />
          <span>{bindError}</span>
        </div>
      )}

      {/* 1. Profile Card */}
      <section className="surface-panel p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6 pb-6 border-b hairline">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-[color:var(--ink)] text-[color:var(--panel)] flex items-center justify-center text-2xl font-bold uppercase shadow-sm">
              {/* Avatar URLs come from OAuth providers; only render http(s) so a
                  tampered value cannot become a javascript:/data: URI. */}
              {/^https?:\/\//i.test(user.avatar_url) ? (
                <img src={user.avatar_url} alt="" className="w-full h-full rounded-full object-cover" />
              ) : (
                user.nickname.slice(0, 1) || "U"
              )}
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h2 className="text-xl font-bold text-[color:var(--ink)]">{user.nickname || "未命名用户"}</h2>
                {user.has_qq_bound && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-500/10 border border-sky-500/20 text-sky-800">
                    QQ 已互联
                  </span>
                )}
              </div>
              <p className="text-xs text-[color:var(--muted)] mt-1 font-mono">用户 ID: #{user.id}</p>
            </div>
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="button-secondary tactile inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold text-[color:var(--muted)] hover:text-[color:var(--ink)] self-start sm:self-center"
          >
            <SignOut size={16} />
            <span>退出登录</span>
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-6 text-sm">
          <div className="flex items-center gap-3 text-[color:var(--ink)]">
            <Envelope size={18} className="text-[color:var(--muted)] shrink-0" />
            <span>邮箱：{user.email || "未绑定邮箱"}</span>
          </div>
          <div className="flex items-center gap-3 text-[color:var(--ink)]">
            <ChatCircleDots size={18} className="text-[color:var(--muted)] shrink-0" />
            <span>QQ 状态：{user.has_qq_bound ? "已绑定快捷登录" : "未绑定"}</span>
          </div>
        </div>
      </section>

      {/* 2. Coupon Wallet Section */}
      <section className="surface-panel p-6 sm:p-8 shadow-sm space-y-6">
        <div className="flex items-start gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-amber-500/25 bg-amber-500/10 text-amber-800">
            <Gift size={18} weight="fill" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-[color:var(--ink)]">我的优惠券</h3>
            <p className="text-xs sm:text-sm text-[color:var(--muted)] mt-1 leading-6">
              已领取的优惠券会按适用店铺独立保存；活动口令和彩蛋领取的优惠券也会自动进入这里。使用前请以对应店铺的结算规则为准。
            </p>
          </div>
        </div>

        {/* Redeem Input Box */}
        <div className="p-4 rounded-xl border border-[color:var(--line)] bg-[color:var(--paper)]">
          <form onSubmit={handleRedeem} className="flex flex-col sm:flex-row items-center gap-3">
            <div className="relative flex-1 w-full">
              <input
                type="text"
                placeholder="输入活动口令或优惠券码（例如 RADAR888）"
                value={redeemCode}
                onChange={(e) => setRedeemCode(e.target.value)}
                className="field text-xs sm:text-sm py-2 px-3.5 rounded-xl w-full"
              />
            </div>
            <button
              type="submit"
              disabled={redeemLoading || !redeemCode.trim()}
              className="button-primary tactile px-5 py-2 rounded-xl text-xs sm:text-sm font-semibold whitespace-nowrap w-full sm:w-auto disabled:opacity-50 inline-flex items-center justify-center gap-1.5"
            >
              <Sparkle size={14} weight="fill" />
              <span>{redeemLoading ? "兑换中..." : "立即兑换"}</span>
            </button>
          </form>
          <p className="mt-2.5 text-[11px] leading-5 text-[color:var(--muted)]">
            优惠券由对应店铺提供，不影响 PriceMemo 的报价排序；具体抵扣、退款和使用限制以店铺结算页为准。
          </p>

          {redeemMsg && (
            <div
              className={`mt-3 p-3 rounded-lg text-xs flex items-center gap-2 ${
                redeemMsg.type === "success"
                  ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-800"
                  : "bg-rose-500/10 border border-rose-500/20 text-rose-800"
              }`}
            >
              {redeemMsg.type === "success" ? (
                <CheckCircle size={16} weight="fill" className="shrink-0" />
              ) : (
                <WarningCircle size={16} weight="fill" className="shrink-0" />
              )}
              <span>{redeemMsg.text}</span>
            </div>
          )}
        </div>

        {/* Coupons List */}
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3 text-xs font-semibold tracking-wider text-[color:var(--muted)] uppercase">
            <span>已领取的优惠券 ({coupons.length})</span>
            <span className="text-[11px] text-[color:var(--muted)] normal-case tracking-normal font-medium">使用规则以对应店铺为准</span>
          </div>

          {coupons.length === 0 ? (
            <div className="p-8 rounded-xl border border-dashed border-[color:var(--line)] text-center text-[color:var(--muted)] space-y-2">
              <Ticket size={32} className="mx-auto text-[color:var(--muted)] opacity-60" />
              <p className="text-xs font-medium">暂时还没有优惠券</p>
              <p className="text-[11px] max-w-sm mx-auto opacity-75">
                浏览商品时可能遇到优惠券彩蛋，也可以在上方输入活动口令进行兑换。
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {coupons.map((coupon) => {
                const isExpired =
                  Boolean(coupon.expires_at) &&
                  new Date(coupon.expires_at as string).getTime() < Date.now();
                const isUsable = !coupon.is_used && !isExpired;
                const hasShopUrl = Boolean(coupon.shop_url?.trim());
                const shopLabel = coupon.shop_name?.trim() || "未指定店铺";
                const statusLabel = coupon.is_used ? "已核销" : isExpired ? "已过期" : "可使用";
                const statusClass = coupon.is_used
                  ? "bg-zinc-500/15 border-zinc-500/30 text-zinc-600"
                  : isExpired
                    ? "bg-rose-500/15 border-rose-500/30 text-rose-700"
                    : "bg-emerald-500/15 border-emerald-500/30 text-emerald-800";
                return (
                <div
                  key={coupon.id}
                  className={`relative overflow-hidden rounded-xl border p-4 flex flex-col justify-between gap-3 shadow-xs ${
                    isUsable
                      ? "border-amber-500/30 bg-gradient-to-br from-amber-500/[0.04] to-amber-500/[0.12]"
                      : "border-[color:var(--line)] bg-[color:var(--subtle)]/30 opacity-70"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3 border-b border-amber-500/15 pb-2.5">
                    <div className="min-w-0">
                      <p className="text-[10px] font-semibold tracking-[.06em] text-[color:var(--muted)] uppercase">适用店铺</p>
                      <p className="mt-0.5 truncate text-xs font-bold text-[color:var(--ink)]" title={shopLabel}>{shopLabel}</p>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border shrink-0 ${statusClass}`}>
                      {statusLabel}
                    </span>
                  </div>

                  <div>
                    <div className="flex items-baseline gap-1 text-amber-700">
                      <span className="text-xs font-bold">¥</span>
                      <span className="text-2xl font-black tracking-tight">{coupon.discount_amount}</span>
                      <span className="text-xs font-semibold ml-1.5 px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-900 border border-amber-500/30">
                        满 {coupon.min_spend} 元可用
                      </span>
                    </div>
                    <h4 className="text-xs sm:text-sm font-bold text-[color:var(--ink)] mt-1.5">
                      {coupon.name}
                    </h4>
                  </div>

                  <div className="pt-2.5 border-t border-amber-500/15 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-[color:var(--muted)]">券码:</span>
                      <code className="px-2 py-0.5 rounded bg-[color:var(--panel)] border border-[color:var(--line)] font-mono font-bold text-[color:var(--ink)] text-xs tracking-wider">
                        {coupon.code}
                      </code>
                      <button
                        type="button"
                        onClick={() => handleCopy(coupon.code)}
                        className="button-secondary tactile p-1.5 rounded-lg text-xs hover:text-amber-700 inline-flex items-center gap-1"
                        title="复制券码"
                      >
                        {copiedCode === coupon.code ? (
                          <Check size={14} className="text-emerald-700" weight="bold" />
                        ) : (
                          <Copy size={14} />
                        )}
                        <span className="text-[11px]">
                          {copiedCode === coupon.code
                            ? "已复制"
                            : copyFailedCode === coupon.code
                              ? "复制失败"
                              : "复制"}
                        </span>
                      </button>
                    </div>

                    {isUsable && hasShopUrl ? (
                      <a
                        href={coupon.shop_url}
                        target="_blank"
                        rel="noreferrer"
                        className="button-primary tactile px-3 py-1 rounded-lg text-xs font-semibold inline-flex items-center justify-center gap-1 self-start sm:self-auto"
                      >
                        <span>去店铺使用</span>
                        <ArrowSquareOut size={12} />
                      </a>
                    ) : isUsable ? (
                      <span
                        className="px-3 py-1 rounded-lg text-xs font-semibold inline-flex items-center justify-center gap-1 self-start sm:self-auto border border-[color:var(--line)] text-[color:var(--muted)] cursor-not-allowed"
                        title="该优惠券暂未配置店铺跳转链接"
                      >
                        <span>店铺链接未配置</span>
                      </span>
                    ) : (
                      <span
                        className="px-3 py-1 rounded-lg text-xs font-semibold inline-flex items-center justify-center gap-1 self-start sm:self-auto border border-[color:var(--line)] text-[color:var(--muted)] cursor-not-allowed"
                        title={coupon.is_used ? "该券已核销，无法再次使用" : "该券已过期"}
                      >
                        <span>{coupon.is_used ? "已核销" : "已过期"}</span>
                      </span>
                    )}
                  </div>

                  <div className="text-[10px] text-[color:var(--muted)] flex flex-wrap items-center justify-between gap-2">
                    <span>仅限 {shopLabel} 使用</span>
                    <span>有效期至：{new Date(coupon.expires_at).toLocaleDateString()}</span>
                  </div>
                </div>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* 3. QQ Bot Notification Card (Hidden when bot_enabled is false) */}
      {(profile.bot_enabled ?? true) && (
        <section className="surface-panel p-6 sm:p-8 shadow-sm space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-sky-500/20 bg-sky-500/10 text-sky-800 text-xs font-semibold mb-2">
                <ChatCircleDots size={14} />
                <span>QQ 机器人实时推送</span>
              </div>
              <h3 className="text-lg font-bold text-[color:var(--ink)]">价格波动自动通知</h3>
              <p className="text-xs sm:text-sm text-[color:var(--muted)] mt-1">
                每次网站执行价格同步时，若发现监控的商品有降价或涨价变动，机器人将自动向您发送私聊通知。
              </p>
            </div>

            {qq_bot_binding && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-emerald-600/20 bg-emerald-500/10 text-emerald-800 text-xs font-semibold self-start sm:self-center">
                <span className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse" />
                <span>已连接推送</span>
              </span>
            )}
          </div>

          {qq_bot_binding ? (
            /* Bound View */
            <div className="space-y-6 pt-2">
              <div className="p-4 rounded-xl border border-[color:var(--line)] bg-[color:var(--paper)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <p className="text-xs text-[color:var(--muted)] font-medium">绑定的 QQ 接收标识</p>
                  <p className="text-sm font-mono font-bold text-[color:var(--ink)] mt-0.5">{qq_bot_binding.target_id}</p>
                </div>
                <button
                  type="button"
                  onClick={handleUnbind}
                  className="text-xs text-[color:var(--danger)] hover:underline font-semibold transition self-start sm:self-center"
                >
                  解绑当前 QQ
                </button>
              </div>

              <div className="space-y-3">
                <h4 className="text-xs font-semibold tracking-wider text-[color:var(--muted)] uppercase">通知偏好配置</h4>

                {/* Toggle Drop */}
                <label className="flex items-center justify-between p-3.5 rounded-xl border border-[color:var(--line)] bg-[color:var(--panel)] hover:bg-[color:var(--paper)] cursor-pointer transition">
                  <div className="space-y-0.5">
                    <span className="text-sm font-semibold text-[color:var(--ink)] flex items-center gap-2">
                      📉 降价通知
                    </span>
                    <p className="text-xs text-[color:var(--muted)]">当监控商品价格下调时，私聊推送降幅、优惠信息与直达链接</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={qq_bot_binding.notify_price_drop}
                    disabled={prefSaving}
                    onChange={() => handleTogglePref("notify_price_drop", qq_bot_binding.notify_price_drop)}
                    className="w-4 h-4 rounded border-[color:var(--line-strong)] accent-[color:var(--ink)]"
                  />
                </label>

                {/* Toggle Hike */}
                <label className="flex items-center justify-between p-3.5 rounded-xl border border-[color:var(--line)] bg-[color:var(--panel)] hover:bg-[color:var(--paper)] cursor-pointer transition">
                  <div className="space-y-0.5">
                    <span className="text-sm font-semibold text-[color:var(--ink)] flex items-center gap-2">
                      📈 涨价通知
                    </span>
                    <p className="text-xs text-[color:var(--muted)]">当监控商品价格上调时，私聊推送涨幅提醒</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={qq_bot_binding.notify_price_hike}
                    disabled={prefSaving}
                    onChange={() => handleTogglePref("notify_price_hike", qq_bot_binding.notify_price_hike)}
                    className="w-4 h-4 rounded border-[color:var(--line-strong)] accent-[color:var(--ink)]"
                  />
                </label>

                {/* Toggle Global Active */}
                <label className="flex items-center justify-between p-3.5 rounded-xl border border-[color:var(--line)] bg-[color:var(--panel)] hover:bg-[color:var(--paper)] cursor-pointer transition">
                  <div className="space-y-0.5">
                    <span className="text-sm font-semibold text-[color:var(--ink)] flex items-center gap-2">
                      🔔 推送总开关
                    </span>
                    <p className="text-xs text-[color:var(--muted)]">一键暂停或恢复 QQ 机器人的全部私聊变动推送</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={qq_bot_binding.is_active}
                    disabled={prefSaving}
                    onChange={() => handleTogglePref("is_active", qq_bot_binding.is_active)}
                    className="w-4 h-4 rounded border-[color:var(--line-strong)] accent-[color:var(--ink)]"
                  />
                </label>
              </div>
            </div>
          ) : (
            /* Unbound View */
            <div className="space-y-6 pt-2">
              {/* 1. Quick One-Click Bind if user already authenticated via QQ */}
              {user.has_qq_bound && (
                <div className="p-4 rounded-xl border border-sky-500/30 bg-sky-500/10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-sky-500/20 text-sky-900">
                        <Lightning size={12} weight="fill" />
                        快捷绑定
                      </span>
                      <h4 className="text-sm font-bold text-[color:var(--ink)]">一键绑定当前登录的 QQ 账号</h4>
                    </div>
                    <p className="text-xs text-[color:var(--muted)]">
                      系统检测到您已使用 QQ 登录，无需额外扫码，点击即可直接开通降价与涨价机器人提醒。
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleBindCurrentQQ}
                    disabled={bindStarting}
                    className="button-primary tactile inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold shrink-0 disabled:opacity-50"
                  >
                    <Lightning size={15} weight="fill" />
                    <span>{bindStarting ? "开通中..." : "一键绑定当前 QQ"}</span>
                  </button>
                </div>
              )}

              {!bindSession ? (
                <div className="p-8 rounded-2xl border border-[color:var(--line)] bg-[color:var(--paper)] text-center space-y-4">
                  <div className="w-12 h-12 rounded-xl border border-sky-500/20 bg-sky-500/10 text-sky-800 flex items-center justify-center mx-auto">
                    <QrCode size={24} />
                  </div>
                  <div>
                    <h4 className="text-base font-bold text-[color:var(--ink)]">手机 QQ 扫码绑定机器人</h4>
                    <p className="text-xs text-[color:var(--muted)] mt-1 max-w-md mx-auto leading-relaxed">
                      使用手机 QQ 扫一扫下方二维码即可一键绑定授权。无需繁琐指令，扫码即刻享受私聊降价通知。
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleStartBind}
                    disabled={bindStarting}
                    className="button-primary tactile inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold"
                  >
                    <QrCode size={18} />
                    <span>{bindStarting ? "正在生成二维码..." : "获取手机 QQ 绑定二维码"}</span>
                  </button>
                </div>
              ) : (
                /* Active Binding Session Display with QR Code */
                <div className="p-6 sm:p-8 rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--paper)] space-y-5 animate-in fade-in duration-200">
                  <div className="text-center space-y-1.5">
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-sky-500/20 bg-sky-500/10 text-sky-800 text-xs font-semibold">
                      <QrCode size={14} />
                      <span>手机 QQ 扫码授权</span>
                    </div>
                    <h4 className="text-base sm:text-lg font-bold text-[color:var(--ink)]">请使用手机 QQ 扫描下方二维码</h4>
                    <p className="text-xs text-[color:var(--muted)] max-w-sm mx-auto">
                      手机 QQ 扫码确认后，系统将自动建立绑定并开启实时私聊推送。
                    </p>
                  </div>

                  {/* Clean QR Code Frame */}
                  <div className="flex flex-col items-center justify-center p-5 rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] max-w-xs mx-auto shadow-sm">
                    <div className="p-3 bg-white rounded-xl border border-[color:var(--line)]">
                      {qrDataUrl ? (
                        <img src={qrDataUrl} alt="QQ 扫码绑定二维码" className="w-48 h-48 object-contain" />
                      ) : qrError ? (
                        <div className="w-48 h-48 flex flex-col items-center justify-center text-[color:var(--muted)] text-xs gap-2 px-3 text-center">
                          <span>二维码生成失败</span>
                          <span className="text-[10px]">请点击下方按钮重新生成，或使用绑定码手动绑定</span>
                        </div>
                      ) : bindSession.qrcode_url ? (
                        <div className="w-48 h-48 flex flex-col items-center justify-center text-[color:var(--muted)] text-xs gap-2">
                          <div className="w-6 h-6 border-2 border-[color:var(--ink)] border-t-transparent rounded-full animate-spin" />
                          <span>正在渲染二维码...</span>
                        </div>
                      ) : (
                        <div className="w-48 h-48 flex flex-col items-center justify-center text-[color:var(--muted)] text-xs gap-2 px-3 text-center">
                          <span>当前未提供扫码入口</span>
                          <span className="text-[10px]">请使用下方绑定码在机器人私聊中完成绑定</span>
                        </div>
                      )}
                    </div>

                    <div className="mt-4 flex items-center gap-2 text-xs font-medium text-[color:var(--muted)]">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                      <span>等待手机扫码中，授权后自动绑定...</span>
                    </div>

                    {bindSession.qrcode_url && (
                      <div className="mt-4 pt-3 border-t hairline w-full">
                        <a
                          href={bindSession.qrcode_url}
                          target="_blank"
                          rel="noreferrer"
                          className="button-secondary tactile w-full text-center py-2 px-3 rounded-lg text-xs font-semibold block"
                        >
                          在当前设备直接打开 QQ 授权 →
                        </a>
                      </div>
                    )}
                  </div>

                  {/* Secondary alternative methods */}
                  <details className="text-xs text-[color:var(--muted)] max-w-md mx-auto pt-2">
                    <summary className="cursor-pointer hover:text-[color:var(--ink)] select-none text-center transition py-1">
                      遇到问题？可点击展开备选绑定方式 ▼
                    </summary>
                    <div className="mt-3 p-4 rounded-xl border border-[color:var(--line)] bg-[color:var(--panel)] space-y-4 text-left">
                      <div>
                        <p className="font-bold text-[color:var(--ink)]">备选方式一：向机器人发送私聊指令</p>
                        <p className="text-[color:var(--muted)] mt-1">
                          在 QQ 中找到 PriceMemo 机器人，直接发送：
                          <code className="inline-block mt-1 px-2 py-0.5 rounded border border-[color:var(--line)] bg-[color:var(--paper)] font-mono text-emerald-700 font-bold">
                            /bind {bindSession.bind_code}
                          </code>
                        </p>
                      </div>
                    </div>
                  </details>

                  <div className="text-center pt-2">
                    <button
                      type="button"
                      onClick={() => setBindSession(null)}
                      className="text-xs text-[color:var(--muted)] hover:text-[color:var(--ink)] hover:underline transition"
                    >
                      取消本次绑定
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* 3. Watchlist quick link */}
      <section className="surface-panel p-6 sm:p-8 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl border border-emerald-600/20 bg-emerald-500/10 text-emerald-800 flex items-center justify-center shrink-0">
            <Bell size={20} />
          </div>
          <div>
            <h4 className="text-sm font-bold text-[color:var(--ink)]">管理您的关注清单</h4>
            <p className="text-xs text-[color:var(--muted)] mt-0.5">查看当前在浏览器中关注的重点比价商品</p>
          </div>
        </div>
        <Link
          href="/watchlist"
          className="button-secondary tactile px-4 py-2 rounded-xl text-xs font-semibold shrink-0"
        >
          前往关注清单 →
        </Link>
      </section>
    </div>
  );
}
