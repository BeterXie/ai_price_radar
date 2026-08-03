import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react/ssr";
import { notFound } from "next/navigation";
import { GuideBlocks } from "@/components/guides/guide-blocks";
import { GuideCallout } from "@/components/guides/guide-callout";
import { GuideChecklist } from "@/components/guides/guide-checklist";
import { GuideComparison } from "@/components/guides/guide-comparison";
import { GuideFaq } from "@/components/guides/guide-faq";
import { GuideJsonLd } from "@/components/guides/guide-json-ld";
import { GuideLayout } from "@/components/guides/guide-layout";
import { GuideSection } from "@/components/guides/guide-section";
import { GuideSources } from "@/components/guides/guide-sources";
import { GuideSteps } from "@/components/guides/guide-steps";
import { GuideWalkthrough } from "@/components/guides/guide-walkthrough";
import { GuideWorkflowCards } from "@/components/guides/guide-workflow-cards";
import { getDeliveryGuide, getProductGuide, getWorkflowGuide, productGuides } from "@/lib/guides/registry";
import type { ProductWorkflowReference, WorkflowGuide } from "@/lib/guides/types";
import { articleJsonLd, BRAND_NAMES, breadcrumbJsonLd, faqJsonLd, guideMetadata, howToJsonLd } from "../../_shared";

type PageProps = { params: Promise<{ productSlug: string }> };

const evidenceChecklist = [
  "商品原页面、商品标题、交付类型、期限、价格和售后条件。",
  "订单编号、支付时间、交付时间和经过遮挡的沟通记录。",
  "官方账户页中的账号标识、套餐、期限或用量状态。",
  "完整错误提示、发生时间和可安全复现的步骤。",
  "截图前遮挡密码、验证码、恢复码、完整 API Key 和支付信息。",
];

