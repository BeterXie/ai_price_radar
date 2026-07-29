import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-[color:var(--line)] bg-[color:var(--ink)] text-white">
      <div className="shell grid gap-10 py-12 md:grid-cols-[1.4fr_.6fr]">
        <div>
          <p className="mono text-xs tracking-[.18em] text-[color:var(--accent)]">核验优先，而非推广</p>
          <h2 className="mt-4 max-w-2xl text-3xl font-semibold tracking-[-.04em]">价格是线索，不是担保。购买前回到原站核验。</h2>
        </div>
        <div className="text-sm leading-7 text-white/60">
          <p>本站仅聚合公开可访问的价格、库存、商品标题和来源链接，不参与交易、收款、交付或售后。</p>
          <div className="mt-4 grid grid-cols-2 gap-x-5 gap-y-2 text-white">
            <Link href="/products">报价目录</Link><Link href="/watchlist">关注清单</Link>
            <Link href="/methodology">数据方法</Link><Link href="/corrections">纠错记录</Link>
            <Link href="/developers">开发者</Link><Link href="/shops/submit">申请收录</Link>
            <Link href="/about">关于本站</Link><Link href="/privacy">隐私政策</Link>
            <Link href="/terms">使用条款</Link><Link href="/security">安全说明</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
