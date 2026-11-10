import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BRAND } from "@/lib/brands";
import { SITE_URL } from "@/lib/site";
import { getArticles } from "@/lib/site-content";
import { BrandArticleIndex } from "@/components/brand-content";

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
  return <BrandArticleIndex articles={result.items}>
    <nav className="article-pagination" aria-label="文章分页">{page > 1 && <Link href={`/articles?page=${page - 1}`}>上一页</Link>}{page * result.page_size < result.total && <Link href={`/articles?page=${page + 1}`}>下一页</Link>}</nav>
  </BrandArticleIndex>;
}
