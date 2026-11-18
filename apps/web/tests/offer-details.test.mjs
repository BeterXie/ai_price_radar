import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { getOffer, ApiError } from "../lib/api.ts";
import OfferPage, { generateMetadata } from "../app/offers/[offerId]/page.tsx";
import OfferNotFound from "../app/offers/[offerId]/not-found.tsx";
import { createElement } from "react";

const renderPage = (props) => (OfferPage.default || OfferPage)(props);

const offer = {
  id: 73, product_slug: "chatgpt-business", product_name: "ChatGPT Business",
  shop_token: "exact-shop", shop_name: "提醒里的店铺", original_name: "Team 5x 同名商品",
  original_description: "当前店铺的商品原文", description_available: true,
  price: "20.00", currency: "CNY", stock_status: "in_stock", stock_count: 2,
  is_comparable: false, is_trusted_price: false, delivery_type: "finished_account",
  warranty: "unknown", auto_delivery: true, source_url: "https://merchant.example/item-specific",
  source_platform_label: "公开来源", observed_at: "2026-11-18T15:28:55Z", risk_flags: [],
};

test("notification landing page renders the exact offer without opening a dialog", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url, options) => {
    const path = new URL(url).pathname;
    calls.push({ path, cache: options.cache });
    if (path === "/api/v1/offers/73") return Response.json(offer);
    if (path.endsWith("/ads")) return Response.json({ enabled: false, items: [] });
    throw new Error(`Unexpected request: ${path}`);
  });
  const props = { params: Promise.resolve({ offerId: "73" }) };
  const html = renderToStaticMarkup(await renderPage(props));
  assert.match(html, /<h1[^>]*>Team 5x 同名商品<\/h1>/);
  assert.match(html, /提醒里的店铺/);
  assert.match(html, /20\.00/);
  assert.match(html, /当前店铺的商品原文/);
  assert.match(html, /href="https:\/\/merchant.example\/item-specific"/);
  assert.doesNotMatch(html, /<dialog|关闭报价详情|正在读取店铺报价/);
  const metadata = await generateMetadata(props);
  const offerCalls = calls.filter((call) => call.path === "/api/v1/offers/73");
  assert.ok(offerCalls.length > 0 && offerCalls.every((call) => call.cache === "no-store"));
  assert.match(metadata.title, /Team 5x 同名商品 · 提醒里的店铺/);
  assert.match(metadata.alternates.canonical, /\/offers\/73$/);
  assert.equal(metadata.robots.index, false);
});

test("invalid and removed offer links never fall back to a different offer", async (context) => {
  let calls = 0;
  context.mock.method(globalThis, "fetch", async () => { calls++; return new Response("", { status: 404 }); });
  for (const id of ["0", "-1", "1/other", "NaN", "9007199254740992"]) assert.equal(await getOffer(id), null);
  assert.equal(calls, 0);
  assert.equal(await getOffer("73"), null);
  await assert.rejects(renderPage({ params: Promise.resolve({ offerId: "73" }) }), /404/);
  const empty = renderToStaticMarkup(createElement(OfferNotFound.default || OfferNotFound));
  assert.match(empty, /商品报价暂不可用/);
  assert.match(empty, /href="\/products"/);
});

test("temporary offer API failure remains an error instead of a false removal", async (context) => {
  context.mock.method(globalThis, "fetch", async () => new Response("", { status: 503 }));
  await assert.rejects(getOffer("73"), (error) => error instanceof ApiError && error.status === 503);
  await assert.rejects(renderPage({ params: Promise.resolve({ offerId: "73" }) }), (error) => error.name === "ApiError" && error.status === 503);
});

test("out-of-stock offers keep their identity and show current availability", async (context) => {
  context.mock.method(globalThis, "fetch", async (url) => new URL(url).pathname === "/api/v1/offers/73"
    ? Response.json({ ...offer, stock_status: "out_of_stock", stock_count: 0 })
    : Response.json({ enabled: false, items: [] }));
  const html = renderToStaticMarkup(await renderPage({ params: Promise.resolve({ offerId: "73" }) }));
  assert.match(html, /Team 5x 同名商品/);
  assert.match(html, /缺货/);
  assert.match(html, /20\.00/);
});
