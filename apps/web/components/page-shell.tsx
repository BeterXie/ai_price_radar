import type { ReactNode } from "react";

type PageHeroProps = {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  aside?: ReactNode;
  compact?: boolean;
};

export function PageHero({ eyebrow, title, description, meta, actions, aside, compact = false }: PageHeroProps) {
  return (
    <header className={`page-hero ${aside ? "grid items-end gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(280px,.42fr)]" : ""}`}>
      <div className={compact ? "max-w-4xl" : "max-w-5xl"}>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1 className={`${compact ? "page-title" : "display-title"} ${eyebrow ? "mt-4" : ""}`}>{title}</h1>
        {description ? <div className="lede mt-6">{description}</div> : null}
        {meta ? <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-[color:var(--muted)]">{meta}</div> : null}
        {actions ? <div className="mt-7 flex flex-wrap gap-3">{actions}</div> : null}
      </div>
      {aside ? <aside>{aside}</aside> : null}
    </header>
  );
}

export function SectionIntro({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: ReactNode; action?: ReactNode }) {
  return (
    <div className="section-intro flex flex-col justify-between gap-5 pb-5 md:flex-row md:items-end">
      <div className="max-w-3xl">
        {eyebrow ? <p className="section-kicker">{eyebrow}</p> : null}
        <h2 className={`${eyebrow ? "mt-3" : ""} section-title`}>{title}</h2>
        {description ? <div className="mt-3 text-sm leading-6 text-[color:var(--muted)]">{description}</div> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function InfoPage({
  eyebrow,
  title,
  description,
  meta,
  children,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  meta?: ReactNode;
  children: ReactNode;
}) {
  return (
    <main id="main-content" className="shell">
      <PageHero eyebrow={eyebrow} title={title} description={description} meta={meta} compact />
      <div className="content-stage py-10 sm:py-14">{children}</div>
    </main>
  );
}
