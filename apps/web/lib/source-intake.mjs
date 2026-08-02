export const SOURCE_INTAKE_OPTIONS = [
  { id: "auto", label: "自动识别（推荐）" },
  { id: "ldxp", label: "链动小铺" },
  { id: "dujiao_next", label: "Dujiao-Next" },
  { id: "merchant_json", label: "商家 JSON Feed" },
  { id: "other", label: "其他独立站" },
];

export const SOURCE_INTAKE_COPY = {
  auto: {
    fieldLabel: "来源地址",
    placeholder: "https://shop.example.com",
    hint: "粘贴店铺首页、商品页面或公开 Feed 地址，例如 https://shop.example.com 或 https://shop.example.com/products/chatgpt-plus。",
  },
  ldxp: {
    fieldLabel: "公开店铺地址",
    placeholder: "https://pay.ldxp.cn/shop/xxxxx",
    hint: "例如 https://pay.ldxp.cn/shop/xxxxx。系统仍会核对实际来源类型。",
  },
  dujiao_next: {
    fieldLabel: "店铺根地址",
    placeholder: "https://shop.example.com",
    hint: "请输入店铺根地址。请勿提交后台、订单查询或支付回调地址。",
  },
  merchant_json: {
    fieldLabel: "公开 JSON Feed 地址",
    placeholder: "https://shop.example.com/ai-price-radar.json",
    hint: "Feed 必须使用公开 HTTPS，例如 https://shop.example.com/ai-price-radar.json。",
  },
  other: {
    fieldLabel: "公开来源地址",
    placeholder: "https://shop.example.com/products/chatgpt-plus",
    hint: "可提交公开店铺首页或商品页；系统会检查可访问性和公开结构。",
  },
};

export function isValidPublicSourceUrl(value) {
  try {
    const url = new URL(value);
    const hostname = url.hostname.toLowerCase();
    return url.protocol === "https:"
      && !url.username
      && !url.password
      && Boolean(hostname)
      && hostname !== "localhost"
      && !hostname.endsWith(".local")
      && !hostname.endsWith(".internal");
  } catch {
    return false;
  }
}
