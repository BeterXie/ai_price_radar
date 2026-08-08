import Link from "next/link";

export default function NotFound() {
  return <main id="main-content" className="shell grid min-h-[62dvh] place-items-center py-20 text-center"><div className="max-w-3xl"><h1 className="page-title mx-auto">页面不存在</h1><p className="lede mx-auto mt-5">链接可能有误，商品也可能已经隐藏。请返回报价目录重新选择。</p><Link href="/products" className="button-primary tactile mt-8">返回报价目录</Link></div></main>;
}
