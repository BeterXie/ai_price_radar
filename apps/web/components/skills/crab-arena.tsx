"use client";

import { useState } from "react";
import { ArrowSquareOut, Check, Copy, Monitor, SquaresFour, Sword, Trophy } from "@phosphor-icons/react";
import { recordSkillCopy } from "@/lib/api";
import { DemoIframe } from "./demo-iframe";

export type CrabModel = {
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
  highlights: string[];
};

const CRAB_MODELS: CrabModel[] = [
  {
    id: "glm-5-3-flash",
    name: "GLM-5.3-Flash",
    badge: "⚡ 纯矢量2D极简美学",
    badgeClass: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
    accentClass: "bg-blue-500",
    demoUrl: "/demos/pk/crab-glm-5-3-flash.html",
    fileSize: "27.8 KB",
    lineCount: "542 行",
    verdict: "轻量优雅 · 纯矢量切线运动学",
    summary:
      "极致精炼的代码实现！严格的切线圆周旋转与透视压缩转向，6足精确分踏3组曲柄，披风随风飘动，确定性伪随机微风草木摇曳，兼具审美灵动与极小运行开销。",
    highlights: [
      "2D 骨骼逆运动学（IK）外拱自然算法",
      "Park-Miller LCG 确定性伪随机草木摇曳",
      "前轮4周、后轮6周、辅助轮8周整除齿比，12秒严格闭环",
      "萌系设计感：飞扬红色小披风、微醺腮红与车把彩带",
    ],
  },
  {
    id: "gemini-38-flash-medium",
    name: "Gemini 3.8 Flash (Medium)",
    badge: "🛠️ 3D工程全家桶狂魔",
    badgeClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
    accentClass: "bg-amber-500",
    demoUrl: "/demos/pk/crab-gemini-38-flash-medium.html",
    fileSize: "80.3 KB",
    lineCount: "1652 行",
    verdict: "全功能3D投影 · 动力学与WebAudio全家桶",
    summary:
      "理工极客级工程堆料！手写 3D 轴测投影与自由拖拽旋转引擎，计算真阿克曼转向角，原生 Web Audio 纯代码合成双音车铃与脚踏声，8足刚性绑定外加墨镜大螯，更提供独立自包含 SVG 动画导出。",
    highlights: [
      "手写 3D 轴测投影引擎，支持鼠标拖拽 360° 旋转视角",
      "真实阿克曼转向角计算（Math.atan2(wheelbase, trackRadius)）",
      "原生 Web Audio 纯代码振荡器合成三音阶车铃与脚踏音效",
      "内置一键导出独立自包含 .SVG 动画文件功能",
    ],
  },
];

