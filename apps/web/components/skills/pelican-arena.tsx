"use client";

import { useState } from "react";
import { ArrowSquareOut, Check, Copy, Eye, Sparkle, SquaresFour, Monitor } from "@phosphor-icons/react";
import { recordSkillCopy } from "@/lib/api";
import { DemoIframe } from "./demo-iframe";

export type ArenaModel = {
  id: string;
  name: string;
  badge: string;
  badgeClass: string;
  accentClass: string;
  demoUrl: string;
  fileSize: string;
  lineCount: string;
  verdict: string;
  summary: string;
};

const ARENA_MODELS: ArenaModel[] = [
  {
    id: "gpt6-astra-full",
    name: "GPT-6-Astra 满血版",
    badge: "🏆 满血天花板",
    badgeClass: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    accentClass: "bg-rose-500",
    demoUrl: "/demos/benchmarks/pelican-gpt6-astra-full.html",
    fileSize: "12 KB",
    lineCount: "111 行",
    verdict: "满血通过",
    summary: "一次成型零测试！完整的海滨风景、飘动橙色围巾、双脚交替踩动曲柄踏板、双轮旋转与眨眼呼吸微动效，诗意与机械推演俱佳。",
  },
  {
    id: "gpt6-astra-degraded",
    name: "GPT-6-Astra 降智版",
    badge: "⚠️ 典型降智",
    badgeClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
    accentClass: "bg-amber-500",
    demoUrl: "/demos/benchmarks/pelican-gpt6-astra-degraded.html",
    fileSize: "8.4 KB",
    lineCount: "158 行",
    verdict: "降智退化",
    summary: "脏 IP / 官方暗中降级时的典型产物。远景层次大幅缩水，肢体与机械运动退化为简单僵硬的上下摆钟平移，失去灵气。",
  },
  {
    id: "gpt56-vds",
    name: "GPT-5.6 + Victor-Design",
    badge: "⭐ Skill 降维打击",
    badgeClass: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
    accentClass: "bg-purple-500",
    demoUrl: "/demos/benchmarks/pelican-gpt56-vds.html",
    fileSize: "16.5 KB",
    lineCount: "397 行",
    verdict: "设计大师调教",
    summary: "挂载 Victor-Design 技能后直接实现艺术级跃升！注入 VDS 3.1 规范、纸张/海风复古配色、胶囊控制栏与极高格调的插画质感。",
  },
  {
    id: "gpt56-chat",
    name: "GPT-5.6 网页裸跑",
    badge: "📉 裸跑流水线",
    badgeClass: "bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20",
    accentClass: "bg-slate-400 dark:bg-slate-600",
    demoUrl: "/demos/benchmarks/pelican-gpt56-chat.html",
    fileSize: "3.1 KB",
    lineCount: "105 行",
    verdict: "普通及格",
    summary: "无 Skill 约束时的默认输出。典型的三根线小车架与一个黄色太阳，无层次感与设计系统支撑，体现了 AI 默认审美的局限。",
  },
  {
    id: "gemini38-flash",
    name: "Gemini 3.8 Flash",
    badge: "⚡ 极客工程狂魔",
    badgeClass: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20",
    accentClass: "bg-emerald-500",
    demoUrl: "/demos/benchmarks/pelican-gemini38-flash.html",
    fileSize: "31.3 KB",
    lineCount: "876 行",
    verdict: "恐怖吞吐量",
    summary: "以极其惊人的代码充沛度将动画做成前端小游戏！自带白天/黄昏/夜晚三套主题切换，且支持加速与减速档位调节交互。",
  },
  {
    id: "bajie-astra",
    name: "GPT-6-Astra 猪八戒",
    badge: "🐷 西游文化彩蛋",
    badgeClass: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
    accentClass: "bg-rose-400",
    demoUrl: "/demos/benchmarks/bajie-gpt6-astra.html",
    fileSize: "15.4 KB",
    lineCount: "215 行",
    verdict: "文化意象拟人化",
    summary: "“去西天，也可以慢慢骑”。黑僧帽、九齿钉耙、飘逸红色僧袍与麦浪山丘，证明满血模型对非现实东方文化角色的空间结构理解力。",
  },
];

