import Link from "next/link";

export default function OfferNotFound() {
  return <main id="main-content" className="shell py-12">
    <h1 className="text-2xl font-semibold">这条商品报价暂不可用</h1>
    <p className="mt-3 text-[color:var(--muted)]">商品可能已下架，或报价数据已过期。</p>
    <Link href="/products" className="mt-6 inline-block underline">查看最新报价</Link>
  </main>;
}
