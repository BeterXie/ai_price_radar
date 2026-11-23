"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";
import {
  ArrowRight, ArrowsDownUp, Bell, BookOpen, CaretDown, ChartLineDown,
  Flask, GithubLogo, List, Plugs, Storefront, X,
} from "@phosphor-icons/react";
import { alertView } from "@/lib/alert-report";
import { BRAND } from "@/lib/brands";
import { GITHUB_REPOSITORY_URL } from "@/lib/community";
import { ThemeToggle } from "@/components/theme-toggle";

export function DirectoryHeader({ account, relayHubEnabled, advertiseEnabled, children }: {
  account: ReactNode;
  relayHubEnabled: boolean;
  advertiseEnabled: boolean;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const query = useSearchParams();
  const menu = useRef<HTMLDetailsElement>(null);
  const closeMenu = () => { if (menu.current) menu.current.open = false; };
  useEffect(closeMenu, [pathname, query]);

  let current = pathname;
  if (pathname === "/alerts") current = `/alerts?view=${alertView(query.get("view"))}`;
  else if (pathname === "/products" && (query.get("brand") || query.get("platform")) === "中转站") current = "/relays";
  else if (pathname.startsWith("/brands/") || pathname.startsWith("/offers/")) current = "/products";

  const mainLinks = [
    { href: "/products", label: "报价目录", icon: ArrowsDownUp },
    ...(relayHubEnabled ? [{ href: "/relays", label: "中转站", icon: Plugs }] : []),
    { href: "/skills", label: "技能与实验室", icon: Flask },
  ];
  const alertLinks = [
    { href: "/alerts?view=team", label: "Team 车提醒", icon: Bell },
    { href: "/alerts?view=drops", label: "降价榜", icon: ChartLineDown },
  ];
  const utilityLinks = [
    { href: "/compare", label: "模型对比" },
    { href: "/guides", label: "购买指南" },
    { href: "/methodology", label: "数据方法" },
    ...(advertiseEnabled ? [{ href: "/advertise", label: "商务合作" }] : []),
  ];
  const isCurrent = (href: string) => current === href || current.startsWith(href + "/");
  function navLink({ href, label, icon: Icon }: typeof mainLinks[number]) {
    return <Link key={href} href={href} prefetch={false} aria-current={isCurrent(href) ? "page" : undefined}>
      <Icon size={18} aria-hidden="true" /><span>{label}</span>
    </Link>;
  }
  const navigation = <>
    <nav className="directory-main-links" aria-label="主要导航" onClick={closeMenu}>{mainLinks.map(navLink)}</nav>
    <nav className="directory-alert-links" aria-label="报价动态" onClick={closeMenu}>{alertLinks.map(navLink)}</nav>
    <Link href="/shops/submit" className="directory-submit" onClick={closeMenu} aria-current={isCurrent("/shops/submit") ? "page" : undefined}>
      <Storefront size={18} aria-hidden="true" />申请收录<ArrowRight size={15} aria-hidden="true" />
    </Link>
    <details key={pathname} className="directory-guides" open={utilityLinks.some(({ href }) => isCurrent(href))}
      onKeyDown={(event) => {
        if (event.key !== "Escape" || !event.currentTarget.open) return;
        event.stopPropagation();
        event.currentTarget.open = false;
        event.currentTarget.querySelector("summary")?.focus();
      }}>
      <summary><BookOpen size={17} aria-hidden="true" />指南与工具<CaretDown size={14} aria-hidden="true" /></summary>
      <nav aria-label="指南与工具" onClick={closeMenu}>
        {utilityLinks.map(({ href, label }) => (
          <Link key={href} href={href} prefetch={false} aria-current={isCurrent(href) ? "page" : undefined}>{label}</Link>
        ))}
      </nav>
    </details>
  </>;

  return <>
    <header className="directory-header">
      <Link href="/" className="directory-logo" aria-label={BRAND.name + " 首页"}>
        <Image src="/brand/logo-icon.png" alt="" width={32} height={32} unoptimized />
        <span>{BRAND.wordmark}</span>
      </Link>
      <div className="directory-desktop-nav">{navigation}</div>
      <div className="directory-account">
        {account}
        <a href={GITHUB_REPOSITORY_URL || "https://github.com/BeterXie/ai_price_radar"} target="_blank" rel="noreferrer" aria-label="GitHub 开源项目"><GithubLogo size={19} aria-hidden="true" /></a>
      </div>
      <ThemeToggle />
      <details className="directory-mobile-menu" ref={menu} onKeyDown={(event) => {
        if (event.key === "Escape" && menu.current?.open) {
          closeMenu();
          menu.current.querySelector("summary")?.focus();
        }
      }}>
        <summary aria-label="站点导航"><List size={22} /><X size={22} /></summary>
        <div>{navigation}</div>
      </details>
    </header>
    {children}
  </>;
}
