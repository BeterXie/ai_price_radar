"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowSquareOut,
  Copy,
  Eye,
  Fire,
  GithubLogo,
  ShareNetwork,
  ShieldCheck,
  Sparkle,
  Star,
  TerminalWindow,
} from "@phosphor-icons/react";
import type { CommunitySkillDetail } from "@/lib/types";
import { recordSkillCopy } from "@/lib/api";
import { PelicanArena } from "@/components/skills/pelican-arena";
import { MarkdownView } from "@/components/skills/markdown-view";
import { DemoIframe } from "@/components/skills/demo-iframe";

const KIND_META: Record<string, { label: string; icon: any; tone: string }> = {
  benchmark: { label: "模型评测", icon: Fire, tone: "orange" },
  skill: { label: "实用 Skills", icon: Sparkle, tone: "purple" },
  article: { label: "技巧与博文", icon: TerminalWindow, tone: "green" },
};

export function SkillDetailView({ skill }: { skill: CommunitySkillDetail }) {
  const [copiedCmd, setCopiedCmd] = useState(false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const meta = KIND_META[skill.kind] || KIND_META.skill;
  const Icon = meta.icon;

  async function copy(text: string, kind: "cmd" | "prompt") {
    try {
      await navigator.clipboard.writeText(text);
      kind === "cmd" ? setCopiedCmd(true) : setCopiedPrompt(true);
      recordSkillCopy(skill.slug).catch(() => {});
      window.setTimeout(() => kind === "cmd" ? setCopiedCmd(false) : setCopiedPrompt(false), 1800);
    } catch {}
  }

  async function share() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopiedLink(true);
      window.setTimeout(() => setCopiedLink(false), 1800);
    } catch {}
  }

  return (
    <main className="container">
      <article className="page-content detail-page">
        <div className="breadcrumb">
          <Link href="/skills"><ArrowLeft size={14} />返回技能与实验室</Link>
          <button type="button" onClick={share}><ShareNetwork size={14} />{copiedLink ? "链接已复制" : "分享"}</button>
        </div>

        <header className="article-heading">
          <div className="inline-items">
            <span className={`pill ${meta.tone}`}><Icon size={13} weight="fill" />{meta.label}</span>
            {skill.stars_count > 0 ? <span className="small-text muted"><Star size={13} weight="fill" />{skill.stars_count >= 1000 ? `${(skill.stars_count / 1000).toFixed(1)}k` : skill.stars_count} Stars</span> : null}
            {skill.repo_url ? <a href={skill.repo_url} target="_blank" rel="noreferrer" className="small-text muted"><GithubLogo size={14} />开源仓库<ArrowSquareOut size={12} /></a> : null}
          </div>
          <h1>{skill.title}</h1>
          <p>{skill.subtitle || skill.summary}</p>
          <div className="article-meta">
            {skill.author_name ? <span>作者 · {skill.author_name}</span> : null}
            <span><Eye size={14} />{skill.view_count} 次浏览</span>
            <span><Copy size={14} />{skill.copy_count} 次复制</span>
            <span>适用 · {skill.target_models?.length ? skill.target_models.join(" / ") : "多模型 / AI 工具"}</span>
          </div>
        </header>

        {skill.install_command ? (
          <section className="terminal-box" aria-label="快速开始">
            <div><span><TerminalWindow size={15} />快速开始</span><button type="button" onClick={() => copy(skill.install_command, "cmd")}><Copy size={14} />{copiedCmd ? "已复制" : "复制命令"}</button></div>
            <code>$ {skill.install_command}</code>
          </section>
        ) : null}

        {skill.prompt_template && skill.demo_type !== "pelican_arena" ? (
          <section className="prompt-box" aria-label="测试提示词">
            <div><TerminalWindow size={16} /><strong>用同一条 Prompt，开始你的测试</strong><button className="text-button" type="button" onClick={() => copy(skill.prompt_template, "prompt")}><Copy size={14} />{copiedPrompt ? "已复制" : "复制 Prompt"}</button></div>
            <p>{skill.prompt_template}</p>
          </section>
        ) : null}

        {skill.demo_type === "pelican_arena" ? <PelicanArena promptText={skill.prompt_template} skillSlug={skill.slug} /> : null}

        {skill.demo_type === "iframe" && skill.demo_url ? (
          <section className="demo-panel">
            <div className="demo-toolbar"><span><span className="status-dot" />在线效果演示</span><a href={skill.demo_url} target="_blank" rel="noreferrer" className="text-button">新窗口打开<ArrowSquareOut size={14} /></a></div>
            <div className="production-demo-frame"><DemoIframe src={skill.demo_url} title={skill.title} className="h-full w-full border-0 bg-white" /></div>
          </section>
        ) : null}

        <section className="article-body production-markdown"><MarkdownView content={skill.content_markdown} /></section>

        <div className="notice"><ShieldCheck size={19} /><div><strong>开放探索，也保留判断</strong><p>社区工具与品牌官方服务相互独立。使用前请核对项目来源，不要提交账号密码、完整 API Key 或其他敏感凭证。</p></div></div>

        {skill.related_product ? (
          <section className="guide-callout">
            <div className="callout-icon"><Sparkle size={24} /></div>
            <div><h3>找到适合这项工作的 AI 产品</h3><p>查看 {skill.related_product.display_name} 的当前公开报价、库存与交付方式。</p></div>
            <Link className="button" href={`/products/${encodeURIComponent(skill.related_product.slug)}`}>查看相关报价<ArrowRight size={16} /></Link>
          </section>
        ) : <section className="guide-callout"><div className="callout-icon"><Sparkle size={24} /></div><div><h3>找到适合这项工作的 AI 产品</h3><p>按商品与交付方式比较，不让单一低价替你做决定。</p></div><Link className="button" href="/products">查看报价目录<ArrowRight size={16} /></Link></section>}
      </article>
    </main>
  );
}
