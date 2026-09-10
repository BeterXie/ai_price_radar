import type { Metadata } from "next";
import Link from "next/link";
import { Fire, MagnifyingGlass, Sparkle, SquaresFour, TerminalWindow } from "@phosphor-icons/react/ssr";
import { getSkills } from "@/lib/api";
import { SkillCard } from "@/components/skills/skill-card";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "AI 技能实验室 - 降智体检、实战 Skills 与前沿技巧分享",
  description: "全网大模型抗降智体检测试、真实产物在线对比，以及来自社区顶尖开发者的实用 Agent Skills 与前沿技巧分享。",
  alternates: { canonical: "https://ai.pricememo.cn/skills" },
  openGraph: { title: "AI 技能实验室 - 降智体检、实战 Skills 与前沿技巧分享", description: "大模型体检、真实产物在线对比，以及实用 Agent Skills 库。", url: "https://ai.pricememo.cn/skills", type: "website" },
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;
function single(params: Record<string, string | string[] | undefined>, key: string) { const value = params[key]; return Array.isArray(value) ? value.at(-1) || "" : value || ""; }

export default async function SkillsPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const kind = single(params, "kind");
  const tag = single(params, "tag");
  const model = single(params, "model");
  const q = single(params, "q");
  const query = new URLSearchParams();
  if (kind) query.set("kind", kind); if (tag) query.set("tag", tag); if (model) query.set("model", model); if (q) query.set("q", q);
  const data = await getSkills(query.toString());
  const items = data?.items || [];
  const total = data?.total || 0;
  const tags = data?.all_tags || [];

  const withParam = (key: string, value: string) => {
    const next = new URLSearchParams(query);
    if (value) next.set(key, value); else next.delete(key);
    const suffix = next.toString();
    return suffix ? `/skills?${suffix}` : "/skills";
  };

  return (
    <main id="main-content" className="container">
      <div className="page-content">
        <section className="labs-hero">
          <div>
            <span className="pill green"><Sparkle size={13} /> 为好奇心，留一间实验室</span>
            <h1>不止会用 AI，<br />更懂得<span className="green-text">用好 AI。</span></h1>
            <p>真实模型评测、精选开源 Skills、开发者实战经验。<br />少一点概念，多一点可以亲手尝试的可能。</p>
            <form action="/skills" method="get" className="search-form compact">
              {kind ? <input type="hidden" name="kind" value={kind} /> : null}{tag ? <input type="hidden" name="tag" value={tag} /> : null}
              <MagnifyingGlass size={18} /><input type="search" name="q" defaultValue={q} placeholder="搜索技能、作者或关键词…" aria-label="搜索技能、作者或关键词" /><button className="button primary" type="submit">搜索</button>
            </form>
          </div>
          <div className="labs-hero-visual" aria-hidden="true"><div className="visual-ring ring-a" /><div className="visual-ring ring-b" /><div className="visual-ring ring-c" /><div className="visual-center"><Sparkle size={58} /></div><span className="visual-chip chip-code"><TerminalWindow size={17} /> build something.</span><span className="visual-chip chip-spark"><Sparkle size={17} /> 好奇心 × 行动力</span><i className="visual-star">✦</i></div>
        </section>

        <div className="labs-toolbar"><div className="tabs"><Link className={!kind ? "active" : ""} href={withParam("kind", "")}><SquaresFour size={15} />全部 <span className="tab-count">{total}</span></Link><Link className={kind === "benchmark" ? "active" : ""} href={withParam("kind", "benchmark")}><Fire size={15} />模型评测</Link><Link className={kind === "skill" ? "active" : ""} href={withParam("kind", "skill")}><Sparkle size={15} />实用 Skills</Link><Link className={kind === "article" ? "active" : ""} href={withParam("kind", "article")}><TerminalWindow size={15} />技巧与博文</Link></div><span className="muted small-text">好内容，持续发现与整理</span></div>

        {tags.length ? <div className="hot-tags"><span>热门标签</span>{tags.slice(0, 8).map((item) => <Link className={tag === item ? "selected" : ""} key={item} href={withParam("tag", tag === item ? "" : item)}># {item}</Link>)}</div> : null}

        {items.length ? <div className="skill-grid">{items.map((skill) => <SkillCard key={skill.id} skill={skill} />)}</div> : <div className="empty"><Sparkle size={34} /><h3>还没有匹配的技能</h3><p>调整关键词或标签，再看看。</p><Link href="/skills" className="button">查看全部技能</Link></div>}
        <div className="bottom-note"><Sparkle size={16} />好工具不止于收藏。选一个，今天就试试。</div>
      </div>
    </main>
  );
}
