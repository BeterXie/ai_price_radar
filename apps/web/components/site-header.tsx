"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRef } from "react";
import { ArrowRight, Bell, GithubLogo, List, Storefront, X } from "@phosphor-icons/react";
import { PlatformIcon } from "@/components/platform-icon";

const primaryLinks = [
  { href: "/products", label: "报价目录" },
  { href: "/skills", label: "技能与实验室", fresh: true },
  { href: "/guides", label: "购买指南" },
  { href: "/methodology", label: "数据方法" },
];

const brandLinks = ["OpenAI", "Claude", "Gemini", "Grok", "X"];

function current(pathname: string, href: string) {
  return href === "/" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}

export function SiteHeader({ advertiseEnabled = false }: { advertiseEnabled?: boolean }) {
  const pathname = usePathname();
  const menuRef = useRef<HTMLDetailsElement>(null);
  const closeMenu = () => {
    if (menuRef.current) menuRef.current.open = false;
  };

  return (
    <>
      <header className="site-header">
        <div className="header-inner">
          <Link href="/" className="logo group" aria-label="AI Price Memory 首页">
            <span className="logo-symbol">
              <Image src="/brand/logo-icon.png" alt="" width={38} height={38} priority className="relative z-[1] h-[31px] w-[31px] object-contain" />
            </span>
            <span>
              <strong>AI Price Memory<span className="logo-period">.</span></strong>
              <small>好选择，从信息透明开始</small>
            </span>
          </Link>

          <nav className="main-nav" aria-label="主要导航">
            {primaryLinks.map((item) => (
              <Link key={item.href} href={item.href} aria-current={current(pathname, item.href) ? "page" : undefined}>
                {item.label}{item.fresh ? <span className="nav-new-dot" aria-hidden="true" /> : null}
              </Link>
            ))}
          </nav>

          <div className="header-actions">
            <Link href="/watchlist" className="watch-button" aria-current={current(pathname, "/watchlist") ? "page" : undefined}>
              <Bell size={17} /><span>关注清单</span>
            </Link>
            <Link href="/shops/submit" className="button primary small-button" aria-current={current(pathname, "/shops/submit") ? "page" : undefined}>
              <Storefront size={15} /><span>申请收录</span>
            </Link>
            <a className="icon-button github-button" href="https://github.com/BeterXie/ai_price_radar" target="_blank" rel="noreferrer" aria-label="GitHub 开源项目">
              <GithubLogo size={19} weight="fill" />
            </a>

            <details ref={menuRef} className="group relative lg:hidden">
              <summary className="icon-button mobile-menu flex cursor-pointer list-none [&::-webkit-details-marker]:hidden" aria-label="切换导航">
                <List className="group-open:hidden" size={21} />
                <X className="hidden group-open:block" size={21} />
              </summary>
              <div className="mobile-nav-panel">
                {primaryLinks.map((item) => (
                  <Link key={item.href} href={item.href} onClick={closeMenu} aria-current={current(pathname, item.href) ? "page" : undefined}>{item.label}</Link>
                ))}
                <Link href="/watchlist" onClick={closeMenu} aria-current={current(pathname, "/watchlist") ? "page" : undefined}><Bell size={16} />关注清单</Link>
                <Link href="/shops/submit" onClick={closeMenu} aria-current={current(pathname, "/shops/submit") ? "page" : undefined}><Storefront size={16} />申请收录</Link>
                {advertiseEnabled ? <Link href="/advertise" onClick={closeMenu}>商务合作</Link> : null}
                <div className="mt-1 border-t border-[color:var(--line)] pt-2">
                  {brandLinks.map((brand) => (
                    <Link key={brand} href={`/products?brand=${encodeURIComponent(brand)}`} onClick={closeMenu}><PlatformIcon platform={brand} size={14} />{brand}</Link>
                  ))}
                </div>
              </div>
            </details>
          </div>
        </div>
      </header>

      {pathname === "/" ? (
        <div className="announcement">
          <span className="announcement-tag">新发现</span>
          <span>从比价格，到比能力。AI 技能与实验室现已上线</span>
          <Link href="/skills">去探索 <ArrowRight size={13} /></Link>
        </div>
      ) : null}
    </>
  );
}
