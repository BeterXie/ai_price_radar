import Link from "next/link";
import { ArrowSquareOut, ShieldCheck } from "@phosphor-icons/react/ssr";
import { BUSINESS_EMAIL, GITHUB_REPOSITORY_URL, SUPPORT_AVAILABLE } from "@/lib/community";

export function SiteFooter({ advertiseEnabled = false }: { advertiseEnabled?: boolean }) {
  const linkGroups = [
    {
      title: "发现与学习",
      links: [
        ["/products", "报价目录"],
        ["/skills", "技能与实验室"],
        ["/guides", "购买指南"],
        ["/watchlist", "关注清单"],
      ],
    },
    {
      title: "数据与反馈",
      links: [
        ["/methodology", "数据方法"],
        ["/shops/submit", "申请收录"],
        ["/corrections", "提交纠错"],
        ["/developers", "开发者接口"],
      ],
    },
    {
      title: advertiseEnabled ? "关于与合作" : "关于",
      links: [
        ["/about", "关于本站"],
        ...(advertiseEnabled ? [["/advertise", "商务合作"] as [string, string]] : []),
        ["/privacy", "隐私政策"],
        ["/terms", "使用条款"],
        ["/security", "安全说明"],
      ],
    },
  ];

  return (
    <footer className="site-footer mt-20">
      <div className="shell grid gap-10 py-12 lg:grid-cols-[1.4fr_1fr_1fr_1fr_1.3fr] lg:gap-8 lg:py-14">
        {/* Brand column */}
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[9px] bg-[color:var(--brand-soft)]">
              <span className="text-[color:var(--brand)] text-xs font-bold">AI</span>
            </div>
            <div>
              <span className="block text-sm font-semibold tracking-[-0.025em]">AI Price Memory</span>
              <span className="block text-[9px] tracking-[0.06em] text-[color:var(--muted)]">好选择，从信息透明开始</span>
            </div>
          </div>
          <p className="mt-4 text-xs leading-6 text-[color:var(--muted)]">
            让 AI 商品信息更透明，<br />让每一次选择更有把握。
          </p>
          <div className="mt-5 flex items-center gap-3">
            <a href={GITHUB_REPOSITORY_URL} target="_blank" rel="noreferrer" aria-label="GitHub 开源仓库" className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-[color:var(--line)] text-[color:var(--muted)] transition-colors hover:border-[color:var(--brand)] hover:text-[color:var(--brand)]">
              <ArrowSquareOut size={15} />
            </a>
            {advertiseEnabled && BUSINESS_EMAIL && (
              <a href={`mailto:${BUSINESS_EMAIL}`} className="text-xs text-[color:var(--muted)] underline underline-offset-2 hover:text-[color:var(--ink)]">{BUSINESS_EMAIL}</a>
            )}
          </div>
        </div>

        {/* Link groups */}
        {linkGroups.map((group) => (
          <div key={group.title}>
            <p className="mb-4 text-[11px] font-semibold tracking-[.07em] text-[color:var(--ink)]">{group.title}</p>
            <div className="grid gap-3 text-sm">
              {group.links.map(([href, label]) => (
                <Link key={href} href={href} className="text-[13px] text-[color:var(--muted)] transition-colors hover:text-[color:var(--ink)]">
                  {label}
                </Link>
              ))}
              {group.title.startsWith("关于") && SUPPORT_AVAILABLE ? (
                <a href="#support-author" className="text-[13px] text-[color:var(--muted)] transition-colors hover:text-[color:var(--ink)]">支持作者</a>
              ) : null}
            </div>
          </div>
        ))}

        {/* Safety notice column */}
        <div className="border-t border-[color:var(--line)] pt-6 lg:border-t-0 lg:border-l lg:pl-6 lg:pt-0">
          <ShieldCheck size={20} className="text-[color:var(--brand)]" />
          <h4 className="mt-3 text-sm font-semibold tracking-[-0.02em]">比价之后，记得核对。</h4>
          <p className="mt-2 text-[11px] leading-[1.85] text-[color:var(--muted)]">
            本站聚合公开报价，不参与交易。价格、库存、交付方式和退款规则以来源页面为准。
          </p>
          <Link href="/guides/buying-checklist" className="mt-3 inline-flex items-center gap-1 text-[11px] font-semibold text-[color:var(--brand)] hover:underline hover:underline-offset-2">
            购买前检查 →
          </Link>
        </div>
      </div>

      <div className="border-t border-[color:var(--line)]">
        <div className="shell flex flex-col gap-2 py-5 text-[11px] text-[color:var(--muted)] sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-center gap-1.5">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-[color:var(--brand)]" aria-hidden="true" />
            AI Price Memory · 让选择更有依据
          </p>
          <p>页面展示最近一次采集结果，购买前请在来源页面重新确认</p>
        </div>
      </div>
    </footer>
  );
}

