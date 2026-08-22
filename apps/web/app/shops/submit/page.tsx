import type { Metadata } from "next";
import { CheckCircle, Eye, ShieldCheck } from "@phosphor-icons/react/ssr";
import { ShopRequestForm } from "@/components/shop-request-form";

export const metadata: Metadata = {
  title: "提交商品来源",
  description: "提交公开店铺、商品页面或商家 Feed，申请加入 AI Price Radar 报价目录。",
  alternates: { canonical: "/shops/submit" },
  openGraph: {
    title: "提交商品来源 · AI Price Radar",
    description: "提交公开店铺或商家 JSON Feed，经过审核和读取验证后加入报价目录。",
    url: "/shops/submit",
  },
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function ShopSubmitPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const rawState = Array.isArray(params.state) ? params.state.at(-1) : params.state;
  const previewState = rawState === "success" ? "submitted" : rawState === "error" ? "error" : undefined;
  return (
    <main id="main-content" className="shell py-12 md:py-16" data-vds-schema="v3.1" data-vds-layer="field" data-vds-action="task-orientation eligibility-check structured-form explicit-feedback">
      <section className="shop-submit-layout">
        <div className="shop-submit-intro lg:pt-4">
          <p className="eyebrow">来源收录</p>
          <h1 className="page-title mt-4" data-vds-role="title">提交商品来源</h1>
          <p className="lede mt-6" data-vds-role="explanation">提交公开店铺、商品页面或结构化 JSON Feed。系统会识别来源类型，并核验可访问性、商品范围和报价信息。</p>
        </div>

        <div className="shop-submit-criteria">
          <div className="mt-10 max-w-xl border-t border-black">
            {[
              { Icon: Eye, title: "核验公开页面", copy: "确认页面或 Feed 无需登录即可访问，并能稳定读取公开商品。" },
              { Icon: ShieldCheck, title: "检查商品范围", copy: "仅收录目标 AI 账号、订阅、充值、API 和相关服务商品。" },
              { Icon: CheckCircle, title: "通过后加入目录", copy: "审核通过并成功读取商品后，符合收录范围的报价会显示在目录中。" },
            ].map(({ Icon, title, copy }) => (
              <div key={title} className="grid grid-cols-[28px_1fr] gap-4 border-b hairline py-5">
                <Icon size={23} />
                <div>
                  <h2 className="font-semibold">{title}</h2>
                  <p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">{copy}</p>
                </div>
              </div>
            ))}
          </div>

          <p className="mt-6 max-w-xl text-sm leading-6 text-[color:var(--muted)]">申请会先经过审核和读取验证。公开可访问、包含目标商品并能稳定核验的来源才会进入报价目录。</p>
        </div>

        <ShopRequestForm previewState={previewState} />
      </section>
    </main>
  );
}
