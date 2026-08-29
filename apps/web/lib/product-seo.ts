import { OFFICIAL_SOURCES } from "@/content/guides/sources";
import type { OfficialSource } from "@/lib/guides/types";
import type { OfficialPriceReference } from "@/lib/types";

export type ProductSeoContent = {
  metaDescription: string;
  intro: string;
  comparisonPoints: readonly string[];
  faqs: readonly { question: string; answer: string }[];
};

export type ProductEvidenceSource = Pick<OfficialSource, "title" | "url" | "publisher" | "lastCheckedAt">;

const BRAND_EVIDENCE_SOURCES: Record<string, readonly OfficialSource[]> = {
  OpenAI: [OFFICIAL_SOURCES.openaiHelp, OFFICIAL_SOURCES.openaiPlatform, OFFICIAL_SOURCES.openaiTerms],
  Claude: [OFFICIAL_SOURCES.anthropicHelp, OFFICIAL_SOURCES.anthropicDocs, OFFICIAL_SOURCES.anthropicTerms],
  Gemini: [OFFICIAL_SOURCES.geminiHelp, OFFICIAL_SOURCES.geminiApi, OFFICIAL_SOURCES.googleAccount],
  Grok: [OFFICIAL_SOURCES.grokHelp, OFFICIAL_SOURCES.grokApi, OFFICIAL_SOURCES.xHelp],
  X: [OFFICIAL_SOURCES.xHelp, OFFICIAL_SOURCES.xPremium, OFFICIAL_SOURCES.xTerms],
};

export function getProductEvidenceSources(
  brand: string,
  officialReference: OfficialPriceReference | null | undefined,
  guideSources: readonly OfficialSource[] = [],
): readonly ProductEvidenceSource[] {
  const priceSource: OfficialSource | null = officialReference
    ? {
        title: `${officialReference.provider} ${officialReference.plan} 官方价格参考`,
        url: officialReference.url,
        publisher: officialReference.provider,
        lastCheckedAt: officialReference.checked_at,
        kind: "platform_official",
      }
    : null;
  const candidates = [
    ...guideSources,
    ...(priceSource ? [priceSource] : []),
    ...(BRAND_EVIDENCE_SOURCES[brand] || []),
  ];
  const seen = new Set<string>();
  const unique = candidates.filter((source) => {
    if (seen.has(source.url)) return false;
    seen.add(source.url);
    return true;
  });

  return unique.slice(0, 3);
}

