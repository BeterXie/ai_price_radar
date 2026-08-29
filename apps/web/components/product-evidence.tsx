import type { ProductEvidenceSource } from "@/lib/product-seo";

export function ProductEvidence({ sources }: { sources: readonly ProductEvidenceSource[] }) {
  if (!sources.length) return null;

  return (
    <details className="mt-6 border-t hairline pt-5" data-seo-evidence="product-sources">
      <summary className="cursor-pointer text-sm font-semibold">
        验证依据 · {sources.length} 个外部来源
      </summary>
      <p className="mt-3 max-w-4xl text-xs leading-6 text-[color:var(--muted)]">
        这些页面用于核对套餐边界、官方使用说明或价格参考；第三方报价仍以原始商品页为准。
      </p>
      <ul className="mt-3 grid gap-2 text-sm">
        {sources.map((source) => (
          <li key={source.url}>
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-[color:var(--brand-strong)] hover:underline"
            >
              {source.title}
            </a>
            <span className="ml-2 text-xs text-[color:var(--muted)]">
              {source.publisher} · 查阅于 {source.lastCheckedAt}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}
