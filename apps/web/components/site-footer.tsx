import Link from "next/link";
import { GITHUB_REPOSITORY_URL, SUPPORT_AVAILABLE } from "@/lib/community";

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-[color:var(--line)] bg-[color:var(--ink)] text-white">
      <div className="shell grid gap-10 py-12 md:grid-cols-[1.4fr_.6fr]">
        <div>
          <p className="mono text-xs tracking-[.18em] text-[color:var(--accent)]">购买前再确认</p>
          <h2 className="mt-4 max-w-2xl text-3xl font-semibold tracking-[-.04em]">价格和库存可能变化，下单前请到商品原页面确认。</h2>
        </div>
        <div className="text-sm leading-7 text-white/60">
          <p>本站仅聚合公开可访问的价格、库存、商品标题和来源链接，不参与交易、收款、交付或售后。</p>
          <div className="mt-4 grid grid-cols-2 gap-x-5 gap-y-2 text-white">
            <Link href="/products">报价目录</Link><Link href="/watchlist">关注清单</Link>
            <Link href="/guides">教程中心</Link><Link href="/guides/buying-checklist">购买前检查</Link>
            <Link href="/guides/security">账号安全</Link><Link href="/methodology">数据方法</Link>
            <Link href="/corrections">纠错记录</Link><Link href="/developers">开发者</Link>
            <Link href="/shops/submit">申请收录</Link><Link href="/about">关于本站</Link>
            <Link href="/privacy">隐私政策</Link><Link href="/terms">使用条款</Link>
            <Link href="/security">安全说明</Link>
            <a href={GITHUB_REPOSITORY_URL} target="_blank" rel="noreferrer">GitHub 点 Star</a>
            {SUPPORT_AVAILABLE && <a href="#support-author">支持作者</a>}
          </div>
        </div>
      </div>
    </footer>
  );
}
