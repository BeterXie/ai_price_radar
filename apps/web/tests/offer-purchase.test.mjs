import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { OfferGroupTable, OfferTable } from "../components/offer-table.tsx";

const offer = {
  id: 42, original_name: "Gemini Plus 6 个月激活链接", shop_name: "示例店铺", shop_token: "example",
  source_url: "https://shop.example/products/42", source_platform: "merchant", source_platform_label: "独立店铺", source_kind_label: "公开报价",
  price: "5.50", currency: "CNY", stock_status: "in_stock", stock_count: 3,
  delivery_type: "redeem_code", service_period: "six_months", warranty: "covered", auto_delivery: true,
  is_comparable: true, is_trusted_price: true, tags: [], risk_flags: [], use_scenarios: [],
  source_health: { score: 100, label: "正常", reasons: [] }, observed_at: "2026-11-16T04:00:00Z",
};

function markup(item, grouped) {
  return renderToStaticMarkup(createElement(grouped ? OfferGroupTable : OfferTable, grouped ? {
    compact: true, totalCount: 1, snapshotId: 42,
    groups: [{ product_slug: "gemini-plus", product_name: "Google AI Plus", fingerprint: "one", representative: item, offer_count: 1, shop_count: 1, in_stock_count: item.stock_status === "in_stock" ? 1 : 0, lowest_price: item.price, price_currency: item.currency }],
  } : { offers: [item] }));
}

test("catalog and standalone offers expose merchant purchasing before long product details", () => {
  for (const grouped of [true, false]) {
    const html = markup(offer, grouped);
    const purchase = html.indexOf('href="https://shop.example/products/42"');
    assert.match(html, /查看店铺报价/);
    assert.match(html, /下单、付款与售后均在店铺网站完成/);
    assert.ok(purchase > 0 && purchase < html.indexOf("商品说明与交付详情"));
    assert.match(html.slice(purchase, purchase + 500), /target="_blank".*去店铺下单/s);
    assert.match(html, /前往 示例店铺 下单（新窗口打开）/);
  }
});

test("out-of-stock and missing-link offers do not promise an available checkout", () => {
  for (const grouped of [true, false]) {
    const unavailable = markup({ ...offer, stock_status: "out_of_stock" }, grouped);
    assert.match(unavailable, /去店铺查看/);
    assert.doesNotMatch(unavailable, /前往 示例店铺 下单/);
    const noLink = markup({ ...offer, source_url: "" }, grouped);
    assert.match(noLink, /暂未提供购买链接/);
    assert.doesNotMatch(noLink, /href="https:\/\/shop\.example/);
  }
});
