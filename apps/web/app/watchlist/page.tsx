import type { Metadata } from "next";
import { InfoPage } from "@/components/page-shell";
import { WatchlistClient } from "@/components/watchlist-client";

export const metadata: Metadata = {
  title: "关注清单与 Atom 订阅",
  description: "在当前浏览器保存关注的 AI 商品和目标价，并生成无需注册的 Atom 订阅地址。",
  alternates: { canonical: "/watchlist" },
};

export default function WatchlistPage() {
  return (
    <InfoPage title="关注清单" description="关注内容保存在当前浏览器，本站不会主动推送通知。如需接收价格或补货更新，请将 Atom 地址添加到阅读器。">
      <WatchlistClient />
    </InfoPage>
  );
}
