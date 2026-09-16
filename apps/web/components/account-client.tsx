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
      margin: 2,
      color: {
        dark: "#000000",
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

  const handleSimulateScan = async () => {
    if (!bindSession) return;
    try {
      // Trigger dev mock scan URL
      await fetch(`/api/v1/auth/qq/scan-mock?session_id=${encodeURIComponent(bindSession.session_id)}`);
      // Next poll tick will detect BOUND
    } catch (err: any) {
      setBindError(err.message || "模拟扫码失败");
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
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400">
        <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-sm">正在加载个人中心...</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="max-w-xl mx-auto py-12 px-4 text-center">
        <div className="w-16 h-16 rounded-2xl bg-zinc-800/80 border border-zinc-700 flex items-center justify-center mx-auto mb-6 text-zinc-400">
          <User size={32} />
        </div>
        <h2 className="text-2xl font-bold text-zinc-100 mb-2">您尚未登录</h2>
        <p className="text-zinc-400 text-sm mb-8 leading-relaxed">
          登录后可管理账号信息、开启商品降价提醒，并绑定 QQ 机器人享受私聊自动推送。
        </p>
        <button
          type="button"
          onClick={() => setShowLoginModal(true)}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-medium text-sm transition shadow-lg shadow-emerald-600/20"
        >
          <User size={18} />
          立即登录 / 注册
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
        <div className="p-4 rounded-xl bg-emerald-900/30 border border-emerald-800/50 text-emerald-300 text-sm flex items-center gap-3">
          <CheckCircle size={20} className="shrink-0 text-emerald-400" />
          <span>{bindSuccess}</span>
        </div>
      )}

      {bindError && (
        <div className="p-4 rounded-xl bg-red-900/30 border border-red-800/50 text-red-300 text-sm flex items-center gap-3">
          <WarningCircle size={20} className="shrink-0 text-red-400" />
          <span>{bindError}</span>
        </div>
      )}

      {/* 1. Profile Card */}
      <section className="rounded-2xl border border-[color:var(--line)] bg-[color:var(--panel)] p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6 pb-6 border-b border-[color:var(--line)]">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center text-white text-2xl font-bold uppercase shadow-inner">
              {user.avatar_url ? (
                <img src={user.avatar_url} alt="" className="w-full h-full rounded-full object-cover" />
              ) : (
                user.nickname.slice(0, 1) || "U"
              )}
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h2 className="text-xl font-bold text-zinc-100">{user.nickname || "未命名用户"}</h2>
                {user.has_qq_bound && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-blue-500/10 border border-blue-500/20 text-blue-400">
                    QQ 已互联
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-400 mt-1">用户 ID: #{user.id}</p>
            </div>
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-zinc-700 hover:bg-zinc-800 text-zinc-300 hover:text-zinc-100 text-xs font-medium transition self-start sm:self-center"
          >
            <SignOut size={16} />
            退出登录
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-6 text-sm">
          <div className="flex items-center gap-3 text-zinc-300">
            <Envelope size={18} className="text-zinc-500" />
            <span>邮箱：{user.email || "未绑定邮箱"}</span>
          </div>
          <div className="flex items-center gap-3 text-zinc-300">
            <ChatCircleDots size={18} className="text-zinc-500" />
            <span>QQ 关联状态：{user.has_qq_bound ? "已绑定快捷登录" : "未绑定"}</span>
          </div>
        </div>
      </section>

      {/* 2. QQ Bot Notification Card (Hidden when bot_enabled is false) */}
      {(profile.bot_enabled ?? true) && (
        <section className="rounded-2xl border border-[color:var(--line)] bg-[color:var(--panel)] p-6 sm:p-8 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium mb-2">
              <ChatCircleDots size={14} />
              QQ 机器人实时推送
            </div>
            <h3 className="text-lg font-bold text-zinc-100">价格波动自动通知</h3>
            <p className="text-xs sm:text-sm text-zinc-400 mt-1">
              每次网站执行价格同步时，若发现监控的商品有降价或涨价变动，机器人将自动向您发送私聊通知。
            </p>
          </div>

          {qq_bot_binding && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium self-start sm:self-center">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              已连接
            </span>
          )}
        </div>

        {qq_bot_binding ? (
          /* Bound View */
          <div className="space-y-6 pt-2">
            <div className="p-4 rounded-xl bg-zinc-800/50 border border-zinc-700/60 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="text-xs text-zinc-400 font-medium">绑定的 QQ 标识</p>
                <p className="text-sm font-mono text-zinc-200 mt-0.5">{qq_bot_binding.target_id}</p>
              </div>
              <button
                type="button"
                onClick={handleUnbind}
                className="text-xs text-red-400 hover:text-red-300 font-medium underline underline-offset-4 transition"
              >
                解绑当前 QQ
              </button>
            </div>

            <div className="space-y-3">
              <h4 className="text-xs font-semibold tracking-wider text-zinc-400 uppercase">通知偏好配置</h4>

              {/* Toggle Drop */}
              <label className="flex items-center justify-between p-3.5 rounded-xl bg-zinc-800/30 border border-zinc-800 hover:border-zinc-700 cursor-pointer transition">
                <div className="space-y-0.5">
                  <span className="text-sm font-medium text-zinc-200 flex items-center gap-2">
                    📉 降价通知
                  </span>
                  <p className="text-xs text-zinc-400">当任何商品价格下调时，私聊推送降幅与链接</p>
                </div>
                <input
                  type="checkbox"
                  checked={qq_bot_binding.notify_price_drop}
                  disabled={prefSaving}
                  onChange={() => handleTogglePref("notify_price_drop", qq_bot_binding.notify_price_drop)}
                  className="w-4 h-4 rounded border-zinc-700 text-emerald-500 focus:ring-emerald-500 focus:ring-offset-zinc-900"
                />
              </label>

              {/* Toggle Hike */}
              <label className="flex items-center justify-between p-3.5 rounded-xl bg-zinc-800/30 border border-zinc-800 hover:border-zinc-700 cursor-pointer transition">
                <div className="space-y-0.5">
                  <span className="text-sm font-medium text-zinc-200 flex items-center gap-2">
                    📈 涨价通知
                  </span>
                  <p className="text-xs text-zinc-400">当任何商品价格上调时，私聊推送涨幅提醒</p>
                </div>
                <input
                  type="checkbox"
                  checked={qq_bot_binding.notify_price_hike}
                  disabled={prefSaving}
                  onChange={() => handleTogglePref("notify_price_hike", qq_bot_binding.notify_price_hike)}
                  className="w-4 h-4 rounded border-zinc-700 text-emerald-500 focus:ring-emerald-500 focus:ring-offset-zinc-900"
                />
              </label>

              {/* Toggle Global Active */}
              <label className="flex items-center justify-between p-3.5 rounded-xl bg-zinc-800/30 border border-zinc-800 hover:border-zinc-700 cursor-pointer transition">
                <div className="space-y-0.5">
                  <span className="text-sm font-medium text-zinc-200 flex items-center gap-2">
                    🔔 推送总开关
                  </span>
                  <p className="text-xs text-zinc-400">暂停或恢复 QQ 机器人的全部消息推送</p>
                </div>
                <input
                  type="checkbox"
                  checked={qq_bot_binding.is_active}
                  disabled={prefSaving}
                  onChange={() => handleTogglePref("is_active", qq_bot_binding.is_active)}
                  className="w-4 h-4 rounded border-zinc-700 text-emerald-500 focus:ring-emerald-500 focus:ring-offset-zinc-900"
                />
              </label>
            </div>
          </div>
        ) : (
          /* Unbound View */
          <div className="space-y-6 pt-2">
            {/* 1. Quick One-Click Bind if user already authenticated via QQ */}
            {user.has_qq_bound && (
              <div className="p-4 rounded-xl bg-gradient-to-r from-blue-950/50 to-indigo-950/30 border border-blue-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-blue-500/20 text-blue-300">
                      <Lightning size={12} weight="fill" />
                      快捷绑定
                    </span>
                    <h4 className="text-sm font-semibold text-zinc-100">一键绑定当前登录的 QQ 账号</h4>
                  </div>
                  <p className="text-xs text-zinc-400">
                    系统检测到您已使用 QQ 登录，无需额外扫码，点击即可直接开通降价与涨价机器人提醒。
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleBindCurrentQQ}
                  disabled={bindStarting}
                  className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-medium text-xs transition shadow-lg shadow-blue-600/20 shrink-0 disabled:opacity-50"
                >
                  <Lightning size={15} weight="fill" />
                  {bindStarting ? "开通中..." : "一键绑定当前 QQ"}
                </button>
              </div>
            )}

            {!bindSession ? (
              <div className="p-6 rounded-xl bg-zinc-800/30 border border-zinc-800/80 text-center space-y-4">
                <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center mx-auto">
                  <QrCode size={24} />
                </div>
                <div>
                  <h4 className="text-base font-semibold text-zinc-200">手机 QQ 扫码绑定机器人</h4>
                  <p className="text-xs text-zinc-400 mt-1 max-w-md mx-auto">
                    打开手机 QQ 扫一扫，确认授权即可秒级完成绑定。无需手动添加好友或输入指令。
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleStartBind}
                  disabled={bindStarting}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-medium text-sm transition shadow-lg shadow-blue-600/20"
                >
                  <QrCode size={18} />
                  {bindStarting ? "正在生成二维码..." : "📱 QQ 扫码绑定机器人"}
                </button>
              </div>
            ) : (
              /* Active Binding Session Display with QR Code */
              <div className="p-6 rounded-2xl bg-zinc-800/50 border border-zinc-700 space-y-6 animate-in fade-in duration-200">
                <div className="text-center space-y-2">
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium">
                    <QrCode size={15} />
                    <span>手机 QQ 扫码授权</span>
                  </div>
                  <h4 className="text-lg font-bold text-zinc-100">请使用手机 QQ 扫描下方二维码</h4>
                  <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                    手机 QQ 扫码授权后，机器人将自动为您开启降价和涨价实时私聊通知。
                  </p>
                </div>

                {/* Real QR Code Display */}
                <div className="flex flex-col items-center justify-center p-6 rounded-2xl bg-zinc-900/90 border border-zinc-800 max-w-xs mx-auto shadow-2xl">
                  <div className="p-3 bg-white rounded-xl shadow-md">
                    {qrDataUrl ? (
                      <img src={qrDataUrl} alt="QQ 扫码绑定二维码" className="w-52 h-52 object-contain" />
                    ) : (
                      <div className="w-52 h-52 flex flex-col items-center justify-center text-zinc-500 text-xs gap-2">
                        <div className="w-6 h-6 border-2 border-zinc-400 border-t-transparent rounded-full animate-spin" />
                        <span>正在生成二维码...</span>
                      </div>
                    )}
                  </div>

                  <div className="mt-4 flex items-center gap-2 text-xs text-zinc-400">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    <span>等待手机 QQ 扫码中，扫码后自动绑定...</span>
                  </div>

                  {/* Direct link & Dev simulation button */}
                  <div className="mt-4 pt-3 border-t border-zinc-800/80 w-full flex flex-col gap-2">
                    {bindSession.qrcode_url && (
                      <a
                        href={bindSession.qrcode_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-center py-1.5 px-3 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs transition"
                      >
                        在当前设备直接打开 QQ 授权 →
                      </a>
                    )}
                    <button
                      type="button"
                      onClick={handleSimulateScan}
                      className="text-center py-1.5 px-3 rounded-lg bg-emerald-950/40 hover:bg-emerald-900/60 border border-emerald-800/40 text-emerald-400 text-xs transition"
                    >
                      🧪 模拟手机扫码成功（开发调试）
                    </button>
                  </div>
                </div>

                {/* Secondary alternative methods */}
                <details className="text-xs text-zinc-500 max-w-md mx-auto pt-1">
                  <summary className="cursor-pointer hover:text-zinc-400 select-none text-center">
                    需要使用备选方式（手动输入或指令）？点击展开 ▼
                  </summary>
                  <div className="mt-3 p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-4 text-left">
                    <div>
                      <p className="font-semibold text-zinc-300">备选方式一：向机器人发送私聊指令</p>
                      <p className="text-zinc-400 mt-1">
                        在 QQ 中找到 PriceMemo 机器人，直接发送：
                        <code className="inline-block mt-1 px-2 py-0.5 rounded bg-zinc-800 font-mono text-emerald-400">
                          /bind {bindSession.bind_code}
                        </code>
                      </p>
                    </div>
                    <div className="pt-2 border-t border-zinc-800">
                      <p className="font-semibold text-zinc-300">备选方式二：手动确认 QQ 号或 OpenID</p>
                      <form onSubmit={handleManualConfirm} className="space-y-2 mt-1.5">
                        <input
                          type="text"
                          placeholder="输入您的 QQ 号或 OpenID"
                          value={manualTargetId}
                          onChange={(e) => setManualTargetId(e.target.value)}
                          className="w-full px-3 py-1.5 rounded-lg bg-zinc-800 border border-zinc-700 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500"
                        />
                        <button
                          type="submit"
                          disabled={bindStarting || !manualTargetId.trim()}
                          className="w-full py-1.5 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition disabled:opacity-50"
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
                    className="text-xs text-zinc-400 hover:text-zinc-200 transition"
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
      <section className="rounded-2xl border border-[color:var(--line)] bg-[color:var(--panel)] p-6 sm:p-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
            <Bell size={20} />
          </div>
          <div>
            <h4 className="text-sm font-bold text-zinc-200">管理您的关注清单</h4>
            <p className="text-xs text-zinc-400 mt-0.5">查看当前在浏览器中关注的重点比价商品</p>
          </div>
        </div>
        <Link
          href="/watchlist"
          className="px-4 py-2 rounded-xl border border-zinc-700 hover:bg-zinc-800 text-zinc-200 text-xs font-medium transition shrink-0"
        >
          前往关注清单 →
        </Link>
      </section>
    </div>
  );
}
