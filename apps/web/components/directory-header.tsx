"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";
import {
  ArrowsDownUp, Bell, BookOpen, ChartLineDown, Flask, GithubLogo, List,
  Plugs, Scales, SlidersHorizontal, Storefront, Tag, X,
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
    { href: "/alerts?view=drops", label: "降价榜", icon: ChartLineDown },
    { href: "/alerts?view=team", label: "Team 车提醒", icon: Bell },
    ...(relayHubEnabled ? [{ href: "/relays", label: "API 中转站", icon: Plugs }] : []),
    { href: "/skills", label: "技能与实验室", icon: Flask },
  ];
  const utilityLinks = [
    { href: "/compare", label: "模型对比", icon: Scales },
    { href: "/guides", label: "购买指南", icon: BookOpen },
    { href: "/methodology", label: "数据方法", icon: SlidersHorizontal },
    { href: "/shops/submit", label: "申请收录", icon: Storefront },
    ...(advertiseEnabled ? [{ href: "/advertise", label: "商务合作", icon: Tag }] : []),
  ];
  function navLink({ href, label, icon: Icon }: typeof mainLinks[number]) {
    const selected = current === href || current.startsWith(href + "/");
    return <Link key={href} href={href} prefetch={false} aria-current={selected ? "page" : undefined}>
      <Icon size={18} aria-hidden="true" /><span>{label}</span>
    </Link>;
  }
  const navigation = <>
    <nav className="directory-main-links" aria-label="主要导航" onClick={closeMenu}>{mainLinks.map(navLink)}</nav>
    <nav className="directory-utility-links" aria-label="帮助导航" onClick={closeMenu}>{utilityLinks.map(navLink)}</nav>
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
