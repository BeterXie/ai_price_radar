import type { Metadata } from "next";
import Link from "next/link";
import { Fire, MagnifyingGlass, Sparkle, TerminalWindow } from "@phosphor-icons/react/ssr";
import { getSkills } from "@/lib/api";
import { SkillCard } from "@/components/skills/skill-card";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "AI 技能实验室 - 降智体检、实战 Skills 与前沿技巧分享",
  description: "全网大模型抗降智体检测试、6大真实产物在线对比，以及来自社区顶尖开发者的实用 Agent Skills（taste-skill, victor-design, agent-browser）与前沿技巧分享。",
  alternates: { canonical: "https://ai.pricememo.cn/skills" },
  openGraph: {
    title: "AI 技能实验室 - 降智体检、实战 Skills 与前沿技巧分享",
    description: "全网大模型抗降智体检测试、6大真实产物在线对比，以及实用 Agent Skills 库。",
    url: "https://ai.pricememo.cn/skills",
    type: "website",
  },
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function single(params: Record<string, string | string[] | undefined>, key: string): string {
  const value = params[key];
  return Array.isArray(value) ? value[value.length - 1] || "" : value || "";
}

export default async function SkillsPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const kind = single(params, "kind");
  const tag = single(params, "tag");
  const model = single(params, "model");
  const query = single(params, "q");

  const queryParams = new URLSearchParams();
  if (kind) queryParams.set("kind", kind);
  if (tag) queryParams.set("tag", tag);
  if (model) queryParams.set("model", model);
  if (query) queryParams.set("q", query);

  const skillsData = await getSkills(queryParams.toString());
  const items = skillsData?.items || [];
  const total = skillsData?.total || 0;
  const allTags = skillsData?.all_tags || [];

  const tabHref = (k: string) => {
    const next = new URLSearchParams(queryParams);
    if (k) next.set("kind", k);
    else next.delete("kind");
    const s = next.toString();
    return s ? `/skills?${s}` : "/skills";
  };

  const tagHref = (t: string) => {
    const next = new URLSearchParams(queryParams);
    if (t === tag) next.delete("tag");
    else next.set("tag", t);
    const s = next.toString();
    return s ? `/skills?${s}` : "/skills";
  };

  return (
    <main className="shell py-8">
      {/* Hero Heading */}
      <header className="rounded-3xl border border-[color:var(--line)] bg-[color:var(--panel)] p-6 sm:p-10 shadow-sm">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-[color:var(--brand-line)] bg-[color:var(--brand-soft)] px-3 py-1 text-xs font-semibold text-[color:var(--brand-strong)]">
            <Sparkle size={14} weight="fill" />
            AI 实验专区 · 持续精选输出
          </div>
          <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-[color:var(--foreground)] sm:text-4xl">
            AI 技能与降智体检实验室
          </h1>
          <p className="mt-2.5 text-sm sm:text-base text-[color:var(--muted)] leading-relaxed">
            汇聚大模型抗降智实测跑分（鹈鹕骑车等零测试 2D 动效对比）、社区顶流开源 Agent Skills（审美规范、Figma 交付、自动化浏览器）、以及资深工程师实战技巧持续输出。
          </p>
        </div>

        {/* Search Input Form */}
        <form action="/skills" method="GET" className="mt-6 flex max-w-lg items-center gap-2">
          {kind ? <input type="hidden" name="kind" value={kind} /> : null}
          {tag ? <input type="hidden" name="tag" value={tag} /> : null}
          <div className="relative flex-1">
            <MagnifyingGlass size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[color:var(--muted)]" />
            <input
              type="text"
              name="q"
              defaultValue={query}
              placeholder="搜索技能名称、作者、Prompt 或关键字..."
              className="w-full rounded-xl border border-[color:var(--line)] bg-[color:var(--card)] py-2.5 pl-10 pr-4 text-xs sm:text-sm text-[color:var(--foreground)] placeholder-[color:var(--muted)] transition focus:border-[color:var(--brand)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand)]"
            />
          </div>
          <button
            type="submit"
            className="shrink-0 rounded-xl bg-[color:var(--foreground)] px-4 py-2.5 text-xs sm:text-sm font-semibold text-[color:var(--panel)] transition hover:opacity-90 active:scale-95"
          >
            搜索
          </button>
        </form>
      </header>

      {/* Kind Navigation Tabs */}
      <div className="mt-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[color:var(--line)] pb-4">
        <div className="flex flex-wrap gap-2">
          <Link
            href={tabHref("")}
            className={`inline-flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs sm:text-sm font-semibold transition ${
              !kind
                ? "border-[color:var(--foreground)] bg-[color:var(--foreground)] text-[color:var(--panel)] shadow-sm"
                : "border-[color:var(--line)] bg-[color:var(--panel)] text-[color:var(--muted)] hover:border-[color:var(--line-strong)] hover:text-[color:var(--foreground)]"
            }`}
          >
            全部 ({total})
          </Link>

          <Link
            href={tabHref("benchmark")}
            className={`inline-flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs sm:text-sm font-semibold transition ${
              kind === "benchmark"
                ? "border-rose-600 bg-rose-600 text-white shadow-sm"
                : "border-[color:var(--line)] bg-[color:var(--panel)] text-[color:var(--muted)] hover:border-rose-500/50 hover:text-rose-600"
            }`}
          >
            <Fire size={14} weight="fill" />
            🔥 降智检测
          </Link>

          <Link
            href={tabHref("skill")}
            className={`inline-flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs sm:text-sm font-semibold transition ${
              kind === "skill"
                ? "border-purple-600 bg-purple-600 text-white shadow-sm"
                : "border-[color:var(--line)] bg-[color:var(--panel)] text-[color:var(--muted)] hover:border-purple-500/50 hover:text-purple-600"
            }`}
          >
            <Sparkle size={14} weight="fill" />
            🎨 实用 Skills
          </Link>

          <Link
            href={tabHref("article")}
            className={`inline-flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs sm:text-sm font-semibold transition ${
              kind === "article"
                ? "border-emerald-600 bg-emerald-600 text-white shadow-sm"
                : "border-[color:var(--line)] bg-[color:var(--panel)] text-[color:var(--muted)] hover:border-emerald-500/50 hover:text-emerald-600"
            }`}
          >
            <TerminalWindow size={14} weight="fill" />
            ✍️ 技巧与博文
          </Link>
        </div>

        {/* Quick Tag Pills */}
        {allTags.length > 0 ? (
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-[color:var(--muted)] mr-1">热门标签:</span>
            {allTags.slice(0, 6).map((t) => {
              const isSelected = t === tag;
              return (
                <Link
                  key={t}
                  href={tagHref(t)}
                  className={`rounded-lg px-2 py-1 transition ${
                    isSelected
                      ? "bg-[color:var(--brand-soft)] font-bold text-[color:var(--brand-strong)]"
                      : "bg-[color:var(--hover)] text-[color:var(--muted)] hover:text-[color:var(--foreground)]"
                  }`}
                >
                  #{t}
                </Link>
              );
            })}
          </div>
        ) : null}
      </div>

      {/* Skills Grid */}
      {items.length > 0 ? (
        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((skill) => (
            <SkillCard key={skill.id} skill={skill} />
          ))}
        </div>
      ) : (
        <div className="mt-16 text-center py-12 rounded-2xl border border-dashed border-[color:var(--line)] bg-[color:var(--panel)]">
          <p className="text-sm text-[color:var(--muted)]">未找到匹配的技能或体检测试项</p>
          <Link href="/skills" className="mt-3 inline-block text-xs font-semibold text-[color:var(--brand-strong)] underline underline-offset-2">
            查看全部技能
          </Link>
        </div>
      )}
    </main>
  );
}
