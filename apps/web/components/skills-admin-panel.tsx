"use client";

import { useEffect, useState } from "react";
import {
  ArrowClockwise,
  ArrowSquareOut,
  Check,
  Eye,
  EyeSlash,
  Fire,
  PencilSimple,
  Plus,
  Sparkle,
  Star,
  TerminalWindow,
  Trash,
  X,
} from "@phosphor-icons/react";
import type { AdminCommunitySkillCreate, AdminCommunitySkillUpdate, CommunitySkillSummary } from "@/lib/types";

export function SkillsAdminPanel({
  apiBase,
  headers,
}: {
  apiBase: string;
  headers: Record<string, string>;
}) {
  const [skills, setSkills] = useState<CommunitySkillSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selectedKind, setSelectedKind] = useState<string>("");
  const [searchTerm, setSearchTerm] = useState<string>("");

  // Modal / Form state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingSkill, setEditingSkill] = useState<CommunitySkillSummary | null>(null);
  const [formSaving, setFormSaving] = useState(false);
  const [formError, setFormError] = useState("");

  // Form fields
  const [formSlug, setFormSlug] = useState("");
  const [formKind, setFormKind] = useState("skill");
  const [formTitle, setFormTitle] = useState("");
  const [formSubtitle, setFormSubtitle] = useState("");
  const [formSummary, setFormSummary] = useState("");
  const [formContent, setFormContent] = useState("");
  const [formPrompt, setFormPrompt] = useState("");
  const [formAuthorName, setFormAuthorName] = useState("");
  const [formAuthorUrl, setFormAuthorUrl] = useState("");
  const [formRepoUrl, setFormRepoUrl] = useState("");
  const [formStars, setFormStars] = useState(0);
  const [formInstallCmd, setFormInstallCmd] = useState("");
  const [formDemoUrl, setFormDemoUrl] = useState("");
  const [formDemoType, setFormDemoType] = useState("none");
  const [formTags, setFormTags] = useState("");
  const [formModels, setFormModels] = useState("");
  const [formRelatedSlug, setFormRelatedSlug] = useState("");
  const [formPinned, setFormPinned] = useState(false);
  const [formVisible, setFormVisible] = useState(true);
  const [formSortOrder, setFormSortOrder] = useState(0);

  const fetchSkills = async () => {
    setLoading(true);
    try {
      const q = new URLSearchParams();
      if (selectedKind) q.set("kind", selectedKind);
      if (searchTerm) q.set("q", searchTerm);
      const res = await fetch(`${apiBase}/api/v1/admin/skills?${q.toString()}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setSkills(data.items || []);
        setTotal(data.total || 0);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSkills();
  }, [selectedKind]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchSkills();
  };

  const openCreateModal = () => {
    setEditingSkill(null);
    setFormSlug("");
    setFormKind("skill");
    setFormTitle("");
    setFormSubtitle("");
    setFormSummary("");
    setFormContent("");
    setFormPrompt("");
    setFormAuthorName("");
    setFormAuthorUrl("");
    setFormRepoUrl("");
    setFormStars(0);
    setFormInstallCmd("");
    setFormDemoUrl("");
    setFormDemoType("none");
    setFormTags("");
    setFormModels("");
    setFormRelatedSlug("");
    setFormPinned(false);
    setFormVisible(true);
    setFormSortOrder(0);
    setFormError("");
    setIsModalOpen(true);
  };

  const openEditModal = async (skill: CommunitySkillSummary) => {
    setEditingSkill(skill);
    setFormSlug(skill.slug);
    setFormKind(skill.kind);
    setFormTitle(skill.title);
    setFormSubtitle(skill.subtitle || "");
    setFormSummary(skill.summary || "");
    setFormAuthorName(skill.author_name || "");
    setFormAuthorUrl(skill.author_url || "");
    setFormRepoUrl(skill.repo_url || "");
    setFormStars(skill.stars_count || 0);
    setFormInstallCmd(skill.install_command || "");
    setFormDemoUrl(skill.demo_url || "");
    setFormDemoType(skill.demo_type || "none");
    setFormTags((skill.tags || []).join(", "));
    setFormModels((skill.target_models || []).join(", "));
    setFormRelatedSlug(skill.related_product_slug || "");
    setFormPinned(skill.is_pinned);
    setFormVisible(skill.is_visible);
    setFormSortOrder(skill.sort_order || 0);
    setFormError("");

    // Fetch full detail for markdown & prompt
    try {
      const res = await fetch(`${apiBase}/api/v1/skills/${encodeURIComponent(skill.slug)}`);
      if (res.ok) {
        const detail = await res.json();
        setFormContent(detail.content_markdown || "");
        setFormPrompt(detail.prompt_template || "");
      }
    } catch {}

    setIsModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormSaving(true);
    setFormError("");

    const tagsArray = formTags
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean);
    const modelsArray = formModels
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean);

    const payload: AdminCommunitySkillCreate = {
      slug: formSlug.trim(),
      kind: formKind,
      title: formTitle.trim(),
      subtitle: formSubtitle.trim(),
      summary: formSummary.trim(),
      content_markdown: formContent,
      prompt_template: formPrompt,
      author_name: formAuthorName.trim(),
      author_url: formAuthorUrl.trim(),
      repo_url: formRepoUrl.trim(),
      stars_count: Number(formStars) || 0,
      install_command: formInstallCmd.trim(),
      demo_url: formDemoUrl.trim(),
      demo_type: formDemoType,
      tags: tagsArray,
      target_models: modelsArray,
      related_product_slug: formRelatedSlug.trim() || null,
      is_pinned: formPinned,
      is_visible: formVisible,
      sort_order: Number(formSortOrder) || 0,
    };

    try {
      let res;
      if (editingSkill) {
        res = await fetch(`${apiBase}/api/v1/admin/skills/${editingSkill.id}`, {
          method: "PUT",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } else {
        res = await fetch(`${apiBase}/api/v1/admin/skills`, {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "保存失败，请检查字段输入");
      }

      setIsModalOpen(false);
      fetchSkills();
    } catch (err: any) {
      setFormError(err.message || "请求失败");
    } finally {
      setFormSaving(false);
    }
  };

  const handleToggleVisibility = async (skill: CommunitySkillSummary) => {
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/skills/${skill.id}/visibility`, {
        method: "PATCH",
        headers,
      });
      if (res.ok) {
        fetchSkills();
      }
    } catch {}
  };

  const handleDelete = async (skill: CommunitySkillSummary) => {
    if (!window.confirm(`确定要彻底删除技能/博文【${skill.title}】吗？`)) return;
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/skills/${skill.id}`, {
        method: "DELETE",
        headers,
      });
      if (res.ok) {
        fetchSkills();
      }
    } catch {}
  };

  return (
    <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
      {/* Table Header */}
      <div className="flex flex-col gap-4 border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-[color:var(--foreground)]">技能、体检与博文管理 (CMS)</span>
            <span className="rounded-full bg-[color:var(--brand-soft)] px-2 py-0.5 text-xs font-bold text-[color:var(--brand-strong)]">
              共 {total} 条
            </span>
          </div>
          <p className="mt-1 text-xs text-[color:var(--muted)]">
            发布、编辑大模型抗降智测试、实战 Agent 技能与技术博文，持续输出优质内容。
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={fetchSkills}
            disabled={loading}
            className="tactile inline-flex items-center gap-1 rounded-[10px] border hairline bg-[color:var(--panel)] px-3 py-2 text-xs font-medium text-[color:var(--foreground)] hover:bg-[color:var(--hover)]"
          >
            <ArrowClockwise size={14} className={loading ? "animate-spin" : ""} />
            <span>刷新</span>
          </button>

          <button
            type="button"
            onClick={openCreateModal}
            className="tactile inline-flex items-center gap-1 rounded-[10px] bg-[color:var(--foreground)] px-3.5 py-2 text-xs font-semibold text-[color:var(--panel)] hover:opacity-90 active:scale-95"
          >
            <Plus size={14} weight="bold" />
            <span>新建内容</span>
          </button>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--line)] bg-[color:var(--panel)] px-5 py-3 text-xs">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setSelectedKind("")}
            className={`rounded-lg px-2.5 py-1 font-medium transition ${
              !selectedKind ? "bg-[color:var(--foreground)] text-[color:var(--panel)]" : "text-[color:var(--muted)] hover:text-[color:var(--foreground)]"
            }`}
          >
            全部类型
          </button>
          <button
            type="button"
            onClick={() => setSelectedKind("benchmark")}
            className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 font-medium transition ${
              selectedKind === "benchmark" ? "bg-rose-600 text-white" : "text-[color:var(--muted)] hover:text-rose-600"
            }`}
          >
            <Fire size={12} weight="fill" />
            降智检测
          </button>
          <button
            type="button"
            onClick={() => setSelectedKind("skill")}
            className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 font-medium transition ${
              selectedKind === "skill" ? "bg-purple-600 text-white" : "text-[color:var(--muted)] hover:text-purple-600"
            }`}
          >
            <Sparkle size={12} weight="fill" />
            实用技能
          </button>
          <button
            type="button"
            onClick={() => setSelectedKind("article")}
            className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 font-medium transition ${
              selectedKind === "article" ? "bg-emerald-600 text-white" : "text-[color:var(--muted)] hover:text-emerald-600"
            }`}
          >
            <TerminalWindow size={12} weight="fill" />
            经验博文
          </button>
        </div>

        <form onSubmit={handleSearch} className="flex items-center gap-1.5">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="搜索标题或作者..."
            className="w-44 rounded-lg border hairline bg-[color:var(--card)] px-2.5 py-1 text-xs text-[color:var(--foreground)] placeholder-[color:var(--muted)] focus:outline-none"
          />
          <button
            type="submit"
            className="rounded-lg bg-[color:var(--hover)] px-2.5 py-1 font-medium text-[color:var(--foreground)]"
          >
            搜索
          </button>
        </form>
      </div>

      {/* Content Table */}
      <div className="divide-y divide-[color:var(--line)]">
        {skills.map((skill) => (
          <div key={skill.id} className="flex flex-col gap-3 px-5 py-3.5 text-xs sm:flex-row sm:items-center sm:justify-between hover:bg-[color:var(--hover)]/40 transition">
            <div className="space-y-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[color:var(--muted)]">#{skill.id}</span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                    skill.kind === "benchmark"
                      ? "bg-rose-500/10 text-rose-600"
                      : skill.kind === "skill"
                      ? "bg-purple-500/10 text-purple-600"
                      : "bg-emerald-500/10 text-emerald-600"
                  }`}
                >
                  {skill.kind === "benchmark" ? "降智体检" : skill.kind === "skill" ? "实用技能" : "经验博文"}
                </span>

                {skill.is_pinned ? (
                  <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-bold text-amber-600">
                    置顶
                  </span>
                ) : null}

                {!skill.is_visible ? (
                  <span className="rounded bg-neutral-500/10 px-1.5 py-0.5 text-[10px] font-bold text-neutral-500">
                    已隐藏
                  </span>
                ) : null}

                <strong className="text-sm font-semibold text-[color:var(--foreground)] truncate">
                  {skill.title}
                </strong>
              </div>

              <div className="flex flex-wrap items-center gap-3 text-[color:var(--muted)]">
                <span className="font-mono text-[11px]">slug: {skill.slug}</span>
                {skill.author_name ? <span>作者: {skill.author_name}</span> : null}
                {skill.stars_count > 0 ? (
                  <span className="inline-flex items-center gap-0.5 text-amber-600">
                    <Star size={11} weight="fill" />
                    {skill.stars_count}
                  </span>
                ) : null}
                <span>👀 {skill.view_count}</span>
                <span>📋 {skill.copy_count}</span>
                {skill.related_product_slug ? (
                  <span className="rounded bg-[color:var(--brand-soft)] px-1 py-0.2 text-[10px] text-[color:var(--brand-strong)] font-medium">
                    关联商品: {skill.related_product_slug}
                  </span>
                ) : null}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-1.5 shrink-0 self-end sm:self-center">
              <a
                href={`/skills/${encodeURIComponent(skill.slug)}`}
                target="_blank"
                rel="noreferrer"
                title="前台预览"
                className="tactile rounded-lg border hairline p-1.5 text-[color:var(--muted)] hover:text-[color:var(--foreground)]"
              >
                <ArrowSquareOut size={14} />
              </a>

              <button
                type="button"
                onClick={() => handleToggleVisibility(skill)}
                title={skill.is_visible ? "点击隐藏" : "点击公开"}
                className="tactile rounded-lg border hairline p-1.5 text-[color:var(--muted)] hover:text-[color:var(--foreground)]"
              >
                {skill.is_visible ? <Eye size={14} /> : <EyeSlash size={14} className="text-neutral-400" />}
              </button>

              <button
                type="button"
                onClick={() => openEditModal(skill)}
                title="编辑内容"
                className="tactile rounded-lg border hairline p-1.5 text-[color:var(--muted)] hover:text-[color:var(--foreground)]"
              >
                <PencilSimple size={14} />
              </button>

              <button
                type="button"
                onClick={() => handleDelete(skill)}
                title="删除"
                className="tactile rounded-lg border hairline p-1.5 text-rose-500 hover:bg-rose-500/10"
              >
                <Trash size={14} />
              </button>
            </div>
          </div>
        ))}

        {skills.length === 0 && !loading ? (
          <div className="py-8 text-center text-xs text-[color:var(--muted)]">暂无内容，点击右上角“新建内容”添加</div>
        ) : null}
      </div>

      {/* Modal Dialog */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs overflow-y-auto">
          <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[color:var(--line)] pb-4">
              <h3 className="text-base font-bold text-[color:var(--foreground)]">
                {editingSkill ? `编辑内容 #${editingSkill.id}` : "新建技能 / 体检 / 博文"}
              </h3>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="rounded-lg p-1 text-[color:var(--muted)] hover:text-[color:var(--foreground)]"
              >
                <X size={18} />
              </button>
            </div>

            {formError ? (
              <div className="mt-4 rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-600">
                {formError}
              </div>
            ) : null}

            <form onSubmit={handleSave} className="mt-4 space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-[color:var(--foreground)]">
                    内容类型 <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={formKind}
                    onChange={(e) => setFormKind(e.target.value)}
                    className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                  >
                    <option value="skill">🎨 实用技能 (Skill)</option>
                    <option value="benchmark">🔥 降智体检 (Benchmark)</option>
                    <option value="article">✍️ 经验博文 (Article)</option>
                  </select>
                </div>

                <div>
                  <label className="font-semibold text-[color:var(--foreground)]">
                    URL Slug <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formSlug}
                    onChange={(e) => setFormSlug(e.target.value)}
                    placeholder="如 pelican-benchmark"
                    className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold text-[color:var(--foreground)]">
                  标题 <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  placeholder="如 taste-skill: Anti-Slop 前端审美规范"
                  className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                />
              </div>

              <div>
                <label className="font-semibold text-[color:var(--foreground)]">副标题 / 一句话标语</label>
                <input
                  type="text"
                  value={formSubtitle}
                  onChange={(e) => setFormSubtitle(e.target.value)}
                  placeholder="如 专治 AI 前端粗制滥造与烂俗审美"
                  className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                />
              </div>

              <div>
                <label className="font-semibold text-[color:var(--foreground)]">卡片摘要 (Summary)</label>
                <textarea
                  rows={2}
                  value={formSummary}
                  onChange={(e) => setFormSummary(e.target.value)}
                  placeholder="简要介绍核心亮点和用途..."
                  className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="font-semibold text-[color:var(--foreground)]">作者名称</label>
                  <input
                    type="text"
                    value={formAuthorName}
                    onChange={(e) => setFormAuthorName(e.target.value)}
                    placeholder="如 Leonxlnx"
                    className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                  />
                </div>
                <div>
                  <label className="font-semibold text-[color:var(--foreground)]">GitHub 仓库地址</label>
                  <input
                    type="text"
                    value={formRepoUrl}
                    onChange={(e) => setFormRepoUrl(e.target.value)}
                    placeholder="https://github.com/..."
                    className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                  />
                </div>
                <div>
                  <label className="font-semibold text-[color:var(--foreground)]">GitHub Stars 数</label>
                  <input
                    type="number"
                    value={formStars}
                    onChange={(e) => setFormStars(Number(e.target.value))}
                    className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-[color:var(--foreground)]">一键安装命令 (CLI)</label>
                  <input
                    type="text"
                    value={formInstallCmd}
                    onChange={(e) => setFormInstallCmd(e.target.value)}
                    placeholder="如 npx skills add https://..."
                    className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 font-mono text-[color:var(--foreground)]"
                  />
                </div>
                <div>
                  <label className="font-semibold text-[color:var(--foreground)]">测试 Prompt (提示词咒语)</label>
                  <input
                    type="text"
                    value={formPrompt}
                    onChange={(e) => setFormPrompt(e.target.value)}
                    placeholder="如 创建一个HTML，内容是SVG绘制..."
                    className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-[color:var(--foreground)]">演示类型 (Demo Type)</label>
                  <select
                    value={formDemoType}
                    onChange={(e) => setFormDemoType(e.target.value)}
                    className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                  >
                    <option value="none">无演示</option>
                    <option value="pelican_arena">多模型对比竞技场 (Pelican Arena)</option>
                    <option value="iframe">单文件 Iframe 演示</option>
                  </select>
                </div>
                <div>
                  <label className="font-semibold text-[color:var(--foreground)]">演示路径 (Demo URL)</label>
                  <input
                    type="text"
                    value={formDemoUrl}
                    onChange={(e) => setFormDemoUrl(e.target.value)}
                    placeholder="/demos/benchmarks/pelican-gpt6-astra-full.html"
                    className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="font-semibold text-[color:var(--foreground)]">标签 (英文/中文逗号分隔)</label>
                  <input
                    type="text"
                    value={formTags}
                    onChange={(e) => setFormTags(e.target.value)}
                    placeholder="UI 审美, 前端, Codex"
                    className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                  />
                </div>
                <div>
                  <label className="font-semibold text-[color:var(--foreground)]">适用模型 (逗号分隔)</label>
                  <input
                    type="text"
                    value={formModels}
                    onChange={(e) => setFormModels(e.target.value)}
                    placeholder="GPT-6 Astra, Claude 4.5 Sonnet, Gemini 3.8, Codex++"
                    className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                  />
                </div>
                <div>
                  <label className="font-semibold text-[color:var(--foreground)]">关联比价商品 Slug</label>
                  <input
                    type="text"
                    value={formRelatedSlug}
                    onChange={(e) => setFormRelatedSlug(e.target.value)}
                    placeholder="如 chatgpt-plus, claude-pro"
                    className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-2 text-[color:var(--foreground)]"
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold text-[color:var(--foreground)]">详细 Markdown 正文</label>
                <textarea
                  rows={8}
                  value={formContent}
                  onChange={(e) => setFormContent(e.target.value)}
                  placeholder="# 标题\n\n正文使用 Markdown 格式编写..."
                  className="mt-1 w-full rounded-lg border hairline bg-[color:var(--card)] p-3 font-mono text-[color:var(--foreground)] leading-relaxed"
                />
              </div>

              <div className="flex flex-wrap items-center gap-6 pt-2">
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formPinned}
                    onChange={(e) => setFormPinned(e.target.checked)}
                    className="rounded border hairline"
                  />
                  <span className="font-semibold text-[color:var(--foreground)]">置顶显示</span>
                </label>

                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formVisible}
                    onChange={(e) => setFormVisible(e.target.checked)}
                    className="rounded border hairline"
                  />
                  <span className="font-semibold text-[color:var(--foreground)]">公开发布</span>
                </label>

                <div className="inline-flex items-center gap-2">
                  <span className="font-semibold text-[color:var(--foreground)]">排序权重:</span>
                  <input
                    type="number"
                    value={formSortOrder}
                    onChange={(e) => setFormSortOrder(Number(e.target.value))}
                    className="w-20 rounded border hairline bg-[color:var(--card)] p-1 text-center"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 border-t border-[color:var(--line)] pt-4">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="rounded-xl border hairline px-4 py-2 font-medium text-[color:var(--muted)] hover:bg-[color:var(--hover)]"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={formSaving}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-[color:var(--foreground)] px-5 py-2 font-bold text-[color:var(--panel)] hover:opacity-90 active:scale-95 disabled:opacity-50"
                >
                  {formSaving ? <ArrowClockwise size={14} className="animate-spin" /> : <Check size={14} />}
                  <span>{formSaving ? "保存中..." : "保存发布"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}
