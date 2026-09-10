import Image from "next/image";
import Link from "next/link";
import { ArrowRight, GithubLogo, Globe, ShieldCheck } from "@phosphor-icons/react/ssr";
import { BUSINESS_EMAIL, GITHUB_REPOSITORY_URL } from "@/lib/community";

export function SiteFooter({ advertiseEnabled = false }: { advertiseEnabled?: boolean }) {
  return (
    <footer className="site-footer">
      <div className="container">
        <div className="footer-main">
          <div className="footer-brand">
            <Link href="/" className="logo" aria-label="AI Price Memory 首页">
              <span className="logo-symbol"><Image src="/brand/logo-icon.png" alt="" width={30} height={30} className="relative z-[1] h-[24px] w-[24px] object-contain" /></span>
              <span><strong>AI Price Memory<span className="logo-period">.</span></strong><small>好选择，从信息透明开始</small></span>
            </Link>
            <p>让 AI 商品信息更透明，<br />让每一次选择更有把握。</p>
            <div className="footer-socials">
              <a href={GITHUB_REPOSITORY_URL} target="_blank" rel="noreferrer" aria-label="GitHub 开源仓库"><GithubLogo size={17} /></a>
              <a href={`mailto:${BUSINESS_EMAIL}`} aria-label="联系邮箱">@</a>
              <Link href="/methodology" aria-label="数据方法"><Globe size={17} /></Link>
            </div>
          </div>

          <div className="footer-links">
            <h4>发现与学习</h4>
            <Link href="/products">报价目录</Link>
            <Link href="/skills">技能与实验室</Link>
            <Link href="/guides">购买指南</Link>
            <Link href="/watchlist">我的关注</Link>
          </div>

          <div className="footer-links">
            <h4>数据与反馈</h4>
            <Link href="/methodology">数据方法</Link>
            <Link href="/shops/submit">申请收录</Link>
            <Link href="/corrections">提交 / 查看纠错</Link>
            <Link href="/developers">开发者接口</Link>
          </div>

          <div className="footer-links">
            <h4>关于与合作</h4>
            <Link href="/about">关于本站</Link>
            {advertiseEnabled ? <Link href="/advertise">商务合作</Link> : null}
            <Link href="/privacy">隐私政策</Link>
            <Link href="/terms">使用条款</Link>
            <Link href="/security">安全说明</Link>
          </div>

          <div className="footer-notice">
            <ShieldCheck size={22} />
            <h4>比价之后，记得核对。</h4>
            <p>本站聚合公开信息，不参与交易。<br />价格、库存与交付规则，<br />请以来源页面为准。</p>
            <Link className="text-button" href="/guides/buying-checklist">购买前检查 <ArrowRight size={14} /></Link>
          </div>
        </div>

        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} AI Price Memory <span className="footer-dot">·</span> 让选择更有依据</span>
          <span><span className="status-dot" />公开报价聚合 <span className="footer-dot">·</span> Powered by PriceMemo</span>
        </div>
      </div>
    </footer>
  );
}
