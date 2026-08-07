"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, GithubLogo, List, Sparkle, Storefront, X } from "@phosphor-icons/react";
import { PlatformIcon } from "@/components/platform-icon";

const primaryLinks = [
  { href: "/products", label: "报价雷达" },
  { href: "/guides", label: "购买指南" },
  { href: "/methodology", label: "数据方法" },
];

const brandLinks = ["OpenAI", "Claude", "Gemini", "Grok", "X"];

function current(pathname: string, href: string) {
  return href === "/" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}

export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="app-header sticky top-0 z-50">
      <div className="shell flex h-[72px] items-center justify-between gap-4">
        <Link href="/" aria-current={pathname === "/" ? "page" : undefined} className="group flex min-w-0 shrink-0 items-center gap-3">
          <span className="brand-mark"><Image src="/icon.svg" alt="" width={25} height={25} priority /></span>
          <span className="min-w-0">
            <span className="flex items-center gap-1.5 truncate font-semibold tracking-[-0.035em]">AI Price Radar <Sparkle size={13} weight="fill" className="text-[color:var(--brand)] opacity-80" /></span>
            <span className="hidden text-[10px] font-medium tracking-[.07em] text-[color:var(--muted)] sm:block">AI 订阅公开报价 · 实时比较</span>
          </span>
        </Link>

        <nav aria-label="主要导航" className="hidden items-center gap-1 rounded-[14px] border border-[color:var(--line)] bg-[color:var(--panel)]/72 p-1 shadow-[0_8px_28px_rgba(55,48,120,.05)] lg:flex">
          {primaryLinks.map((item) => (
            <Link key={item.href} href={item.href} aria-current={current(pathname, item.href) ? "page" : undefined} className="nav-link">
              {item.label}
            </Link>
          ))}
          <span className="mx-1 h-5 w-px bg-[color:var(--line)]" aria-hidden="true" />
          {brandLinks.slice(0, 4).map((brand) => (
            <Link key={brand} href={`/products?platform=${encodeURIComponent(brand)}`} className="nav-link hidden 2xl:inline-flex">
              <PlatformIcon platform={brand} size={14} />{brand}
            </Link>
          ))}
        </nav>

        <div className="flex shrink-0 items-center gap-2">
          <Link href="/watchlist" aria-current={current(pathname, "/watchlist") ? "page" : undefined} className="header-action hidden sm:inline-flex">
            <Bell size={18} />关注清单
          </Link>
          <Link href="/shops/submit" aria-current={current(pathname, "/shops/submit") ? "page" : undefined} className="header-action hidden md:inline-flex">
            <Storefront size={18} />申请收录
          </Link>
          <a href="https://github.com/BeterXie/ai_price_radar" target="_blank" rel="noreferrer" aria-label="在 GitHub 查看 AI Price Radar 开源项目" title="GitHub 开源项目" className="github-action grid h-10 w-10 shrink-0 place-items-center rounded-[11px] text-white">
            <GithubLogo size={20} weight="fill" />
          </a>

          <details className="group relative lg:hidden">
            <summary className="grid h-10 w-10 cursor-pointer list-none place-items-center rounded-[11px] border border-[color:var(--line-strong)] bg-[color:var(--panel)]/86 [&::-webkit-details-marker]:hidden" aria-label="打开站点导航">
              <List className="group-open:hidden" size={21} />
              <X className="hidden group-open:block" size={21} />
            </summary>
            <div className="mobile-nav-panel">
              <nav aria-label="移动端导航" className="grid p-2">
                {primaryLinks.map((item) => (
                  <Link key={item.href} href={item.href} aria-current={current(pathname, item.href) ? "page" : undefined} className="nav-link min-h-11">
                    {item.label}
                  </Link>
                ))}
                <Link href="/watchlist" aria-current={current(pathname, "/watchlist") ? "page" : undefined} className="nav-link min-h-11"><Bell size={17} />关注清单</Link>
                <Link href="/shops/submit" aria-current={current(pathname, "/shops/submit") ? "page" : undefined} className="nav-link min-h-11"><Storefront size={17} />申请收录</Link>
              </nav>
              <div className="border-t border-[color:var(--line)] p-3">
                <p className="px-2 text-[11px] font-semibold tracking-[.06em] text-[color:var(--muted)]">按品牌查看报价</p>
                <div className="mt-2 grid grid-cols-2 gap-1">
                  {brandLinks.map((brand) => (
                    <Link key={brand} href={`/products?platform=${encodeURIComponent(brand)}`} className="nav-link min-h-11">
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
