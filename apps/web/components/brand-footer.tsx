import Link from "next/link";
import { ArrowUpRight } from "@phosphor-icons/react/ssr";
import { BRAND, SITE_ID } from "@/lib/brands";
import { GITHUB_REPOSITORY_URL } from "@/lib/community";

export function BrandFooter({ advertiseEnabled }: { advertiseEnabled: boolean }) {
  const legal = <nav className="brand-legal" aria-label="法律与项目信息"><Link href="/about">关于</Link><Link href="/privacy">隐私</Link><Link href="/terms">条款</Link><Link href="/security">安全</Link>{GITHUB_REPOSITORY_URL && <a href={GITHUB_REPOSITORY_URL} target="_blank" rel="noreferrer">开源 <ArrowUpRight size={13} /></a>}</nav>;
  const links = <nav className="brand-footer-links" aria-label="页脚导航"><Link href="/products">报价目录</Link><Link href="/articles">文章</Link><Link href="/watchlist">关注清单</Link><Link href="/methodology">数据方法</Link><Link href="/corrections">纠错记录</Link><Link href="/developers">开发者接口</Link><Link href="/shops/submit">申请收录</Link>{advertiseEnabled && <Link href="/advertise">商务合作</Link>}</nav>;
  const notice = <p className="brand-footer-notice">本站聚合公开报价，不参与交易。价格、库存、交付方式和退款规则以来源页面为准。</p>;
  if (SITE_ID === "aisi") return <footer className="brand-footer editorial-footer shell"><div><span className="footer-wordmark">aisi.plus</span><h2>让选择，从容一点。</h2>{notice}</div><div>{links}{legal}</div></footer>;
  if (SITE_ID === "pricein") return <footer className="brand-footer shop-footer"><div className="shell"><div className="shop-footer-reminder"><strong>比过价，更要看清交付。</strong>{notice}</div><div className="shop-footer-bottom"><span className="footer-wordmark">PriceIn</span>{links}</div>{legal}</div></footer>;
  return <footer className={`brand-footer ${SITE_ID === "aiprice" ? "terminal-footer" : "index-footer"} shell`}><div><span className="footer-wordmark">{BRAND.wordmark}</span>{notice}</div>{links}{legal}</footer>;
}
