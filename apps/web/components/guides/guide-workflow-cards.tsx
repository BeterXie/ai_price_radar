import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react/ssr";
import type {
  ProductWorkflowReference,
  WorkflowGuide,
  WorkflowRelevance,
} from "@/lib/guides/types";

const RELEVANCE_LABELS: Record<WorkflowRelevance, string> = {
  recommended: "推荐",
  conditional: "条件适用",
  advanced: "高级",
};

const RELEVANCE_STYLES: Record<WorkflowRelevance, string> = {
  recommended: "bg-[color:var(--accent-ink)]/10 text-[color:var(--accent-ink)]",
  conditional: "bg-black/[.06] text-black/70",
  advanced: "bg-[#94751d]/10 text-[#7a5d16]",
};

export interface WorkflowCardEntry {
  reference: ProductWorkflowReference;
  guide: WorkflowGuide;
}

export function GuideWorkflowCards({ entries }: { entries: readonly WorkflowCardEntry[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {entries.map(({ reference, guide }) => (
        <Link
          key={guide.slug}
          href={`/guides/workflows/${guide.slug}`}
          className="tactile group flex min-h-64 flex-col justify-between rounded-[14px] border hairline bg-[color:var(--panel)] p-5 hover:border-[color:var(--brand)] focus-visible:border-[color:var(--line-strong)]"
        >
          <div className="space-y-4">
            <span className={`inline-flex min-h-7 items-center rounded-full px-3 text-xs font-semibold ${RELEVANCE_STYLES[reference.relevance]}`}>
              {RELEVANCE_LABELS[reference.relevance]}
            </span>
            <h3 className="text-lg font-semibold tracking-[-.025em]">{guide.title}</h3>
            <ol aria-label="工作流步骤" className="flex flex-wrap items-center gap-2">
              {guide.flow.map((node, index) => (
                <li key={node} className="flex flex-wrap items-center gap-2 text-sm font-medium">
                  <span className="rounded-[8px] border hairline px-2.5 py-1.5">{node}</span>
                  {index < guide.flow.length - 1 ? (
                    <ArrowRight size={15} className="text-black/40" aria-hidden="true" />
                  ) : null}
                </li>
              ))}
            </ol>
            <p className="text-sm leading-6 text-[color:var(--muted)]">适合：{reference.audience}</p>
            <p className="text-sm leading-6 text-[color:var(--muted)]">选择条件：{reference.condition}</p>
            {reference.note ? (
              <p className="rounded-[10px] bg-black/[.045] p-3 text-xs leading-5 text-black/65">{reference.note}</p>
            ) : null}
          </div>
          <span className="mt-5 flex min-h-11 items-center gap-2 text-sm font-medium">
            查看完整教程
            <ArrowRight size={17} className="transition-transform group-hover:translate-x-1" aria-hidden="true" />
          </span>
        </Link>
      ))}
    </div>
  );
}
