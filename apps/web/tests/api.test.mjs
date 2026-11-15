import assert from "node:assert/strict";
import test from "node:test";
import { promises as fs } from "node:fs";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";

import { apiFetch, ApiError, getMeta, getProduct, getProducts, getShop, getSkillDetail } from "../lib/api.ts";

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
  context.mock.method(fs, "stat", async () => ({ size: 100 }));
  context.mock.method(fs, "readFile", async (filename) => Buffer.from(JSON.stringify(
    path.basename(filename) === "latest.json" ? { snapshot_id: 42 } : {
      schema_version: "price-radar.catalog.v1", snapshot_id: 42,
      snapshot_at: "2026-11-15T00:00:00Z", total: 2,
      items: [{ slug: "chatgpt-pro-5x", display_name: "Legacy" }, { slug: "chatgpt-pro-100", display_name: "Pro" }],
    }
  )));
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
  assert.ok(!calls.some((path) => path.startsWith("/data/")));
  assert.ok(calls.includes("/api/v1/products"));
});

test("API reads share a time budget and never replay writes or retry too early", async (context) => {
  let calls = 0;
  context.mock.method(globalThis, "fetch", async () => {
    calls += 1;
    return Response.json({}, { status: 503 });
  });
  await assert.rejects(() => apiFetch("/unavailable", 1), ApiError);
  assert.equal(calls, 2);
  calls = 0;
  await assert.rejects(() => apiFetch("/write", 1, { method: "POST" }), ApiError);
  assert.equal(calls, 1);
  calls = 0;
  context.mock.method(globalThis, "fetch", async () => {
    calls += 1;
    return Response.json({}, { status: 429, headers: { "Retry-After": "60" } });
  });
  await assert.rejects(() => apiFetch("/limited", 1), (error) => error.status === 429);
  assert.equal(calls, 1);

  calls = 0;
  context.mock.method(globalThis, "fetch", async (_url, { signal }) => {
    calls += 1;
    return new Promise((_resolve, reject) => signal.addEventListener("abort", () => reject(signal.reason), { once: true }));
  });
  const controller = new AbortController();
  const pending = apiFetch("/slow", 1, { signal: controller.signal });
  controller.abort(new Error("caller deadline"));
  await assert.rejects(pending, /caller deadline/);
  assert.equal(calls, 1);
});

test("required metadata tolerates a cold read and recovers from a transient failure", async (context) => {
  let calls = 0;
  const metadata = { source_platforms: [], relay_station_count: 0 };
  context.mock.method(globalThis, "fetch", async (_url, { signal }) => {
    calls += 1;
    if (calls === 1) return Response.json({}, { status: 503 });
    await delay(1400, undefined, { signal });
    return Response.json(metadata);
  });
  assert.deepEqual(await getMeta(), metadata);
  assert.equal(calls, 2);
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
