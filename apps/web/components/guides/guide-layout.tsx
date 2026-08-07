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
    <main id="main-content" className="shell py-8 sm:py-12">
      <nav aria-label="面包屑" className="overflow-x-auto">
        <ol className="flex min-w-max items-center gap-1 text-sm text-black/55">
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

      <header className="max-w-[82ch] border-b border-black pb-8 pt-7 sm:pb-10">
        <h1 className="text-4xl font-semibold leading-[1.05] tracking-[-.055em] sm:text-5xl lg:text-6xl">{title}</h1>
        <p className="mt-5 max-w-[72ch] text-base leading-7 text-[color:var(--muted)] sm:text-lg sm:leading-8">{description}</p>
        <p className="mono mt-5 text-xs text-[color:var(--muted)]">最后核验：{lastReviewedAt}</p>
      </header>

      <div className="mt-6">
        <GuideToc items={toc} mobile />
      </div>

      <div className="mt-8 grid items-start gap-12 lg:grid-cols-[minmax(0,82ch)_240px] lg:justify-between">
        <article className="min-w-0 space-y-12">{children}</article>
        <aside><GuideToc items={toc} /></aside>
      </div>

      {footer ? <footer className="mt-14 max-w-[82ch] border-t border-black pt-8">{footer}</footer> : null}
    </main>
  );
}
