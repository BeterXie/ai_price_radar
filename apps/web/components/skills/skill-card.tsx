"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Copy, Fire, GithubLogo, Sparkle, Star, TerminalWindow } from "@phosphor-icons/react";
import type { CommunitySkillSummary } from "@/lib/types";
import { recordSkillCopy } from "@/lib/api";

const KIND_META: Record<string, { label: string; icon: any; badgeClass: string }> = {
  benchmark: {
    label: "降智体检",
    icon: Fire,
    badgeClass: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
  },
  skill: {
    label: "实用技能",
    icon: Sparkle,
    badgeClass: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
  },
  article: {
    label: "经验博文",
    icon: TerminalWindow,
    badgeClass: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  },
};

export function SkillCard({ skill }: { skill: CommunitySkillSummary }) {
  const [copied, setCopied] = useState(false);
  const meta = KIND_META[skill.kind] || KIND_META.skill;
  const IconComponent = meta.icon;

  const copyPayload = skill.install_command || skill.prompt_template;

  const handleCopy = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!copyPayload) return;
    try {
      await navigator.clipboard.writeText(copyPayload);
      setCopied(true);
      recordSkillCopy(skill.slug).catch(() => {});
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  };

  return (
    <div className="group relative flex flex-col justify-between rounded-2xl border border-[color:var(--line)] bg-[color:var(--panel)] p-5 shadow-sm transition hover:border-[color:var(--line-strong)] hover:shadow-md">
      <div>
        {/* Top Header Row */}
        <div className="flex items-center justify-between gap-2">
          <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold ${meta.badgeClass}`}>
            <IconComponent size={13} weight="fill" />
            {meta.label}
          </span>

          {skill.stars_count > 0 ? (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--muted)]">
              <Star size={13} weight="fill" className="text-amber-500" />
              {skill.stars_count >= 1000 ? `${(skill.stars_count / 1000).toFixed(1)}k` : skill.stars_count}
            </span>
          ) : null}
        </div>

        {/* Title & Subtitle */}
        <div className="mt-3">
          <Link href={`/skills/${encodeURIComponent(skill.slug)}`} className="focus:outline-none">
            <h3 className="text-base font-bold text-[color:var(--foreground)] transition group-hover:text-[color:var(--brand-strong)] sm:text-lg">
              {skill.title}
            </h3>
          </Link>
          {skill.subtitle ? (
            <p className="mt-1 text-xs font-medium text-[color:var(--muted)] sm:text-sm">
              {skill.subtitle}
            </p>
          ) : null}
        </div>

        {/* Summary */}
        <p className="mt-2.5 line-clamp-3 text-xs text-[color:var(--muted)] leading-relaxed sm:text-sm">
          {skill.summary}
        </p>

        {/* Target Models & Tags */}
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          {skill.target_models?.map((model) => (
            <span
              key={model}
              className="rounded border border-[color:var(--line)] bg-[color:var(--card)] px-1.5 py-0.5 text-[11px] font-medium text-[color:var(--muted)]"
            >
              {model}
            </span>
          ))}
          {skill.tags?.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="rounded bg-[color:var(--hover)] px-1.5 py-0.5 text-[11px] text-[color:var(--muted)]"
            >
              #{tag}
            </span>
          ))}
        </div>
      </div>

      {/* Bottom Footer Actions */}
      <div className="mt-5 border-t border-[color:var(--line)] pt-3 flex items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2 min-w-0">
          {skill.author_name ? (
            <span className="truncate text-[color:var(--muted)]">
              作者: <strong className="font-semibold text-[color:var(--foreground)]">{skill.author_name}</strong>
            </span>
          ) : (
            <span className="text-[color:var(--muted)]">社区精选</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {copyPayload ? (
            <button
              type="button"
              onClick={handleCopy}
              title={skill.install_command ? "复制安装命令" : "复制测试 Prompt"}
              className="inline-flex items-center gap-1 rounded-lg border border-[color:var(--line)] bg-[color:var(--card)] px-2.5 py-1 text-xs font-medium text-[color:var(--foreground)] transition hover:bg-[color:var(--hover)]"
            >
              {copied ? <Check size={13} className="text-emerald-500" /> : <Copy size={13} />}
              <span>{copied ? "已复制" : skill.install_command ? "安装" : "复制"}</span>
            </button>
          ) : null}

          <Link
            href={`/skills/${encodeURIComponent(skill.slug)}`}
            className="inline-flex items-center gap-1 rounded-lg bg-[color:var(--foreground)] px-3 py-1 font-semibold text-[color:var(--panel)] transition hover:opacity-90"
          >
            详情 ➔
          </Link>
        </div>
      </div>
    </div>
  );
}
