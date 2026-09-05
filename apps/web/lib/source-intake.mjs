export const SOURCE_INTAKE_OPTIONS = [
  { id: "auto", label: "自动识别（推荐）" },
  { id: "ldxp", label: "链动小铺" },
  { id: "16688", label: "16688" },
  { id: "dujiao_next", label: "Dujiao-Next（暂停收录）", disabled: true },
  { id: "woocommerce", label: "WooCommerce" },
  { id: "schema_org", label: "Schema.org 独立站" },
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
    hint: "例如 https://wzyp.cn/shop/xxxxx 或 https://pay.ldxp.cn/shop/xxxxx。系统仍会核对实际来源类型。",
  },
  16688: {
    fieldLabel: "16688 店铺地址",
    placeholder: "https://www.16688.com.cn/shop/HARVEY",
    hint: "例如 https://www.16688.com.cn/shop/HARVEY；系统会读取公开店铺商品和真实店铺编号。",
  },
  dujiao_next: {
    fieldLabel: "店铺根地址",
    placeholder: "https://shop.example.com",
    hint: "请输入店铺根地址。请勿提交后台、订单查询或支付回调地址。",
  },
  woocommerce: {
    fieldLabel: "WooCommerce 店铺地址",
    placeholder: "https://shop.example.com",
    hint: "请输入公开店铺根地址；系统会验证无需登录的 WooCommerce Store API。",
  },
  schema_org: {
    fieldLabel: "独立站或商品页地址",
    placeholder: "https://shop.example.com/products/example",
    hint: "站点须通过 Sitemap 和 Schema.org Product/Offer JSON-LD 公开商品信息。",
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
