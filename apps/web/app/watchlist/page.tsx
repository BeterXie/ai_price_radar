import type { Metadata } from "next";
import { WatchlistClient } from "@/components/watchlist-client";

export const metadata: Metadata = {
  title: "关注清单与价格提醒",
  description: "在浏览器本地关注 AI 商品价格和库存，并生成无需注册的 Atom 订阅地址。",
  alternates: { canonical: "/watchlist" },
};

export default function WatchlistPage() {
  return (
    <main id="main-content" className="shell py-12">
      <header className="border-b border-black pb-10">
        <p className="mono text-xs tracking-[.15em] text-black/45">Local watchlist / Atom feed</p>
        <h1 className="mt-4 text-5xl font-semibold tracking-[-.06em] sm:text-6xl">关注价格与补货</h1>
        <p className="mt-5 max-w-3xl text-base leading-7 text-[color:var(--muted)]">关注清单保存在当前浏览器，不需要注册账号。目标价用于标记是否达到条件；Atom Feed 可交给阅读器持续订阅。</p>
      </header>
      <div className="py-10"><WatchlistClient /></div>
    </main>
  );
}
