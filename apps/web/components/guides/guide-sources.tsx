import { ArrowSquareOut } from "@phosphor-icons/react/ssr";
import type { OfficialSource } from "@/lib/guides/types";

export function GuideSources({ sources }: { sources: readonly OfficialSource[] }) {
  return (
    <ul className="grid gap-3">
      {sources.map((source) => (
        <li key={source.url}>
          <a href={source.url} target="_blank" rel="noreferrer" className="group grid min-h-14 gap-1 rounded-[12px] border hairline bg-[color:var(--panel)] p-4 hover:border-[color:var(--brand)] sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
            <span>
              <span className="font-semibold group-hover:underline">{source.title}</span>
              <span className="mt-1 block text-xs text-[color:var(--muted)]">
                {source.kind === "project_official" ? "项目官方" : "平台官方"} · {source.publisher}，核验于 {source.lastCheckedAt}
              </span>
            </span>
            <ArrowSquareOut size={19} className="hidden sm:block" aria-hidden="true" />
          </a>
        </li>
      ))}
    </ul>
  );
}