export function generateStaticParams() {
  return Object.values(productGuides).map((guide) => ({ productSlug: guide.productSlug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { productSlug } = await params;
  const guide = getProductGuide(productSlug);
  if (!guide) return { title: "产品教程不存在", robots: { index: false, follow: true } };
  return guideMetadata(guide.title, guide.description, `/guides/products/${guide.productSlug}`);
}

export default async function ProductGuidePage({ params }: PageProps) {
  const { productSlug } = await params;
  const guide = getProductGuide(productSlug);
  if (!guide) notFound();

  const deliveryEntries = guide.supportedDeliveryTypes.map((type) => getDeliveryGuide(type)).filter((item) => item !== undefined);
  const comparisonBlocks = guide.overview.filter((block) => block.type === "comparison");
  const overviewBlocks = guide.overview.filter((block) => block.type === "paragraph");
  const workflowEntries = (guide.workflowReferences ?? [])
    .map((reference) => ({
      reference,
      guide: getWorkflowGuide(reference.workflowSlug),
    }))
    .filter(
      (entry): entry is {
        reference: ProductWorkflowReference;
        guide: WorkflowGuide;
      } => Boolean(entry.guide),
    );
  const problemRows = deliveryEntries.flatMap((delivery) =>
    delivery.commonProblems.map((item) => [delivery.shortLabel, item.problem, item.action]),
  );
  const path = `/guides/products/${guide.productSlug}`;
  const toc = [
    { id: "what-is", label: "这是什么" },
    ...(guide.walkthrough ? [{ id: "walkthrough", label: "照着做" }] : []),
    { id: "differences", label: "相邻套餐区别" },
    { id: "audience", label: "适合哪些用户" },
    { id: "delivery-types", label: "常见交付方式" },
    { id: "buying-checklist", label: "购买前确认" },
    { id: "delivery-guides", label: "购买后使用" },
    { id: "verification", label: "确认服务生效" },
    ...(workflowEntries.length
      ? [{ id: "usage-workflows", label: "用于 Codex" }]
      : []),
    { id: "problems", label: "常见错误" },
    { id: "security", label: "安全和隐私" },
    { id: "after-sales", label: "售后证据" },
    { id: "faq", label: "常见问题" },
    { id: "sources", label: "官方来源" },
  ];

  return (
    <>
      <GuideJsonLd data={[
        breadcrumbJsonLd([
          { name: "首页", path: "/" },
          { name: "教程中心", path: "/guides" },
          { name: BRAND_NAMES[guide.brand], path: `/guides/brands/${guide.brand}` },
          { name: guide.title, path },
        ]),
        articleJsonLd({ title: guide.title, description: guide.description, path, dateModified: guide.lastReviewedAt }),
        howToJsonLd({
          title: guide.walkthrough?.title ?? `${guide.title}购买前确认`,
          description: guide.description,
          steps: guide.walkthrough?.steps.map((step) => step.action) ?? guide.buyingChecklist,
        }),
        faqJsonLd(guide.faq),
      ]} />
      <GuideLayout
        breadcrumbs={[
          { href: "/", label: "首页" },
          { href: "/guides", label: "教程中心" },
          { href: `/guides/brands/${guide.brand}`, label: BRAND_NAMES[guide.brand] },
          { label: guide.title },
        ]}
        title={guide.title}
        description={guide.description}
        lastReviewedAt={guide.lastReviewedAt}
        toc={toc}
        footer={
          <div className="space-y-6">
            <GuideCallout tone="warning" title="使用前请确认">
              {guide.disclaimer}
            </GuideCallout>
            <Link href={`/products/${encodeURIComponent(guide.productSlug)}`} className="tactile flex min-h-12 items-center justify-between text-sm font-semibold">
              返回该产品报价目录
              <ArrowRight size={18} aria-hidden="true" />
            </Link>
          </div>
        }
      >
        <GuideSection id="what-is" title="这是什么"><GuideBlocks blocks={overviewBlocks} /></GuideSection>

        {guide.walkthrough ? (
          <GuideSection id="walkthrough" title="照着做：从交付到确认生效">
            <GuideWalkthrough walkthrough={guide.walkthrough} />
          </GuideSection>
        ) : null}

        <GuideSection id="differences" title="它与相邻套餐有什么区别" intro="名称相近的套餐可能在权益、用量、组织管理和计费方式上不同，最终以官方产品页和账户页为准。">
          {comparisonBlocks.length ? <GuideBlocks blocks={comparisonBlocks} /> : (
            <GuideCallout title="不要只按标题判断">购买前核对官方套餐名称、权益范围、期限和使用入口，避免把网页订阅、团队席位与 API 额度混为一类。</GuideCallout>
          )}
        </GuideSection>

        <GuideSection id="audience" title="适合哪些用户"><GuideChecklist items={guide.audience} /></GuideSection>

        <GuideSection id="delivery-types" title="第三方市场常见交付方式" intro="选择交付方式后，再确认账号控制权、可修改设置和售后条件。">
          <div className="grid gap-3 sm:grid-cols-2">
            {deliveryEntries.map((delivery) => (
              <a key={delivery.deliveryType} href={`#delivery-${delivery.deliveryType}`} className="flex min-h-14 items-center justify-between rounded-[12px] border hairline bg-[color:var(--panel)] px-4 text-sm font-semibold hover:border-black">
                {delivery.shortLabel}
                <span className="text-black/40" aria-hidden="true">#</span>
              </a>
            ))}
          </div>
        </GuideSection>

        <GuideSection id="buying-checklist" title="购买前确认"><GuideChecklist items={guide.buyingChecklist} /></GuideSection>

        <GuideSection id="delivery-guides" title="购买后会收到什么与使用步骤" intro="只按商品原页面明确写出的交付方式操作。遇到额外索取敏感信息或要求绕过验证时应停止。">
          <div className="space-y-8">
            {deliveryEntries.map((delivery) => (
              <section key={delivery.deliveryType} id={`delivery-${delivery.deliveryType}`} className="scroll-mt-24 rounded-[16px] border border-black bg-[color:var(--panel)] p-5 sm:p-6">
                <div className="flex flex-wrap items-start justify-between gap-4 border-b hairline pb-4">
                  <div>
                    <h3 className="text-xl font-semibold">{delivery.shortLabel}</h3>
                    <p className="mt-2 text-sm leading-6 text-black/60">{delivery.summary}</p>
                  </div>
                  <Link href={`/guides/delivery/${delivery.deliveryType}`} className="flex min-h-11 items-center text-sm font-semibold hover:underline">完整交付指南</Link>
                </div>
                <div className="mt-6 space-y-7">
                  <GuideChecklist title="会收到什么" items={delivery.whatYouReceive} />
                  <GuideSteps title="使用步骤" items={delivery.usageSteps} />
                  <GuideChecklist title="如何确认生效" items={delivery.verifySuccess} />
                </div>
              </section>
            ))}
          </div>
        </GuideSection>

        <GuideSection id="verification" title="如何确认服务已经生效"><GuideChecklist items={guide.verificationChecklist} /></GuideSection>

        {workflowEntries.length ? (
          <GuideSection
            id="usage-workflows"
            title="购买后如何用于 Codex"
            intro="先确认账号、套餐或席位已经生效，再选择本地账号池、服务器账号池，或直接 API 路线。Cockpit/Sub2API 负责上游账号与 API，CC Switch/Codex++ 负责把接口配置给 Codex。"
          >
            <GuideWorkflowCards entries={workflowEntries} />
          </GuideSection>
        ) : null}

        <GuideSection id="problems" title="常见错误与处理">
          <GuideComparison columns={["交付方式", "问题", "安全处理"]} rows={problemRows} />
        </GuideSection>

        <GuideSection id="security" title="安全和隐私提示">
          <GuideCallout tone="danger" title="重要风险不会折叠">
            <ul className="list-disc space-y-2 pl-5">{guide.riskNotes.map((note) => <li key={note}>{note}</li>)}</ul>
          </GuideCallout>
        </GuideSection>

        <GuideSection id="after-sales" title="售后需要准备什么"><GuideChecklist items={evidenceChecklist} /></GuideSection>

        <GuideSection id="faq" title="常见问题"><GuideFaq items={guide.faq} /></GuideSection>

        <GuideSection id="sources" title="官方来源"><GuideSources sources={guide.officialSources} /></GuideSection>
      </GuideLayout>
    </>
  );
}
