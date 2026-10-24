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
  unknown: "形态待确认",
};

export const PERIOD_LABELS: Record<string, string> = {
  one_day: "1 天 / 日抛",
  one_week: "1 周",
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

export const BRAND_TABS = ["OpenAI", "Claude", "Gemini", "Grok", "X", "Cursor"] as const;
export type BrandName = (typeof BRAND_TABS)[number];

export const PRODUCT_TABS: Record<BrandName, { label: string; slug: string }[]> = {
  OpenAI: [
    { label: "Free", slug: "chatgpt-account" },
    { label: "Plus", slug: "chatgpt-plus" },
    { label: "Pro 5x", slug: "chatgpt-pro-5x" },
    { label: "Pro 20x", slug: "chatgpt-pro-20x" },
    { label: "Pro 倍率未注明", slug: "chatgpt-pro" },
    { label: "Go", slug: "chatgpt-go" },
    { label: "Business / Team", slug: "chatgpt-business" },
    { label: "Edu", slug: "chatgpt-edu" },
    { label: "Enterprise", slug: "chatgpt-enterprise" },
    { label: "K12 商家标记", slug: "chatgpt-k12" },
    { label: "OpenAI API", slug: "openai-api-credit" },
    { label: "手机接码", slug: "chatgpt-access-service" },
  ],
  Claude: [
    { label: "Pro", slug: "claude-pro" },
    { label: "Max 5x", slug: "claude-max-5x" },
    { label: "Max 20x", slug: "claude-pro-20x" },
    { label: "Max 倍率未注明", slug: "claude-max" },
    { label: "Team", slug: "claude-team" },
    { label: "Enterprise", slug: "claude-enterprise" },
    { label: "Claude 账号", slug: "claude-account" },
    { label: "Claude API", slug: "claude-api-access" },
    { label: "订阅等级未注明", slug: "claude-subscription" },
  ],
  Gemini: [
    { label: "AI Plus", slug: "gemini-plus" },
    { label: "AI Pro", slug: "gemini-pro" },
    { label: "AI Ultra", slug: "gemini-ultra" },
    { label: "Ultra 5x", slug: "gemini-ultra-5x" },
    { label: "Ultra 20x", slug: "gemini-ultra-20x" },
    { label: "Advanced 历史名称", slug: "gemini-advanced" },
    { label: "Gemini 账号", slug: "gemini-account" },
    { label: "Gemini API", slug: "gemini-api-access" },
    { label: "订阅等级未注明", slug: "gemini-subscription" },
  ],
  Grok: [
    { label: "SuperGrok", slug: "grok-super" },
    { label: "SuperGrok Heavy", slug: "grok-heavy" },
    { label: "Plus", slug: "grok-plus" },
    { label: "Premium", slug: "grok-premium" },
    { label: "Super", slug: "grok-plan-super" },
    { label: "Ultra", slug: "grok-ultra" },
    { label: "Grok 账号", slug: "grok-account" },
    { label: "Grok API", slug: "grok-api-access" },
    { label: "订阅等级未注明", slug: "grok-subscription" },
  ],
  X: [
    { label: "Basic", slug: "x-premium-basic" },
    { label: "Premium", slug: "x-premium" },
    { label: "Premium+", slug: "x-premium-plus" },
  ],
  Cursor: [
    { label: "Cursor Pro", slug: "cursor-pro" },
    { label: "Cursor Pro+", slug: "cursor-pro-plus" },
    { label: "Cursor Ultra", slug: "cursor-ultra" },
    { label: "Cursor Plus", slug: "cursor-plus" },
    { label: "Cursor Premium", slug: "cursor-premium" },
    { label: "Cursor Super", slug: "cursor-super" },
    { label: "Teams / Business", slug: "cursor-business" },
    { label: "Enterprise", slug: "cursor-enterprise" },
    { label: "Cursor 账号", slug: "cursor-account" },
    { label: "订阅等级未注明", slug: "cursor-subscription" },
  ],
};

export const ALL_PRODUCTS = BRAND_TABS.flatMap((brand) =>
  PRODUCT_TABS[brand].map((product) => ({
    brand,
    ...product,
  }))
);
