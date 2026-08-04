import Link from "next/link";

export const metadata = {
  title: "数据来源与收录政策 | AI Price Radar",
};

export default function SourcePolicyPage() {
  return (
    <main className="mx-auto max-w-3xl space-y-6 px-4 py-10">
      <h1 className="text-2xl font-semibold">数据来源与收录政策</h1>
      <section className="space-y-3 rounded-[18px] border hairline bg-[color:var(--panel)] p-6 text-sm leading-7 text-black/75">
        <p>AI Price Radar 是独立的、非官方的公开价格信息索引，与任何商家平台均无合作关系。</p>
        <p>我们只展示商家公开页面中可以匿名访问的事实字段：店铺名称、商品名称、公开价格、库存/上下架状态与商品公开链接。</p>
        <p>本站不代替商家页面；商品详情、交付、售后与交易均以原站为准。我们不缓存第三方商品图片，也不在本站代下单。</p>
        <p>每条报价均标注最后观察时间，并提供“查看原商品”“报告错误”“申请停止收录”入口。</p>
        <p>数据更新时间与来源可通过 <Link className="underline" href="/api/v1/meta">/api/v1/meta</Link> 查看。</p>
      </section>
      <div className="flex flex-wrap gap-3">
        <Link href="/source-opt-out" className="tactile rounded-[10px] border hairline px-4 py-2 text-sm">
          申请停止收录
        </Link>
        <Link href="/source-correction" className="tactile rounded-[10px] border hairline px-4 py-2 text-sm">
          报告错误
        </Link>
      </div>
    </main>
  );
}
