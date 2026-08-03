import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react/ssr";
import { notFound } from "next/navigation";
import { GuideCallout } from "@/components/guides/guide-callout";
import { GuideChecklist } from "@/components/guides/guide-checklist";
import { GuideComparison } from "@/components/guides/guide-comparison";
import { GuideJsonLd } from "@/components/guides/guide-json-ld";
import { GuideLayout } from "@/components/guides/guide-layout";
import { GuideSection } from "@/components/guides/guide-section";
import { GuideSources } from "@/components/guides/guide-sources";
import { GuideSteps } from "@/components/guides/guide-steps";
import { deliveryGuides, getDeliveryGuide } from "@/lib/guides/registry";
import type { KnownDeliveryType } from "@/lib/guides/types";
import { articleJsonLd, breadcrumbJsonLd, guideMetadata, howToJsonLd } from "../../_shared";

type PageProps = { params: Promise<{ deliveryType: string }> };

export function generateStaticParams() {
  return Object.values(deliveryGuides).map((guide) => ({ deliveryType: guide.deliveryType }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { deliveryType } = await params;
  const guide = getDeliveryGuide(deliveryType as KnownDeliveryType);
  if (!guide) return { title: "交付教程不存在", robots: { index: false, follow: true } };
  return guideMetadata(guide.title, guide.summary, `/guides/delivery/${guide.deliveryType}`);
}

export default async function DeliveryGuidePage({ params }: PageProps) {
  const { deliveryType } = await params;
  const guide = getDeliveryGuide(deliveryType as KnownDeliveryType);
  if (!guide) notFound();

  const path = `/guides/delivery/${guide.deliveryType}`;
  const toc = [
    { id: "definition", label: "这是什么" },
    { id: "receive", label: "会收到什么" },
    { id: "before-buying", label: "购买前确认" },
    { id: "usage", label: "使用步骤" },
    { id: "verification", label: "确认成功" },
    { id: "problems", label: "常见问题" },
    { id: "risks", label: "风险提示" },
    { id: "sources", label: "官方来源" },
  ];

  return (
    <>
      <GuideJsonLd data={[
        breadcrumbJsonLd([
          { name: "首页", path: "/" },
          { name: "教程中心", path: "/guides" },
          { name: guide.shortLabel, path },
        ]),
        articleJsonLd({ title: guide.title, description: guide.summary, path, dateModified: guide.lastReviewedAt }),
        howToJsonLd({ title: guide.title, description: guide.summary, steps: guide.usageSteps }),
      ]} />
      <GuideLayout
        breadcrumbs={[
          { href: "/", label: "首页" },
          { href: "/guides", label: "教程中心" },
          { label: guide.shortLabel },
        ]}
        title={guide.title}
        description={guide.summary}
        lastReviewedAt={guide.lastReviewedAt}
        toc={toc}
        footer={
          <Link href="/products" className="tactile flex min-h-12 items-center justify-between text-sm font-semibold">
            返回报价目录
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
        }
      >
        <GuideSection id="definition" title={`${guide.shortLabel}是什么`} intro={guide.summary}>
          <GuideCallout title="先确认交付名称">商品标题可能使用简称或行业俗称，请以商品原页面明确写出的账号归属、期限、权限和售后条件判断。</GuideCallout>
        </GuideSection>

        <GuideSection id="receive" title="购买后会收到什么"><GuideChecklist items={guide.whatYouReceive} /></GuideSection>

        <GuideSection id="before-buying" title="购买前确认"><GuideChecklist items={guide.beforeBuying} /></GuideSection>

        <GuideSection id="usage" title="安全使用步骤"><GuideSteps items={guide.usageSteps} /></GuideSection>

        <GuideSection id="verification" title="如何确认交付成功"><GuideChecklist items={guide.verifySuccess} /></GuideSection>

        <GuideSection id="problems" title="常见问题与处理">
          <GuideComparison
            columns={["问题", "安全处理"]}
            rows={guide.commonProblems.map((item) => [item.problem, item.action])}
          />
        </GuideSection>

        <GuideSection id="risks" title="控制权、安全和隐私风险">
          <GuideCallout tone="danger" title="重要风险不会折叠">
            <ul className="list-disc space-y-2 pl-5">{guide.riskNotes.map((note) => <li key={note}>{note}</li>)}</ul>
          </GuideCallout>
        </GuideSection>

        <GuideSection id="sources" title="官方来源"><GuideSources sources={guide.officialSources} /></GuideSection>
      </GuideLayout>
    </>
  );
}