const PRODUCT_SEO: Record<string, ProductSeoContent> = {
  "chatgpt-account": {
    metaDescription: "比较 ChatGPT Free 账号公开报价、库存、交付方式、质保与更新时间，查看原始商品信息和店铺来源。",
    intro: "这里聚合明确出售 ChatGPT Free 账号的公开报价，不把 Plus、Pro、中转或 API 服务混入普通账号价格。",
    comparisonPoints: ["确认账号是否需要二次验证，以及交付后能否修改资料。", "区分成品号、首登号、日抛号和共享账号，并分别核对质保。"],
    faqs: [
      { question: "ChatGPT Free 报价为什么差异很大？", answer: "账号地区、注册方式、是否可改资料、质保期限和交付自动化程度都会影响价格。" },
      { question: "这个页面包含 Plus 或 Pro 吗？", answer: "不包含。标题明确的 Plus、Go、K12 和 Pro 会进入各自的商品类型页面。" },
    ],
  },
  "chatgpt-plus": {
    metaDescription: "比较 ChatGPT Plus 公开报价，区分直充、成品号、首登号、体验号、共享号池与中转服务。",
    intro: "ChatGPT Plus 报价按交付形态拆分展示。主最低价只统计可直接比较的 Plus 报价，号池、中转和辅助服务不会冒充标准月订阅低价。",
    comparisonPoints: ["先确认是订阅充值、Plus 成品号还是短期体验账号。", "核对使用周期、首登要求、质保范围和是否允许修改账号资料。", "价格明显偏低时，需结合商品类型和商品原文判断，不能只看金额。"],
    faqs: [
      { question: "为什么页面上的最低价不是所有相关商品最低价？", answer: "标准最低价只比较交付形态相近的报价。共享号池、中转、接码和辅助服务会单独保留，但不参与主价格。" },
      { question: "“不是 Plus”的商品会进入这里吗？", answer: "分类规则会识别否定语境；误分类也可以通过页面纠错入口提交审核。" },
    ],
  },
  "chatgpt-go": {
    metaDescription: "查询 ChatGPT Go 公开报价、库存、交付方式与更新时间，避免与 Plus、Pro 或普通账号混淆。",
    intro: "本页只聚合标题明确标注 ChatGPT Go 的商品，并与 ChatGPT Free、Plus 和 Pro 报价分开比较。",
    comparisonPoints: ["确认商品名称和描述都指向 Go，而不是普通账号或其他订阅。", "核对订阅周期、充值方式、账号归属和售后条件。"],
    faqs: [
      { question: "ChatGPT Go 会和 Plus 一起比较吗？", answer: "不会。Go 与 Plus 是不同商品类型，各自计算报价和最低价。" },
      { question: "标题没有写 Go 的商品会被收录吗？", answer: "不会仅凭描述猜测。标题需要明确出现 Go 商品语境。" },
    ],
  },
  "chatgpt-k12": {
    metaDescription: "比较 ChatGPT K12、Team 与 Business 席位公开报价，查看邀请方式、期限、库存、质保和来源。",
    intro: "K12 页面统一收纳明确的 Team、Business、团队席位、车位和邀请类商品，避免把团队席位误当成个人 Plus 或 Pro。",
    comparisonPoints: ["确认交付是团队邀请、现成席位还是包含管理权限的账号。", "核对席位有效期、退出或被移除后的处理方式，以及是否提供补位。", "Team 与 Business 商品按 K12 口径归类，但原始标题和描述会完整保留。"],
    faqs: [
      { question: "为什么 Team 和 Business 会出现在 K12？", answer: "当前目录把团队邀请、Business、Team、车位和母号类商品统一归入 K12 团队席位口径，方便与个人订阅分开比较。" },
      { question: "团队席位价格可以和个人 Plus 直接比较吗？", answer: "不建议。两者的账号归属、管理权限和失效风险不同，应分别查看。" },
    ],
  },
  "chatgpt-pro-5x": {
    metaDescription: "比较明确标注 ChatGPT Pro 5x 的公开报价、交付形态、库存、质保和更新时间。",
    intro: "本页只把明确标注 Pro 5x 权益的商品纳入标准分类，普通 Pro、20x、共享号池和中转服务不会参与同类最低价。",
    comparisonPoints: ["核对商品是独享账号、充值服务还是共享使用形式。", "确认 5x 标识来自商品标题或明确权益说明，而不是分类猜测。", "查看质保、账号资料修改权限和价格偏低提示。"],
    faqs: [
      { question: "没有写 5x 的 Pro 会出现在这里吗？", answer: "不会。未明确倍率的商品保留在通用 ChatGPT Pro 分类。" },
      { question: "Pro 号池会参与最低价吗？", answer: "共享号池可以作为相关商品展示，但不会参与独享或可直接比较报价的主最低价。" },
    ],
  },
  "chatgpt-pro-20x": {
    metaDescription: "比较明确标注 ChatGPT Pro 20x 的公开报价、库存、交付方式、期限、质保与来源。",
    intro: "ChatGPT Pro 20x 页面只比较明确标注对应倍率的商品，并把账号、充值、号池和服务型报价分开呈现。",
    comparisonPoints: ["确认 20x 权益、使用周期和账号归属是否在商品原文中写明。", "区分独享账号、代充、共享号池和短期使用权。", "价格明显偏低时重点核对限制条件和售后范围。"],
    faqs: [
      { question: "20x 和 5x 会混在一起吗？", answer: "不会。只有标题或明确商品信息确认倍率后才进入对应页面。" },
      { question: "最低价是否代表完整 Pro 20x 账号？", answer: "不一定。请同时查看交付形态；页面会把不可直接比较的号池和服务报价排除在主最低价之外。" },
    ],
  },
  "chatgpt-pro": {
    metaDescription: "查询未明确 5x 或 20x 倍率的 ChatGPT Pro 公开报价、交付方式、库存和更新时间。",
    intro: "通用 ChatGPT Pro 页面收纳明确写明 Pro、但没有足够信息判断 5x 或 20x 倍率的商品，避免系统替商家猜测权益。",
    comparisonPoints: ["先回到商品原文确认具体倍率、周期和账号类型。", "权益不清晰的报价不应直接与明确 5x 或 20x 商品比较。"],
    faqs: [
      { question: "为什么商品没有进入 Pro 5x 或 20x？", answer: "商品信息没有明确倍率时，系统会保留在通用 Pro 分类，不自动推断。" },
      { question: "确认倍率后可以修正分类吗？", answer: "可以通过纠错入口提供来源信息，管理员核验后可重新分类。" },
    ],
  },
  "openai-api-credit": {
    metaDescription: "比较 OpenAI API 额度与访问服务公开报价，查看额度口径、交付方式、库存、更新时间和来源。",
    intro: "OpenAI API 额度与 ChatGPT 会员订阅分开统计。本页保留额度、令牌访问和相关 API 服务的原始口径。",
    comparisonPoints: ["确认报价单位是余额、额度、调用量还是一段时间的访问权限。", "核对是否为官方 API、代理访问或中转服务，并查看使用限制。"],
    faqs: [
      { question: "API 额度等于 ChatGPT Plus 吗？", answer: "不等于。API 使用与 ChatGPT 网页会员是不同产品和计费口径。" },
      { question: "为什么有些报价不参与最低价？", answer: "额度单位或交付方式无法直接比较时，系统会保留来源，但不把它当作标准同类价格。" },
    ],
  },
  "chatgpt-access-service": {
    metaDescription: "查看 ChatGPT 与 Codex 接码、验证、提链、邮箱等周边服务公开报价，不与会员价格混算。",
    intro: "这里集中展示 ChatGPT 与 Codex 的接码、验证、提链、邮箱和辅助开通服务，避免它们因低价进入 Plus 或账号目录。",
    comparisonPoints: ["确认购买的是辅助服务而不是账号、订阅或 API 额度。", "查看服务适用范围、成功条件、退款规则和交付方式。"],
    faqs: [
      { question: "周边服务会拉低 Plus 最低价吗？", answer: "不会。周边服务是独立标准分类，不参与 Plus 或 Pro 的主最低价。" },
      { question: "为什么还要保留这些商品？", answer: "它们与目标产品相关，独立展示可以保留公开市场信息，同时避免误导会员价格。" },
    ],
  },
  "codex-access": {
    metaDescription: "比较 Codex 账号与访问服务公开报价，区分账号、共享访问、中转服务、期限和质保。",
    intro: "Codex 页面聚合明确面向 Codex 的账号与访问商品，并把账号交付、共享使用和中转服务分开判断。",
    comparisonPoints: ["确认交付的是可登录账号、团队席位、共享访问还是中转接口。", "核对可用环境、使用期限、接码要求和售后范围。"],
    faqs: [
      { question: "Codex 商品会和 ChatGPT Plus 混在一起吗？", answer: "不会按关键词直接混算。明确出售 Codex 访问的商品进入本页，Plus 仅在自身页面比较。" },
      { question: "中转服务是否参与账号最低价？", answer: "不参与。中转和账号是不同交付形态，会分别展示。" },
    ],
  },
  "claude-pro": {
    metaDescription: "比较 Claude Pro 公开报价、库存、交付方式、使用期限、质保与店铺更新时间。",
    intro: "Claude Pro 页面只聚合明确的 Pro 订阅或账号商品，并把普通 Claude 账号与 API 访问分开。",
    comparisonPoints: ["区分订阅充值、Pro 成品号、短期账号和共享使用。", "核对账号地区、登录验证、使用周期和质保条款。"],
    faqs: [
      { question: "普通 Claude 账号会进入 Pro 最低价吗？", answer: "不会。没有明确 Pro 语境的账号会进入 Claude 账号分类。" },
      { question: "Claude API 报价会在这里展示吗？", answer: "不会混入主报价。API 访问有独立目录。" },
    ],
  },
  "claude-account": {
    metaDescription: "查询 Claude 普通账号公开报价、库存、交付方式、登录要求、质保和更新时间。",
    intro: "本页收录明确出售 Claude 账号、但未确认 Pro 订阅的商品，避免普通账号被误当作 Claude Pro。",
    comparisonPoints: ["确认账号是否带订阅、能否修改资料以及是否需要二次验证。", "根据成品号、首登号、日抛号和共享形式分别比较。"],
    faqs: [
      { question: "Claude 账号一定包含 Pro 吗？", answer: "不一定。只有商品明确说明 Pro 权益时才进入 Claude Pro 页面。" },
      { question: "购买前最需要核对什么？", answer: "重点查看登录方式、资料修改权限、账号地区、质保期限和退款条件。" },
    ],
  },
  "claude-api-access": {
    metaDescription: "比较 Claude API 访问与额度服务公开报价，查看计费口径、交付方式、库存和来源。",
    intro: "Claude API 访问与 Claude 网页账号、Pro 订阅分开统计，报价需结合额度单位和接入方式判断。",
    comparisonPoints: ["确认价格对应余额、调用额度、时间套餐还是代理访问。", "核对接口地址、模型范围、速率限制和余额有效期。"],
    faqs: [
      { question: "Claude API 和 Claude Pro 是同一项服务吗？", answer: "不是。网页订阅与 API 访问是不同产品，不能直接比较价格。" },
      { question: "中转 API 会被保留吗？", answer: "会按实际交付形态标注，但不会伪装成官方额度或会员订阅。" },
    ],
  },
  "gemini-advanced": {
    metaDescription: "比较 Gemini Advanced 公开报价、库存、充值或账号交付方式、使用期限和更新时间。",
    intro: "Gemini Advanced 页面聚合明确的 Advanced 订阅商品，并与普通 Gemini 账号和 Gemini API 分开。",
    comparisonPoints: ["确认是订阅充值、带权益账号还是短期共享使用。", "核对地区、周期、账号归属、资料修改权限和售后。"],
    faqs: [
      { question: "普通 Gemini 账号会参与 Advanced 最低价吗？", answer: "不会。没有明确 Advanced 权益的账号进入普通账号分类。" },
      { question: "如何判断价格是否明显偏低？", answer: "查看交付方式、周期和质保；体验号、共享号或辅助服务通常不能与完整订阅直接比较。" },
    ],
  },
  "gemini-account": {
    metaDescription: "查询 Gemini 普通账号公开报价、库存、交付方式、账号限制、质保和更新时间。",
    intro: "本页展示明确出售 Gemini 账号、但不属于 Advanced 订阅或 API 额度的公开商品。",
    comparisonPoints: ["确认账号地区、注册方式、登录验证和资料修改权限。", "普通邮箱、教程或工具不会仅凭分类名称进入账号报价。"],
    faqs: [
      { question: "Gemini 账号包含 Advanced 吗？", answer: "不一定。商品需要明确标注 Advanced 权益才进入对应页面。" },
      { question: "普通 Gmail 会被收录吗？", answer: "不会仅因为位于 Gemini 分类下就公开，标题还需要有明确的目标商品语境。" },
    ],
  },
  "gemini-api-access": {
    metaDescription: "比较 Gemini API 访问、额度和中转服务公开报价，查看计费单位、限制、库存和来源。",
    intro: "Gemini API 页面按额度和访问方式展示公开报价，不与 Gemini Advanced 或普通账号价格混算。",
    comparisonPoints: ["确认价格单位、可用模型、调用限制和额度有效期。", "区分直接额度、代理访问和中转服务。"],
    faqs: [
      { question: "Gemini API 价格能和 Advanced 会员比较吗？", answer: "不能。API 与网页订阅的使用方式和计费单位不同。" },
      { question: "为什么必须查看商品原文？", answer: "API 报价常按余额、调用量或时间套餐计价，金额本身不能完整表达单位。" },
    ],
  },
  "grok-super": {
    metaDescription: "比较 SuperGrok 公开报价、库存、账号或充值交付方式、使用期限、质保与来源。",
    intro: "SuperGrok 与普通 Grok 账号、Grok API 和 X Premium 分开归类；附赠权益不会改变标题明确出售的主商品。",
    comparisonPoints: ["确认主商品是 SuperGrok，而不是附赠 SuperGrok 的其他订阅。", "核对账号归属、订阅周期、登录限制和质保。"],
    faqs: [
      { question: "包含 X Premium 的 SuperGrok 会归到哪里？", answer: "如果标题明确出售 SuperGrok，附赠 X Premium 不会改变主分类。" },
      { question: "普通 Grok 账号会参与最低价吗？", answer: "不会。普通账号在 Grok 账号页面单独比较。" },
    ],
  },
  "grok-account": {
    metaDescription: "查询 Grok 普通账号公开报价、库存、功能限制、交付方式、质保和更新时间。",
    intro: "本页展示明确出售 Grok 账号、但不属于 SuperGrok、API 或 X Premium 订阅的商品。",
    comparisonPoints: ["确认账号是否带付费权益，以及网页版、客户端等使用限制。", "极低价格常对应普通号、体验号或功能受限账号，需要结合描述判断。"],
    faqs: [
      { question: "低至几分钱的 Grok 账号可靠吗？", answer: "价格可能真实，但通常对应普通账号、体验或功能限制。页面会保留报价并提示价格明显偏低，而不是直接当作完整付费订阅。" },
      { question: "Grok 账号和 X Premium 是一回事吗？", answer: "不是。X Premium 是独立产品系列，按 Basic、Premium 和 Premium+ 分类。" },
    ],
  },
  "grok-api-access": {
    metaDescription: "比较 Grok API 访问、额度与中转服务公开报价，查看计费单位、限制、库存和来源。",
    intro: "Grok API 页面聚合明确的接口访问与额度商品，不与 Grok 账号或 SuperGrok 订阅混算。",
    comparisonPoints: ["确认额度单位、模型范围、速率限制和有效期。", "区分直接 API 额度、代理访问和中转服务。"],
    faqs: [
      { question: "Grok API 报价包含账号吗？", answer: "通常不包含。API 访问和网页账号是不同交付形态，应以原始商品说明为准。" },
      { question: "不同额度套餐可以直接按总价比较吗？", answer: "不建议。需要先统一额度、调用量或有效期口径。" },
    ],
  },
  "x-premium-basic": {
    metaDescription: "查询 X Premium Basic 公开报价、库存、充值方式、使用期限和更新时间。",
    intro: "X Premium Basic 与 Premium、Premium+ 以及 Grok 商品独立分类，只收录明确标注 Basic 档位的报价。",
    comparisonPoints: ["确认档位名称明确为 Basic，并核对充值账号和地区要求。", "查看订阅周期、代充方式和售后范围。"],
    faqs: [
      { question: "为什么当前可能看不到 Basic 报价？", answer: "最近更新的数据中没有符合分类和展示条件的报价时，页面会保留商品说明，但不展示占位价格。" },
      { question: "Basic 会和 Premium 混算吗？", answer: "不会，三个档位分别统计报价。" },
    ],
  },
  "x-premium": {
    metaDescription: "比较 X Premium 会员充值公开报价、库存、充值方式、订阅周期、质保和店铺来源。",
    intro: "本页只比较明确的 X Premium 中间档会员充值或账号商品，并与 Basic、Premium+ 和 Grok 分开。",
    comparisonPoints: ["确认档位是 Premium，而不是 Basic、Premium+ 或附赠权益。", "核对代充地区、订阅周期、账号要求和退款条件。"],
    faqs: [
      { question: "X Premium 包含 Grok 时会归到哪里？", answer: "如果标题明确出售 X Premium，附带的 Grok 权益不会改变 X Premium 主分类。" },
      { question: "三个 X Premium 档位会一起算最低价吗？", answer: "不会。Basic、Premium 和 Premium+ 各自计算报价。" },
    ],
  },
  "x-premium-plus": {
    metaDescription: "比较 X Premium+ 会员充值公开报价、库存、订阅周期、交付方式、质保和来源。",
    intro: "X Premium+ 页面只收录明确标注最高档位的会员充值或账号商品，不与 X Premium、Basic 或 SuperGrok 混算。",
    comparisonPoints: ["确认标题明确写有 Premium+，避免与 Premium 中间档混淆。", "核对充值地区、账号状态、订阅周期和售后规则。"],
    faqs: [
      { question: "SuperGrok 附赠 X Premium+ 会归到本页吗？", answer: "如果标题主商品是 SuperGrok，会保留在 SuperGrok 页面；主商品明确是 X Premium+ 时才进入本页。" },
      { question: "报价数量少时最低价可靠吗？", answer: "样本少时价格代表性有限，应重点查看更新时间、库存和原始商品说明。" },
    ],
  },
};

