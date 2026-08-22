import type { Metadata } from "next";
import { AdminPanel } from "@/components/admin-panel";
import { InfoPage } from "@/components/page-shell";

export const metadata: Metadata = { title: "管理后台", robots: { index: false, follow: false } };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function AdminPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const rawState = Array.isArray(params.state) ? params.state.at(-1) : params.state;
  return (
    <InfoPage eyebrow="内部操作" title="管理与审核" description="处理来源、分类、纠错和发布状态。管理密钥只保存在当前页面内存中，并随管理请求发送；生产环境仍应在反向代理层增加身份认证。">
      <AdminPanel previewState={rawState === "error" ? "error" : undefined} />
    </InfoPage>
  );
}
