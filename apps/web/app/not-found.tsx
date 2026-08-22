import Link from "next/link";

export default function NotFound() {
  return <main id="main-content" className="shell grid min-h-[62dvh] place-items-center py-20 text-center" data-vds-schema="v3.1" data-vds-layer="field"><div className="max-w-3xl"><p className="eyebrow">访问未完成</p><h1 className="page-title mx-auto mt-4">页面不存在</h1><p className="lede mx-auto mt-5">链接可能有误，商品也可能已经隐藏。可以返回报价目录重新选择。</p><div className="mt-8 flex flex-wrap justify-center gap-3"><Link href="/products" className="button-primary tactile">返回报价目录</Link><Link href="/" className="button-secondary tactile">返回首页</Link></div></div></main>;
}
