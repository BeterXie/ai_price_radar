import Link from "next/link";

export default function NotFound() {
  return <main className="shell grid min-h-[60dvh] place-items-center py-20 text-center"><div><p className="mono text-xs uppercase tracking-[.15em] text-black/45">404 / not indexed</p><h1 className="mt-4 text-6xl font-semibold tracking-[-.06em]">这里没有可展示的数据。</h1><p className="mt-5 text-black/50">商品可能尚未分类、已经隐藏或链接输入错误。</p><Link href="/products" className="tactile mt-8 inline-block rounded-[10px] bg-[color:var(--ink)] px-5 py-3 text-sm text-white">返回报价目录</Link></div></main>;
}
