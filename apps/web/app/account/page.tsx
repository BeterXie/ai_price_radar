import type { Metadata } from "next";
import { InfoPage } from "@/components/page-shell";
import { AccountClient } from "@/components/account-client";

export const metadata: Metadata = {
  title: "个人中心与推送设置",
  description: "管理 PriceMemo 个人账号，绑定 QQ 机器人以接收降价和涨价变动通知。",
  alternates: { canonical: "/account" },
};

export default function AccountPage() {
  return (
    <InfoPage
      eyebrow="账号与通知"
      title="个人中心"
      description="管理您的个人账户，绑定 QQ 机器人接收 AI 服务商品价格波动与降价实时提醒。"
    >
      <AccountClient />
    </InfoPage>
  );
}
