import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowRight, BookOpen, Plugs } from "@phosphor-icons/react/ssr";
import { BRAND, IS_PRIMARY_SITE, SITE_ID } from "@/lib/brands";
import type { Article } from "@/lib/site-content";

const articleCopy = {
  pricememo: ["文章", "AI 使用与订阅"],
  aiprice: ["观察与记录", "关于订阅、工具与价格的进一步阅读。"],
  aisi: ["慢慢读，\n慢慢找到答案。", "工具如何走进日常，订阅如何做出选择。"],
  pricein: ["订阅功课，买前做。", "从使用需求到购买细节，多了解一点再决定。"],
  openprice: ["文章档案", "按发布时间记录本站文章，开放查阅。"],
}[SITE_ID];

export function BrandArticleIndex({ articles, children }: { articles: Article[]; children: ReactNode }) {
  if (IS_PRIMARY_SITE) return <main className="shell article-index">
    <header className="article-index-heading"><h1>文章</h1><p>{BRAND.name} · AI 使用与订阅</p></header>
    {articles.length ? <div className="article-grid">{articles.map(article => <article key={article.id}>
      <p className="article-meta">{article.category || "文章"}{article.published_at ? ` · ${article.published_at.slice(0, 10)}` : ""}</p>
      <h2><Link href={`/articles/${article.slug}`}>{article.title}</Link></h2><p>{article.summary}</p>
      <Link className="text-action" href={`/articles/${article.slug}`}>阅读全文 <span aria-hidden="true">↗</span></Link>
    </article>)}</div> : <div className="empty-state"><p>文章正在准备中。</p><Link href="/products" className="text-action">先看看当前报价 →</Link></div>}
    {children}
  </main>;
  const items = articles.length ? <div className="article-grid">{articles.map((article, i) => <article key={article.id}><span className="article-number">{String(i + 1).padStart(2, "0")}</span><p className="article-meta">{article.category || "文章"}{article.published_at ? ` · ${article.published_at.slice(0, 10)}` : ""}</p><h2><Link href={`/articles/${article.slug}`}>{article.title}</Link></h2><p>{article.summary}</p><Link className="text-action" href={`/articles/${article.slug}`}>阅读全文 <ArrowRight size={16} /></Link></article>)}</div> : <section className="brand-content-empty"><BookOpen size={36} /><div><h2>文章正在准备中</h2><p>新的使用心得与订阅观察，发布后会在这里出现。</p><Link href="/products">先看看当前报价 <ArrowRight size={17} /></Link></div></section>;
  return <main className="shell article-index"><header className="article-index-heading"><p className="brand-eyebrow">{SITE_ID === "aisi" ? "THE JOURNAL / 阅读" : SITE_ID === "aiprice" ? "RESEARCH LOG / 文章" : SITE_ID === "openprice" ? "03 / ARTICLE ARCHIVE" : "READ BEFORE YOU BUY"}</p><h1>{articleCopy[0]}</h1><p>{articleCopy[1]}</p></header><div className="article-index-layout">{SITE_ID === "aiprice" || SITE_ID === "openprice" ? <aside className="article-index-aside"><span>{BRAND.name}</span><h2>文章目录</h2><p>本站独立发布的文章。</p><Link href="/products">报价目录 ↗</Link><Link href="/methodology">数据说明 ↗</Link></aside> : null}<div>{items}{children}</div></div></main>;
}

export function BrandArticleFrame({ article, children }: { article: Article; children: ReactNode }) {
  if (IS_PRIMARY_SITE) return <main className="shell article-page">{children}</main>;
  return <main className="shell article-page"><div className="article-reading-layout">{!IS_PRIMARY_SITE && SITE_ID !== "aisi" && <aside className="article-reading-aside"><Link href="/articles">← 文章目录</Link><p className="brand-eyebrow">{SITE_ID === "aiprice" ? "RESEARCH NOTE" : SITE_ID === "pricein" ? "购买前的阅读" : "DOCUMENT / 文章"}</p><p>{article.category || "文章"}</p>{article.author && <p>{article.author}</p>}<time>{article.published_at?.slice(0, 10)}</time><Link href="/products">对照当前报价 ↗</Link></aside>}{children}</div>{SITE_ID === "aisi" && <nav className="editorial-reading-end" aria-label="继续阅读"><BookOpen size={28} /><p>读完之后，再看看你的选择。</p><Link href="/products">翻开订阅目录 →</Link><Link href="/articles">返回全部文章 →</Link></nav>}</main>;
}

export function BrandRelayFrame({ count, children }: { count: number | null; children: ReactNode }) {
  if (IS_PRIMARY_SITE) return <>{children}</>;
  const title = SITE_ID === "aiprice" ? "API 中转站观察台" : SITE_ID === "aisi" ? "连接工具的另一种方式。" : SITE_ID === "pricein" ? "选一个合适的 API 中转站" : "中转站目录";
  const note = <aside className="brand-relay-note"><Plugs size={32} /><h2>{SITE_ID === "aisi" ? "认识它，再使用它。" : "如何查看这份目录"}</h2><p>查看公开服务信息、模型分组与检测记录。收录不构成推荐或担保。</p><dl><div><dt>收录站点</dt><dd>{count === null ? "暂不可用" : count}</dd></div><div><dt>比较依据</dt><dd>站点资料与检测记录</dd></div></dl><Link href="/products?comparable=false&delivery_type=relay_api">查看中转类商品 →</Link></aside>;
  return <><header className="brand-relay-heading"><p className="brand-eyebrow">{SITE_ID === "openprice" ? "02 / RELAY DIRECTORY" : SITE_ID === "aiprice" ? "NETWORK / API RELAYS" : "API 中转站目录"}</p><h1>{title}</h1><p>了解来源、计费与可用情况，再决定如何接入。</p></header><div className="brand-relay-layout">{note}<div className="brand-relay-content">{children}</div></div></>;
}
