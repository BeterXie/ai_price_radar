import type { ReactNode } from "react";

type GuideIndexProps = {
  id?: string;
  title: string;
  description?: string;
  children: ReactNode;
  empty?: boolean;
};

export function GuideIndex({ id, title, description, children, empty = false }: GuideIndexProps) {
  return (
    <section id={id} className="scroll-mt-24 border-t border-[color:var(--line-strong)] py-10 sm:py-12">
      <div className="guide-index-heading max-w-3xl">
        <h2 className="text-3xl font-semibold tracking-[-.045em]">{title}</h2>
        {description ? <p className="mt-3 text-sm leading-6 text-[color:var(--muted)]">{description}</p> : null}
      </div>
      {empty ? (
        <div className="empty-state mt-6 !p-6 text-sm">
          没有符合当前条件的教程。可以清空筛选后再试。
        </div>
      ) : (
        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{children}</div>
      )}
    </section>
  );
}
