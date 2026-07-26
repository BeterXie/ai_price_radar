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
];
