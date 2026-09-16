"use client";

import React, { useState, useEffect } from "react";
import type { AuthSessionState } from "@/lib/types";
import { requestEmailLoginCode, verifyEmailLoginCode } from "@/lib/auth-client";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (session: AuthSessionState) => void;
}

export function LoginModal({ isOpen, onClose, onSuccess }: LoginModalProps) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"email" | "code">("email");
  const [countdown, setCountdown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setInterval(() => {
      setCountdown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [countdown]);

  if (!isOpen) return null;

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

  const handleQQLogin = () => {
    window.location.href = "/api/v1/auth/qq/login";
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md rounded-2xl bg-zinc-900 border border-zinc-800 p-6 sm:p-8 shadow-2xl text-zinc-100"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 text-zinc-400 hover:text-zinc-100 text-xl font-bold w-8 h-8 rounded-full flex items-center justify-center hover:bg-zinc-800 transition"
          aria-label="关闭"
        >
          ✕
        </button>

        <div className="mb-6">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium mb-3">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            快速安全登录
          </div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight">登录 PriceMemo</h2>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1">
            登录后可开启价格变动提醒、绑定 QQ 机器人、享受实时推送
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-900/30 border border-red-800/50 text-red-300 text-xs sm:text-sm">
            {error}
          </div>
        )}

        {info && (
          <div className="mb-4 p-3 rounded-lg bg-emerald-900/30 border border-emerald-800/50 text-emerald-300 text-xs sm:text-sm">
            {info}
          </div>
        )}

        {/* QQ Quick Login */}
        <div className="space-y-3">
          <button
            type="button"
            onClick={handleQQLogin}
            className="w-full flex items-center justify-center gap-3 py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-medium text-sm transition shadow-lg shadow-blue-600/20"
          >
            <svg className="w-5 h-5 fill-current" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12c0 2.85 1.2 5.41 3.12 7.23-.08-.6-.12-1.21-.12-1.83 0-3.31 2.69-6 6-6s6 2.69 6 6c0 .62-.04 1.23-.12 1.83C18.8 17.41 20 14.85 20 12c0-5.52-4.48-10-10-10zm0 15c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3z" />
            </svg>
            <span>QQ 快捷登录</span>
          </button>
        </div>

        <div className="relative my-6 text-center">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-zinc-800" />
          </div>
          <span className="relative bg-zinc-900 px-3 text-xs text-zinc-500">
            或使用邮箱验证码登录
          </span>
        </div>

        {/* Email Login Form */}
        <form onSubmit={step === "email" ? handleSendCode : handleVerify} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              邮箱地址
            </label>
            <input
              type="email"
              placeholder="name@example.com"
              value={email}
              disabled={step === "code" && countdown > 0}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-800/80 border border-zinc-700 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition disabled:opacity-60"
            />
          </div>

          {step === "code" && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-zinc-400">
                  6 位验证码
                </label>
                <button
                  type="button"
                  disabled={countdown > 0 || loading}
                  onClick={() => handleSendCode()}
                  className="text-xs text-emerald-400 hover:text-emerald-300 disabled:text-zinc-500 transition"
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
                className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-800/80 border border-zinc-700 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 tracking-widest text-center font-mono text-lg transition"
                autoFocus
              />
            </div>
          )}

          <div className="pt-2">
            {step === "email" ? (
              <button
                type="submit"
                disabled={loading || !email}
                className="w-full py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 text-white font-medium text-sm transition shadow-lg shadow-emerald-600/20 flex items-center justify-center gap-2"
              >
                {loading ? "发送中..." : "获取邮箱验证码"}
              </button>
            ) : (
              <div className="space-y-2">
                <button
                  type="submit"
                  disabled={loading || code.length < 4}
                  className="w-full py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 text-white font-medium text-sm transition shadow-lg shadow-emerald-600/20 flex items-center justify-center gap-2"
                >
                  {loading ? "验证中..." : "登录 / 注册"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setStep("email");
                    setCode("");
                  }}
                  className="w-full py-2 text-xs text-zinc-400 hover:text-zinc-200 transition"
                >
                  更换邮箱
                </button>
              </div>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
