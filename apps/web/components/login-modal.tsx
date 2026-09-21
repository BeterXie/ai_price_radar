"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { X, EnvelopeSimple, Sparkle, LockKey } from "@phosphor-icons/react";
import type { AuthSessionState } from "@/lib/types";
import {
  loginWithPassword,
  requestEmailLoginCode,
  setAccountPassword,
  verifyEmailLoginCode,
} from "@/lib/auth-client";
import { validatePasswordConfirmation } from "@/lib/password-policy";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (session: AuthSessionState) => void;
}

type LoginMode = "code" | "password";

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function LoginModal({ isOpen, onClose, onSuccess }: LoginModalProps) {
  const [mounted, setMounted] = useState(false);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [mode, setMode] = useState<LoginMode>("code");
  const [password, setPassword] = useState("");
  const [step, setStep] = useState<"email" | "code" | "set-password">("email");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [countdown, setCountdown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const dialogRef = useRef<HTMLDivElement | null>(null);
  const emailInputRef = useRef<HTMLInputElement | null>(null);
  const codeInputRef = useRef<HTMLInputElement | null>(null);
  const passwordInputRef = useRef<HTMLInputElement | null>(null);
  const newPasswordInputRef = useRef<HTMLInputElement | null>(null);
  // The email the pending code was requested for. Verification must use it,
  // not whatever is currently typed into the (still editable) input.
  const requestedEmailRef = useRef<string>("");
  const requestGenerationRef = useRef(0);
  // Verified session held while the first-login "set password" step is shown;
  // onSuccess fires only after the user saves a password or explicitly skips.
  const pendingSessionRef = useRef<AuthSessionState | null>(null);

  const closeModal = useCallback(() => {
    requestGenerationRef.current += 1;
    requestedEmailRef.current = "";
    pendingSessionRef.current = null;
    setLoading(false);
    onClose();
  }, [onClose]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setInterval(() => {
      setCountdown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [countdown]);

  useEffect(() => {
    if (isOpen) return;
    requestGenerationRef.current += 1;
    requestedEmailRef.current = "";
    pendingSessionRef.current = null;
    setLoading(false);
    setStep("email");
    setMode("code");
    setCode("");
    setPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setError(null);
    setInfo(null);
  }, [isOpen]);

  // Focus management: move focus into the dialog on open, keep Tab inside it,
  // close on Escape, and restore focus to the trigger on close.
  useEffect(() => {
    if (!isOpen || !mounted) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;

    const focusTarget =
      step === "code"
        ? codeInputRef.current
        : step === "set-password"
          ? newPasswordInputRef.current
          : emailInputRef.current;
    (focusTarget || dialogRef.current)?.focus?.();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeModal();
        return;
      }
      if (event.key !== "Tab") return;
      const container = dialogRef.current;
      if (!container) return;
      const focusable = Array.from(
        container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      ).filter((el) => el.offsetParent !== null || el === document.activeElement);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [closeModal, isOpen, mounted, step]);

  const handleBackToEmail = useCallback(() => {
    // Reset before showing the email step so a late response from the previous
    // request cannot drive the new flow.
    requestGenerationRef.current += 1;
    requestedEmailRef.current = "";
    setLoading(false);
    setStep("email");
    setCode("");
    setError(null);
    setInfo(null);
  }, []);

  const switchMode = useCallback((next: LoginMode) => {
    setMode(next);
    setStep("email");
    setError(null);
    setInfo(null);
  }, []);

  if (!isOpen || !mounted) return null;

  const handleSendCode = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail || !cleanEmail.includes("@")) {
      setError("请输入有效的邮箱地址");
      return;
    }
    setError(null);
    setInfo(null);
    setLoading(true);
    const requestEmail = cleanEmail;
    const generation = ++requestGenerationRef.current;
    try {
      const res = await requestEmailLoginCode(requestEmail);
      if (generation !== requestGenerationRef.current) return;
      if (res.success) {
        // Freeze the email this code belongs to and verify against it later.
        requestedEmailRef.current = requestEmail;
        setStep("code");
        setCountdown(res.retry_after || 60);
        setInfo(res.message || "验证码已发送至您的邮箱");
      } else {
        setError(res.message);
        if (res.retry_after > 0) setCountdown(res.retry_after);
      }
    } catch (err: unknown) {
      if (generation !== requestGenerationRef.current) return;
      setError(err instanceof Error ? err.message : "发送失败，请稍后重试");
    } finally {
      if (generation === requestGenerationRef.current) setLoading(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^\d{6}$/.test(code.trim())) {
      setError("请输入收到的 6 位验证码");
      return;
    }
    setError(null);
    setLoading(true);
    const verifyEmail = requestedEmailRef.current || email.trim();
    const generation = ++requestGenerationRef.current;
    try {
      const session = await verifyEmailLoginCode(verifyEmail, code.trim());
      if (generation !== requestGenerationRef.current) return;
      if (session.authenticated) {
        // First login (account just created or never had a password): offer
        // the one-time set-password step before handing the session back.
        if (session.user && session.user.has_password === false) {
          pendingSessionRef.current = session;
          setNewPassword("");
          setConfirmPassword("");
          setError(null);
          setInfo(null);
          setStep("set-password");
          setLoading(false);
          return;
        }
        onSuccess(session);
        closeModal();
      } else {
        setError("登录验证失败，请重试");
      }
    } catch (err: unknown) {
      if (generation !== requestGenerationRef.current) return;
      setError(err instanceof Error ? err.message : "验证码错误或已失效");
    } finally {
      if (generation === requestGenerationRef.current) setLoading(false);
    }
  };

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail || !cleanEmail.includes("@")) {
      setError("请输入有效的邮箱地址");
      return;
    }
    if (!password) {
      setError("请输入登录密码");
      return;
    }
    setError(null);
    setInfo(null);
    setLoading(true);
    const generation = ++requestGenerationRef.current;
    try {
      const session = await loginWithPassword(cleanEmail, password);
      if (generation !== requestGenerationRef.current) return;
      if (session.authenticated) {
        onSuccess(session);
        closeModal();
      } else {
        setError("邮箱或密码错误");
      }
    } catch (err: unknown) {
      if (generation !== requestGenerationRef.current) return;
      setError(err instanceof Error ? err.message : "登录失败，请稍后重试");
    } finally {
      if (generation === requestGenerationRef.current) setLoading(false);
    }
  };

  const handleSetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    const policyError = validatePasswordConfirmation(newPassword, confirmPassword);
    if (policyError) {
      setError(policyError);
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const result = await setAccountPassword({ password: newPassword });
      if (result.success) {
        const pending = pendingSessionRef.current;
        const session: AuthSessionState = pending
          ? {
              ...pending,
              user: pending.user ? { ...pending.user, has_password: true } : pending.user,
            }
          : { authenticated: true, user: null };
        onSuccess(session);
        closeModal();
      } else {
        setError(result.message || "密码设置失败，请稍后重试");
        setLoading(false);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "密码设置失败，请稍后重试");
      setLoading(false);
    }
  };

  const handleSkipSetPassword = () => {
    const pending = pendingSessionRef.current;
    if (pending) onSuccess(pending);
    closeModal();
  };

  const inputClass =
    "w-full px-3.5 py-2.5 rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] text-sm text-[color:var(--ink)] placeholder-[color:var(--muted)] focus:outline-none focus:border-[color:var(--focus)] focus:ring-1 focus:ring-[color:var(--focus)] transition disabled:opacity-60 disabled:bg-[color:var(--subtle)]";

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="login-dialog-title"
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-200"
    >
      {/* Editorial Dimmed Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
        onClick={closeModal}
        aria-hidden="true"
      />

      {/* Modal Dialog Card adhering to PriceMemo paper design system */}
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="relative w-full max-w-md my-auto rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-6 sm:p-8 shadow-2xl text-[color:var(--ink)] z-10 transition-all focus:outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={closeModal}
          className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-lg text-[color:var(--muted)] hover:bg-[color:var(--subtle)] hover:text-[color:var(--ink)] transition"
          aria-label="关闭"
        >
          <X size={18} weight="bold" />
        </button>

        <div className="mb-6">
          {step === "set-password" ? (
            <>
              <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-600/20 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-800 mb-3">
                <LockKey size={13} weight="fill" />
                <span>首次登录 · 账号安全</span>
              </div>
              <h2 id="login-dialog-title" className="text-xl sm:text-2xl font-bold tracking-tight text-[color:var(--ink)]">
                设置登录密码
              </h2>
              <p className="text-xs sm:text-sm text-[color:var(--muted)] mt-1.5 leading-relaxed">
                注册成功！设置登录密码后，下次可直接使用邮箱 + 密码快捷登录；也可以跳过，稍后在个人中心设置。
              </p>
            </>
          ) : mode === "password" ? (
            <>
              <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-600/20 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-800 mb-3">
                <LockKey size={13} weight="fill" />
                <span>邮箱 + 密码快捷登录</span>
              </div>
              <h2 id="login-dialog-title" className="text-xl sm:text-2xl font-bold tracking-tight text-[color:var(--ink)]">
                登录 PriceMemo
              </h2>
              <p className="text-xs sm:text-sm text-[color:var(--muted)] mt-1.5 leading-relaxed">
                使用您在个人中心设置的登录密码快捷登录；忘记密码时可随时切换到验证码登录。
              </p>
            </>
          ) : (
            <>
              <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-600/20 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-800 mb-3">
                <Sparkle size={13} weight="fill" />
                <span>邮箱安全免密登录</span>
              </div>
              <h2 id="login-dialog-title" className="text-xl sm:text-2xl font-bold tracking-tight text-[color:var(--ink)]">
                登录 PriceMemo
              </h2>
              <p className="text-xs sm:text-sm text-[color:var(--muted)] mt-1.5 leading-relaxed">
                输入邮箱获取 6 位动态验证码；登录后可设置降价提醒并绑定机器人接收实时价格变动。
              </p>
            </>
          )}
        </div>

        {error && (
          <div className="mb-4 rounded-[9px] border border-[color:var(--danger)]/30 bg-[color:var(--danger-soft)] text-[color:var(--danger)] p-3 text-xs sm:text-sm">
            {error}
          </div>
        )}

        {info && (
          <div className="mb-4 rounded-[9px] border border-[color:var(--success)]/30 bg-[color:var(--success-soft)] text-[color:var(--success)] p-3 text-xs sm:text-sm">
            {info}
          </div>
        )}

        {step === "set-password" ? (
          /* First-login password setup */
          <form onSubmit={handleSetPassword} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-[color:var(--ink)] mb-1.5">
                登录密码
              </label>
              <input
                ref={newPasswordInputRef}
                type="password"
                placeholder="8-64 位，需包含字母和数字"
                autoComplete="new-password"
                maxLength={64}
                value={newPassword}
                disabled={loading}
                onChange={(e) => setNewPassword(e.target.value)}
                className={inputClass}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[color:var(--ink)] mb-1.5">
                确认密码
              </label>
              <input
                type="password"
                placeholder="再次输入登录密码"
                autoComplete="new-password"
                maxLength={64}
                value={confirmPassword}
                disabled={loading}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={inputClass}
              />
            </div>
            <div className="pt-2 space-y-2">
              <button
                type="submit"
                disabled={loading || !newPassword || !confirmPassword}
                className="button-primary tactile w-full py-2.5 rounded-xl text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "正在保存..." : "保存密码"}
              </button>
              <button
                type="button"
                onClick={handleSkipSetPassword}
                disabled={loading}
                className="w-full py-2 text-xs font-medium text-[color:var(--muted)] hover:text-[color:var(--ink)] transition text-center disabled:opacity-50"
              >
                暂不设置，直接进入
              </button>
            </div>
          </form>
        ) : (
          <>
            {/* Login mode tabs */}
            <div
              role="tablist"
              aria-label="登录方式"
              className="grid grid-cols-2 gap-1 rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--subtle)] p-1 mb-5"
            >
              <button
                type="button"
                role="tab"
                aria-selected={mode === "code"}
                onClick={() => switchMode("code")}
                className={`py-1.5 rounded-lg text-xs font-semibold transition ${
                  mode === "code"
                    ? "bg-[color:var(--panel)] text-[color:var(--ink)] shadow-sm"
                    : "text-[color:var(--muted)] hover:text-[color:var(--ink)]"
                }`}
              >
                验证码登录
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === "password"}
                onClick={() => switchMode("password")}
                className={`py-1.5 rounded-lg text-xs font-semibold transition ${
                  mode === "password"
                    ? "bg-[color:var(--panel)] text-[color:var(--ink)] shadow-sm"
                    : "text-[color:var(--muted)] hover:text-[color:var(--ink)]"
                }`}
              >
                密码登录
              </button>
            </div>

            {mode === "code" ? (
              /* Email code login form (existing flow) */
              <form onSubmit={step === "email" ? handleSendCode : handleVerify} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-[color:var(--ink)] mb-1.5">
                    电子邮箱
                  </label>
                  <div className="relative">
                    <input
                      ref={emailInputRef}
                      type="email"
                      placeholder="name@example.com"
                      value={email}
                      disabled={step === "code" || loading}
                      onChange={(e) => setEmail(e.target.value)}
                      className={inputClass}
                    />
                  </div>
                  {step === "code" && requestedEmailRef.current && (
                    <p className="mt-1.5 text-[11px] text-[color:var(--muted)]">
                      验证码已发送至 {requestedEmailRef.current}，请使用该邮箱收到的验证码登录。
                    </p>
                  )}
                </div>

                {step === "code" && (
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-xs font-semibold text-[color:var(--ink)]">
                        6 位动态验证码
                      </label>
                      <button
                        type="button"
                        disabled={countdown > 0 || loading}
                        onClick={() => handleSendCode()}
                        className="text-xs font-semibold text-[color:var(--info)] hover:underline disabled:text-[color:var(--muted)] disabled:no-underline transition"
                      >
                        {countdown > 0 ? `${countdown}s 后可重新获取` : "重新获取验证码"}
                      </button>
                    </div>
                    <input
                      ref={codeInputRef}
                      type="text"
                      placeholder="123456"
                      maxLength={6}
                      value={code}
                      onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                      className="w-full px-3.5 py-2.5 rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] text-base text-[color:var(--ink)] placeholder-[color:var(--muted)] focus:outline-none focus:border-[color:var(--focus)] focus:ring-1 focus:ring-[color:var(--focus)] tracking-widest text-center font-mono font-bold transition"
                    />
                  </div>
                )}

                <div className="pt-2">
                  {step === "email" ? (
                    <button
                      type="submit"
                      disabled={loading || !email}
                      className="button-primary tactile w-full py-2.5 rounded-xl text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {loading ? "正在发送验证码..." : "获取邮箱验证码"}
                    </button>
                  ) : (
                    <div className="space-y-2">
                      <button
                        type="submit"
                        disabled={loading || code.length !== 6}
                        className="button-primary tactile w-full py-2.5 rounded-xl text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {loading ? "正在验证..." : "登录 / 注册"}
                      </button>
                      <button
                        type="button"
                        onClick={handleBackToEmail}
                        className="w-full py-2 text-xs font-medium text-[color:var(--muted)] hover:text-[color:var(--ink)] transition text-center"
                      >
                        更换其他邮箱
                      </button>
                    </div>
                  )}
                </div>
              </form>
            ) : (
              /* Password login form */
              <form onSubmit={handlePasswordLogin} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-[color:var(--ink)] mb-1.5">
                    电子邮箱
                  </label>
                  <input
                    ref={emailInputRef}
                    type="email"
                    placeholder="name@example.com"
                    autoComplete="email"
                    value={email}
                    disabled={loading}
                    onChange={(e) => setEmail(e.target.value)}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[color:var(--ink)] mb-1.5">
                    登录密码
                  </label>
                  <input
                    ref={passwordInputRef}
                    type="password"
                    placeholder="请输入登录密码"
                    autoComplete="current-password"
                    maxLength={128}
                    value={password}
                    disabled={loading}
                    onChange={(e) => setPassword(e.target.value)}
                    className={inputClass}
                  />
                  <p className="mt-1.5 text-[11px] text-[color:var(--muted)]">
                    首次使用或忘记密码？切换到「验证码登录」，登录后可在个人中心设置新密码。
                  </p>
                </div>
                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={loading || !email || !password}
                    className="button-primary tactile w-full py-2.5 rounded-xl text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {loading ? "正在登录..." : "登录"}
                  </button>
                </div>
              </form>
            )}
          </>
        )}
      </div>
    </div>,
    document.body
  );
}
