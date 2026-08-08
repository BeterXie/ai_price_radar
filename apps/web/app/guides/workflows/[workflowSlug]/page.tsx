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
import { GuideWalkthrough } from "@/components/guides/guide-walkthrough";
import { getWorkflowGuide, workflowGuides } from "@/lib/guides/registry";
import { articleJsonLd, breadcrumbJsonLd, faqJsonLd, guideMetadata, howToJsonLd } from "../../_shared";

type PageProps = { params: Promise<{ workflowSlug: string }> };

export function generateStaticParams() {
  return Object.values(workflowGuides).map((guide) => ({ workflowSlug: guide.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { workflowSlug } = await params;
  const guide = getWorkflowGuide(workflowSlug);
  if (!guide) return { title: "工作流教程不存在", robots: { index: false, follow: true } };
  return guideMetadata(guide.title, guide.description, `/guides/workflows/${guide.slug}`);
}

export default async function WorkflowGuidePage({ params }: PageProps) {
  const { workflowSlug } = await params;
  const guide = getWorkflowGuide(workflowSlug);
  if (!guide) notFound();

  const path = `/guides/workflows/${guide.slug}`;
  const toc = [
    { id: "what-is", label: "适用场景" },
    { id: "flow", label: "配置流程" },
    { id: "audience", label: "适合哪些用户" },
    { id: "prerequisites", label: "开始前准备" },
    ...guide.variants.map((item) => ({
      id: `variant-${item.id}`,
      label: item.id === "cc-switch" ? "方案 A：CC Switch" : "方案 B：Codex++",
    })),
    { id: "verification", label: "如何确认成功" },
    { id: "problems", label: "常见错误" },
    { id: "security", label: "安全与隐私" },
    { id: "faq", label: "常见问题" },
    { id: "sources", label: "资料来源" },
  ];

  return (
    <>
      <GuideJsonLd
        data={[
          breadcrumbJsonLd([
            { name: "首页", path: "/" },
            { name: "教程中心", path: "/guides" },
            { name: guide.title, path },
          ]),
          articleJsonLd({ title: guide.title, description: guide.description, path, dateModified: guide.lastReviewedAt }),
          ...guide.variants.map((item) =>
            howToJsonLd({
              title: item.title,
              description: item.description,
              steps: item.walkthrough.steps.map((step) => step.action),
            }),
          ),
          faqJsonLd(guide.faq),
        ]}
      />
      <GuideLayout
        breadcrumbs={[
          { href: "/", label: "首页" },
          { href: "/guides", label: "教程中心" },
          { label: guide.title },
        ]}
        title={guide.title}
        description={guide.description}
        lastReviewedAt={guide.lastReviewedAt}
        toc={toc}
        footer={
          <div className="space-y-6">
            <GuideCallout tone="warning" title="第三方与凭证风险">
              Cockpit Tools、Sub2API、CC Switch 和 Codex++ 均为第三方项目，与 OpenAI 和 AI Price Radar 没有隶属关系。不要把完整 Cookie、Access Token、Refresh Token、API Key、恢复码或 auth.json 上传到本站、聊天机器人或公开仓库。
            </GuideCallout>
            <Link href="/guides" className="tactile flex min-h-12 items-center justify-between text-sm font-semibold">
              返回教程中心
              <ArrowRight size={18} aria-hidden="true" />
            </Link>
          </div>
        }
      >
      <GuideSection id="what-is" title="适用场景">
          <GuideBlocks blocks={guide.overview} />
        </GuideSection>

      <GuideSection id="flow" title="配置流程" intro="上游负责账号与 API，下游客户端负责把接口配置给 Codex。">
          <ol aria-label="工作流步骤" className="grid gap-3">
            {guide.flow.map((node, index) => (
              <li key={node} className="flex flex-wrap items-center gap-3 rounded-[12px] border hairline bg-[color:var(--panel)] px-4 py-3 text-sm font-semibold">
                <span>{node}</span>
                {index < guide.flow.length - 1 ? (
                  <ArrowRight size={18} className="text-black/40" aria-hidden="true" />
                ) : null}
              </li>
            ))}
          </ol>
        </GuideSection>

        <GuideSection id="audience" title="适合哪些用户">
          <GuideChecklist items={guide.audience} />
        </GuideSection>

        <GuideSection id="prerequisites" title="开始前准备">
          <GuideChecklist items={guide.prerequisites} />
        </GuideSection>

        {guide.variants.map((item) => (
          <GuideSection
            key={item.id}
            id={`variant-${item.id}`}
            title={item.title}
            intro={item.description}
          >
            <GuideWalkthrough walkthrough={item.walkthrough} />
          </GuideSection>
        ))}

        <GuideSection id="verification" title="如何确认成功">
          <GuideChecklist items={guide.verificationChecklist} />
        </GuideSection>

        <GuideSection id="problems" title="常见错误">
          <GuideComparison
            columns={["问题", "可能原因", "处理动作"]}
            rows={guide.commonProblems.map((item) => [item.problem, item.likelyCause, item.action])}
          />
        </GuideSection>

        <GuideSection id="security" title="安全与隐私">
        <GuideCallout tone="danger" title="请先确认这些风险">
            <ul className="list-disc space-y-2 pl-5">
              {guide.riskNotes.map((note) => <li key={note}>{note}</li>)}
            </ul>
          </GuideCallout>
        </GuideSection>

        <GuideSection id="faq" title="常见问题">
          <GuideFaq items={guide.faq} />
        </GuideSection>

        <GuideSection id="sources" title="资料来源">
          <GuideSources sources={guide.sources} />
        </GuideSection>
      </GuideLayout>
    </>
  );
}
