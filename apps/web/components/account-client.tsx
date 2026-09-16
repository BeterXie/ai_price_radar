"use client";

import React, { useEffect, useState, useRef } from "react";
import Link from "next/link";
import QRCode from "qrcode";
import {
  Bell,
  CheckCircle,
  ChatCircleDots,
  Envelope,
  SignOut,
  User,
  WarningCircle,
  QrCode,
  SlidersHorizontal,
  Lightning,
} from "@phosphor-icons/react";
import type { UserProfileResponse, UserBotBinding, QQBotBindingStartResponse } from "@/lib/types";
import {
  fetchUserProfile,
  logout,
  startQQBotBinding,
  checkQQBotBinding,
  manualConfirmQQBotBinding,
  updateQQNotificationPreferences,
  unbindQQBot,
  bindCurrentLoggedInQQ,
} from "@/lib/auth-client";
import { LoginModal } from "@/components/login-modal";

export function AccountClient() {
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<UserProfileResponse | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);

  // Binding states
  const [bindSession, setBindSession] = useState<QQBotBindingStartResponse | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [bindStarting, setBindStarting] = useState(false);
  const [manualTargetId, setManualTargetId] = useState("");
  const [bindError, setBindError] = useState<string | null>(null);
  const [bindSuccess, setBindSuccess] = useState<string | null>(null);
  const [prefSaving, setPrefSaving] = useState(false);

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await fetchUserProfile();
      setProfile(data);
    } catch {
      setProfile(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Generate QR Code data URL when session starts
  useEffect(() => {
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
      });
    return () => {
      cancelled = true;
    };
  }, [bindSession?.qrcode_url]);

  // Poll binding session
  useEffect(() => {
    if (!bindSession) return;

    const interval = setInterval(async () => {
      try {
        const res = await checkQQBotBinding(bindSession.session_id);
        if (res.status === "BOUND") {
          clearInterval(interval);
          setBindSession(null);
          setBindSuccess("🎉 恭喜！手机 QQ 扫码绑定成功！已为您开启价格变动通知。");
          loadData();
        } else if (res.status === "EXPIRED") {
          clearInterval(interval);
          setBindError("二维码已过期，请重新点击刷新");
          setBindSession(null);
        }
      } catch {
        // transient error, continue polling
      }
    }, 2000);

    pollTimerRef.current = interval;
    return () => clearInterval(interval);
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
        setBindSuccess("🎉 已成功一键绑定您当前登录的 QQ！");
        loadData();
      }
    } catch (err: any) {
      setBindError(err.message || "绑定失败");
    } finally {
      setBindStarting(false);
    }
  };

  const handleManualConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bindSession || !manualTargetId.trim()) return;
    setBindStarting(true);
    setBindError(null);
    try {
      const res = await manualConfirmQQBotBinding(bindSession.bind_code, manualTargetId.trim());
      if (res.success) {
        setBindSession(null);
        setBindSuccess("🎉 QQ 机器人绑定成功！");
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
              {user.avatar_url ? (
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

      {/* 2. QQ Bot Notification Card (Hidden when bot_enabled is false) */}
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
                      ) : (
                        <div className="w-48 h-48 flex flex-col items-center justify-center text-[color:var(--muted)] text-xs gap-2">
                          <div className="w-6 h-6 border-2 border-[color:var(--ink)] border-t-transparent rounded-full animate-spin" />
                          <span>正在渲染二维码...</span>
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
                      <div className="pt-3 border-t hairline">
                        <p className="font-bold text-[color:var(--ink)]">备选方式二：手动输入 QQ 号或 OpenID</p>
                        <form onSubmit={handleManualConfirm} className="space-y-2 mt-2">
                          <input
                            type="text"
                            placeholder="输入您的 QQ 号或 OpenID"
                            value={manualTargetId}
                            onChange={(e) => setManualTargetId(e.target.value)}
                            className="field text-xs py-2 px-3 rounded-lg"
                          />
                          <button
                            type="submit"
                            disabled={bindStarting || !manualTargetId.trim()}
                            className="button-primary tactile w-full py-2 px-3 rounded-lg text-xs font-semibold disabled:opacity-50"
                          >
                            {bindStarting ? "绑定中..." : "确认绑定"}
                          </button>
                        </form>
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
