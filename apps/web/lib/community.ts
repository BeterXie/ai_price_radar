function safeHttpsUrl(value: string | undefined) {
  const candidate = value?.trim() || "";
  try {
    const parsed = new URL(candidate);
    return parsed.protocol === "https:" && !parsed.username && !parsed.password ? parsed.href : "";
  } catch {
    return "";
  }
}

function safeBusinessEmail(value: string | undefined) {
  const candidate = value?.trim().toLowerCase() || "";
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(candidate) ? candidate : "";
}

export const GITHUB_REPOSITORY_URL = safeHttpsUrl(process.env.NEXT_PUBLIC_GITHUB_REPOSITORY_URL);
export const BUSINESS_EMAIL = safeBusinessEmail(process.env.NEXT_PUBLIC_BUSINESS_EMAIL);

export type SupportMethod = {
  id: "wechat" | "alipay";
  label: string;
  qrUrl: string;
};

function safeQrUrl(value: string | undefined) {
  const candidate = value?.trim() || "";
  if (candidate.startsWith("/") && !candidate.startsWith("//")) return candidate;
  try {
    return new URL(candidate).protocol === "https:" ? candidate : "";
  } catch {
    return "";
  }
}

const configuredSupportMethods: SupportMethod[] = [
  {
    id: "wechat",
    label: "微信支付",
    qrUrl: safeQrUrl(process.env.NEXT_PUBLIC_SUPPORT_WECHAT_QR_URL),
  },
  {
    id: "alipay",
    label: "支付宝",
    qrUrl: safeQrUrl(process.env.NEXT_PUBLIC_SUPPORT_ALIPAY_QR_URL),
  },
];

export const SUPPORT_METHODS = configuredSupportMethods.filter((method) => Boolean(method.qrUrl));

export const SUPPORT_AVAILABLE = process.env.NEXT_PUBLIC_SUPPORT_ENABLED === "true" && SUPPORT_METHODS.length > 0;

// Community & Private Traffic Configuration
export const COMMUNITY_QQ_GROUP = process.env.NEXT_PUBLIC_COMMUNITY_QQ_GROUP || "938741334";
export const COMMUNITY_QQ_GROUP_URL =
  process.env.NEXT_PUBLIC_COMMUNITY_QQ_URL ||
  "https://qm.qq.com/cgi-bin/qm/qr?k=community&jump_from=webapi";
export const COMMUNITY_WECHAT_QR_URL = safeQrUrl(
  process.env.NEXT_PUBLIC_COMMUNITY_WECHAT_QR_URL
);
export const COMMUNITY_ENABLED = process.env.NEXT_PUBLIC_COMMUNITY_ENABLED !== "false";

// Global Site Notice Configuration
export type SiteNoticeConfig = {
  id: string;
  badge: string;
  title: string;
  content: string;
  linkText?: string;
  linkUrl?: string;
  enabled: boolean;
};

export const CURRENT_SITE_NOTICE: SiteNoticeConfig = {
  id: "notice-20260915-agent-feed",
  badge: "最新动态",
  title: "已支持 16688 平台商户比价与 Agent 开放快照",
  content: "我们新增了 16688 渠道 AI 商品实时抓取，并上线了面向 AI Agent 与开发者的全站静态只读 Feed。",
  linkText: "查看开发文档",
  linkUrl: "/developers",
  enabled: process.env.NEXT_PUBLIC_SITE_NOTICE_ENABLED !== "false",
};