export function CrabArena({
  promptText = "",
  skillSlug = "",
}: {
  promptText?: string;
  skillSlug?: string;
}) {
  const [viewMode, setViewMode] = useState<"gallery" | "single">("gallery");
  const [selectedId, setSelectedId] = useState<string>("glm-5-3-flash");
  const [copied, setCopied] = useState(false);

  const activeModel = CRAB_MODELS.find((m) => m.id === selectedId) || CRAB_MODELS[0];

  const handleCopy = async () => {
    if (!promptText) return;
    try {
      await navigator.clipboard.writeText(promptText);
      setCopied(true);
      if (skillSlug) {
        recordSkillCopy(skillSlug).catch(() => {});
      }
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <section className="mt-8 rounded-2xl border border-[color:var(--line)] bg-[color:var(--panel)] p-4 shadow-sm sm:p-6">
      {/* Top Header & Overview */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 px-2 py-0.5 text-xs font-bold">
              <Sword size={12} weight="fill" />
              双模型巅峰对决
            </span>
            <span className="text-xs font-medium text-[color:var(--muted)]">
              同等高难度 Prompt · 零人工修正
            </span>
          </div>

          <h2 className="mt-2 text-xl font-bold tracking-tight text-[color:var(--foreground)] sm:text-2xl">
            螃蟹骑三轮车 · 12秒闭环动画实测视窗
          </h2>
          <p className="mt-1 text-sm text-[color:var(--muted)]">
            对比两大前沿主力模型在空间几何、机械连杆、逆向运动学（IK）与审美风格上的截然不同解题思路。
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
              <span>分屏对比</span>
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
              <span>{copied ? "已复制测试词" : "复制测试 Prompt"}</span>
            </button>
          ) : null}
        </div>
      </div>

      {/* Mode 1: Dual Column Gallery */}
      {viewMode === "gallery" ? (
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4 lg:gap-6">
          {CRAB_MODELS.map((model) => (
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

              {/* Colored Accent Line */}
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

                <p className="text-[color:var(--muted)] leading-relaxed line-clamp-3">
                  {model.summary}
                </p>

                {/* Highlights Pills */}
                <div className="mt-1 flex flex-wrap gap-1">
                  {model.highlights.map((h) => (
                    <span
                      key={h}
                      className="rounded bg-[color:var(--hover)] px-1.5 py-0.5 text-[10px] text-[color:var(--muted)]"
                    >
                      ✓ {h}
                    </span>
                  ))}
                </div>

                <div className="mt-1 flex items-center justify-end">
                  <a
                    href={model.demoUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-semibold text-[color:var(--brand-strong)] underline underline-offset-2 hover:opacity-80 text-xs"
                  >
                    <span>全屏独占打开</span>
                    <ArrowSquareOut size={12} />
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Mode 2: Single Focus View */
        <div className="mt-6 flex flex-col gap-4">
          {/* Tab Selector */}
          <div className="flex flex-wrap gap-2 border-b border-[color:var(--line)] pb-3">
            {CRAB_MODELS.map((model) => {
              const isSelected = model.id === selectedId;
              return (
                <button
                  key={model.id}
                  type="button"
                  onClick={() => setSelectedId(model.id)}
                  className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-xs sm:text-sm font-semibold transition ${
                    isSelected
                      ? "border-[color:var(--foreground)] bg-[color:var(--foreground)] text-[color:var(--panel)] shadow-sm"
                      : "border-[color:var(--line)] bg-[color:var(--card)] text-[color:var(--muted)] hover:text-[color:var(--foreground)]"
                  }`}
                >
                  <span>{model.name}</span>
                  <span className={`text-[10px] px-1.5 py-0.2 rounded border ${model.badgeClass}`}>
                    {model.fileSize}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Active Model Stage */}
          <div className="rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--card)] p-4 sm:p-6 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-bold text-[color:var(--foreground)]">
                    {activeModel.name}
                  </h3>
                  <span className={`inline-block rounded-md border px-2 py-0.5 text-xs font-bold ${activeModel.badgeClass}`}>
                    {activeModel.verdict}
                  </span>
                </div>
                <p className="mt-1 text-xs text-[color:var(--muted)]">
                  体积：{activeModel.fileSize} ｜ 代码量：{activeModel.lineCount}
                </p>
              </div>

              <a
                href={activeModel.demoUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-xl border border-[color:var(--line)] bg-[color:var(--panel)] px-3 py-1.5 text-xs font-medium text-[color:var(--foreground)] hover:bg-[color:var(--hover)] transition w-fit"
              >
                <span>全屏打开</span>
                <ArrowSquareOut size={13} />
              </a>
            </div>

            <div className="relative aspect-[16/10] w-full overflow-hidden rounded-xl border border-[color:var(--line-strong)] bg-neutral-900 shadow-inner">
              <DemoIframe
                src={activeModel.demoUrl}
                title={activeModel.name}
                className="h-full w-full border-0 bg-white"
              />
            </div>

            <div className="mt-4 rounded-xl bg-[color:var(--panel)] p-4 text-xs">
              <h4 className="font-semibold text-[color:var(--foreground)] mb-1">工程与设计亮点：</h4>
              <p className="text-[color:var(--muted)] leading-relaxed mb-3">{activeModel.summary}</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {activeModel.highlights.map((h) => (
                  <div key={h} className="flex items-center gap-1.5 text-[color:var(--muted)]">
                    <span className="text-emerald-500 font-bold">✓</span>
                    <span>{h}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Head-to-head Comparison Table */}
      <div className="mt-8 overflow-hidden rounded-xl border border-[color:var(--line)] bg-[color:var(--card)]">
        <div className="border-b border-[color:var(--line)] bg-[color:var(--subtle)] px-4 py-3">
          <h3 className="text-xs sm:text-sm font-bold text-[color:var(--foreground)] flex items-center gap-2">
            <Trophy size={16} className="text-amber-500" />
            双模型解题架构全景对照表
          </h3>
        </div>
        <div className="overflow-x-auto text-xs">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[color:var(--line)] text-[color:var(--muted)] bg-[color:var(--card)]">
                <th className="py-2.5 px-4 font-semibold">对比维度</th>
                <th className="py-2.5 px-4 font-semibold text-blue-600 dark:text-blue-400">GLM-5.3-Flash</th>
                <th className="py-2.5 px-4 font-semibold text-amber-600 dark:text-amber-400">Gemini 3.8 Flash (Medium)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--line)] text-[color:var(--foreground)]">
              <tr>
                <td className="py-2.5 px-4 font-medium text-[color:var(--muted)]">建模维度</td>
                <td className="py-2.5 px-4">2D 纯矢量平面 + 切线圆周变换</td>
                <td className="py-2.5 px-4">真 3D 轴测空间投影（X, Y, Z + 视角旋转）</td>
              </tr>
              <tr>
                <td className="py-2.5 px-4 font-medium text-[color:var(--muted)]">转向拟真</td>
                <td className="py-2.5 px-4">车把周期旋转 + 前轮 scale(cos) 仿透视</td>
                <td className="py-2.5 px-4">真实阿克曼转向角（arctan(wheelbase / R)）</td>
              </tr>
              <tr>
                <td className="py-2.5 px-4 font-medium text-[color:var(--muted)]">肢体与曲柄绑定</td>
                <td className="py-2.5 px-4">2 钳臂握把 + 6 步足锁3轮曲柄（2+2+2）</td>
                <td className="py-2.5 px-4">8 步足严格刚性铰接 + 额外大螯举墨镜致意</td>
              </tr>
              <tr>
                <td className="py-2.5 px-4 font-medium text-[color:var(--muted)]">代码量 / 体积</td>
                <td className="py-2.5 px-4 font-mono font-bold text-emerald-600 dark:text-emerald-400">542 行 / 27.8 KB（极轻量）</td>
                <td className="py-2.5 px-4 font-mono font-bold text-amber-600 dark:text-amber-400">1652 行 / 80.3 KB（全功能）</td>
              </tr>
              <tr>
                <td className="py-2.5 px-4 font-medium text-[color:var(--muted)]">环境与背景</td>
                <td className="py-2.5 px-4">LCG 确定性伪随机微风摇曳花坛与草丛</td>
                <td className="py-2.5 px-4">3D 砌石挡土墙、路面砖纹与实时动态软阴影</td>
              </tr>
              <tr>
                <td className="py-2.5 px-4 font-medium text-[color:var(--muted)]">音频与交互增强</td>
                <td className="py-2.5 px-4">基础播放/暂停与空格键快捷键</td>
                <td className="py-2.5 px-4">Web Audio 纯代码合成双音车铃与脚踏声、3D 拖拽、SVG 导出</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
