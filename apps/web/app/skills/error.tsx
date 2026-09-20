"use client";

import Link from "next/link";
import { WarningCircle } from "@phosphor-icons/react";

export default function SkillsError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="shell py-16">
      <section className="max-w-2xl border-y border-[color:var(--line-strong)] py-10" role="alert">
        <WarningCircle size={28} className="text-[color:var(--danger)]" aria-hidden="true" />
        <h1 className="mt-4 text-2xl font-semibold">技能列表暂时无法读取</h1>
        <p className="mt-3 text-sm leading-6 text-[color:var(--muted)]">服务暂时不可用，不代表当前筛选没有结果。</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button type="button" onClick={reset} className="button-primary tactile">重新读取</button>
          <Link href="/skills" className="button-secondary tactile">返回技能首页</Link>
        </div>
      </section>
    </main>
  );
}
