import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { InfoPage } from "@/components/page-shell";
import { getTotalPages, PaginationNav, parsePage } from "@/components/pagination-nav";
import { getCorrections } from "@/lib/api";
import { exactTime } from "@/lib/format";
import type { PublicCorrectionPage } from "@/lib/types";
import { ReportForm } from "@/components/report-form";

export const dynamic = "force-dynamic";
const PAGE_SIZE = 25;
type SearchParams = Promise<{ page?: string }>;

export async function generateMetadata({ searchParams }: { searchParams: SearchParams }): Promise<Metadata> {
  const page = parsePage((await searchParams).page, PAGE_SIZE);
  return {
    title: "公开纠错记录",
    description: "查看已解决并允许公开的报价纠错摘要与商家回应。",
    alternates: { canonical: page > 1 ? `/corrections?page=${page}` : "/corrections" },
  };
}
const kinds: Record<string, string> = { correction: "信息更正", unavailable: "无法购买", fraud_concern: "风险疑问", shop_request: "收录申请", other: "其他" };

export default async function CorrectionsPage({ searchParams }: { searchParams: SearchParams }) {
  const page = parsePage((await searchParams).page, PAGE_SIZE);
  let data: PublicCorrectionPage | null = null;
  let loadFailed = false;
  try { data = await getCorrections(`limit=${PAGE_SIZE}&offset=${(page - 1) * PAGE_SIZE}`); } catch { loadFailed = true; }
  const totalPages = getTotalPages(data?.total || 0, PAGE_SIZE);
  if (data && page > totalPages) redirect(totalPages > 1 ? `/corrections?page=${totalPages}` : "/corrections");
  return (
    <InfoPage eyebrow="数据与反馈" title="公开纠错记录" description="这里只显示已处理并允许公开的摘要。联系方式、私密描述和内部审核记录不会出现在本页。">
      {loadFailed ? <div className="empty-state" role="alert"><p>纠错记录暂时无法加载。</p><a href="/corrections" className="button-primary mt-6">重新加载</a></div> : !data?.items.length ? <div className="empty-state" role="status">暂无公开纠错记录。</div> : (
        <div className="divide-y divide-[color:var(--line)] border-y border-[color:var(--line-strong)]">
          {data.items.map((item) => <article key={item.id} className="grid gap-4 py-7 md:grid-cols-[180px_1fr]"><div><p className="mono text-xs font-semibold text-[color:var(--info)]">#{item.id} · {kinds[item.kind] || item.kind}</p><p className="mt-2 text-xs text-[color:var(--muted)]">处理于 {exactTime(item.resolved_at)}</p></div><div><h2 className="text-lg font-semibold">{item.public_summary}</h2>{item.merchant_response && <div className="surface-subtle mt-4 p-4"><p className="text-xs font-semibold text-[color:var(--muted)]">商家公开回应</p><p className="mt-2 whitespace-pre-line text-sm leading-6 text-[color:var(--muted)]">{item.merchant_response}</p></div>}</div></article>)}
        </div>
      )}
      {data ? (
        <PaginationNav
          page={page}
          totalPages={totalPages}
          hrefForPage={(nextPage) => nextPage > 1 ? `/corrections?page=${nextPage}` : "/corrections"}
          ariaLabel="公开纠错记录分页"
        />
      ) : null}
      <section className="mt-12 max-w-2xl border-t border-[color:var(--line-strong)] pt-8">
        <h3 className="mb-4 text-base font-semibold text-[color:var(--ink)]">提交新的纠错或反馈</h3>
        <ReportForm />
      </section>
    </InfoPage>
  );
}
