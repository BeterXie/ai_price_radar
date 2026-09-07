"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowLeft,
  ArrowSquareOut,
  Check,
  Copy,
  Eye,
  Fire,
  GithubLogo,
  ShareNetwork,
  Sparkle,
  Star,
  TerminalWindow,
} from "@phosphor-icons/react";
import type { CommunitySkillDetail } from "@/lib/types";
import { recordSkillCopy } from "@/lib/api";
import { PelicanArena } from "@/components/skills/pelican-arena";
import { MarkdownView } from "@/components/skills/markdown-view";
import { DemoIframe } from "@/components/skills/demo-iframe";

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

export function SkillDetailView({ skill }: { skill: CommunitySkillDetail }) {
  const [copiedCmd, setCopiedCmd] = useState(false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  const meta = KIND_META[skill.kind] || KIND_META.skill;
  const IconComponent = meta.icon;

  const handleCopyInstall = async () => {
    if (!skill.install_command) return;
    try {
      await navigator.clipboard.writeText(skill.install_command);
      setCopiedCmd(true);
      recordSkillCopy(skill.slug).catch(() => {});
      setTimeout(() => setCopiedCmd(false), 2000);
    } catch {}
  };

  const handleCopyPrompt = async () => {
    if (!skill.prompt_template) return;
    try {
      await navigator.clipboard.writeText(skill.prompt_template);
      setCopiedPrompt(true);
      recordSkillCopy(skill.slug).catch(() => {});
      setTimeout(() => setCopiedPrompt(false), 2000);
    } catch {}
  };

  const handleShare = async () => {
    try {
      if (typeof window !== "undefined") {
        await navigator.clipboard.writeText(window.location.href);
        setCopiedLink(true);
        setTimeout(() => setCopiedLink(false), 2000);
      }
    } catch {}
  };

  return (
    <article className="shell py-8">
      {/* Breadcrumb & Top Bar */}
      <div className="flex items-center justify-between gap-4 border-b border-[color:var(--line)] pb-4 text-xs">
        <Link
          href="/skills"
          className="inline-flex items-center gap-1.5 font-medium text-[color:var(--muted)] transition hover:text-[color:var(--foreground)]"
        >
          <ArrowLeft size={14} />
          <span>返回技能与实验室</span>
        </Link>

        <button
          type="button"
          onClick={handleShare}
          className="inline-flex items-center gap-1 text-[color:var(--muted)] hover:text-[color:var(--foreground)] transition"
        >
          {copiedLink ? <Check size={14} className="text-emerald-500" /> : <ShareNetwork size={14} />}
          <span>{copiedLink ? "链接已复制" : "分享本页"}</span>
        </button>
      </div>

      {/* Main Header */}
      <header className="mt-6">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-semibold ${meta.badgeClass}`}>
            <IconComponent size={14} weight="fill" />
            {meta.label}
          </span>

          {skill.stars_count > 0 ? (
            <span className="inline-flex items-center gap-1 rounded-md border border-[color:var(--line)] bg-[color:var(--card)] px-2.5 py-1 text-xs font-semibold text-[color:var(--muted)]">
              <Star size={13} weight="fill" className="text-amber-500" />
              {skill.stars_count >= 1000 ? `${(skill.stars_count / 1000).toFixed(1)}k Stars` : `${skill.stars_count} Stars`}
            </span>
          ) : null}

          {skill.repo_url ? (
            <a
              href={skill.repo_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 rounded-md border border-[color:var(--line)] bg-[color:var(--card)] px-2.5 py-1 text-xs font-semibold text-[color:var(--foreground)] transition hover:bg-[color:var(--hover)]"
            >
              <GithubLogo size={14} />
              <span>官方开源仓库</span>
              <ArrowSquareOut size={12} />
            </a>
          ) : null}
        </div>

        <h1 className="mt-3 text-2xl font-bold tracking-tight text-[color:var(--foreground)] sm:text-3xl lg:text-4xl">
          {skill.title}
        </h1>

        {skill.subtitle ? (
          <p className="mt-2 text-base font-medium text-[color:var(--muted)] sm:text-lg">
            {skill.subtitle}
          </p>
        ) : null}

        {/* Metadata Row */}
        <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-[color:var(--muted)]">
          {skill.author_name ? (
            <div>
              原作者:{" "}
              {skill.author_url ? (
                <a
                  href={skill.author_url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-semibold text-[color:var(--foreground)] underline underline-offset-2 hover:opacity-80"
                >
                  {skill.author_name}
                </a>
              ) : (
                <strong className="font-semibold text-[color:var(--foreground)]">{skill.author_name}</strong>
              )}
            </div>
          ) : null}

          <div className="inline-flex items-center gap-1">
            <Eye size={14} />
            <span>{skill.view_count} 次浏览</span>
          </div>

          <div className="inline-flex items-center gap-1">
            <Copy size={14} />
            <span>{skill.copy_count} 次复制</span>
          </div>

          <div>
            适用模型:{" "}
            {skill.target_models?.length ? (
              <span className="font-medium text-[color:var(--foreground)]">
                {skill.target_models.join(" / ")}
              </span>
            ) : (
              "通用"
            )}
          </div>
        </div>
      </header>

      {/* Quick Action Commands / Prompts */}
      {skill.install_command ? (
        <div className="mt-6 overflow-hidden rounded-xl border border-[color:var(--line-strong)] bg-neutral-900 text-neutral-100 p-4 font-mono text-xs sm:text-sm">
          <div className="flex items-center justify-between text-neutral-400 text-xs mb-2">
            <span>一键安装命令 (终端执行)</span>
            <button
              type="button"
              onClick={handleCopyInstall}
              className="inline-flex items-center gap-1 rounded bg-neutral-800 px-2 py-1 text-white hover:bg-neutral-700 transition"
            >
              {copiedCmd ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
              <span>{copiedCmd ? "已复制命令" : "复制命令"}</span>
            </button>
          </div>
          <div className="overflow-x-auto select-all leading-relaxed text-emerald-400">
            $ {skill.install_command}
          </div>
        </div>
      ) : null}

      {skill.prompt_template && skill.demo_type !== "pelican_arena" ? (
        <div className="mt-6 rounded-xl border border-dashed border-[color:var(--brand-line)] bg-[color:var(--brand-soft)]/40 p-4 text-xs sm:text-sm">
          <div className="flex items-center justify-between text-[color:var(--brand-strong)] font-semibold mb-1.5">
            <span>测试 Prompt：</span>
            <button
              type="button"
              onClick={handleCopyPrompt}
              className="inline-flex items-center gap-1 font-bold underline underline-offset-2 hover:opacity-80"
            >
              {copiedPrompt ? <Check size={13} /> : <Copy size={13} />}
              <span>{copiedPrompt ? "已复制 Prompt" : "复制 Prompt"}</span>
            </button>
          </div>
          <div className="font-mono text-[color:var(--foreground)] select-all leading-relaxed">
            {skill.prompt_template}
          </div>
        </div>
      ) : null}

      {/* Interactive Pelican Arena Viewer */}
      {skill.demo_type === "pelican_arena" ? (
        <PelicanArena promptText={skill.prompt_template} skillSlug={skill.slug} />
      ) : null}

      {/* Standalone Iframe Viewer (e.g. Bajie or VictorDesign) */}
      {skill.demo_type === "iframe" && skill.demo_url ? (
        <div className="mt-8 rounded-2xl border border-[color:var(--line)] bg-[color:var(--panel)] p-4 shadow-sm sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-[color:var(--foreground)]">在线效果演示</h2>
            <a
              href={skill.demo_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--brand-strong)] underline underline-offset-2"
            >
              <span>新窗口全屏打开</span>
              <ArrowSquareOut size={13} />
            </a>
          </div>
          <div className="relative aspect-[16/10] w-full overflow-hidden rounded-xl border border-[color:var(--line-strong)] bg-neutral-900 shadow-inner">
            <DemoIframe
              src={skill.demo_url}
              title={skill.title}
              className="h-full w-full border-0 bg-white"
            />
          </div>
        </div>
      ) : null}

      {/* Markdown Body Content */}
      <div className="mt-8">
        <MarkdownView content={skill.content_markdown} />
      </div>

      {/* Conversion Banner: Related Product */}
      {skill.related_product ? (
        <div className="mt-12 rounded-2xl border border-[color:var(--brand-line)] bg-[color:var(--brand-soft)]/50 p-6 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <span className="inline-block rounded-full bg-[color:var(--brand-strong)]/10 px-2.5 py-0.5 text-xs font-bold text-[color:var(--brand-strong)]">
                满血体验推荐
              </span>
              <h3 className="mt-2 text-lg font-bold text-[color:var(--foreground)] sm:text-xl">
                想要获得满血无降智体验或运行该技能？
              </h3>
              <p className="mt-1 text-xs sm:text-sm text-[color:var(--muted)]">
                查看 <strong>{skill.related_product.display_name}</strong> 当前全网店铺最低报价、合租车位、直充与质保对比。
              </p>
            </div>

            <Link
              href={`/products/${encodeURIComponent(skill.related_product.slug)}`}
              className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-[color:var(--foreground)] px-5 py-3 text-sm font-bold text-[color:var(--panel)] shadow-sm transition hover:opacity-90 active:scale-95"
            >
              <span>查看 {skill.related_product.display_name} 实时底价</span>
              <span>➔</span>
            </Link>
          </div>
        </div>
      ) : null}
    </article>
  );
}
