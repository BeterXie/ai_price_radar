import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getArticle } from "@/lib/site-content";
import { BRAND } from "@/lib/brands";
import { SITE_URL } from "@/lib/site";
import { MarkdownView } from "@/components/skills/markdown-view";
import { JsonLd } from "@/components/structured-data";
import { BrandArticleFrame } from "@/components/brand-content";

export const dynamic = "force-dynamic";
type Props = { params: Promise<{ slug: string }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const article = await getArticle((await params).slug);
  if (!article) notFound();
  const url = `${SITE_URL}/articles/${article.slug}`;
  return { title: article.seo_title || article.title, description: article.seo_description || article.summary,
    alternates: { canonical: url }, openGraph: { type: "article", title: article.title, description: article.summary, url, siteName: BRAND.name,
      publishedTime: article.published_at || undefined, modifiedTime: article.updated_at } };
}
export default async function ArticlePage({ params }: Props) {
  const article = await getArticle((await params).slug);
  if (!article) notFound();
  return <BrandArticleFrame article={article}><article>
    <Link href="/articles" className="text-action">← 全部文章</Link>
    <header><p className="article-meta">{article.category}{article.published_at ? ` · ${article.published_at.slice(0, 10)}` : ""}</p><h1>{article.title}</h1>
      {article.summary && <p className="article-summary">{article.summary}</p>}{article.author && <p className="article-meta">{article.author}</p>}</header>
    <div className="article-body"><MarkdownView content={article.markdown || ""} /></div>
    <JsonLd data={{ "@context": "https://schema.org", "@type": "Article", headline: article.title, description: article.summary,
      mainEntityOfPage: `${SITE_URL}/articles/${article.slug}`, datePublished: article.published_at, dateModified: article.updated_at,
      ...(article.author ? { author: { "@type": "Person", name: article.author } } : {}),
      publisher: { "@type": "Organization", name: BRAND.name, url: SITE_URL } }} />
  </article></BrandArticleFrame>;
}
