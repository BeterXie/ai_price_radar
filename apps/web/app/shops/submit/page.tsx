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

export default function ShopSubmitPage() {
  return (
    <main id="main-content" className="shell py-12 md:py-16">
      <section className="grid gap-10 lg:grid-cols-[.85fr_1.15fr] lg:gap-16">
        <div className="lg:pt-4">
          <p className="mono text-xs tracking-[.15em] text-black/45">来源收录</p>
          <h1 className="mt-4 max-w-xl text-5xl font-semibold leading-[.96] tracking-[-.06em] sm:text-6xl">提交商品来源</h1>
          <p className="mt-6 max-w-xl text-base leading-7 text-[color:var(--muted)]">提交公开店铺、商品页面或结构化 JSON Feed。来源类型默认自动识别，我们会核验可访问性、商品范围和报价信息，再决定是否收录。</p>

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

          <p className="mt-6 max-w-xl text-xs leading-5 text-black/45">提交申请不代表自动收录。非公开来源、不含目标商品或无法稳定核验的来源不会进入公开目录。</p>
        </div>

        <ShopRequestForm />
      </section>
    </main>
  );
}