const PRODUCT_OG_TITLES: Record<string, string> = {
  "chatgpt-account": "ChatGPT Free",
  "chatgpt-plus": "ChatGPT Plus",
  "chatgpt-go": "ChatGPT Go",
  "chatgpt-k12": "ChatGPT K12 / Team",
  "chatgpt-pro-5x": "ChatGPT Pro 5x",
  "chatgpt-pro-20x": "ChatGPT Pro 20x",
  "chatgpt-pro": "ChatGPT Pro",
  "openai-api-credit": "OpenAI API Credit",
  "chatgpt-access-service": "ChatGPT / Codex Services",
  "codex-access": "Codex Access",
  "claude-pro": "Claude Pro",
  "claude-account": "Claude Account",
  "claude-api-access": "Claude API",
  "gemini-advanced": "Gemini Advanced",
  "gemini-account": "Gemini Account",
  "gemini-api-access": "Gemini API",
  "grok-super": "SuperGrok",
  "grok-account": "Grok Account",
  "grok-api-access": "Grok API",
  "x-premium-basic": "X Premium Basic",
  "x-premium": "X Premium",
  "x-premium-plus": "X Premium+",
};

export function getProductSeoContent(slug: string, displayName: string, fallbackDescription: string): ProductSeoContent {
  return PRODUCT_SEO[slug] || {
    metaDescription: fallbackDescription,
    intro: fallbackDescription,
    comparisonPoints: [
      `核对 ${displayName} 的交付形态、使用期限、库存和质保。`,
      "购买前回到原始店铺确认最新价格与商品限制。",
    ],
    faqs: [
      { question: "页面报价是否由本站销售？", answer: "不是。本站只聚合公开报价，不参与交易、收款、交付或售后。" },
      { question: "为什么价格会变化？", answer: "店铺会调整价格和库存，页面展示最近一次成功更新的结果。" },
    ],
  };
}

export function getProductOgTitle(slug: string) {
  return PRODUCT_OG_TITLES[slug] || slug.split("-").map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
}
