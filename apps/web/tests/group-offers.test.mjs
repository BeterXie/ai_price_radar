import assert from "node:assert/strict";
import test from "node:test";

import { fetchGroupShopOffers } from "../lib/group-offers.ts";

test("group offers use the page snapshot when it still has matching offers", async () => {
  const originalFetch = globalThis.fetch;
  const urls = [];
  try {
    globalThis.fetch = async (url) => {
      urls.push(new URL(url, "https://example.test"));
      return { ok: true, json: async () => ({ items: [{ id: 1 }] }) };
    };
    const result = await fetchGroupShopOffers("test-product", "same-group", "comparable=true&in_stock=true", 42);
    assert.deepEqual(result, { items: [{ id: 1 }], refreshed: false });
    assert.equal(urls.length, 1);
    assert.equal(urls[0].searchParams.get("snapshot"), "42");
    assert.equal(urls[0].searchParams.get("in_stock"), "true");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("group offers retry the current snapshot when the page snapshot is empty", async () => {
  const originalFetch = globalThis.fetch;
  const urls = [];
  try {
    globalThis.fetch = async (url) => {
      const parsed = new URL(url, "https://example.test");
      urls.push(parsed);
      return { ok: true, json: async () => ({ items: parsed.searchParams.has("snapshot") ? [] : [{ id: 2 }] }) };
    };
    const result = await fetchGroupShopOffers("test-product", "same-group", "comparable=true&snapshot=1", 42);
    assert.deepEqual(result, { items: [{ id: 2 }], refreshed: true });
    assert.equal(urls.length, 2);
    assert.equal(urls[0].searchParams.get("snapshot"), "42");
    assert.equal(urls[1].searchParams.has("snapshot"), false);
    assert.equal(urls[1].searchParams.get("comparable"), "true");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("group offers retry the current snapshot when the old snapshot is unavailable", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async (url) => {
      const hasSnapshot = new URL(url, "https://example.test").searchParams.has("snapshot");
      return hasSnapshot
        ? { ok: false, status: 404 }
        : { ok: true, json: async () => ({ items: [{ id: 3 }] }) };
    };
    const result = await fetchGroupShopOffers("test-product", "same-group", "", 42);
    assert.deepEqual(result, { items: [{ id: 3 }], refreshed: true });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
