import type { Metadata } from "next";
import { InfoPage } from "@/components/page-shell";
import { WatchlistClient } from "@/components/watchlist-client";

export const metadata: Metadata = {
  title: "关注清单与 Atom 订阅",
  description: "在当前浏览器保存关注的 AI 商品和目标价，并生成无需注册的 Atom 订阅地址。",
  alternates: { canonical: "/watchlist" },
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function WatchlistPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const rawState = Array.isArray(params.state) ? params.state.at(-1) : params.state;
  const previewState = rawState === "empty" || rawState === "loading" || rawState === "error" ? rawState : undefined;
  return (
    <InfoPage eyebrow="当前浏览器" title="关注清单" description="保存关注商品和目标价，并生成可添加到阅读器的 Atom 地址。关注内容只保存在当前浏览器。">
      <WatchlistClient previewState={previewState} />
    </InfoPage>
  );
}
