import type { Metadata } from "next";
import { InfoPage } from "@/components/page-shell";
import { getCorrections } from "@/lib/api";
import { exactTime } from "@/lib/format";
import type { PublicCorrectionPage } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "公开纠错记录", description: "查看已解决并允许公开的报价纠错摘要与商家回应。", alternates: { canonical: "/corrections" } };
const kinds: Record<string, string> = { correction: "信息更正", unavailable: "无法购买", fraud_concern: "风险疑问", shop_request: "收录申请", other: "其他" };

export default async function CorrectionsPage() {
  let data: PublicCorrectionPage | null = null;
  let loadFailed = false;
  try { data = await getCorrections("limit=100"); } catch { loadFailed = true; }
  return (
    <InfoPage eyebrow="数据与反馈" title="公开纠错记录" description="这里只显示已处理并允许公开的摘要。联系方式、私密描述和内部审核记录不会出现在本页。">
      {loadFailed ? <div className="empty-state" role="alert"><p>纠错记录暂时无法加载。</p><a href="/corrections" className="button-primary mt-6">重新加载</a></div> : !data?.items.length ? <div className="empty-state" role="status">暂无公开纠错记录。</div> : (
        <div className="divide-y divide-[color:var(--line)] border-y border-[color:var(--line-strong)]">
          {data.items.map((item) => <article key={item.id} className="grid gap-4 py-7 md:grid-cols-[180px_1fr]"><div><p className="mono text-xs font-semibold text-[color:var(--info)]">#{item.id} · {kinds[item.kind] || item.kind}</p><p className="mt-2 text-xs text-[color:var(--muted)]">处理于 {exactTime(item.resolved_at)}</p></div><div><h2 className="text-lg font-semibold">{item.public_summary}</h2>{item.merchant_response && <div className="surface-subtle mt-4 p-4"><p className="text-xs font-semibold text-[color:var(--muted)]">商家公开回应</p><p className="mt-2 whitespace-pre-line text-sm leading-6 text-[color:var(--muted)]">{item.merchant_response}</p></div>}</div></article>)}
        </div>
      )}
    </InfoPage>
  );
}
