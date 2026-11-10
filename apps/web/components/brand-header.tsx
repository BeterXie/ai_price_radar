"use client";

import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { ArrowUpRight, ChartLine, List, BookOpen, Plugs, SquaresFour } from "@phosphor-icons/react";
import { BRAND, SITE_ID } from "@/lib/brands";
import { SearchBox } from "./search-box";

export function BrandHeader({ account, relayHubEnabled, advertiseEnabled, children }: { account: ReactNode; relayHubEnabled: boolean; advertiseEnabled: boolean; children: ReactNode }) {
  const pathname = usePathname();
  const menu = useRef<HTMLDetailsElement>(null);
  const closeMenu = () => { if (menu.current) menu.current.open = false; };
  useEffect(() => { if (menu.current) menu.current.open = false; }, [pathname]);
  const links = [{ href: "/products", label: "报价目录", icon: ChartLine }, ...(relayHubEnabled ? [{ href: "/relays", label: "中转站", icon: Plugs }] : []), { href: "/articles", label: "文章", icon: BookOpen }];
  const nav = <nav className="brand-main-nav" aria-label="主要导航" onClick={closeMenu}>{links.map(({ href, label, icon: Icon }, i) => <Link key={href} href={href} aria-current={pathname === href || pathname.startsWith(`${href}/`) ? "page" : undefined}><Icon size={20} /><span>{label}</span><small>0{i + 1}</small></Link>)}</nav>;
  const logo = <Link href="/" className="brand-logo" aria-label={`${BRAND.name} 首页`}><span className="brand-logo-mark" aria-hidden>{SITE_ID === "aiprice" ? <ChartLine size={25} /> : SITE_ID === "pricein" ? <SquaresFour size={26} weight="fill" /> : BRAND.mark}</span><span>{BRAND.wordmark}</span></Link>;
  const utility = <nav className="brand-utility" aria-label="帮助导航" onClick={closeMenu}><Link href="/compare">模型对比</Link><Link href="/methodology">数据方法</Link><Link href="/shops/submit">申请收录 <ArrowUpRight size={14} /></Link>{advertiseEnabled && <Link href="/advertise">商务合作</Link>}</nav>;
  const mobile = <details className="brand-mobile-menu" ref={menu}><summary aria-label="打开站点导航"><List size={23} /></summary><div>{nav}{utility}</div></details>;
  if (SITE_ID === "aiprice") return <><header className="terminal-header"><div>{logo}<p className="terminal-nav-label">WORKSPACE</p>{nav}{utility}</div><div className="terminal-account">{account}<span>公开报价 · 独立比较</span></div>{mobile}</header>{children}</>;
  if (SITE_ID === "aisi") return <><header className="editorial-header shell"><div className="editorial-masthead"><span>AI · 订阅 · 生活</span>{logo}<div className="brand-account">{account}{mobile}</div></div><div className="editorial-nav-row">{nav}{utility}</div></header>{children}</>;
  if (SITE_ID === "pricein") return <><header className="shop-header"><div className="shop-topbar shell">{logo}<div className="shop-header-search"><SearchBox placeholder="搜一搜，比较 AI 订阅价格" compact /></div><div className="brand-account">{account}{mobile}</div></div><div className="shop-nav-row"><div className="shell">{nav}{utility}</div></div></header>{children}</>;
  return <><header className="index-header shell"><div>{logo}<span className="index-header-note">公开价格索引</span></div>{nav}<div className="brand-account">{account}{mobile}</div></header>{children}</>;
}
