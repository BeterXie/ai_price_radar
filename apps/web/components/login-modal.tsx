"use client";

import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { X, EnvelopeSimple, Sparkle } from "@phosphor-icons/react";
import type { AuthSessionState } from "@/lib/types";
import { requestEmailLoginCode, verifyEmailLoginCode } from "@/lib/auth-client";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (session: AuthSessionState) => void;
}

export function LoginModal({ isOpen, onClose, onSuccess }: LoginModalProps) {
  const [mounted, setMounted] = useState(false);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"email" | "code">("email");
  const [countdown, setCountdown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

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
    try {
      const res = await requestEmailLoginCode(cleanEmail);
      if (res.success) {
        setStep("code");
        setCountdown(res.retry_after || 60);
        setInfo(res.message || "验证码已发送至您的邮箱");
      } else {
        setError(res.message);
        if (res.retry_after > 0) setCountdown(res.retry_after);
      }
    } catch (err: any) {
      setError(err.message || "发送失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) {
      setError("请输入收到的 6 位验证码");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const session = await verifyEmailLoginCode(email.trim(), code.trim());
      if (session.authenticated) {
        onSuccess(session);
        onClose();
      } else {
        setError("登录验证失败，请重试");
      }
    } catch (err: any) {
      setError(err.message || "验证码错误或已失效");
    } finally {
      setLoading(false);
    }
  };

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
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Dialog Card adhering to PriceMemo paper design system */}
      <div
        className="relative w-full max-w-md my-auto rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-6 sm:p-8 shadow-2xl text-[color:var(--ink)] z-10 transition-all"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-lg text-[color:var(--muted)] hover:bg-[color:var(--subtle)] hover:text-[color:var(--ink)] transition"
          aria-label="关闭"
        >
          <X size={18} weight="bold" />
        </button>

        <div className="mb-6">
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

        {/* Email Login Form */}
        <form onSubmit={step === "email" ? handleSendCode : handleVerify} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[color:var(--ink)] mb-1.5">
              电子邮箱
            </label>
            <div className="relative">
              <input
                type="email"
                placeholder="name@example.com"
                value={email}
                disabled={step === "code" && countdown > 0}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] text-sm text-[color:var(--ink)] placeholder-[color:var(--muted)] focus:outline-none focus:border-[color:var(--focus)] focus:ring-1 focus:ring-[color:var(--focus)] transition disabled:opacity-60 disabled:bg-[color:var(--subtle)]"
              />
            </div>
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
                type="text"
                placeholder="123456"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                className="w-full px-3.5 py-2.5 rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] text-base text-[color:var(--ink)] placeholder-[color:var(--muted)] focus:outline-none focus:border-[color:var(--focus)] focus:ring-1 focus:ring-[color:var(--focus)] tracking-widest text-center font-mono font-bold transition"
                autoFocus
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
                  disabled={loading || code.length < 4}
                  className="button-primary tactile w-full py-2.5 rounded-xl text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {loading ? "正在验证..." : "登录 / 注册"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setStep("email");
                    setCode("");
                  }}
                  className="w-full py-2 text-xs font-medium text-[color:var(--muted)] hover:text-[color:var(--ink)] transition text-center"
                >
                  更换其他邮箱
                </button>
              </div>
            )}
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}
