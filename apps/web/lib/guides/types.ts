export const BRAND_SLUGS = ["openai", "claude", "gemini", "grok", "x"] as const;

export type BrandSlug = (typeof BRAND_SLUGS)[number];

export const KNOWN_DELIVERY_TYPES = [
  "subscription_recharge",
  "finished_account",
  "semi_finished_account",
  "team_seat",
  "card_code",
  "api_credit",
  "verification_service",
  "shared_pool",
  "relay_api",
  "trial_account",
] as const;

export type KnownDeliveryType = (typeof KNOWN_DELIVERY_TYPES)[number];
export type DeliveryType = KnownDeliveryType | "unknown";

export const PRODUCT_SLUGS = [
  "chatgpt-account",
  "chatgpt-plus",
  "chatgpt-go",
  "chatgpt-k12",
  "chatgpt-pro-5x",
  "chatgpt-pro-20x",
  "chatgpt-pro",
  "openai-api-credit",
  "chatgpt-access-service",
  "codex-access",
  "claude-pro",
  "claude-account",
  "claude-api-access",
  "gemini-advanced",
  "gemini-account",
  "gemini-api-access",
  "grok-super",
  "grok-account",
  "grok-api-access",
  "x-premium-basic",
  "x-premium",
  "x-premium-plus",
] as const;

export type ProductSlug = (typeof PRODUCT_SLUGS)[number];

export const WORKFLOW_GUIDE_SLUGS = [
  "openai-codex",
  "cockpit-to-codex",
  "sub2api-to-codex",
  "api-endpoint-to-codex",
] as const;

export type WorkflowGuideSlug = (typeof WORKFLOW_GUIDE_SLUGS)[number];

export type WorkflowRelevance =
  | "recommended"
  | "conditional"
  | "advanced";

export interface ProductWorkflowReference {
  workflowSlug: WorkflowGuideSlug;
  relevance: WorkflowRelevance;

  /**
   * 用户满足什么条件时选择此路线。
   * 必填，不允许仅写“视情况而定”。
   */
  condition: string;

  /**
   * 卡片中显示的目标用户。
   */
  audience: string;

  /**
   * 产品特有警告。例如 Team/K12 管理员可撤销席位。
   */
  note?: string;
}

export type WorkflowVariantId = "cc-switch" | "codex-plusplus";

export interface WorkflowVariant {
  id: WorkflowVariantId;
  title: string;
  description: string;
  walkthrough: GuideWalkthrough;
}

export interface WorkflowProblem {
  problem: string;
  likelyCause: string;
  action: string;
}

export interface WorkflowGuide {
  slug: WorkflowGuideSlug;
  title: string;
  description: string;

  /**
   * 用于卡片直接展示链路，例如：
   * ["OpenAI 账号", "Cockpit", "CC Switch / Codex++", "Codex"]
   */
  flow: readonly string[];

  audience: readonly string[];
  prerequisites: readonly string[];
  overview: readonly GuideBlock[];

  /**
   * 详细页中分别展示 CC Switch 和 Codex++ 两个方案。
   * 不做 Tab；使用两个独立 section，方便 SEO 和无 JS 阅读。
   */
  variants: readonly WorkflowVariant[];

  verificationChecklist: readonly string[];
  commonProblems: readonly WorkflowProblem[];
  riskNotes: readonly string[];
  faq: readonly GuideFaq[];

  /**
   * OpenAI 官方文档和第三方项目自己的官方仓库都可以放入，
   * 但必须通过 source.kind 明确区分。
   */
  sources: readonly GuideSource[];
  lastReviewedAt: string;
}

export const GENERAL_GUIDE_SLUGS = [
  "buying-checklist",
  "account-control",
  "subscription-verification",
  "troubleshooting",
  "after-sales-evidence",
  "security",
] as const;

export type GeneralGuideSlug = (typeof GENERAL_GUIDE_SLUGS)[number];

export type GuideBlock =
  | { type: "paragraph"; text: string }
  | { type: "steps"; title?: string; items: readonly string[] }
  | { type: "checklist"; title?: string; items: readonly string[] }
  | {
      type: "callout";
      tone: "info" | "warning" | "danger" | "success";
      title: string;
      text: string;
    }
  | {
      type: "comparison";
      title?: string;
      columns: readonly string[];
      rows: readonly (readonly string[])[];
    }
  | {
      type: "faq";
      items: readonly GuideFaq[];
    };

export interface GuideFaq {
  question: string;
  answer: string;
}

export interface GuideWalkthroughStep {
  title: string;
  action: string;
  items?: readonly string[];
  links?: readonly { label: string; url: string }[];
  result: string;
  trouble?: string;
}

export interface GuideWalkthrough {
  title: string;
  intro: string;
  steps: readonly GuideWalkthroughStep[];
}

export type GuideSourceKind =
  | "platform_official"
  | "project_official";

export interface GuideSource {
  title: string;
  url: string;
  publisher: string;
  lastCheckedAt: string;
  kind: GuideSourceKind;
}

/**
 * 临时兼容现有代码，后续可以逐步移除旧名。
 */
export type OfficialSource = GuideSource;

export interface ProductGuide {
  productSlug: ProductSlug;
  brand: BrandSlug;
  title: string;
  description: string;
  audience: readonly string[];
  supportedDeliveryTypes: readonly KnownDeliveryType[];
  overview: readonly GuideBlock[];
  walkthrough?: GuideWalkthrough;
  workflowReferences?: readonly ProductWorkflowReference[];
  buyingChecklist: readonly string[];
  verificationChecklist: readonly string[];
  riskNotes: readonly string[];
  faq: readonly GuideFaq[];
  officialSources: readonly OfficialSource[];
  disclaimer: string;
  lastReviewedAt: string;
}

export interface DeliveryGuide {
  deliveryType: KnownDeliveryType;
  title: string;
  shortLabel: string;
  summary: string;
  whatYouReceive: readonly string[];
  beforeBuying: readonly string[];
  usageSteps: readonly string[];
  verifySuccess: readonly string[];
  commonProblems: readonly { problem: string; action: string }[];
  riskNotes: readonly string[];
  officialSources: readonly OfficialSource[];
  lastReviewedAt: string;
}

export interface BrandGuide {
  brand: BrandSlug;
  title: string;
  description: string;
  overview: readonly GuideBlock[];
  productSlugs: readonly ProductSlug[];
  planNotes: readonly string[];
  commonDeliveryTypes: readonly KnownDeliveryType[];
  riskNotes: readonly string[];
  officialSources: readonly OfficialSource[];
  lastReviewedAt: string;
}

export interface GeneralGuide {
  slug: GeneralGuideSlug;
  title: string;
  description: string;
  blocks: readonly GuideBlock[];
  officialSources: readonly OfficialSource[];
  lastReviewedAt: string;
}

export interface GuideRegistry {
  brands: Readonly<Record<BrandSlug, BrandGuide>>;
  products: Readonly<Record<ProductSlug, ProductGuide>>;
  delivery: Readonly<Record<KnownDeliveryType, DeliveryGuide>>;
  general: Readonly<Record<GeneralGuideSlug, GeneralGuide>>;
  workflows: Readonly<Record<WorkflowGuideSlug, WorkflowGuide>>;
}
