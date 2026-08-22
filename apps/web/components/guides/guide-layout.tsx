import Link from "next/link";
import type { ReactNode } from "react";
import { CaretRight } from "@phosphor-icons/react/ssr";
import { GuideToc, type GuideTocItem } from "./guide-toc";

type Breadcrumb = {
  href?: string;
  label: string;
};

type GuideLayoutProps = {
  breadcrumbs: Breadcrumb[];
  title: string;
  description: string;
  lastReviewedAt: string;
  toc: GuideTocItem[];
  children: ReactNode;
  footer?: ReactNode;
};

export function GuideLayout({ breadcrumbs, title, description, lastReviewedAt, toc, children, footer }: GuideLayoutProps) {
  return (
    <main id="main-content" className="shell py-5 sm:py-8" data-vds-schema="v3.1" data-vds-layer="field" data-vds-action="breadcrumb-orientation review-status sticky-toc longform-evidence">
      <nav aria-label="面包屑" className="overflow-x-auto">
        <ol className="flex min-w-max items-center gap-1 text-sm text-[color:var(--muted)]">
          {breadcrumbs.map((item, index) => (
            <li key={`${item.label}-${index}`} className="flex items-center">
              {index > 0 ? <CaretRight size={14} className="mx-1 text-black/30" aria-hidden="true" /> : null}
              {item.href ? (
                <Link href={item.href} className="flex min-h-11 items-center px-1 hover:text-[color:var(--ink)] hover:underline">{item.label}</Link>
              ) : (
                <span aria-current="page" className="flex min-h-11 items-center px-1 text-[color:var(--ink)]">{item.label}</span>
              )}
            </li>
          ))}
        </ol>
      </nav>

      <header className="page-hero !pt-7" data-vds-layer="event">
        <p className="eyebrow"><span className="signal-dot" aria-hidden="true" />教程已复核</p>
        <h1 className="page-title mt-5" data-vds-role="title">{title}</h1>
        <p className="lede mt-5" data-vds-role="explanation">{description}</p>
        <p className="status-pill status-info mt-5" data-vds-role="evidence">最近复核 {lastReviewedAt}</p>
      </header>

      <div className="mt-6">
        <GuideToc items={toc} mobile />
      </div>

      <div className="mt-8 grid items-start gap-12 lg:grid-cols-[minmax(0,82ch)_260px] lg:justify-between">
        <article className="guide-article min-w-0 space-y-12" data-vds-layer="evidence">{children}</article>
        <aside><GuideToc items={toc} /></aside>
      </div>

      {footer ? <footer className="mt-14 max-w-[82ch] border-t border-[color:var(--line-strong)] pt-8">{footer}</footer> : null}
    </main>
  );
}
