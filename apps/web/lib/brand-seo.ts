import type { BrandName } from "@/lib/catalog";

const BRAND_CONTENT: Partial<Record<BrandName, { title: string; description: string }>> = {
  OpenAI: {
    title: "OpenAI 比价｜ChatGPT Plus、Pro 订阅价格对比",
    description: "比较 OpenAI ChatGPT Plus、Pro、Go 等订阅的公开报价、库存和店铺来源。可按直充、成品账号、期限和质保筛选，API 额度与共享商品单独查看。",
  },
  Claude: {
    title: "Claude 比价｜Pro、Max、Team 订阅价格对比",
    description: "比较 Claude Pro、Max 5x、Max 20x 与 Team 的公开报价、库存和更新时间。先确认套餐、交付方式、期限与质保，再查看各店铺价格。",
  },
  Gemini: {
    title: "Gemini 比价｜Google AI Pro、Ultra 订阅价格对比",
    description: "比较 Gemini、Google AI Pro 与 Ultra 的公开订阅报价和库存。区分套餐档位、成品账号、直充与使用期限，并保留商家原文和报价来源。",
  },
};

export function getBrandSeoContent(brand: BrandName) {
  return BRAND_CONTENT[brand] || {
    title: `${brand} 比价｜账号与订阅价格对比`,
    description: `查看 ${brand} 商品的公开价格、库存、店铺来源和更新时间，按商品类别、交付方式、期限与质保筛选报价。`,
  };
}
