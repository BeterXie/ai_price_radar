"use client";

import Link from "next/link";
import { WarningCircle } from "@phosphor-icons/react";

export default function ProductsError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="shell py-16">
      <section className="max-w-2xl border-y border-[color:var(--line-strong)] py-10" role="alert">
        <WarningCircle size={28} className="text-[color:var(--danger)]" aria-hidden="true" />
        <h1 className="mt-4 text-2xl font-semibold">报价服务暂时无法读取</h1>
        <p className="mt-3 text-sm leading-6 text-[color:var(--muted)]">这不是商品不存在。当前筛选条件仍保留，可以重试读取或返回商品目录。</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button type="button" onClick={reset} className="button-primary tactile">重新读取</button>
          <Link href="/products" className="button-secondary tactile">返回商品目录</Link>
        </div>
      </section>
    </main>
  );
}
