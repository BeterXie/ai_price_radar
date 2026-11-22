const PRODUCT_SLUG_ALIASES: Readonly<Record<string, string>> = {
  "chatgpt-pro-5x": "chatgpt-pro-100",
  "chatgpt-pro-20x": "chatgpt-pro-200",
};

export function canonicalProductSlug(slug: string): string {
  return Object.prototype.hasOwnProperty.call(PRODUCT_SLUG_ALIASES, slug) ? PRODUCT_SLUG_ALIASES[slug] : slug;
}

export const DELIVERY_TYPE_LABELS: Record<string, string> = {
  subscription_recharge: "官方直充 / 代充",
  finished_account: "成品账号",
  semi_finished_account: "半成品 / 首登号",
  team_seat: "团队席位",
  card_code: "卡密 / 兑换码",
  trial_account: "日抛 / 体验号",
  shared_pool: "共享号池",
  relay_api: "中转 / 反代",
  api_credit: "API 额度",
  verification_service: "验证 / 接码服务",
  virtual_card: "虚拟卡",
  gift_card: "礼品卡",
  hosting_service: "服务器租用",
  unknown: "形态待确认",
};

export const PERIOD_LABELS: Record<string, string> = {
  one_day: "1 天 / 日抛",
  one_week: "1 周",
  fifteen_days: "15 天",
  three_months: "3 个月",
  six_months: "6 个月",
  one_month: "1 个月",
  one_year: "1 年",
  unknown: "期限未注明",
};

export const WARRANTY_LABELS: Record<string, string> = {
  none: "无质保",
  first_login: "仅首登质保",
  one_hour: "1 小时",
  one_day: "24 小时",
  three_days: "3 天",
  seven_days: "7 天",
  fifteen_days: "15 天",
  subscription_term: "订阅期",
  unknown: "质保未注明",
};

export const SCENARIO_LABELS: Record<string, string> = {
  web: "网页",
  desktop: "客户端",
  codex: "Codex",
  api: "API",
  relay: "中转 / 反代",
};

export const BRAND_TABS = ["OpenAI", "Claude", "Gemini", "Grok", "X", "Cursor", "MUSE", "JEV"] as const;
export type BrandName = (typeof BRAND_TABS)[number];
export function brandCatalogPath(brand: string): string {
  return BRAND_TABS.includes(brand as BrandName)
    ? `/brands/${brand.toLowerCase()}`
    : brand ? `/products?brand=${encodeURIComponent(brand)}` : "/products";
}

export function brandFromSlug(slug: string): BrandName | undefined {
  return BRAND_TABS.find((brand) => brand.toLowerCase() === slug);
}
export const AUXILIARY_CATEGORIES = ["邮箱", "接码 / 验证", "虚拟卡", "礼品卡", "社媒账号", "Apple ID", "VPS"] as const;
export const isAuxiliaryCategory = (category: string) => AUXILIARY_CATEGORIES.some((name) => name === category);
export const STANDALONE_PRODUCTS = [{ label: "手机接码", slug: "chatgpt-access-service", brand: "接码 / 验证", name: "OpenAI / ChatGPT 接码" }] as const;
export const PRODUCT_CATEGORIES = [...BRAND_TABS, ...AUXILIARY_CATEGORIES] as const;
export type ProductCategory = (typeof PRODUCT_CATEGORIES)[number];
export const RELAY_CATALOG_HREF = "/products?brand=%E4%B8%AD%E8%BD%AC%E7%AB%99";

export const OFFICIAL_PLAN_SOURCES: Partial<Record<ProductCategory, string>> = {
  OpenAI: "https://help.openai.com/en/articles/9793128-about-chatgpt-pro-tiers",
  Claude: "https://claude.com/pricing",
  Gemini: "https://one.google.com/intl/en/about/google-ai-plans/",
  Grok: "https://x.ai/pricing",
  X: "https://docs.x.ai/x-subscription/overview",
  Cursor: "https://cursor.com/pricing",
};

