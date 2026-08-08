import type { Metadata } from "next";
import { AdminPanel } from "@/components/admin-panel";
import { InfoPage } from "@/components/page-shell";

export const metadata: Metadata = { title: "管理后台", robots: { index: false, follow: false } };

export default function AdminPage() {
  return (
    <InfoPage title="管理与审核" description="处理来源、分类、纠错和发布状态。管理密钥仅保存在当前页面内存中，并随管理请求发送；不会写入 Cookie 或 localStorage。生产环境仍应在反向代理层增加身份认证。">
      <AdminPanel />
    </InfoPage>
  );
}
