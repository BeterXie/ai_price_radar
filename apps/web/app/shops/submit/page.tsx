import type { Metadata } from "next";
import Link from "next/link";
import { CheckCircle, Eye, ShieldCheck } from "@phosphor-icons/react/ssr";
import { ShopRequestForm } from "@/components/shop-request-form";
import { BUSINESS_EMAIL } from "@/lib/community";
import { getMeta } from "@/lib/api";

export const metadata: Metadata = {
  title: "提交商品来源",
  description: "提交公开店铺、商品页面、商家 Feed 或 API 中转站，申请加入 AI Price Memory (AI Price Radar)。",
  alternates: { canonical: "/shops/submit" },
  openGraph: {
    title: "提交商品来源 · AI Price Memory / AI Price Radar",
    description: "提交公开商品来源或 API 中转站，审核后展示报价或接口检测结果。",
    url: "/shops/submit",
  },
};

export default async function ShopSubmitPage({ searchParams }: { searchParams: Promise<{ type?: string }> }) {
  const meta = await getMeta().catch(() => null);
  const { type } = await searchParams;

  return (
    <main id="main-content" className="shell py-12 md:py-16" data-vds-schema="v3.1" data-vds-layer="field" data-vds-action="task-orientation eligibility-check structured-form explicit-feedback">
      <section className="shop-submit-layout">
        <div className="shop-submit-intro lg:pt-4">
          <p className="eyebrow">来源收录</p>
          <h1 className="page-title mt-4" data-vds-role="title">提交商品来源</h1>
          <p className="lede mt-6" data-vds-role="explanation">提交公开店铺、商品页面、结构化 JSON Feed 或 API 中转站。商品来源核验报价信息；中转站使用提供的 Base URL、检测密钥和模型进行接口探活。</p>
        </div>

        <div className="shop-submit-criteria">
          <div className="mt-10 max-w-xl border-t border-black">
            {[
              { Icon: Eye, title: "核验来源信息", copy: "商品页面或 Feed 需公开可访问；中转站需提供公开官网和可用的接口信息。" },
              { Icon: ShieldCheck, title: "确认提交权限", copy: "使用已验证的登录邮箱提交。中转站密钥加密保存，请使用专门用于检测的低额度密钥。" },
              { Icon: CheckCircle, title: "审核后展示", copy: "商品读取成功后显示报价；中转站审核上线后开始按小时采样，展示可用性和延迟。" },
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

          <p className="mt-6 max-w-xl text-sm leading-6 text-[color:var(--muted)]">申请先进入审核队列。接口检测会发送简短模型请求，可能消耗少量额度；结果仅代表该密钥和模型在采样时的表现。</p>
          {meta?.advertise_enabled ? (
            <div className="mt-6 max-w-xl rounded-[12px] border border-[color:var(--line)] bg-[color:var(--surface)] p-4 text-xs leading-6 text-[color:var(--muted)]">
              <span className="font-semibold text-[color:var(--ink)]">💡 需要更多商业曝光与推广合作？</span>
              <p className="mt-1">
                如需开展核心分类置顶推荐、CPS 专属优惠码合作或品牌赞助，请参阅{" "}
                <Link href="/advertise" className="font-medium underline text-[color:var(--ink)]">
                  商务合作 / 广告投放
                </Link>
                ，或直接发送邮件至{" "}
                <a href={`mailto:${BUSINESS_EMAIL}`} className="font-medium underline text-[color:var(--ink)]">
                  {BUSINESS_EMAIL}
                </a>
                。
              </p>
            </div>
          ) : null}
        </div>

        <ShopRequestForm initialSourceType={type === "relay" ? "relay" : "ldxp"} />
      </section>
    </main>
  );
}
