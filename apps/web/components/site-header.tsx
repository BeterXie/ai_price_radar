import Link from "next/link";
import Image from "next/image";
import { GithubLogo } from "@phosphor-icons/react/ssr";
import { PlatformIcon } from "@/components/platform-icon";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b hairline bg-[color:var(--paper)]/95 backdrop-blur">
      <div className="shell flex h-16 items-center justify-between gap-6">
        <Link href="/" className="flex items-center gap-3 font-semibold tracking-[-0.03em]">
          <Image src="/icon.svg" alt="" width={32} height={32} priority />
          <span>AI Price Radar</span>
        </Link>
        <nav className="hidden items-center gap-5 text-sm lg:flex">
          <Link href="/products" className="hover:opacity-60">全部报价</Link>
          {[
            ["OpenAI", "OpenAI"],
            ["Claude", "Claude"],
            ["Gemini", "Gemini"],
            ["Grok", "Grok"],
            ["X", "X"],
          ].map(([platform, label]) => (
            <Link key={platform} href={`/products?platform=${platform}`} className="flex items-center gap-1.5 hover:opacity-60">
              <PlatformIcon platform={platform} size={14} />{label}
            </Link>
          ))}
        </nav>
        <a
          href="https://github.com/BeterXie/ai_price_radar"
          target="_blank"
          rel="noreferrer"
          aria-label="在 GitHub 查看 AI Price Radar 开源项目"
          title="GitHub 开源项目"
          className="tactile grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[color:var(--ink)] text-white"
        >
          <GithubLogo size={22} weight="fill" />
        </a>
      </div>
    </header>
  );
}
