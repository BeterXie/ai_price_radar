import type { Metadata } from "next";
import { AdminPanel } from "@/components/admin-panel";

export const metadata: Metadata = { title: "管理后台", robots: { index: false, follow: false } };

export default function AdminPage() {
  return (
    <main className="shell py-12">
      <header className="border-b border-black pb-10"><p className="mono text-xs uppercase tracking-[.15em] text-black/45">Private operations</p><h1 className="mt-4 text-6xl font-semibold tracking-[-.065em]">管理与审核</h1><p className="mt-5 max-w-2xl text-[color:var(--muted)]">管理密钥只保存在当前浏览器内存中，不会写入服务端。生产环境仍建议在反向代理层增加身份认证。</p></header>
      <div className="py-10"><AdminPanel /></div>
    </main>
  );
}