// API access, seller labels and uncertain tiers are useful filters, but must
// not be presented as additional official account plans.
export const PRODUCT_TABS: Record<ProductCategory, { label: string; slug: string; other?: boolean }[]> = {
  OpenAI: [
    { label: "Free", slug: "chatgpt-account" },
    { label: "Plus", slug: "chatgpt-plus" },
    { label: "Go", slug: "chatgpt-go" },
    { label: "Pro 100 / 5x", slug: "chatgpt-pro-100" },
    { label: "Pro 200 / 20x", slug: "chatgpt-pro-200" },
    { label: "Pro 500", slug: "chatgpt-pro-500" },
    { label: "Business / Team", slug: "chatgpt-business" },
    { label: "Edu", slug: "chatgpt-edu" },
    { label: "Enterprise", slug: "chatgpt-enterprise" },
    { label: "Pro 档位待确认", slug: "chatgpt-pro", other: true },
    { label: "K12 商家标记", slug: "chatgpt-k12", other: true },
    { label: "OpenAI API", slug: "openai-api-credit", other: true },
  ],
  Claude: [
    { label: "Pro", slug: "claude-pro" },
    { label: "Max 5x", slug: "claude-max-5x" },
    { label: "Max 20x", slug: "claude-pro-20x" },
    { label: "Max 档位待确认", slug: "claude-max", other: true },
    { label: "Team", slug: "claude-team" },
    { label: "Enterprise", slug: "claude-enterprise" },
    { label: "基础账号", slug: "claude-account", other: true },
    { label: "Claude API", slug: "claude-api-access", other: true },
    { label: "订阅等级待确认", slug: "claude-subscription", other: true },
  ],
  Gemini: [
    { label: "AI Plus", slug: "gemini-plus" },
    { label: "AI Pro", slug: "gemini-pro" },
    { label: "Ultra 档位待确认", slug: "gemini-ultra", other: true },
    { label: "Ultra 5x", slug: "gemini-ultra-5x" },
    { label: "Ultra 20x", slug: "gemini-ultra-20x" },
    { label: "Advanced 历史名称", slug: "gemini-advanced", other: true },
    { label: "基础账号", slug: "gemini-account", other: true },
    { label: "Gemini API", slug: "gemini-api-access", other: true },
    { label: "订阅等级待确认", slug: "gemini-subscription", other: true },
  ],
  Grok: [
    { label: "SuperGrok 旧名称", slug: "grok-super", other: true },
    { label: "SuperGrok Heavy 旧名称", slug: "grok-heavy", other: true },
    { label: "Plus", slug: "grok-plus" },
    { label: "Premium", slug: "grok-premium" },
    { label: "Super", slug: "grok-plan-super" },
    { label: "Ultra", slug: "grok-ultra" },
    { label: "Teams", slug: "grok-team" },
    { label: "Enterprise", slug: "grok-enterprise" },
    { label: "基础账号", slug: "grok-account", other: true },
    { label: "Grok API", slug: "grok-api-access", other: true },
    { label: "订阅等级待确认", slug: "grok-subscription", other: true },
  ],
  X: [
    { label: "基础账号", slug: "x-account", other: true },
    { label: "Plus", slug: "x-subscription-plus" },
    { label: "Premium 统一订阅", slug: "x-subscription-premium" },
    { label: "Super", slug: "x-subscription-super" },
    { label: "Ultra", slug: "x-subscription-ultra" },
    { label: "Teams", slug: "x-subscription-teams" },
    { label: "Enterprise", slug: "x-subscription-enterprise" },
    { label: "Basic 原套餐", slug: "x-premium-basic", other: true },
    { label: "X Premium 原套餐", slug: "x-premium", other: true },
    { label: "Premium+ 原套餐", slug: "x-premium-plus", other: true },
  ],
  Cursor: [
    { label: "Pro 旧名称", slug: "cursor-pro", other: true },
    { label: "Pro+ 旧名称", slug: "cursor-pro-plus", other: true },
    { label: "Cursor Plus", slug: "cursor-plus" },
    { label: "Cursor Premium", slug: "cursor-premium" },
    { label: "Cursor Super", slug: "cursor-super" },
    { label: "Cursor Ultra", slug: "cursor-ultra" },
    { label: "Teams / Business", slug: "cursor-business" },
    { label: "Enterprise", slug: "cursor-enterprise" },
    { label: "基础账号", slug: "cursor-account", other: true },
    { label: "订阅等级待确认", slug: "cursor-subscription", other: true },
  ],
  MUSE: [
    { label: "账号 / 成品号", slug: "muse-account", other: true },
    { label: "API Key / 额度", slug: "muse-api-credit", other: true },
    { label: "邀请码 / 激活码", slug: "muse-invite", other: true },
    { label: "订阅等级待确认", slug: "muse-subscription", other: true },
  ],
  JEV: [
    { label: "账号 / 成品号", slug: "jev-account", other: true },
    { label: "API Key / 额度", slug: "jev-api-credit", other: true },
    { label: "邀请码 / 激活码", slug: "jev-invite", other: true },
    { label: "订阅等级待确认", slug: "jev-subscription", other: true },
  ],
  "邮箱": [
    { label: "Gmail / Google", slug: "email-gmail", other: true },
    { label: "Outlook / Hotmail", slug: "email-outlook", other: true },
    { label: "教育邮箱", slug: "email-education", other: true },
    { label: "iCloud", slug: "email-icloud", other: true },
    { label: "其他邮箱", slug: "email-account", other: true },
  ],
  "接码 / 验证": [
    { label: "OpenAI / ChatGPT", slug: "chatgpt-access-service", other: true },
    { label: "Google / Gemini", slug: "verification-google", other: true },
    { label: "Claude / Anthropic", slug: "verification-claude", other: true },
    { label: "Cursor", slug: "verification-cursor", other: true },
    { label: "MUSE", slug: "muse-access-service", other: true },
    { label: "JEV", slug: "jev-access-service", other: true },
    { label: "社媒验证", slug: "verification-social", other: true },
    { label: "PayPal", slug: "verification-paypal", other: true },
    { label: "通用接码", slug: "verification-general", other: true },
    { label: "真人 / KYC", slug: "verification-kyc", other: true },
  ],
  "虚拟卡": [{ label: "虚拟卡", slug: "virtual-card", other: true }],
  "礼品卡": [{ label: "礼品卡", slug: "gift-card", other: true }],
  "社媒账号": [{ label: "社媒账号", slug: "social-media-account", other: true }],
  "Apple ID": [{ label: "Apple ID / 苹果账号", slug: "apple-id-account", other: true }],
  VPS: [{ label: "VPS / 云服务器", slug: "vps", other: true }],
};

export const ALL_PRODUCTS = PRODUCT_CATEGORIES.flatMap((brand) =>
  PRODUCT_TABS[brand].map((product) => ({
    brand,
    ...product,
  }))
);
