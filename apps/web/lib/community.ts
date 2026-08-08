export const GITHUB_REPOSITORY_URL = "https://github.com/BeterXie/ai_price_radar";

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
    qrUrl: safeQrUrl(process.env.NEXT_PUBLIC_SUPPORT_WECHAT_QR_URL || "https://ai.pricememo.cn/support/wechat.jpg"),
  },
  {
    id: "alipay",
    label: "支付宝",
    qrUrl: safeQrUrl(process.env.NEXT_PUBLIC_SUPPORT_ALIPAY_QR_URL || "https://ai.pricememo.cn/support/alipay.jpg"),
  },
];

export const SUPPORT_METHODS = configuredSupportMethods.filter((method) => Boolean(method.qrUrl));

export const SUPPORT_AVAILABLE =
  process.env.NEXT_PUBLIC_SUPPORT_ENABLED !== "false" &&
  SUPPORT_METHODS.length > 0;
