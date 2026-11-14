import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, getProduct, getProducts, getShop, getSkillDetail } from "../lib/api.ts";

test("API helpers canonicalize legacy Pro requests without changing offer titles", async (context) => {
  const calls = [];
  const title = "ChatGPT Pro 5x 独享月付 原标题";
  context.mock.method(globalThis, "fetch", async (url) => {
    calls.push(new URL(String(url)));
    const data = String(url).includes("/products?")
      ? { items: [], total: 0 }
      : { slug: "chatgpt-pro-100", display_name: "ChatGPT Pro 100", offers: [{ title }] };
    return new Response(JSON.stringify(data), { status: 200 });
  });
  const product = await getProduct("chatgpt-pro-5x", "period=one_month&source_platform=16688");
  assert.equal(calls[0].pathname, "/api/v1/products/chatgpt-pro-100");
  assert.equal(calls[0].searchParams.get("period"), "one_month");
  assert.equal(calls[0].searchParams.get("source_platform"), "16688");
  assert.equal(product.offers[0].title, title);
  await getProducts("products=chatgpt-pro-5x,chatgpt-pro-100,chatgpt-pro-20x&in_stock=true");
  assert.equal(calls[1].searchParams.get("products"), "chatgpt-pro-100,chatgpt-pro-200");
  assert.equal(calls[1].searchParams.get("in_stock"), "true");
});

test("catalog bypasses old immutable snapshots that still split Pro aliases", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url) => {
    const path = new URL(String(url)).pathname;
    calls.push(path);
    const data = path === "/data/latest.json"
      ? { snapshot_id: 42 }
      : path.startsWith("/data/v1/snapshots/")
        ? { products: [{ slug: "chatgpt-pro-5x" }, { slug: "chatgpt-pro-100" }] }
        : { items: [{ slug: "chatgpt-pro-100" }], total: 1 };
    return new Response(JSON.stringify(data), { status: 200 });
  });
  const catalog = await getProducts("sort=quality");
  assert.deepEqual(catalog.items.map((item) => item.slug), ["chatgpt-pro-100"]);
  assert.ok(calls.includes("/data/v1/snapshots/42.json"));
  assert.ok(calls.includes("/api/v1/products"));
});

test("shop pages resolve raw and escaped native tokens with pagination", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url) => {
    const request = new URL(String(url));
    calls.push(request);
    const token = decodeURIComponent(request.pathname.split("/").at(-1));
    return token === "catfk:V6J6VKYC"
      ? Response.json({ token, offer_count: 18 })
      : Response.json({ detail: "shop not found" }, { status: 404 });
  });

  for (const token of ["catfk:V6J6VKYC", "catfk%3AV6J6VKYC"]) {
    const shop = await getShop(token, "offer_limit=30&offer_offset=30");
    assert.equal(shop?.token, "catfk:V6J6VKYC");
    assert.equal(shop?.offer_count, 18);
  }
  assert.equal(calls.length, 2);
  assert.ok(calls.every((url) => url.searchParams.get("offer_offset") === "30"));
  assert.equal(await getShop("catfk%invalid"), null);
  assert.equal(calls.length, 2);
});

test("API resource helpers only treat 404 as missing", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({ ok: false, status: 404, json: async () => ({}) });
    assert.equal(await getProduct("missing"), null);
    assert.equal(await getShop("missing"), null);
    assert.equal(await getSkillDetail("missing"), null);

    globalThis.fetch = async () => ({ ok: false, status: 503, json: async () => ({}) });
    await assert.rejects(() => getProduct("unavailable"), (error) => error instanceof ApiError && error.status === 503);
    await assert.rejects(() => getShop("unavailable"), (error) => error instanceof ApiError && error.status === 503);
    await assert.rejects(() => getSkillDetail("unavailable"), (error) => error instanceof ApiError && error.status === 503);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
