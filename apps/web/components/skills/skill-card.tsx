"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Copy, Fire, Sparkle, Star, TerminalWindow } from "@phosphor-icons/react";
import type { CommunitySkillSummary } from "@/lib/types";
import { recordSkillCopy } from "@/lib/api";

const KIND_META: Record<string, { label: string; icon: any; tone: string }> = {
  benchmark: { label: "模型评测", icon: Fire, tone: "orange" },
  skill: { label: "实用 Skills", icon: Sparkle, tone: "purple" },
  article: { label: "技巧与博文", icon: TerminalWindow, tone: "green" },
};

export function SkillCard({ skill }: { skill: CommunitySkillSummary }) {
  const [copied, setCopied] = useState(false);
  const meta = KIND_META[skill.kind] || KIND_META.skill;
  const Icon = meta.icon;
  const payload = skill.install_command || skill.prompt_template;

  async function copy() {
    if (!payload) return;
    try {
      await navigator.clipboard.writeText(payload);
      setCopied(true);
      recordSkillCopy(skill.slug).catch(() => {});
      setTimeout(() => setCopied(false), 1800);
    } catch {}
  }

  return (
    <article className="skill-card">
      <div className="skill-card-meta"><span className={`pill ${meta.tone}`}><Icon size={12} weight="fill" />{meta.label}</span>{skill.stars_count > 0 ? <span><Star size={13} weight="fill" />{skill.stars_count >= 1000 ? `${(skill.stars_count / 1000).toFixed(1)}k` : skill.stars_count}</span> : null}</div>
      <Link className="skill-title" href={`/skills/${encodeURIComponent(skill.slug)}`}>{skill.title}</Link>
      {skill.subtitle ? <h4>{skill.subtitle}</h4> : null}
      <p>{skill.summary}</p>
      <div className="skill-tags">{skill.target_models?.slice(0, 2).map((model) => <Link key={model} href={`/skills?model=${encodeURIComponent(model)}`}>{model}</Link>)}{skill.tags?.slice(0, 4).map((tag) => <Link key={tag} href={`/skills?tag=${encodeURIComponent(tag)}`}>{tag}</Link>)}</div>
      <div className="skill-card-footer"><span><span className={`author-avatar ${meta.tone}`}>{(skill.author_name || "社")[0]}</span>{skill.author_name || "社区精选"}</span><div className="inline-items">{payload ? <button type="button" className="text-button" onClick={copy}>{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? "已复制" : "复制"}</button> : null}<Link className="text-button" href={`/skills/${encodeURIComponent(skill.slug)}`}>探索 →</Link></div></div>
    </article>
  );
}
