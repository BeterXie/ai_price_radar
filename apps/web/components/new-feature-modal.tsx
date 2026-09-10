"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowRight, Fire, Sparkle, X } from "@phosphor-icons/react";

const FEATURE_STORAGE_KEY = "apr:feature_notice:skills_benchmark_v3753";

export function NewFeatureModal() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    try {
      if (typeof window === "undefined") return;
      // If already dismissed, never show again
      if (localStorage.getItem(FEATURE_STORAGE_KEY)) return;
      // Don't show if user is already browsing the skills section or admin
      if (pathname.startsWith("/skills") || pathname.startsWith("/admin")) return;

      const timer = window.setTimeout(() => {
        try {
          if (!localStorage.getItem(FEATURE_STORAGE_KEY)) {
            setIsOpen(true);
          }
        } catch {
          // Ignore storage errors
        }
      }, 30_000); // 30 seconds

      return () => window.clearTimeout(timer);
    } catch {
      return;
    }
  }, [pathname]);

  const handleDismiss = () => {
    try {
      localStorage.setItem(FEATURE_STORAGE_KEY, "1");
    } catch {
      // Storage might be unavailable
    }
    setIsOpen(false);
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="feature-dialog-title"
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 sm:p-6 animate-in fade-in duration-300"
    >
      {/* Dimmed backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
        onClick={handleDismiss}
        aria-hidden="true"
      />

      {/* Modal Dialog Card */}
      <div className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-6 shadow-2xl transition-all sm:my-8 z-10">
        {/* Top Header with Close Button */}
        <div className="flex items-start justify-between gap-4">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
            <Sparkle size={13} weight="fill" />
            重磅上新 · 实验室与社区技能库
          </div>
          <button
            type="button"
            onClick={handleDismiss}
            aria-label="关闭更新提示"
            className="grid h-11 w-11 shrink-0 place-items-center rounded-lg text-[color:var(--muted)] hover:bg-[color:var(--subtle)] hover:text-[color:var(--ink)] transition"
          >
            <X size={18} />
          </button>
        </div>

        <h2
          id="feature-dialog-title"
          className="mt-3 text-xl font-bold tracking-tight text-[color:var(--ink)] sm:text-2xl"
        >
          全网大模型“降智检测”与精选 Skill 竞技场已上线！
        </h2>

        <p className="mt-2 text-sm leading-relaxed text-[color:var(--muted)]">
          为了帮您在购买或使用 AI 模型时避坑，我们新增了公开的技能与模型性能实验室：
        </p>

        {/* Feature Highlights */}
        <div className="mt-4 space-y-2.5 rounded-xl border border-[color:var(--line)] bg-[color:var(--subtle)] p-3.5 text-sm">
          <div className="flex items-start gap-2.5">
            <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md bg-rose-500/10 text-rose-600 dark:text-rose-400 font-bold">
              <Fire size={13} weight="fill" />
            </span>
            <div className="text-[color:var(--ink)] leading-snug">
              <span className="font-semibold">“鹈鹕骑自行车”零测试降智评测：</span>
              <span className="text-[color:var(--muted)]">
                实测 GPT-6 Astra、GPT-5.6、Gemini 3.8 等前沿模型输出，一眼识别满血版与偷懒降智版！
              </span>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md bg-purple-500/10 text-purple-600 dark:text-purple-400 font-bold">
              <Sparkle size={13} weight="fill" />
            </span>
            <div className="text-[color:var(--ink)] leading-snug">
              <span className="font-semibold">首批 11 款官方开源生产级 Skill：</span>
              <span className="text-[color:var(--muted)]">
                涵盖 Karpathy 审美重塑（taste-skill）、Vercel 原生 Rust 浏览器、阿里代码审查等。
              </span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-6 flex flex-col-reverse sm:flex-row items-center justify-end gap-3">
          <button
            type="button"
            onClick={handleDismiss}
            className="button-secondary w-full sm:w-auto"
          >
            稍后再看
          </button>
          <Link
            href="/skills/pelican-bicycle-benchmark"
            onClick={handleDismiss}
            className="button-primary tactile w-full sm:w-auto"
          >
            <span>立即试玩竞技场</span>
            <ArrowRight size={15} weight="bold" />
          </Link>
        </div>
      </div>
    </div>
  );
}
