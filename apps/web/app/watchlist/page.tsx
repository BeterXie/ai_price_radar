import type { Metadata } from "next";
import { InfoPage } from "@/components/page-shell";
import { WatchlistClient } from "@/components/watchlist-client";

export const metadata: Metadata = {
  title: "关注清单与降价提醒",
  description: "云端持久化监控关注的 AI 商品和目标价，支持通过已绑定的邮箱与 QQ / 微信 机器人实时接收降价通知。",
  alternates: { canonical: "/watchlist" },
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function WatchlistPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const rawState = Array.isArray(params.state) ? params.state.at(-1) : params.state;
  const previewState = rawState === "empty" || rawState === "loading" || rawState === "error" ? rawState : undefined;
  return (
    <InfoPage
      eyebrow="价格监控与提醒"
      title="关注清单与降价提醒"
      description="监控重点商品价格走势与现货库存。支持设定目标预期价，并在达到降价条件时通过已绑定的邮箱或 QQ / 微信 机器人私聊接收实时推送。"
    >
      <WatchlistClient previewState={previewState} />
    </InfoPage>
  );
}

