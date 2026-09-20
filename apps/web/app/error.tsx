"use client";

import { ArrowClockwise } from "@phosphor-icons/react";

export default function AppError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="shell py-16" role="alert">
      <div className="mx-auto max-w-xl border-y border-[color:var(--line-strong)] py-10 text-center">
        <p className="section-kicker">数据暂不可用</p>
        <h1 className="mt-3 text-2xl font-semibold">报价目录加载失败</h1>
        <p className="mt-3 text-sm leading-7 text-[color:var(--muted)]">当前快照或接口暂时不可访问，请稍后重新加载。</p>
        <button type="button" onClick={reset} className="button-primary tactile mt-6 inline-flex items-center gap-2">
          <ArrowClockwise size={17} />
          重新加载
        </button>
      </div>
    </main>
  );
}
