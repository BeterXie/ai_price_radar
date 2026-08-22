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
    <header className={`page-hero ${aside ? "grid items-end gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(280px,.42fr)]" : ""}`} data-vds-layer="event">
      <div className={compact ? "max-w-4xl" : "max-w-5xl"}>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1 className={`${compact ? "page-title" : "display-title"} ${eyebrow ? "mt-4" : ""}`} data-vds-role="title">{title}</h1>
        {description ? <div className="lede mt-6" data-vds-role="explanation">{description}</div> : null}
        {meta ? <div className="page-meta mt-5" data-vds-role="evidence">{meta}</div> : null}
        {actions ? <div className="mt-7 flex flex-wrap gap-3" data-vds-role="action">{actions}</div> : null}
      </div>
      {aside ? <aside data-vds-layer="evidence">{aside}</aside> : null}
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
    <main id="main-content" className="shell" data-vds-schema="v3.1" data-vds-layer="field" data-vds-action="page-orientation factual-sequence responsive-reading closing-path">
      <PageHero eyebrow={eyebrow} title={title} description={description} meta={meta} compact />
      <div className="content-stage py-10 sm:py-14">{children}</div>
    </main>
  );
}

export function FactLedger({ items }: { items: readonly (readonly [string, ReactNode])[] }) {
  return (
    <div className="fact-ledger" data-vds-layer="evidence">
      {items.map(([title, copy]) => (
        <section key={title} className="fact-ledger-row">
          <h2>{title}</h2>
          <div>{copy}</div>
        </section>
      ))}
    </div>
  );
}
