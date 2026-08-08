import Link from "next/link";
import { ArrowSquareOut } from "@phosphor-icons/react/ssr";
import { GITHUB_REPOSITORY_URL, SUPPORT_AVAILABLE } from "@/lib/community";

const linkGroups = [
  {
    title: "浏览",
    links: [["/products", "报价目录"], ["/watchlist", "关注清单"], ["/guides", "购买指南"], ["/guides/buying-checklist", "购买前检查"]],
  },
  {
    title: "数据与反馈",
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
          <h2 className="text-2xl font-semibold leading-tight tracking-[-.035em] sm:text-3xl">购买前请核对来源页面</h2>
          <p className="mt-4 text-sm leading-7 text-[color:var(--muted)]">本站聚合公开报价，不参与交易。价格、库存、交付方式和退款规则以来源页面为准。</p>
          <a href={GITHUB_REPOSITORY_URL} target="_blank" rel="noreferrer" className="footer-cta mt-7 inline-flex min-h-11 items-center gap-2 rounded-[12px] px-4 text-sm font-semibold">
            查看开源仓库 <ArrowSquareOut size={16} />
          </a>
        </div>
        <nav aria-label="页脚导航" className="grid grid-cols-2 gap-8 sm:grid-cols-3">
          {linkGroups.map((group) => (
            <div key={group.title}>
              <p className="text-xs font-semibold tracking-[.08em] text-[color:var(--muted)]">{group.title}</p>
              <div className="mt-4 grid gap-3 text-sm">
                {group.links.map(([href, label]) => <Link key={href} href={href} className="text-[color:var(--muted)] transition-colors hover:text-[color:var(--ink)]">{label}</Link>)}
                {group.title === "项目" && SUPPORT_AVAILABLE ? <a href="#support-author" className="text-[color:var(--muted)] transition-colors hover:text-[color:var(--ink)]">支持作者</a> : null}
              </div>
            </div>
          ))}
        </nav>
      </div>
      <div className="border-t border-[color:var(--line)]">
        <div className="shell flex flex-col gap-2 py-5 text-[11px] text-[color:var(--muted)] sm:flex-row sm:items-center sm:justify-between">
          <p>AI Price Radar 开源项目</p>
          <p>页面展示最近一次采集结果，购买前请在来源页面重新确认</p>
        </div>
      </div>
    </footer>
  );
}