export function PelicanArena({ promptText = "", skillSlug = "" }: { promptText?: string; skillSlug?: string }) {
  const [viewMode, setViewMode] = useState<"gallery" | "single">("gallery");
  const [selectedId, setSelectedId] = useState<string>("gpt6-astra-full");
  const [copied, setCopied] = useState(false);

  const activeModel = ARENA_MODELS.find((m) => m.id === selectedId) || ARENA_MODELS[0];

  const handleCopy = async () => {
    if (!promptText) return;
    try {
      await navigator.clipboard.writeText(promptText);
      setCopied(true);
      if (skillSlug) {
        recordSkillCopy(skillSlug).catch(() => {});
      }
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  };

  return (
    <section className="mt-8 rounded-2xl border border-[color:var(--line)] bg-[color:var(--panel)] p-4 shadow-sm sm:p-6">
      {/* Top Header & Overview */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 px-2 py-0.5 text-xs font-bold">
              {ARENA_MODELS.length} 个模型
            </span>
            <span className="text-xs font-medium text-[color:var(--muted)]">
              同一句提示词
            </span>
          </div>

          <h2 className="mt-2 text-xl font-bold tracking-tight text-[color:var(--foreground)] sm:text-2xl">
            在线试玩与满血对比视窗
          </h2>
          <p className="mt-1 text-sm text-[color:var(--muted)]">
            点击切换查看不同模型在零测试要求下直接生成的 2D 动画真实效果，一眼辨识满血与降智。
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* View Mode Switcher */}
          <div className="inline-flex rounded-xl border border-[color:var(--line)] bg-[color:var(--card)] p-1 text-xs font-medium">
            <button
              type="button"
              onClick={() => setViewMode("gallery")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 transition ${
                viewMode === "gallery"
                  ? "bg-[color:var(--foreground)] text-[color:var(--panel)] shadow-sm font-semibold"
                  : "text-[color:var(--muted)] hover:text-[color:var(--foreground)]"
              }`}
            >
              <SquaresFour size={14} weight="bold" />
              <span>双列画廊</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode("single")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 transition ${
                viewMode === "single"
                  ? "bg-[color:var(--foreground)] text-[color:var(--panel)] shadow-sm font-semibold"
                  : "text-[color:var(--muted)] hover:text-[color:var(--foreground)]"
              }`}
            >
              <Monitor size={14} weight="bold" />
              <span>单视窗精选</span>
            </button>
          </div>

          {promptText ? (
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-xl border border-[color:var(--line)] bg-[color:var(--card)] px-3 py-1.5 text-xs font-semibold text-[color:var(--foreground)] shadow-sm transition hover:bg-[color:var(--hover)] active:scale-95"
            >
              {copied ? <Check size={14} weight="bold" className="text-emerald-500" /> : <Copy size={14} weight="bold" />}
              <span>{copied ? "已复制体检词" : "复制测试 Prompt"}</span>
            </button>
          ) : null}
        </div>
      </div>

      {/* Mode 1: 2-Column Gallery Grid (参考图片样式排版) */}
      {viewMode === "gallery" ? (
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4 lg:gap-6">
          {ARENA_MODELS.map((model) => (
            <div
              key={model.id}
              className="flex flex-col rounded-2xl border border-[color:var(--line)] bg-[color:var(--card)] p-3.5 sm:p-4 shadow-sm transition hover:border-[color:var(--line-strong)] hover:shadow-md"
            >
              {/* Card Header Row */}
              <div className="flex items-center justify-between px-0.5 pb-1 text-xs sm:text-sm">
                <span className="font-bold text-[color:var(--foreground)] tracking-tight sm:text-base">
                  {model.name}
                </span>
                <span className="font-medium text-[color:var(--muted)] text-xs">
                  {model.badge}
                </span>
              </div>

              {/* Colored Accent Line (参考图片中的彩色分界线) */}
              <div className={`h-[2.5px] w-full rounded-full mb-2.5 ${model.accentClass}`} />

              {/* Iframe Preview */}
              <div className="relative aspect-[16/10] w-full overflow-hidden rounded-xl border border-[color:var(--line-strong)] bg-neutral-900 shadow-inner">
                <DemoIframe
                  src={model.demoUrl}
                  title={model.name}
                  className="h-full w-full border-0 bg-white"
                />
              </div>

              {/* Info & Diagnosis */}
              <div className="mt-3 flex flex-col justify-between flex-1 gap-2 pt-1 border-t border-[color:var(--line)]/60 text-xs">
                <div className="flex items-center justify-between text-[color:var(--muted)]">
                  <span className={`inline-block rounded-md border px-1.5 py-0.5 text-[10px] font-bold ${model.badgeClass}`}>
                    {model.verdict}
                  </span>
                  <span className="font-mono text-[11px]">
                    {model.fileSize} · {model.lineCount}
                  </span>
                </div>

                <p className="text-xs text-[color:var(--muted)] leading-relaxed">
                  {model.summary}
                </p>

                <div className="flex items-center justify-between pt-1 border-t border-[color:var(--line)]/40">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedId(model.id);
                      setViewMode("single");
                    }}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-[color:var(--brand-strong)] hover:underline"
                  >
                    <Eye size={13} />
                    <span>大屏深度视窗</span>
                  </button>

                  <a
                    href={model.demoUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-[color:var(--muted)] hover:text-[color:var(--foreground)]"
                  >
                    <span>新窗口全屏</span>
                    <ArrowSquareOut size={12} />
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Mode 2: Single Focus Viewport */
        <div className="mt-6">
          {/* Model Tabs */}
          <div className="flex flex-wrap gap-2 border-b border-[color:var(--line)] pb-4">
            {ARENA_MODELS.map((model) => {
              const isActive = model.id === selectedId;
              return (
                <button
                  key={model.id}
                  type="button"
                  onClick={() => setSelectedId(model.id)}
                  className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-medium transition sm:text-sm ${
                    isActive
                      ? "border-[color:var(--brand)] bg-[color:var(--brand-soft)] text-[color:var(--brand-strong)] shadow-sm font-semibold"
                      : "border-[color:var(--line)] bg-[color:var(--card)] text-[color:var(--muted)] hover:border-[color:var(--line-strong)] hover:text-[color:var(--foreground)]"
                  }`}
                >
                  <span className={`inline-block rounded-md border px-1.5 py-0.5 text-[10px] font-bold ${model.badgeClass}`}>
                    {model.verdict}
                  </span>
                  <span>{model.name}</span>
                </button>
              );
            })}
          </div>

          {/* Model Diagnosis Banner */}
          <div className="mt-4 flex flex-col gap-3 rounded-xl border border-[color:var(--line)] bg-[color:var(--card)] p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2.5">
                <span className="font-semibold text-[color:var(--foreground)]">{activeModel.name}</span>
                <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${activeModel.badgeClass}`}>
                  {activeModel.badge}
                </span>
                <span className="text-xs text-[color:var(--muted)]">
                  {activeModel.fileSize} · {activeModel.lineCount}
                </span>
              </div>
              <p className="text-xs text-[color:var(--muted)] sm:text-sm leading-relaxed">
                {activeModel.summary}
              </p>
            </div>

            <a
              href={activeModel.demoUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-[color:var(--line)] bg-[color:var(--panel)] px-3 py-1.5 text-xs font-medium text-[color:var(--foreground)] transition hover:bg-[color:var(--hover)] self-start sm:self-center"
            >
              <span>独立窗口打开</span>
              <ArrowSquareOut size={14} />
            </a>
          </div>

          {/* Iframe Viewport */}
          <div className="mt-4 relative aspect-[16/10] w-full overflow-hidden rounded-xl border border-[color:var(--line-strong)] bg-neutral-900 shadow-inner">
            <DemoIframe
              key={activeModel.id}
              src={activeModel.demoUrl}
              title={activeModel.name}
              className="h-full w-full border-0 bg-white"
            />
          </div>
        </div>
      )}

      {/* Prompt Callout */}
      {promptText ? (
        <div className="mt-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-dashed border-[color:var(--brand-line)] bg-[color:var(--brand-soft)]/50 p-3.5 text-xs sm:text-sm text-[color:var(--brand-strong)]">
          <div className="flex items-center gap-2 font-mono">
            <span className="font-bold">体检咒语：</span>
            <span className="select-all break-all">{promptText}</span>
          </div>
          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex shrink-0 items-center gap-1.5 font-bold underline underline-offset-2 hover:opacity-80"
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "已复制" : "点击复制"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
