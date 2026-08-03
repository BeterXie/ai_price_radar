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

export interface OfficialSource {
  title: string;
  url: string;
  publisher: string;
  lastCheckedAt: string;
}

export interface ProductGuide {
  productSlug: ProductSlug;
  brand: BrandSlug;
  title: string;
  description: string;
  audience: readonly string[];
  supportedDeliveryTypes: readonly KnownDeliveryType[];
  overview: readonly GuideBlock[];
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
}
