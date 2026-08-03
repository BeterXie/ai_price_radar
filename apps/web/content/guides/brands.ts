import type { BrandGuide } from "@/lib/guides/types";
import { LAST_REVIEWED_AT, OFFICIAL_SOURCES } from "./sources";

export const brandGuideEntries = [
  {
    brand: "openai",
    title: "OpenAI 产品、账号与 API 指南",
    description: "区分 ChatGPT Free、Plus、Go、Pro、团队席位、Codex 与 OpenAI API，理解第三方交付的控制权差异。",
    overview: [
      { type: "paragraph", text: "OpenAI 品牌下既有 ChatGPT 网页产品，也有 Codex 访问与按量计费的 API。网页订阅不会自动附带 API 额度。" },
      {
        type: "comparison",
        title: "先区分使用入口",
        columns: ["类别", "适合场景", "计费或权限"],
        rows: [
          ["ChatGPT 个人套餐", "网页和客户端对话", "账号订阅与套餐权限"],
          ["Team / Business / K12", "组织工作区", "管理员分配的席位"],
          ["Codex", "编码代理与开发工作流", "依赖账号或组织提供的访问权限"],
          ["OpenAI API", "程序调用模型", "项目额度、API Key 与按量计费"],
        ],
      },
    ],
    productSlugs: [
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
    ],
    planNotes: [
      "Free、Plus、Go 与 Pro 是不同账号套餐；5x、20x 等商品口径必须回到原商品确认，不由本站推断。",
      "团队席位受工作区管理员控制，不等于个人拥有组织或席位。",
      "API 与网页会员分别计费，API Key 需要独立保护和用量监控。",
    ],
    commonDeliveryTypes: ["subscription_recharge", "finished_account", "team_seat", "api_credit", "shared_pool", "relay_api"],
    riskNotes: [
      "第三方账号可能缺少邮箱或恢复渠道控制权；不要保存隐私、机密或支付信息。",
      "只从 OpenAI 官方页面核对套餐、账单和 API 用量，第三方商品规则以原页面为准。",
    ],
    officialSources: [OFFICIAL_SOURCES.openaiHelp, OFFICIAL_SOURCES.openaiPlatform, OFFICIAL_SOURCES.openaiTerms],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    brand: "claude",
    title: "Claude 账号、Pro 与 API 指南",
    description: "了解 Claude 基础账号、Claude Pro 与 Claude API 的区别，并核对账号、充值和中转交付风险。",
    overview: [
      { type: "paragraph", text: "Claude 网页账号用于对话体验，Pro 是个人付费套餐；Anthropic API 通过 Console 单独管理与计费。" },
      {
        type: "comparison",
        columns: ["类别", "主要用途", "需要核对"],
        rows: [
          ["基础账号", "普通网页访问", "登录方式与控制权"],
          ["Claude Pro", "更高网页使用额度与付费功能", "套餐状态、期限与续费"],
          ["Claude API", "程序调用 Claude", "Key、额度、模型与速率限制"],
        ],
      },
    ],
    productSlugs: ["claude-pro", "claude-account", "claude-api-access"],
    planNotes: [
      "普通 Claude 账号不等于 Pro；必须在官方账户页核对付费状态。",
      "Pro 订阅不包含 Anthropic API 用量，两者不能直接比价。",
      "中转 API 由第三方处理请求，不属于 Anthropic 官方 API。",
    ],
    commonDeliveryTypes: ["subscription_recharge", "finished_account", "semi_finished_account", "api_credit", "relay_api"],
    riskNotes: ["共享或他人注册账号存在找回与隐私风险。", "API Key 不应写入公开代码；第三方中转不处理敏感数据。"],
    officialSources: [OFFICIAL_SOURCES.anthropicHelp, OFFICIAL_SOURCES.anthropicDocs, OFFICIAL_SOURCES.anthropicTerms],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    brand: "gemini",
    title: "Gemini 账号、Advanced 与 API 指南",
    description: "区分 Gemini 基础账号、Gemini Advanced / Google AI 套餐和 Gemini API 的账号及计费边界。",
    overview: [
      { type: "paragraph", text: "Gemini Apps 依赖 Google 账号；付费 Gemini 套餐与面向开发者的 Gemini API 是不同入口和计费体系。" },
      {
        type: "comparison",
        columns: ["类别", "账号体系", "重点核验"],
        rows: [
          ["Gemini 基础账号", "Google 账号", "账号归属、登录与数据设置"],
          ["Gemini Advanced", "Google 账号中的付费权益", "套餐名称、期限与订阅状态"],
          ["Gemini API", "Google AI 开发者服务", "API Key、项目、额度与账单"],
        ],
      },
    ],
    productSlugs: ["gemini-advanced", "gemini-account", "gemini-api-access"],
    planNotes: [
      "基础账号不保证包含 Advanced 付费权益。",
      "兑换码可能受账号、地区、套餐或新用户资格限制。",
      "Gemini API 额度不能替代 Gemini Apps 的付费订阅。",
    ],
    commonDeliveryTypes: ["subscription_recharge", "finished_account", "card_code", "api_credit", "relay_api"],
    riskNotes: ["Google 账号可能连接邮箱、云盘等个人数据，第三方账号尤其不应承载私人资料。", "API 与中转服务需分别核对数据处理方。"],
    officialSources: [OFFICIAL_SOURCES.geminiHelp, OFFICIAL_SOURCES.geminiApi, OFFICIAL_SOURCES.googleAccount],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    brand: "grok",
    title: "Grok、SuperGrok 与 xAI API 指南",
    description: "区分 Grok 基础账号、SuperGrok 订阅和 xAI API，避免把 X Premium 附带权益误作同一商品。",
    overview: [
      { type: "paragraph", text: "Grok 和 SuperGrok 属于 xAI 产品体系；xAI API 面向程序调用。X Premium 是 X 平台的独立产品系列，即使某些权益有关联也不应混算。" },
      {
        type: "comparison",
        columns: ["类别", "主要用途", "不应混同"],
        rows: [
          ["Grok 账号", "基础产品访问", "SuperGrok 付费权益"],
          ["SuperGrok", "付费 Grok 使用", "X Premium 档位"],
          ["xAI API", "程序调用模型", "网页账号和订阅"],
        ],
      },
    ],
    productSlugs: ["grok-super", "grok-account", "grok-api-access"],
    planNotes: [
      "商品标题的主产品决定分类；附带权益不改变主商品。",
      "普通账号、短期账号与 SuperGrok 完整订阅不能直接比较。",
      "第三方中转不等于 xAI 官方 API。",
    ],
    commonDeliveryTypes: ["subscription_recharge", "finished_account", "trial_account", "api_credit", "relay_api"],
    riskNotes: ["确认账号登录入口、恢复渠道和隐私边界。", "中转请求可能由第三方记录，不发送敏感或保密数据。"],
    officialSources: [OFFICIAL_SOURCES.grokHelp, OFFICIAL_SOURCES.grokApi],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    brand: "x",
    title: "X Premium 档位与充值指南",
    description: "区分 X Premium Basic、Premium 和 Premium+ 三个档位，核对充值账号、周期、续费与账号控制权。",
    overview: [
      { type: "paragraph", text: "X Premium 商品按 Basic、Premium 和 Premium+ 分档。具体功能、资格和价格可能调整，购买后应以 X 官方账户页显示为准。" },
      {
        type: "comparison",
        columns: ["档位", "目录口径", "购买前确认"],
        rows: [
          ["Premium Basic", "基础付费档位", "标题明确写明 Basic"],
          ["Premium", "中间档位", "不要与 Basic 或 Premium+ 混淆"],
          ["Premium+", "最高档位目录", "确认 + 标识、周期和实际权益"],
        ],
      },
    ],
    productSlugs: ["x-premium-basic", "x-premium", "x-premium-plus"],
    planNotes: [
      "三个档位分别统计；商品主标题需明确对应档位。",
      "代充前核对目标 X 账号、套餐与期限，避免充错账号。",
      "成品 X 账号的邮箱、恢复渠道和 MFA 控制权需单独确认。",
    ],
    commonDeliveryTypes: ["subscription_recharge", "finished_account"],
    riskNotes: ["账号共享或转让可能受官方条款限制。", "第三方账号不要绑定支付方式，也不要存放私信、身份或业务敏感数据。"],
    officialSources: [OFFICIAL_SOURCES.xHelp, OFFICIAL_SOURCES.xTerms],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
] as const satisfies readonly BrandGuide[];
