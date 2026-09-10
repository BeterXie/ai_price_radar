import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft, BookOpenText, ShieldCheck } from "@phosphor-icons/react/ssr";
import { GuideToc, type GuideTocItem } from "./guide-toc";

type Breadcrumb = { href?: string; label: string };
type GuideLayoutProps = { breadcrumbs: Breadcrumb[]; title: string; description: string; lastReviewedAt: string; toc: GuideTocItem[]; children: ReactNode; footer?: ReactNode };

export function GuideLayout({ breadcrumbs, title, description, lastReviewedAt, toc, children, footer }: GuideLayoutProps) {
  const category = breadcrumbs[breadcrumbs.length - 1]?.label || "购买指南";
  return (
    <main id="main-content" className="container" data-vds-schema="v3.1">
      <div className="page-content detail-page">
        <nav className="breadcrumb" aria-label="面包屑">
          <Link href="/guides"><ArrowLeft size={14} />返回购买指南</Link>
          <span>{category}</span>
        </nav>
        <header className="article-heading">
          <span className="pill green"><BookOpenText size={13} />{category}</span>
          <h1>{title}</h1>
          <p>{description}</p>
          <div className="article-meta"><span>最近复核 · {lastReviewedAt}</span><span>以品牌官方页面和实际商品说明为准</span></div>
        </header>
        <div className="production-mobile-toc"><GuideToc items={toc} mobile /></div>
        <div className="reading-layout">
          <article className="article-body guide-article">{children}</article>
          <aside className="article-toc">
            <GuideToc items={toc} />
            <div><ShieldCheck size={24} /><strong>多一次核对，<br />少一分不确定。</strong><p>保护隐私，保留凭证。</p></div>
          </aside>
        </div>
        {footer ? <footer className="production-guide-footer">{footer}</footer> : null}
      </div>
    </main>
  );
}
