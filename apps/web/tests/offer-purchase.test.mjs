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
    totalCount: 1, snapshotId: 42,
    groups: [{ product_slug: "gemini-plus", product_name: "Google AI Plus", fingerprint: "one", representative: item, offer_count: 1, shop_count: 1, in_stock_count: item.stock_status === "in_stock" ? 1 : 0, lowest_price: item.price, price_currency: item.currency }],
  } : { offers: [item] }));
}

test("catalog and standalone offers expose purchasing directly in the market table", () => {
  for (const grouped of [true, false]) {
    const html = markup(offer, grouped);
    const purchase = html.indexOf('href="https://shop.example/products/42"');
    assert.match(html, /quote-market-table/);
    assert.match(html, /<th scope="col">店铺<\/th><th scope="col">报价<\/th><th scope="col">库存<\/th>/);
    assert.ok(purchase > 0 && purchase < html.indexOf("商品详情</button>"));
    assert.match(html.slice(purchase, purchase + 500), /target="_blank".*去原站下单/s);
    assert.match(html, /去原站下单：示例店铺 · Gemini Plus 6 个月激活链接（新窗口打开）/);
    assert.doesNotMatch(html, /<details|查看店铺报价/);
  }
});

test("unavailable stock is explicit and a missing source URL never becomes a purchase link", () => {
  for (const grouped of [true, false]) {
    const unavailable = markup({ ...offer, stock_status: "out_of_stock" }, grouped);
    assert.match(unavailable, /缺货/);
    assert.doesNotMatch(unavailable, /有货 ·/);
    const noLink = markup({ ...offer, source_url: "" }, grouped);
    assert.match(noLink, /暂无原站链接/);
    assert.doesNotMatch(noLink, /去原站下单/);
    assert.doesNotMatch(noLink, /href="https:\/\/shop\.example/);
  }
});

test("same-product ordering asks the user to choose a shop and keeps a separate details action", () => {
  const html = renderToStaticMarkup(createElement(OfferGroupTable, {
    totalCount: 1, snapshotId: 42,
    groups: [{ product_slug: "gemini-plus", product_name: "Google AI Plus", fingerprint: "one", representative: offer, offer_count: 3, shop_count: 2 }],
  }));
  assert.match(html, /<button[^>]+class="quote-visit"[^>]+aria-haspopup="dialog"/);
  assert.match(html, /去原站下单：选择 Gemini Plus 6 个月激活链接 的店铺/);
  assert.match(html, /同款 <b\b[^>]*>2<\/b> 家/);
  assert.match(html, />商品详情<\/button>/);
  assert.doesNotMatch(html, /href="https:\/\/shop.example\/products\/42"/);
});

test("quote lists contain only products even when a sponsor is available for the detail dialog", () => {
  const ad = { id: 7, placement: "claude_feed", title: "Sponsor offer", description: "Sponsor description", sponsor_name: "Sponsor", link_url: "https://sponsor.example/", image_url: "", cta_text: "了解详情" };
  for (const count of [4, 5, 12, 35]) {
    const groups = Array.from({ length: count }, (_, index) => ({ product_slug: "gemini-plus", fingerprint: String(index), representative: { ...offer, id: index + 1 }, shop_count: 1, offer_count: 1 }));
    const render = (contextAds) => renderToStaticMarkup(createElement(OfferGroupTable, { groups, totalCount: 40, snapshotId: 42, contextAds }));
    const html = render({ feed: ad });
    const body = html.match(/<tbody>([\s\S]*?)<\/tbody>/)?.[1];
    assert.ok(body, "market table must have a quote body");
    const rows = [...body.matchAll(/<tr\b[^>]*>/g)];
    assert.equal(rows.length, count);
    assert.doesNotMatch(html, /context-sponsor-feed|data-ad-id|sponsor\.example/);
    assert.doesNotMatch(render({}), /data-ad-id/);
  }
});
