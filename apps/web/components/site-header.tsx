"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRef } from "react";
import { Bell, GithubLogo, List, Storefront, Tag, X } from "@phosphor-icons/react";
import { PlatformIcon } from "@/components/platform-icon";

const primaryLinks = [
  { href: "/products", label: "报价目录" },
  { href: "/skills", label: "技能与实验室" },
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
    <header className="app-header sticky top-0 z-50">
      <div className="shell flex h-[68px] items-center justify-between gap-3">
        <Link href="/" aria-current={pathname === "/" ? "page" : undefined} className="group flex min-w-0 shrink-0 items-center py-1">
          <Image
            src="/brand/logo.png"
            alt="AI Price Radar · AI 订阅比价"
            width={133}
            height={42}
            priority
            className="h-10 w-auto object-contain transition-opacity group-hover:opacity-90"
          />
        </Link>

        <nav aria-label="主要导航" className="hidden items-center gap-1 rounded-[14px] border border-[color:var(--line)] bg-[color:var(--panel)]/72 p-1 shadow-[0_8px_28px_rgba(18,19,15,.05)] lg:flex">
          {primaryLinks.map((item) => (
            <Link key={item.href} href={item.href} aria-current={current(pathname, item.href) ? "page" : undefined} className="nav-link inline-flex">
              {item.label}
            </Link>
          ))}
          <span className="mx-1 h-5 w-px bg-[color:var(--line)]" aria-hidden="true" />
          {brandLinks.slice(0, 4).map((brand) => (
            <Link key={brand} href={`/products?platform=${encodeURIComponent(brand)}`} className="nav-link brand-nav-link">
              <PlatformIcon platform={brand} size={14} />{brand}
            </Link>
          ))}
        </nav>

        <div className="flex shrink-0 items-center gap-2">
          <Link href="/watchlist" aria-current={current(pathname, "/watchlist") ? "page" : undefined} className="header-action header-action-watch">
            <Bell size={18} />关注清单
          </Link>
          <Link href="/shops/submit" aria-current={current(pathname, "/shops/submit") ? "page" : undefined} className="header-action header-action-submit">
            <Storefront size={18} />申请收录
          </Link>
          <a href="https://github.com/BeterXie/ai_price_radar" target="_blank" rel="noreferrer" aria-label="在 GitHub 查看 AI Price Radar 开源项目" title="GitHub 开源项目" className="github-action grid h-10 w-10 shrink-0 place-items-center rounded-[11px] text-white">
            <GithubLogo size={20} weight="fill" />
          </a>

          <details ref={menuRef} className="group relative lg:hidden">
            <summary className="grid h-10 w-10 cursor-pointer list-none place-items-center rounded-[11px] border border-[color:var(--line-strong)] bg-[color:var(--panel)]/86 [&::-webkit-details-marker]:hidden" aria-label="打开站点导航">
              <List className="group-open:hidden" size={21} />
              <X className="hidden group-open:block" size={21} />
            </summary>
            <div className="mobile-nav-panel">
              <nav aria-label="移动端导航" className="grid p-2">
                {primaryLinks.map((item) => (
                  <Link key={item.href} href={item.href} onClick={closeMenu} aria-current={current(pathname, item.href) ? "page" : undefined} className="nav-link flex min-h-11">
                    {item.label}
                  </Link>
                ))}
                <Link href="/watchlist" onClick={closeMenu} aria-current={current(pathname, "/watchlist") ? "page" : undefined} className="nav-link flex min-h-11"><Bell size={17} />关注清单</Link>
                <Link href="/shops/submit" onClick={closeMenu} aria-current={current(pathname, "/shops/submit") ? "page" : undefined} className="nav-link flex min-h-11"><Storefront size={17} />申请收录</Link>
                {advertiseEnabled ? (
                  <Link href="/advertise" onClick={closeMenu} aria-current={current(pathname, "/advertise") ? "page" : undefined} className="nav-link flex min-h-11"><Tag size={17} />商务合作</Link>
                ) : null}
              </nav>
              <div className="border-t border-[color:var(--line)] p-3">
                <p className="px-2 text-[11px] font-semibold tracking-[.06em] text-[color:var(--muted)]">按品牌查看报价</p>
                <div className="mt-2 grid grid-cols-2 gap-1">
                  {brandLinks.map((brand) => (
                    <Link key={brand} href={`/products?platform=${encodeURIComponent(brand)}`} onClick={closeMenu} className="nav-link flex min-h-11">
                      <PlatformIcon platform={brand} size={15} />{brand}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </details>
        </div>
      </div>
    </header>
  );
}
