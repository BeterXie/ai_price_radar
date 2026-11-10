import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BRAND } from "@/lib/brands";
import { SITE_URL } from "@/lib/site";
import { getArticles } from "@/lib/site-content";

export const dynamic = "force-dynamic";
type Props = { searchParams: Promise<{ page?: string }> };
function pageNumber(raw?: string) { return raw && /^[1-9]\d{0,5}$/.test(raw) ? Number(raw) : 1; }
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const page = pageNumber((await searchParams).page);
  return { title: "文章", description: `${BRAND.name} 的 AI 使用与订阅文章。`, alternates: { canonical: `${SITE_URL}/articles${page > 1 ? `?page=${page}` : ""}` } };
}
export default async function ArticlesPage({ searchParams }: Props) {
  const page = pageNumber((await searchParams).page);
  const result = await getArticles(page);
  if (page > 1 && !result.items.length) notFound();
  return <main className="shell article-index">
    <header className="article-index-heading"><h1>文章</h1><p>{BRAND.name} · AI 使用与订阅</p></header>
    {result.items.length ? <div className="article-grid">{result.items.map(article => <article key={article.id}>
      <p className="article-meta">{article.category || "文章"}{article.published_at ? ` · ${article.published_at.slice(0, 10)}` : ""}</p>
      <h2><Link href={`/articles/${article.slug}`}>{article.title}</Link></h2><p>{article.summary}</p>
      <Link className="text-action" href={`/articles/${article.slug}`}>阅读全文 <span aria-hidden="true">↗</span></Link>
    </article>)}</div> : <div className="empty-state"><p>文章正在准备中。</p><Link href="/products" className="text-action">先看看当前报价 →</Link></div>}
    <nav className="article-pagination" aria-label="文章分页">{page > 1 && <Link href={`/articles?page=${page - 1}`}>上一页</Link>}{page * result.page_size < result.total && <Link href={`/articles?page=${page + 1}`}>下一页</Link>}</nav>
  </main>;
}
