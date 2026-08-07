import Link from "next/link";
import { ArrowSquareOut, Sparkle } from "@phosphor-icons/react/ssr";
import { GITHUB_REPOSITORY_URL, SUPPORT_AVAILABLE } from "@/lib/community";

const linkGroups = [
  {
    title: "比较",
    links: [["/products", "报价雷达"], ["/watchlist", "关注清单"], ["/guides", "购买指南"], ["/guides/buying-checklist", "购买前检查"]],
  },
  {
    title: "证据",
    links: [["/methodology", "数据方法"], ["/corrections", "纠错记录"], ["/developers", "开发者接口"], ["/shops/submit", "申请收录"]],
  },
  {
    title: "项目",
    links: [["/about", "关于本站"], ["/privacy", "隐私政策"], ["/terms", "使用条款"], ["/security", "安全说明"]],
  },
];

export function SiteFooter() {
  return (
    <footer className="site-footer mt-20">
      <div className="shell grid gap-12 py-12 lg:grid-cols-[1.15fr_1fr] lg:py-16">
        <div className="max-w-xl">
          <p className="eyebrow !text-[color:var(--accent)]"><Sparkle size={14} weight="fill" aria-hidden="true" />买之前，多看一眼证据</p>
          <h2 className="mt-5 text-3xl font-semibold leading-tight tracking-[-.045em] sm:text-4xl">把价格、库存和来源放在同一张桌面上。</h2>
          <p className="mt-5 text-sm leading-7 text-white/62">AI Price Radar 只聚合公开报价，不参与交易。最终购买前，请回到来源页面再次确认商品含义、交付方式、退款规则与实时库存。</p>
          <a href={GITHUB_REPOSITORY_URL} target="_blank" rel="noreferrer" className="footer-cta mt-7 inline-flex min-h-11 items-center gap-2 rounded-[12px] px-4 text-sm font-semibold">
            查看开源仓库 <ArrowSquareOut size={16} />
          </a>
        </div>
        <nav aria-label="页脚导航" className="grid grid-cols-2 gap-8 sm:grid-cols-3">
          {linkGroups.map((group) => (
            <div key={group.title}>
              <p className="text-xs font-semibold tracking-[.08em] text-white/42">{group.title}</p>
              <div className="mt-4 grid gap-3 text-sm">
                {group.links.map(([href, label]) => <Link key={href} href={href} className="text-white/70 transition-colors hover:text-white">{label}</Link>)}
                {group.title === "项目" && SUPPORT_AVAILABLE ? <a href="#support-author" className="text-white/70 transition-colors hover:text-white">支持作者</a> : null}
              </div>
            </div>
          ))}
        </nav>
      </div>
      <div className="border-t border-white/10">
        <div className="shell flex flex-col gap-2 py-5 text-[11px] text-white/42 sm:flex-row sm:items-center sm:justify-between">
          <p>AI Price Radar · 开源公开报价聚合</p>
          <p>价格、库存与可用性以来源页面实时信息为准</p>
        </div>
      </div>
    </footer>
  );
}
