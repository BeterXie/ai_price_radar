import type { ReactNode } from "react";

export function GuideSection({ id, title, intro, children }: { id: string; title: string; intro?: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24">
      <h2 className="border-b border-[color:var(--line-strong)] pb-3 text-2xl font-semibold tracking-[-.035em] sm:text-3xl">{title}</h2>
      {intro ? <p className="mt-5 text-base leading-8 text-black/70">{intro}</p> : null}
      <div className="mt-5">{children}</div>
    </section>
  );
}
